# Architecture and design deviations

This note compares the repository as implemented with the submitted Software
Requirements Specification (SRS), Software Architecture Document (SAD), and
Software Test Plan (STP). Those documents describe the intended design and
acceptance scope; they are not evidence that every requirement has been
implemented or verified. The comparisons below refer to the SRS's software
interfaces and communications requirements, the SAD's architecture and
technology choices (Sections 3.5–3.6) and API design (Section 4.3), and the
STP's proposed test strategy and environment (Sections 5–6).

## Architecture and technology

| Topic | Submitted design | Current repository |
| --- | --- | --- |
| Application architecture | The SAD selects a layered monolithic web application with separate business modules and cross-cutting security services. | The implementation is a single Django project and `core` app using Django models, forms, views, templates, and ORM transactions. It is a server-rendered monolith; there are no separately deployed services. |
| Database | The SRS names MySQL as a relational database option/interface; the SAD specifies MySQL. | SQLite is the default when `DB_ENGINE` is unset and is used by CI. MySQL is selectable with `DB_ENGINE=mysql` and the `DB_*` settings. |
| Client interface | The SAD describes a responsive web UI and also sketches REST-style JSON endpoints and API documentation. | The implemented interface is Django-rendered HTML with forms and role-aware pages. The repository does not expose the SAD's proposed JSON API endpoints or include an OpenAPI specification. |
| Validation and persistence | The SAD describes separate validation and data-access components. | Validation is implemented through Django forms and model constraints; database access uses Django's ORM. These are framework-level components, not separately deployed services. |

## Requirements and test-plan status

- Complaint submission/status updates and occupancy and pending-request views
  are implemented in the current code. Older status text elsewhere in the
  repository that describes complaints or occupancy reports as planned is
  stale.
- Backup scheduling/restoration, external email or notification integration,
  operational monitoring, availability measurement, and load/performance
  measurement are not provided as working operational services in this
  repository. They remain design or test-plan goals, not verified capabilities.
- The STP proposes broader system, performance, reliability, recovery,
  usability, browser, and security validation. The checked-in CI workflow runs
  `python manage.py check` and `python manage.py test`; those checks do not
  establish that every STP test case or non-functional target has passed.
- The automated suite uses the configured database. The MySQL-specific
  concurrent-allocation test is skipped on SQLite, so a SQLite test run is not
  evidence of MySQL concurrency behavior.
- HTTPS behavior has Django-level tests and example Nginx/systemd deployment
  templates. Production settings require an externally supplied strong secret,
  secure cookies, and HTTPS redirects; proxy-header trust is opt-in. The
  repository contains no deployment certificates and does not establish that
  a live TLS deployment has been configured or verified.

For local setup, environment variables, demo account password setup, and the
commands currently run in CI, see the [README](../README.md). Requirement-to-
implementation and test references are in
[requirements traceability](requirements-traceability.md).
