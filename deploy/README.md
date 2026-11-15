# Production-like HTTPS deployment

The Nginx template terminates TLS and proxies requests to Gunicorn on loopback.
It forwards the original host and a fixed `X-Forwarded-Proto: https`; the Django
settings trust those headers only when `DJANGO_TRUST_PROXY_SSL_HEADER=True`.
Keep the application server private behind this proxy. The template uses the
example hostname `hostel.example.edu`; replace it with the real hostname in
both `deploy/nginx.conf` and Django's `DJANGO_ALLOWED_HOSTS`.

## Prepare the host and Django

Point the hostname's DNS records at the deployment host and allow inbound TCP
ports 80 and 443. Install Nginx, Certbot, and its webroot integration using the
host OS package manager. Configure the systemd service to run from
`/srv/hostel-management`; it binds Gunicorn to `127.0.0.1:8000`, not a public
interface.

Provide the existing `deploy/hostel-management.service` environment file at
`/srv/hostel-management/.env` with production values, for example:

```dotenv
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=hostel.example.edu
DJANGO_TRUST_PROXY_SSL_HEADER=True
DJANGO_HSTS_SECONDS=0
DB_ENGINE=mysql
```

Supply `DJANGO_SECRET_KEY` and database credentials from the deployment's
secret manager or another protected, operator-managed source; do not put real
secrets in this repository. Django requires the production secret to be at
least 50 characters with at least 16 distinct characters. The `.env` file must
be readable by the service account because Django loads it at startup. Keep
HSTS disabled until HTTPS has been verified for every served hostname.

## Provision and install the certificate

The checked-in Nginx template refers to certificate files that must already
exist, so first activate a temporary HTTP-only Nginx server for the real
hostname. Create the ACME webroot and use a bootstrap server block like this:

```nginx
server {
    listen 80;
    server_name hostel.example.edu;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files $uri =404;
    }

    location / {
        return 404;
    }
}
```

Create the webroot before enabling the bootstrap site:

```sh
sudo install -d -o root -g www-data -m 0755 /var/www/certbot
```

After confirming the bootstrap site is active and `sudo nginx -t` succeeds,
request the certificate with the webroot authenticator:

```sh
sudo certbot certonly --webroot --webroot-path /var/www/certbot -d hostel.example.edu
```

Certbot will prompt for its operator and agreement details. Once issuance
succeeds, install `deploy/nginx.conf` as the active Nginx site, replacing every
example hostname and confirming the certificate paths match the issued
certificate. Enable the site if needed, then validate and reload:

```sh
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart hostel-management
```

The template serves ACME challenge files over HTTP and redirects other HTTP
requests to the fixed HTTPS hostname, avoiding redirects based on an
unvalidated incoming `Host` value. HTTPS requests are proxied with `Host` and
`X-Forwarded-Host` set to Nginx's normalized `$host`, and
`X-Forwarded-Proto` overwritten to `https`. With the trusted-proxy setting on,
Django validates the forwarded host against `DJANGO_ALLOWED_HOSTS` and treats
the request as secure, avoiding a redirect loop. Do not enable that setting if
clients can reach Gunicorn directly or if another proxy can pass client-supplied
forwarding headers through unchanged.

## Renewal and verification

Enable the Certbot systemd timer and install a deploy hook so Nginx reloads
after a successful certificate renewal:

```sh
sudo install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx >/dev/null
sudo chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
```

On the deployment host, check the installed certificate and both HTTP and HTTPS
responses:

```sh
sudo certbot certificates
sudo nginx -t
curl -I http://hostel.example.edu/
curl -I https://hostel.example.edu/
openssl s_client -connect hostel.example.edu:443 -servername hostel.example.edu -verify_return_error </dev/null
```

The HTTP response should be a redirect to the HTTPS hostname. HTTPS should
return the application response (often a redirect to login) without redirecting
back to HTTP; the TLS verification command should complete without certificate
errors. Also run `python manage.py check --deploy` in the production
environment. Only after HTTPS is verified for all served hostnames, consider
setting `DJANGO_HSTS_SECONDS=31536000`. Enable HSTS subdomains or preload only
when every affected subdomain is also HTTPS-ready.

These are operator-run deployment steps. This repository change does not
provision certificates, configure DNS, or verify a live deployment.

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
## Database backup schedule

The backup service and timer templates use the same `www-data` account,
working directory, virtual environment, and protected `.env` file as the web
service. Review and adjust all paths before installation. Create the backup
directory so only the service account can access it:

```sh
sudo install -d -o www-data -g www-data -m 0700 /var/backups/hostel-management
sudo cp deploy/hostel-management-backup.service /etc/systemd/system/
sudo cp deploy/hostel-management-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hostel-management-backup.timer
```

The timer runs daily at 02:15 with a randomized delay of up to 15 minutes.
Backups older than 30 days are pruned only after a new backup succeeds.
Install the matching `mysqldump` client for MySQL deployments. The
`DB_PASSWORD` is written to a short-lived, owner-only MySQL client option file,
not command-line arguments; protect the environment file and service account
accordingly. Backups contain sensitive records and should be encrypted before
transfer or off-site storage.

Check `systemctl list-timers hostel-management-backup.timer` and the service
journal for scheduled-run results. For a test restore, use
`restore_database_backup` to create a new SQLite file that is not the active
database, or restore a MySQL dump only into a separately provisioned,
disposable MySQL instance and empty test schema. Verify representative records
and application behavior before recording the restore drill. Neither the
example timer nor automated SQLite tests prove that a production host has been
configured or that its production data has been restored.
