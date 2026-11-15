# Performance check (TC-Perf-01)

Run the bounded benchmark from the repository root:

```sh
python manage.py performance_check
```

By default the command sends 120 measured requests with four concurrent
loopback clients, after two warm-up requests per operation. To change the load,
use `--requests` (6–300) and `--concurrency` (1–8). The command writes the
machine-readable report to `docs/performance-results.json`; pass `--output` to
choose another report path.

The harness starts a separate Django process with settings that force a new
SQLite database inside a uniquely named temporary directory. It migrates and
populates that database with synthetic data: 5 hostels, 10 blocks, 100 rooms,
100 students, 80 active allocations, 20 pending transfer requests, and 20 open
complaints. It starts Django's threaded WSGI handler bound only to
`127.0.0.1`, authenticates a synthetic staff account, then requests these
server-rendered staff operations:

| Operation | Measured requests | p90 |
| --- | ---: | ---: |
| Staff dashboard | 20 | 54.943 ms |
| Student list | 20 | 222.704 ms |
| Hostel list | 20 | 982.040 ms |
| Allocation list | 20 | 138.214 ms |
| Occupancy report | 20 | 82.242 ms |
| Pending requests | 20 | 203.937 ms |
| **Overall** | **120** | **740.134 ms** |

The p90 uses the nearest-rank method. A run passes only when every measured and
warm-up request returns HTTP 200 and both the overall and each operation's p90
are at most 3,000 ms. Failed status codes, connection errors, and latency
threshold failures are retained in the JSON report and cause a nonzero command
exit.

## Recorded run

The retained result in [`performance-results.json`](performance-results.json)
was collected on 2026-11-15 at 09:35 UTC: Windows 10, Python 3.11.2, Django
5.2.18, and 12 reported logical CPUs. The 120-request measured phase took 6.93
seconds. Overall median was 133.397 ms, p90 740.134 ms, p95 823.846 ms, and
maximum 1,046.521 ms. There were no HTTP or warm-up failures; all six
operations and the overall result met the 3-second threshold.

## Scope and limitations

This is a repeatable local application-level check, not a production load
test. The fixture size and four-client load are synthetic and are not derived
from production traffic. The database is temporary SQLite, and the request
server and clients share one Windows development host; the benchmark does not
include a production database, deployment server, proxy, TLS termination,
network latency, production hardware, or production data volume. The host's
CPU model and memory were not recorded. These results satisfy the documented
local scenario only and do not establish production performance.
