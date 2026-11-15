# Requirements traceability and test report

This report maps every numbered requirement in the SRS to its related GitHub
issue, current implementation evidence, and the verification status evidenced
by the latest full CI run. A passing automated test does not establish
production, performance, availability, usability, recovery, or MySQL compliance
unless the stated environment and measurement were actually exercised.

## Requirement traceability matrix

| SRS requirement | Requirement summary | Related issue(s) | Implementation evidence | Test case and result |
| --- | --- | --- | --- | --- |
| HMS-F-001 | Authenticate registered students and staff with valid credentials. | #3 | Login route using Django `LoginView` in `core/urls.py`. | TC-Auth-01; `AuthenticationWorkflowTests.test_user_can_log_in_with_valid_credentials` — **Pass (CI)**. |
| HMS-F-002 | Reject invalid credentials and deny protected access. | #3 | Django `LoginView` and `login_required`/role guards in `core/views.py` and `core/permissions.py`. | TC-Auth-02; `AuthenticationWorkflowTests.test_user_cannot_log_in_with_invalid_password` and protected-dashboard redirect assertion — **Pass (CI)**. |
| HMS-F-003 | Enforce role-based access for Student, Warden, and Administrator. | #4, #8 | `UserRole`, `get_user_role` in `core/models.py`; `role_required` in `core/permissions.py`; role-guarded views in `core/views.py`. | TC-Auth-03; `RoleBasedAccessTests` — **Pass (CI)**. |
| HMS-F-010 | Let authorized staff maintain student records with unique student IDs. | #23 | `student_create`, `student_update` in `core/views.py`; `Student.student_id` in `core/models.py`. | TC-STU-01; `StudentRecordTests.test_staff_can_create_student`, `.test_duplicate_student_id_is_rejected`, `.test_staff_can_update_student` — **Pass (CI)**. |
| HMS-F-011 | Maintain hostel, block, and room records, including capacity and availability. | #24 | `hostel_create`, `block_create`, `room_create`, `room_update`, `hostel_list` in `core/views.py`; `RoomForm` in `core/forms.py`. | TC-RM-01; `HostelOperationsTests.test_staff_can_create_hostel_and_block_records`, `.test_staff_can_create_room_and_audit_action`, `.test_staff_can_update_hostel_block_and_room_records` — **Pass (CI)**. |
| HMS-F-020 | Allocate an available room to an eligible student. | #25 | `allocate_student` in `core/services.py`; `allocation_create` in `core/views.py`. | TC-AL-01; `AllocationServiceTests.test_service_allocates_student_when_room_has_space`, `HostelOperationsTests.test_staff_can_allocate_available_room_and_audit_action` — **Pass (CI)**. |
| HMS-F-021 | Record allocation date and status. | #25 | `Allocation` fields and `save` in `core/models.py`; allocation creation in `core/services.py`. | TC-AL-02; allocation/date/status assertions in `HostelOperationsTests.test_staff_can_allocate_available_room_and_audit_action` — **Pass (CI)**. |
| HMS-F-022 | Reject allocation when room capacity is reached. | #26 | Capacity check in `allocate_student` (`core/services.py`); room capacity validation in `core/forms.py`. | TC-AL-03; `AllocationServiceTests.test_service_rejects_allocation_when_room_is_full`, `HostelOperationsTests.test_full_room_cannot_receive_second_allocation` — **Pass (CI)**. The MySQL concurrency-only test is **Skipped** on SQLite. |
| HMS-F-023 | Prevent a student from having more than one active allocation. | #26 | Conditional uniqueness constraint and active-allocation guard in `core/models.py`; duplicate check in `core/services.py`. | TC-AL-04; `HostelOperationsTests.test_student_cannot_be_allocated_to_a_second_room`, `CoreModelTests.test_student_cannot_have_two_active_allocations` — **Pass (CI)**. |
| HMS-F-024 | Let authorized staff record student check-in. | #32 | `check_in` in `core/views.py`; active stay fields in `Allocation` (`core/models.py`). | TC-AL-05; `StudentCheckInOutTests.test_check_in_reactivates_previous_allocation`, `.test_check_in_cannot_exceed_room_capacity` — **Pass (CI)**. |
| HMS-F-025 | Record check-out and update room occupancy. | #32 | `check_out` in `core/views.py`; allocation status/date fields and `Room.occupied_count` in `core/models.py`. | TC-AL-06; `StudentCheckInOutTests.test_check_out_updates_stay_status_and_occupancy` — **Pass (CI)**. |
| HMS-F-030 | Let a student submit a room-transfer request with a reason. | #37 | `transfer_create` in `core/views.py`; `TransferRequestForm` and `TransferRequest` in `core/forms.py` and `core/models.py`. | TC-TR-01; `HostelOperationsTests.test_student_can_submit_and_staff_can_approve_transfer`, `.test_empty_transfer_reason_is_rejected` — **Pass (CI)**. |
| HMS-F-031 | Let authorized staff approve or reject a transfer request. | #38 | `transfer_review` in `core/views.py`; review status and reviewer fields in `TransferRequest` (`core/models.py`). | TC-TR-02; `HostelOperationsTests.test_student_can_submit_and_staff_can_approve_transfer`, `.test_staff_can_reject_transfer_without_changing_allocation`; role-denial test in `core/test_permissions.py` — **Pass (CI)**. |
| HMS-F-032 | Update old and new allocations consistently after an approved transfer. | #39 | Atomic `transfer_student` in `core/services.py`; atomic `transfer_review` in `core/views.py`. | TC-TR-03; `HostelOperationsTests.test_student_can_submit_and_staff_can_approve_transfer`, `.test_approval_rejects_full_destination_without_partial_transfer`; `AllocationServiceTests.test_transfer_rolls_back_old_allocation_when_new_allocation_fails` — **Pass (CI)**. |
| HMS-F-033 | Let students submit hostel complaints with a unique reference and status. | #11 | `Complaint` model in `core/models.py`; `complaint_create` in `core/views.py`. | TC-CMP-01; `ComplaintSubmissionTests.test_student_can_submit_complaint_with_unique_reference_and_open_status` — **Pass (CI)**. |
| HMS-F-034 | Let authorized staff update complaint status and resolution remarks. | #13 | `complaint_update` in `core/views.py`; `ComplaintUpdateForm` and `Complaint` in `core/forms.py` and `core/models.py`. | TC-CMP-02; `ComplaintUpdateTests.test_warden_and_administrators_can_update_status_and_remarks`, `.test_updated_status_and_remarks_are_visible_to_student` — **Pass (CI)**. |
| HMS-F-040 | Generate occupancy and vacancy summaries. | #16 | `occupancy_report` in `core/views.py`; occupancy aggregation uses active allocations. | TC-RPT-01; `HostelOperationsTests.test_occupancy_report_counts_active_allocations_and_vacancies` — **Pass (CI)**. |
| HMS-F-041 | Show pending transfer requests and unresolved complaints. | #17 | `pending_requests_dashboard` in `core/views.py`; `core/templates/core/pending_requests.html`. | TC-RPT-02; `PendingRequestsDashboardTests.test_dashboard_displays_pending_transfers`, `.test_dashboard_displays_unresolved_complaints` — **Pass (CI)**. |
| HMS-F-042 | Audit important administrative actions with actor, action, and timestamp. | #18 | `record_audit` in `core/services.py`; `audit` helper and audited views in `core/views.py`; `AuditLog` in `core/models.py`. | TC-AUD-01; `AuditLogAccessTests.test_room_and_allocation_admin_changes_are_audited`, `HostelOperationsTests.test_staff_can_create_room_and_audit_action` — **Pass (CI)**. |
| HMS-NF-001 | 90th-percentile response time at most 3 seconds under normal load. | #5 (open) | No benchmark/load-test harness or measured result found in this repository. | TC-Perf-01 — **Not run**; no latency or percentile result is claimed. |
| HMS-NF-002 | At least 99% monthly availability, excluding scheduled maintenance. | #6 (closed; evidence incomplete) | No in-repository uptime data or completed monthly observation found. | TC-REL-01 — **Not measured**; a full observation period and operational monitoring evidence are external prerequisites. |
| HMS-NF-003 | Keep allocation/occupancy consistent and enforce room capacity. | #9, #26 | Allocation constraints and transactional services in `core/models.py` and `core/services.py`; occupancy logic in `core/views.py`. | TC-DATA-01; `CoreModelTests`, `AllocationServiceTests`, and capacity/transfer regression tests — **Pass on SQLite (CI)**. MySQL-specific concurrent allocation remains unverified. |
| HMS-NF-004 | Provide responsive, understandable desktop and mobile interfaces. | #33 (closed; implementation merged), #10 (open) | Responsive base markup in `core/templates/core/base.html`; a `max-width: 600px` breakpoint in `core/static/core/site.css`. Presence of responsive styles is not usability evidence. | TC-UX-01 — **Not run**; no desktop/mobile browser test results are recorded. |
| HMS-NF-005 | Schedule database backups and verify restoration. | #7 (closed; evidence incomplete) | No backup schedule, backup/restore procedure, or checked-in execution evidence found in this repository. | TC-REC-01 — **Not run**; backup and restore are not demonstrated by the CI suite. |
| HMS-SR-001 | Require authentication for protected student and administrative functions. | #3, #8 | Django authentication views and `login_required`/role guards in `core/views.py` and `core/permissions.py`. | TC-SEC-01; `RoleBasedAccessTests.test_anonymous_user_is_redirected_to_login` and anonymous-access tests — **Pass (CI)**. |
| HMS-SR-002 | Enforce role-based authorization for Student, Warden, and Administrator. | #4, #8 | `UserRole` and `role_required` in `core/models.py` and `core/permissions.py`; guarded endpoints in `core/views.py`. | TC-SEC-02; `RoleBasedAccessTests` — **Pass (CI)**. |
| HMS-SR-003 | Store passwords using secure one-way hashing, never plaintext. | #19, #8 | Django password hashing; verified in `core/test_security.py` and `core/tests.py`. | TC-SEC-03; `PasswordHashingTests.test_user_password_is_stored_as_a_verifiable_hash`, `StudentRecordTests.test_passwords_are_stored_using_a_hash` — **Pass (CI)**. |
| HMS-SR-004 | Protect production client-server communication with HTTPS/TLS. | #21 (open), #8 | Production security settings in `config/settings.py`; example Nginx TLS proxy in `deploy/nginx.conf`; deployment guidance in `deploy/README.md`. Certificate and host are deployment-supplied. | TC-SEC-04 — **Partial**: Django HTTPS redirect/proxy behavior is tested by `HttpsProxySecurityTests`; no live TLS handshake or deployed certificate was verified. |
| HMS-SR-005 | Validate inputs and mitigate injection/malformed-input risks. | #20, #8 | Forms in `core/forms.py`; Django ORM-backed queries and input checks in `core/views.py`. | TC-SEC-05; `InputValidationSecurityTests` — **Pass (CI)** for the exercised malformed and injection-oriented inputs. |

