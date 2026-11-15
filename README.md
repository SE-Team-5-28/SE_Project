# Hostel Management System

A Django web application for managing student hostel records, hostels, blocks,
rooms, allocations, room transfers, complaints, occupancy reports, and audit
events. It provides role-aware student, warden, and administrator screens.

## Team

| Name | SRN |
| --- | --- |
| R Agilesh | PES2UG24CS385 |
| R G Nithik | PES2UG24CS386 |
| R Muralidharan | PES2UG24CS387 |
| R Pooja | PES2UG24CS388 |

## Current scope

Implemented workflows include authentication and role checks, student and
hostel record management, room allocation and check-in/check-out, student
transfer requests with staff review, complaint submission and updates,
occupancy and pending-request reports, and audit-log viewing.

The application is a server-rendered Django site, not a public JSON API.
University-wide academic administration, payment processing, external
notifications, and integrations are outside the current implementation.
For documented differences from the submitted design and test plan, see
[Architecture and design deviations](docs/architecture-deviations.md).

## Requirements

- Python 3.10 or later (the CI workflow currently runs Python 3.12)
- Git
- SQLite for the default local setup; no separate database server is needed
- A MySQL server only if you choose the optional MySQL configuration

## Local setup

Clone the repository and create and activate a virtual environment:

```powershell
git clone https://github.com/SE-Team-5-28/SE_Project.git
Set-Location SE_Project
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On macOS or Linux, activate it with:

```sh
git clone https://github.com/SE-Team-5-28/SE_Project.git
cd SE_Project
python -m venv .venv
source .venv/bin/activate
```

Install the application dependencies:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead of `Copy-Item`.
Review `.env` before running the app. The example is configured for local
SQLite use and leaves `DJANGO_SECRET_KEY` blank; with `DJANGO_DEBUG=True`, the
application uses a development-only fallback. Production requires an
externally supplied key of at least 50 characters with at least 16 distinct
characters. Keep production secrets out of source control and never put them
in `.env.example`.

Apply database migrations and start the development server:

```sh
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The database file `db.sqlite3` is created in
the repository root and is ignored by Git.

## Configuration

`config/settings.py` loads variables from the repository-root `.env` file.
Unset variables use the defaults below. Boolean values are enabled by setting
`True` (case-insensitive). In production (`DJANGO_DEBUG=False`), secure session
and CSRF cookies and HTTP-to-HTTPS redirects are enforced regardless of the
development toggles. Sessions expire after one hour, expire when the browser
closes, and are refreshed on requests.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | empty | Django signing key. An insecure fallback is used only in debug mode; production requires an external key of at least 50 characters and 16 distinct characters. |
| `DJANGO_DEBUG` | `True` | Enables Django debug mode; set to `False` for production. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated hostnames accepted by Django. |
| `DJANGO_COOKIE_SECURE` | `False` | Enables HTTPS-only session and CSRF cookies in debug mode; cookies are always secure in production. |
| `DJANGO_SECURE_SSL_REDIRECT` | `False` | Enables HTTP-to-HTTPS redirects in debug mode; redirects are always enabled in production. |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | `False` | Trusts `X-Forwarded-Proto: https` only when `True`; enable only behind a trusted proxy that overwrites the header and blocks direct client access to the app server. |
| `DJANGO_HSTS_SECONDS` | `0` | Sets the HSTS duration in seconds; configure only after HTTPS is verified. |
| `DJANGO_HSTS_INCLUDE_SUBDOMAINS` | `False` | Includes subdomains in HSTS when `True`; use only when every subdomain supports HTTPS. |
| `DJANGO_HSTS_PRELOAD` | `False` | Enables HSTS preload when `True`; use only after verifying all preload requirements. |
| `DB_ENGINE` | `sqlite` | Select `sqlite` (any non-`mysql` value uses SQLite) or `mysql`. |
| `SQLITE_DB_PATH` | `<repository>/db.sqlite3` | Optional path for the SQLite database; useful for isolated restore tests. |
| `DB_NAME` | `hms_db` | MySQL database name; used only when `DB_ENGINE=mysql`. |
| `DB_USER` | `root` | MySQL username; used only when `DB_ENGINE=mysql`. |
| `DB_PASSWORD` | empty | MySQL password; used only when `DB_ENGINE=mysql`. |
| `DB_HOST` | `127.0.0.1` | MySQL host; used only when `DB_ENGINE=mysql`. |
| `DB_PORT` | `3306` | MySQL port; used only when `DB_ENGINE=mysql`. |

### Optional MySQL setup

Install and start MySQL, create a database and user, then set `DB_ENGINE=mysql`
and the `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` values in
`.env` (uncomment the corresponding example entries if you copied
`.env.example`). The MySQL Python driver is included in `requirements.txt`. Run
`python manage.py migrate` after configuring the connection. SQLite remains
the default for local development and CI.

## Database backups and restore tests

Create a consistent backup of the configured database with:

```sh
python manage.py backup_database --output-dir /var/backups/hostel-management --keep-days 30
```

