import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.crypto import get_random_string


User = get_user_model()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PROBE = (
    "import json; import config.settings as s; "
    "print(json.dumps({"
    "'debug': s.DEBUG, "
    "'local_fallback': s.SECRET_KEY == "
    "'local-development-only-insecure-secret', "
    "'session_cookie_secure': s.SESSION_COOKIE_SECURE, "
    "'csrf_cookie_secure': s.CSRF_COOKIE_SECURE, "
    "'ssl_redirect': s.SECURE_SSL_REDIRECT, "
    "'session_cookie_age': s.SESSION_COOKIE_AGE, "
    "'expire_at_browser_close': s.SESSION_EXPIRE_AT_BROWSER_CLOSE, "
    "'save_every_request': s.SESSION_SAVE_EVERY_REQUEST, "
    "'proxy_ssl_header': s.SECURE_PROXY_SSL_HEADER, "
    "'use_x_forwarded_host': s.USE_X_FORWARDED_HOST"
    "}))"
)


class PasswordHashingTests(TestCase):
    def test_user_password_is_stored_as_a_verifiable_hash(self):
        raw_password = "password-hashing-test-value"
        user = User.objects.create_user(
            username="hashed_password_user",
            password=raw_password,
        )
        user.refresh_from_db()

        self.assertNotEqual(user.password, raw_password)
        hasher = identify_hasher(user.password)
        self.assertTrue(user.password.startswith(f"{hasher.algorithm}$"))
        self.assertTrue(user.check_password(raw_password))


@override_settings(
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SECURE_SSL_REDIRECT=False,
)
class ProtectedSessionWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.password = "secure-session-test-password"
        self.user = User.objects.create_user(
            username="secure_session_user",
            password=self.password,
        )

    def test_login_requires_csrf_and_sets_a_protected_session_cookie(self):
        login_page = self.client.get(reverse("login"), secure=True)
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
                "csrfmiddlewaretoken": login_page.context["csrf_token"],
            },
            secure=True,
            HTTP_REFERER="https://testserver/login",
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        session_cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(session_cookie["secure"])
        self.assertTrue(session_cookie["httponly"])
        self.assertEqual(session_cookie["samesite"], "Lax")
        self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]["secure"])
        self.assertEqual(
            self.client.get(reverse("dashboard"), secure=True).status_code,
            200,
        )

    def test_logout_requires_csrf_and_ends_the_authenticated_session(self):
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.post(reverse("logout"), secure=True).status_code,
            403,
        )

        login_page = self.client.get(reverse("login"), secure=True)
        response = self.client.post(
            reverse("logout"),
            {"csrfmiddlewaretoken": login_page.context["csrf_token"]},
            secure=True,
            HTTP_REFERER="https://testserver/login",
        )

        self.assertRedirects(
            response,
            reverse("login"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("dashboard"), secure=True),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )


class ProductionSettingsTests(SimpleTestCase):
    def run_settings_probe(self, secret, *, debug=False, trust_proxy=False):
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_DEBUG": str(debug),
                "DJANGO_SECRET_KEY": secret,
                "DJANGO_COOKIE_SECURE": "False",
                "DJANGO_SECURE_SSL_REDIRECT": "False",
                "DJANGO_TRUST_PROXY_SSL_HEADER": str(trust_proxy),
                "DJANGO_HSTS_SECONDS": "0",
                "DJANGO_HSTS_INCLUDE_SUBDOMAINS": "False",
                "DJANGO_HSTS_PRELOAD": "False",
            }
        )
        return subprocess.run(
            [sys.executable, "-c", SETTINGS_PROBE],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_local_development_has_a_safe_convenience_default(self):
        result = self.run_settings_probe("", debug=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertTrue(config["debug"])
        self.assertTrue(config["local_fallback"])
        self.assertFalse(config["session_cookie_secure"])
        self.assertFalse(config["ssl_redirect"])

    def test_production_requires_an_externally_supplied_secret(self):
        result = self.run_settings_probe("")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY must be externally supplied", result.stderr)

    def test_production_rejects_a_weak_secret(self):
        for secret in ("short-test-key", "x" * 64):
            with self.subTest(secret_length=len(secret)):
                result = self.run_settings_probe(secret)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "DJANGO_SECRET_KEY must be externally supplied",
                    result.stderr,
                )

    def test_production_enables_secure_cookies_https_and_session_controls(self):
        test_only_key = (
            "test-only-settings-probe-" + get_random_string(60)
        )
        result = self.run_settings_probe(test_only_key)

        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertTrue(config["session_cookie_secure"])
        self.assertTrue(config["csrf_cookie_secure"])
        self.assertTrue(config["ssl_redirect"])
        self.assertEqual(config["session_cookie_age"], 3600)
        self.assertTrue(config["expire_at_browser_close"])
        self.assertTrue(config["save_every_request"])
        self.assertIsNone(config["proxy_ssl_header"])
        self.assertFalse(config["use_x_forwarded_host"])

    def test_proxy_headers_are_trusted_only_when_explicitly_enabled(self):
        test_only_key = (
            "test-only-settings-probe-" + get_random_string(60)
        )
        result = self.run_settings_probe(test_only_key, trust_proxy=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(
            config["proxy_ssl_header"],
            ["HTTP_X_FORWARDED_PROTO", "https"],
        )
        self.assertTrue(config["use_x_forwarded_host"])


class HttpsDeploymentConfigTests(SimpleTestCase):
    def test_nginx_terminates_tls_and_sets_trusted_proxy_headers(self):
        nginx_config = (PROJECT_ROOT / "deploy" / "nginx.conf").read_text()

        for directive in (
            "listen 443 ssl http2;",
            "ssl_protocols TLSv1.2 TLSv1.3;",
            "ssl_certificate /etc/letsencrypt/live/hostel.example.edu/fullchain.pem;",
            "ssl_certificate_key /etc/letsencrypt/live/hostel.example.edu/privkey.pem;",
            "proxy_set_header Host $host;",
            "proxy_set_header X-Forwarded-Host $host;",
            "proxy_set_header X-Forwarded-Proto https;",
            "proxy_pass http://127.0.0.1:8000;",
            "location ^~ /.well-known/acme-challenge/",
            "return 301 https://hostel.example.edu$request_uri;",
        ):
            with self.subTest(directive=directive):
                self.assertIn(directive, nginx_config)

    def test_systemd_keeps_the_application_server_on_loopback(self):
        service_config = (
            PROJECT_ROOT / "deploy" / "hostel-management.service"
        ).read_text()

        self.assertIn("--bind 127.0.0.1:8000", service_config)
        self.assertNotIn("--bind 0.0.0.0:8000", service_config)

    def test_deployment_guide_covers_proxy_trust_and_certificate_lifecycle(self):
        deployment_guide = (PROJECT_ROOT / "deploy" / "README.md").read_text()

        for requirement in (
            "DJANGO_TRUST_PROXY_SSL_HEADER=True",
            "certbot certonly --webroot",
            "certbot renew --dry-run",
            "nginx -t",
            "curl -I http://",
            "curl -I https://",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, deployment_guide)
