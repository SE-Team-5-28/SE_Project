# Production-like HTTPS deployment

1. Set `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, production hosts, `DB_ENGINE=mysql`, and `DJANGO_COOKIE_SECURE=True` in `.env`.
2. Set `DJANGO_SECURE_SSL_REDIRECT=True` and `DJANGO_HSTS_SECONDS=31536000` only after HTTPS is working.
3. Install `requirements-production.txt`, run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
4. Install the systemd unit and Nginx configuration, replacing the example domain and certificate paths.
5. Obtain certificates with Certbot, then verify the HTTP redirect and `python manage.py check --deploy`.

These templates contain no private keys or certificates.
