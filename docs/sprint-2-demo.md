# Sprint 2 demo and freeze record

This runbook describes a reproducible local demonstration and records the
tested application baseline. It is not a video, a human demo review, or
production acceptance.

## Tested baseline

- Application baseline: `main` at `f20a4d3a3bb78941b6f3254b69376c6993394900`,
  the merge of PR #67.
- GitHub Actions run
  [43700883963](https://github.com/SE-Team-5-28/SE_Project/actions/runs/43700883963)
  completed successfully for that commit. It ran `python manage.py check` and
  `python manage.py test`.
- Local verification on Windows with Python 3.11 and SQLite: `python manage.py
  check` passed; `python manage.py test` ran 131 tests, with 130 passing and
  one skipped. The skipped test is the MySQL-only concurrent-allocation test.
- No release tag was created. For this issue, “freeze” means recording this
  tested application baseline and limiting this delivery to demo/release
  documentation; it does not disable future development or establish
  production readiness.

## Reproducible two-minute walkthrough

Use a fresh disposable checkout/database, not production or a database
containing real student data. Install the dependencies as described in the
repository README. The seed command creates synthetic demo records and role
accounts without setting usable passwords.

In PowerShell, select a new SQLite file and prepare the sample data:

```powershell
$env:SQLITE_DB_PATH = Join-Path $env:TEMP 'hms-sprint2-demo.sqlite3'
python manage.py migrate
python manage.py seed_demo
python manage.py changepassword demo_student1
python manage.py changepassword demo_warden
python manage.py runserver 127.0.0.1:8000
```

Choose a new file name if that path already exists. Enter temporary passwords
interactively; do not put them in the recording. The same `SQLITE_DB_PATH`
must be set in the terminal running each command. On macOS/Linux, set
`SQLITE_DB_PATH` to a new disposable path with `export` before running the
same Django commands. Open <http://127.0.0.1:8000/> in two browser profiles
(student and warden) and sign in before starting the capture.

| Time | Demonstration |
| --- | --- |
| 0:00–0:18 | Show the student dashboard and the seeded active allocation for Demo Student One. |
| 0:18–0:42 | Submit a room-transfer request for Block A, Room 102, with the synthetic reason “Sprint 2 demo request”; show that it is pending. |
| 0:42–1:15 | Switch to the warden profile, open Pending Requests, and approve the transfer. |
| 1:15–1:42 | Return to the student profile and show the request as approved. |
| 1:42–2:00 | In the warden profile, show the updated allocation/occupancy and finish on the application. |

Use a screen recorder that captures the browser and lasts two minutes. Keep the
recording limited to this seeded local database; do not show passwords,
personal data, or production systems. Record the browser/OS and tested commit
alongside the video, then upload or link the actual recording in the
repository or issue after a human has reviewed it.

## Recording and review status

No recording was created in this environment. Although the Playwright Python
package is installed, its Chromium executable is absent; neither OBS nor
FFmpeg is installed. A real two-minute capture therefore requires an operator
with a working browser and screen recorder to run the walkthrough above,
upload/link the resulting video, and complete the demo review. No video or
human acceptance is claimed here.

## Remaining verification evidence

These are verification gaps, not claims that the corresponding features are
broken:

| Reference | Evidence still required |
| --- | --- |
| #5 performance | Existing results cover only the documented local synthetic workload. Run and retain measurements on the intended production-like infrastructure and workload. |
| #6 availability | Deploy an independent uptime monitor and retain a complete observation period to assess the monthly availability target. |
| #10 device QA | Run and record the supported workflows on physical iOS and Android devices using their native browsers; desktop and mobile emulation do not replace this. |
| #21 TLS | Verify a live TLS handshake and certificate for the deployed hostname; configuration templates and automated tests are not live-deployment evidence. |
| #7 backup/restore | Demonstrate a scheduled production backup and a restore into a separate disposable MySQL environment, then record verification of representative data. Local SQLite backup tests do not establish this. |

Automated checks found no new code defect to report, but they do not substitute
for the missing demo review or external verification above. Keep issue #15
open until its recording/link and human review are supplied; do not treat this
documentation or the passing SQLite CI run as completion of those criteria.
