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
