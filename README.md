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
SQLite use. Generate a unique `DJANGO_SECRET_KEY` for any environment beyond
throwaway local development. Never commit `.env` or put real credentials in
`.env.example`.

Apply database migrations and start the development server:

```sh
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The database file `db.sqlite3` is created in
the repository root and is ignored by Git.

## Configuration

`config/settings.py` loads variables from the repository-root `.env` file.
Unset variables use the defaults below. Boolean values are enabled only by
setting `True` (case-insensitive).

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | `dev-only-change-me` | Django signing key. Replace with a unique, private value outside disposable local use. |
| `DJANGO_DEBUG` | `False` | Enables Django debug mode when set to `True`; use only for local development. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated hostnames accepted by Django. |
| `DJANGO_COOKIE_SECURE` | `False` | Sets session and CSRF cookies to HTTPS-only when `True`. |
| `DJANGO_SECURE_SSL_REDIRECT` | `False` | Redirects HTTP requests to HTTPS when `True`; enable only behind working HTTPS. |
| `DJANGO_HSTS_SECONDS` | `0` | Enables HSTS for the configured number of seconds; increase only after HTTPS is verified. |
| `DB_ENGINE` | `sqlite` | Select `sqlite` (any non-`mysql` value uses SQLite) or `mysql`. |
| `DB_NAME` | `hms_db` | MySQL database name; used only when `DB_ENGINE=mysql`. |
| `DB_USER` | `root` | MySQL username; used only when `DB_ENGINE=mysql`. |
| `DB_PASSWORD` | empty | MySQL password; used only when `DB_ENGINE=mysql`. |
| `DB_HOST` | `127.0.0.1` | MySQL host; used only when `DB_ENGINE=mysql`. |
| `DB_PORT` | `3306` | MySQL port; used only when `DB_ENGINE=mysql`. |

### Optional MySQL setup

Install and start MySQL, create a database and user, then set `DB_ENGINE=mysql`
and the `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` values in
`.env`. The MySQL Python driver is included in `requirements.txt`. Run
`python manage.py migrate` after configuring the connection. SQLite remains the
default for local development and CI.

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

## Deployment notes

`requirements-production.txt` adds Gunicorn. The files in `deploy/` are example
systemd and Nginx configuration for a Linux host using MySQL and HTTPS; replace
the example paths, domain, and certificate references and review all settings
for the target environment. `deploy/README.md` describes the intended
configuration steps. These templates are not evidence of a deployed or
externally verified service: this repository does not include TLS
certificates, production credentials, backup/restore automation, or runtime
monitoring.

## Repository guide

```text
config/                         Django settings, URLs, and WSGI/ASGI entrypoints
core/                           Application models, views, templates, tests, and seed command
docs/Hostel_Management_System_SRS.pdf
docs/Hostel_Management_System_SAD.docx
docs/Hostel_Management_System_Test_Plan.pdf
docs/architecture-deviations.md Current implementation compared with the submitted design
docs/requirements-traceability.md Requirements, implementation, and test references
deploy/                         Example production-like configuration templates
requirements.txt                Local and CI Python dependencies
requirements-production.txt     Dependencies including Gunicorn
```

The submitted Software Requirements Specification (SRS), Software Architecture
Document (SAD), and Software Test Plan (STP) describe planned requirements and
designs; see the deviations document for what is implemented and what remains
unverified.
