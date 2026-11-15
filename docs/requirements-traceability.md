# Requirements traceability and verification report

| Requirement / issue | Implementation | Verification |
| --- | --- | --- |
| Manage hostels, blocks and rooms (#24) | `Hostel`, `Block`, `Room` models and staff CRUD views | `HostelOperationsTests`, Django system check |
| Allocate eligible student (#25) | Capacity validation, one active allocation constraint, allocation screen | `test_staff_can_allocate_available_room_and_audit_action`, `test_full_room_cannot_receive_second_allocation` |
| Submit room transfer requests (#37) | `TransferRequest`, student form, staff review workflow | `test_student_can_submit_and_staff_can_approve_transfer` |
| Complete approved room transfers (#39) | Atomic allocation swap, locked destination-capacity check, and staff approval action | `test_student_can_submit_and_staff_can_approve_transfer`, `test_approval_rejects_full_destination_without_partial_transfer`, `test_transfer_rolls_back_old_allocation_when_new_allocation_fails` |
| Responsive base layout and role dashboards (#33) | `base.html`, responsive CSS, staff/student navigation | Template smoke coverage through Django tests |
| Secure hashing and sessions (#19) | Django password hasher, HTTP-only/SameSite session cookies, CSRF middleware | Login workflow and password-hashing tests |
| Audit administrative actions (#18) | Actor/timestamp audit events for room and allocation operations; role-restricted, read-only audit screen and Django admin | `HostelOperationsTests`, `StudentCheckInOutTests`, `AuditLogAccessTests` |
| HTTPS/TLS deployment (#21) | Example Nginx TLS proxy, Gunicorn systemd unit, and configurable Django security settings | Django forwarded-protocol/redirect tests and deployment-template review; no live TLS deployment verified |

## Scope deviations

SQLite is the default for local development and CI; MySQL can be selected with
`DB_ENGINE=mysql`. Complaint submission/status updates and occupancy and
pending-request views are implemented in the current repository. Backup and
restore operations, external notification integrations, and production
availability/performance measurements are not established by the code or
tests. The proposed public JSON APIs in the SAD are not present; the current
application uses server-rendered Django pages and forms. See
[`architecture-deviations.md`](architecture-deviations.md) for the comparison
with the submitted SRS, SAD, and STP.

## Test commands

```text
python manage.py check
python manage.py test
python manage.py check --deploy
```

The standard system check and automated test suite are run by CI. The
deployment check is an additional configuration review and may report
warnings when local development settings are in use; it is not evidence of a
live production deployment.

## Security test evidence (#8)

| Test case | Security check | Verification | Result |
| --- | --- | --- | --- |
| TC-SEC-01 | Authentication | `AuthenticationWorkflowTests`: valid login, invalid password rejection, and logout/session invalidation | Pass |
| TC-SEC-02 | Role restrictions | `RoleBasedAccessTests`: role-appropriate dashboard access, denied cross-role access, and anonymous redirect | Pass |
| TC-SEC-03 | Password storage | `StudentRecordTests.test_passwords_are_stored_using_a_hash` | Pass |
| TC-SEC-04 | HTTPS | `HttpsProxySecurityTests`: forwarded HTTPS is accepted without a redirect loop; HTTP redirects to HTTPS | Pass |
| TC-SEC-05 | Input validation | `InputValidationSecurityTests`: injection strings, malformed values, oversized values, and invalid create requests are rejected | Pass |

Execution: `python manage.py test` found 99 tests; all passed, with one
MySQL-only concurrency test skipped on SQLite. The HTTPS tests exercise
Django's forwarded-protocol and redirect handling; they do not run Nginx or
perform a live TLS handshake. No deployment certificate or server is available
in this test environment.

## Sprint 1 test coverage (#34)

| Test plan cases | Coverage |
| --- | --- |
| TC-Auth-01–03 | `AuthenticationWorkflowTests`: valid login, invalid password rejection, and logout/session invalidation |
| TC-STU-01 | `StudentRecordTests`: student creation and duplicate student ID rejection; `CoreModelTests`: database uniqueness for student IDs |
| TC-RM-01 | `HostelOperationsTests.test_staff_can_create_room_and_audit_action`: room creation; `CoreModelTests`: unique room code, unique room number per block, and minimum capacity constraints |
| TC-AL-01–06 | `HostelOperationsTests` and `AllocationServiceTests`: available-room allocation, full-room rejection, duplicate active allocation rejection, and audit behavior; `CoreModelTests`: database guard against multiple active allocations and reallocation after completion; `StudentCheckInOutTests`: stay check-in/check-out and capacity protection |

Latest full-suite verification: see the security test evidence above. Django system checks reported no issues.
