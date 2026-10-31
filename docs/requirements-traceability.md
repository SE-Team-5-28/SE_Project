# Requirements traceability and verification report

| Requirement / issue | Implementation | Verification |
| --- | --- | --- |
| Manage hostels, blocks and rooms (#24) | `Hostel`, `Block`, `Room` models and staff CRUD views | `HostelOperationsTests`, Django system check |
| Allocate eligible student (#25) | Capacity validation, one active allocation constraint, allocation screen | `test_staff_can_allocate_available_room_and_audit_action`, `test_full_room_cannot_receive_second_allocation` |
| Submit room transfer requests (#37) | `TransferRequest`, student form, staff review workflow | `test_student_can_submit_and_staff_can_approve_transfer` |
| Responsive base layout and role dashboards (#33) | `base.html`, responsive CSS, staff/student navigation | Template smoke coverage through Django tests |
| Secure hashing and sessions (#19) | Django password hasher, HTTP-only/SameSite session cookies, CSRF middleware | Existing login tests plus `manage.py check --deploy` in production configuration |
| Audit administrative actions (#18) | Immutable read-only `AuditLog` admin and audit helper | Allocation and transfer tests assert audit records |
| HTTPS/TLS deployment (#21) | Nginx TLS proxy, Gunicorn systemd unit, secure Django settings | `deploy/README.md` deployment checklist |

## Scope deviations

The repository's original SRS describes MySQL as the proposed database. SQLite is now the default for local development and CI to make setup reproducible; production deployments still use MySQL by setting `DB_ENGINE=mysql`. Complaint management, occupancy reports, and backup/restore remain planned work and are not represented as complete here.

## Test command

```text
python manage.py test
python manage.py check --deploy
```

## Sprint 1 test coverage (#34)

| Test plan cases | Coverage |
| --- | --- |
| TC-Auth-01–03 | `AuthenticationWorkflowTests`: valid login, invalid password rejection, and logout/session invalidation |
| TC-STU-01 | `StudentRecordTests`: student creation and duplicate student ID rejection; `CoreModelTests`: database uniqueness for student IDs |
| TC-RM-01 | `HostelOperationsTests.test_staff_can_create_room_and_audit_action`: room creation; `CoreModelTests`: unique room code, unique room number per block, and minimum capacity constraints |
| TC-AL-01–06 | `HostelOperationsTests` and `AllocationServiceTests`: available-room allocation, full-room rejection, duplicate active allocation rejection, and audit behavior; `CoreModelTests`: database guard against multiple active allocations and reallocation after completion; `StudentCheckInOutTests`: stay check-in/check-out and capacity protection |

Latest verification: `python manage.py test` found 51 tests; all passed, with one MySQL-only concurrency test skipped on the SQLite test database. Django system checks reported no issues.
