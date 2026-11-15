# Production-like HTTPS deployment

Set `DJANGO_DEBUG=False`, production hosts, `DB_ENGINE=mysql`, and a strong,
externally generated `DJANGO_SECRET_KEY` in the deployment environment. The
application refuses to start in this mode if the key is missing, shorter than
50 characters, or has fewer than 16 distinct characters. Generate a key with
Django's `get_random_secret_key()` utility and keep it in a secret manager; do
not commit it to `.env.example` or source control. The local-only fallback key
is used only while `DJANGO_DEBUG=True`.

Production mode always enables secure session and CSRF cookies and HTTP-to-HTTPS
redirects; the development cookie and redirect toggles cannot disable them.
Sessions expire after one hour, are refreshed on requests, and expire when the
browser closes.

For TLS terminated by the included Nginx reverse proxy, set
`DJANGO_TRUST_PROXY_SSL_HEADER=True` only when the application server is not
directly reachable by clients and the proxy overwrites `X-Forwarded-Proto`
(as the provided configuration does). Otherwise leave it false and rely on the
WSGI server's HTTPS scheme. Trusting a client-controlled forwarding header can
defeat HTTPS detection.

Configure HSTS (`DJANGO_HSTS_SECONDS=31536000`) only after HTTPS is verified
for every served hostname. Enable `DJANGO_HSTS_INCLUDE_SUBDOMAINS` or preload
only after confirming all subdomains meet the same HTTPS requirement. Then
install `requirements-production.txt`, run migrations and `collectstatic`,
and check the live configuration with `python manage.py check --deploy`.

The Nginx and systemd templates use example domains and certificate paths;
provide valid TLS certificates through your deployment process. These
templates contain no private keys or certificates.
