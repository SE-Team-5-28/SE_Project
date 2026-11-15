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

## Health monitoring and recovery

The application exposes `GET /healthz`, which returns `{"status":"ok"}` when
Django can serve requests. It does not check the database, and it reveals no
deployment details. The included systemd health-check service probes this
endpoint on loopback every minute, records each result in the system journal,
and restarts `hostel-management.service` after a failed probe. If the retry
still fails, the check is logged as failed; inspect the application and
database logs and resolve the underlying fault rather than repeatedly
restarting blindly.

After installing this repository at `/srv/hostel-management` and installing
`curl`, install the monitor units and enable the timer:

```sh
sudo install -m 0644 deploy/hostel-management-healthcheck.service \
  /etc/systemd/system/hostel-management-healthcheck.service
sudo install -m 0644 deploy/hostel-management-healthcheck.timer \
  /etc/systemd/system/hostel-management-healthcheck.timer
sudo systemctl daemon-reload
sudo systemctl enable --now hostel-management-healthcheck.timer
```

Verify operation and review the recorded checks and restarts:

```sh
sudo systemctl status hostel-management.service
sudo systemctl status hostel-management-healthcheck.timer
sudo journalctl -u hostel-management-healthcheck.service --since "24 hours ago"
sudo journalctl -u hostel-management.service --since "24 hours ago"
```

For manual recovery, inspect the logs first, correct configuration or
dependency failures, then run `sudo systemctl restart hostel-management.service`
and verify `curl --fail https://your-hostname/healthz`. The health-check timer
only probes the local application process; use an independent external uptime
monitor against the public HTTPS URL to detect host, proxy, DNS, network, and
TLS failures. Journal records begin only after the monitor is installed and
are not historical uptime evidence. Do not claim the 99% monthly target is
met until a complete month of trustworthy measurements is available.