The matrix contains 29 unique numbered SRS IDs: 19 HMS-F requirements, five
HMS-NF requirements, and five HMS-SR requirements. The SRS also lists search
and record retrieval as a major product function, but provides no separate
numbered requirement for it; no dedicated search route or test was found in
this baseline, so it is not represented as a passing numbered requirement.

## Latest test execution

The latest successful Django CI run on `main` is
[run 43698611722](https://github.com/SE-Team-5-28/SE_Project/actions/runs/43698611722)
for commit `6846c8485608c8ad8000ebaa6a9906bfe5df070c` (2026-11-15). Its job ran
`python manage.py check` and `python manage.py test`; **117 tests ran, 116
passed, one was skipped, and none failed**. The skipped test is
`AllocationConcurrencyTests.test_two_concurrent_requests_cannot_overfill_room`,
which explicitly requires MySQL. CI sets `DB_ENGINE=sqlite`, so the run does
not verify MySQL-specific database behavior.

## Open verification items, deviations, and external dependencies

- **Performance (#5):** TC-Perf-01 has no workload definition or result; normal
  load and p90 latency require a measured test environment.
- **Availability (#6):** the issue is closed, but the repository contains no
  monthly uptime observation. The issue's stated 99% target cannot be claimed
  without an observation period and monitoring evidence.
- **Usability (#10; implementation #33):** the responsive layout and role
  dashboards from #33 are merged; #10 remains open. Supported desktop/mobile
  browser checks and usability results are still absent.
- **Recovery (#7):** the issue is closed, but no scheduled backup and restore
  evidence is present in this repository. TC-REC-01 remains unverified.
- **Production TLS (#21):** the application and Nginx templates configure
  HTTPS behavior, but the example domain/certificate paths need real
  deployment values; no live handshake was performed.
- **Database:** the SRS/STP specify MySQL; SQLite is the local/CI default.
  Production MySQL configuration and a MySQL server are external dependencies.
  The one MySQL-only concurrency test was skipped, so its result is unknown.
- **Unnumbered SRS feature:** search and record retrieval are described in SRS
  §2.2 but have no numbered requirement ID, and no dedicated implementation
  route/test was found.
- **Architecture deviation:** the SAD's proposed JSON APIs/OpenAPI
  specification are not present; the application is server-rendered Django.
  The comparison and other design deviations are recorded in
  `docs/architecture-deviations.md`.
- **Document state:** the SRS and STP identify themselves as drafts. This
  trace records repository and CI evidence; it does not assert release
  acceptance or overall SRS compliance.