The command defaults to `DB_BACKUP_DIR` or `./backups`, keeps backup files
private, and removes matching backups older than the retention window only
after a successful new backup. SQLite backups use SQLite's online backup API
and are checked with `integrity_check` and `foreign_key_check`. MySQL backups
use `mysqldump`; install the matching MySQL client tools and keep
`DB_PASSWORD` in the protected environment file. The command writes the
password to a short-lived, owner-only MySQL option file rather than passing it
on the command line. Backups contain sensitive application data: store them
outside the repository on access-controlled storage, encrypt them at rest and
in transit, and keep an independently protected off-site copy.

Restore a SQLite backup to a **new disposable database file** to verify it
without changing the configured application database:

```sh
python manage.py restore_database_backup --backup /path/to/hms-sqlite-backup.sqlite3 --target /tmp/hms-restore-test.sqlite3
```

The command refuses to overwrite an existing file or the currently configured
SQLite database, and checks database and foreign-key integrity. The automated
test suite also restores a generated backup and asserts a known user's email
survives. For MySQL, restore only to a separate, disposable MySQL instance and
an empty test schema whose name differs from `DB_NAME`; for example:

```sh
mysql --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --database="$RESTORE_TEST_DB" < /path/to/hms-mysql-backup.sql
```

Then compare representative records and row counts with the source snapshot.
The repository's CI does not provision MySQL, so it does not claim a MySQL
restore or production restore was performed.

The `deploy/hostel-management-backup.service` and
`deploy/hostel-management-backup.timer` templates schedule a daily backup at
02:15 with a 15-minute randomized delay and 30-day local retention. Configure
the host paths and permissions, then install and enable them with systemd:

```sh
sudo install -d -o www-data -g www-data -m 0700 /var/backups/hostel-management
sudo cp deploy/hostel-management-backup.service /etc/systemd/system/
sudo cp deploy/hostel-management-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hostel-management-backup.timer
sudo systemctl start hostel-management-backup.service
sudo systemctl status hostel-management-backup.service
```

The last commands verify the first scheduled-job configuration on the target
host; this repository cannot confirm a deployment's live schedule, backup
storage, or disaster-recovery readiness. Periodically restore a recent backup
into an isolated test environment, verify critical records and application
behavior, record the result, and adjust frequency/retention to meet the
service's recovery objectives.

## Demo data and accounts

After migrations, create repeatable sample hostel, room, allocation, student,
and role data with:

```sh
python manage.py seed_demo
```

The command creates these usernames: `demo_student1`, `demo_student2`,
`demo_warden`, and `demo_admin`. It deliberately does **not** set usable
passwords. Set a password for each account you want to use by running
`python manage.py changepassword <username>` and entering a password when
prompted, for example:

```sh
python manage.py changepassword demo_student1
```

The command can be run again to ensure the demo records exist. It does not
create a production account or initialize a production database.
The [Sprint 2 demo and freeze record](docs/sprint-2-demo.md) provides a
reproducible walkthrough and records its verification gaps.

## Checks and tests

Run the standard Django system check and automated test suite:

```sh
python manage.py check
python manage.py test
```

The CI workflow runs these same commands with SQLite. The test suite also
contains a MySQL-only concurrency test; it is skipped when the active database
is not MySQL. `python manage.py check --deploy` can report production
configuration warnings, but passing it alone does not establish that a live
deployment is secure or available.

Run the bounded local performance scenario and retain its JSON result with:

```sh
python manage.py performance_check
```

The scenario, result, and environment limitations are documented in
[Performance check (TC-Perf-01)](docs/performance-checks.md).

## Deployment notes

`requirements-production.txt` adds Gunicorn. The files in `deploy/` are example
systemd and Nginx configuration for a Linux host using MySQL and HTTPS; replace
the example paths, domain, and certificate references and review all settings
for the target environment. `deploy/README.md` describes the intended
configuration steps, including the production key requirements and when to
trust the reverse-proxy HTTPS header, plus the installable systemd health
monitor and recovery procedure. These templates are not evidence of a deployed
or externally verified service: this repository does not include TLS
certificates, production credentials, backup/restore automation, or external
uptime measurements.

## Repository guide

```text
config/                         Django settings, URLs, and WSGI/ASGI entrypoints
core/                           Application models, views, templates, tests, and seed command
docs/Hostel_Management_System_SRS.pdf
docs/Hostel_Management_System_SAD.docx
docs/Hostel_Management_System_Test_Plan.pdf
docs/architecture-deviations.md Current implementation compared with the submitted design
docs/performance-checks.md       TC-Perf-01 scenario, results, and limitations
docs/performance-results.json    Retained local benchmark measurements
docs/requirements-traceability.md Requirements, implementation, and test references
docs/sprint-2-demo.md             Sprint 2 demo sequence and tested baseline
deploy/                         Example production-like configuration templates
requirements.txt                Local and CI Python dependencies
requirements-production.txt     Dependencies including Gunicorn
```

The submitted Software Requirements Specification (SRS), Software Architecture
Document (SAD), and Software Test Plan (STP) describe planned requirements and
designs; see the deviations document for what is implemented and what remains
unverified.
