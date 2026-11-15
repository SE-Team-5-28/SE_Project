import http.client
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse
from django.core.wsgi import get_wsgi_application

from core.models import (
    Allocation,
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
    UserRole,
)


THRESHOLD_MS = 3000
MIN_REQUESTS = 6
MAX_REQUESTS = 300
MAX_CONCURRENCY = 8
WARMUP_REQUESTS_PER_ROUTE = 2


def percentile(values, percent):
    if not values:
        return None
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return sorted(values)[max(0, math.ceil(percent / 100 * len(values)) - 1)]


def summarize(samples):
    if not samples:
        return {}
    return {
        "count": len(samples),
        "min_ms": round(min(samples), 3),
        "median_ms": round(statistics.median(samples), 3),
        "p90_ms": round(percentile(samples, 90), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "max_ms": round(max(samples), 3),
        "mean_ms": round(statistics.mean(samples), 3),
    }


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class Command(BaseCommand):
    help = (
        "Benchmark common staff pages over loopback HTTP using disposable "
        "SQLite data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--requests",
            type=int,
            default=120,
            help=(
                f"Number of measured requests ({MIN_REQUESTS}-{MAX_REQUESTS}; "
                "default: 120)."
            ),
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=4,
            help=(
                f"Concurrent loopback clients (1-{MAX_CONCURRENCY}; "
                "default: 4)."
            ),
        )
        parser.add_argument(
            "--output",
            default="docs/performance-results.json",
            help="Path for the retained JSON report.",
        )

    def handle(self, *args, **options):
        request_count = options["requests"]
        concurrency = options["concurrency"]
        if not MIN_REQUESTS <= request_count <= MAX_REQUESTS:
            raise CommandError(
                f"--requests must be between {MIN_REQUESTS} and "
                f"{MAX_REQUESTS}."
            )
        if not 1 <= concurrency <= MAX_CONCURRENCY:
            raise CommandError(
                f"--concurrency must be between 1 and {MAX_CONCURRENCY}."
            )

        if os.environ.get("HMS_PERFORMANCE_WORKER") == "1":
            result = self._run_worker(request_count, concurrency)
            report_path = self._write_report(result, options["output"])
            self._report_result(result, report_path)
            if not result["passed"]:
                raise CommandError(
                    "Performance check failed; inspect the retained report "
                    "for HTTP errors or p90 values above the limit."
                )
            return

        with tempfile.TemporaryDirectory(prefix="hms-performance-") as temp_dir:
            temp_path = Path(temp_dir)
            report_path = temp_path / "results.json"
            environment = os.environ.copy()
            environment.update(
                {
                    "DB_ENGINE": "sqlite",
                    "DJANGO_DEBUG": "True",
                    "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
                    "DJANGO_SECURE_SSL_REDIRECT": "False",
                    "DJANGO_COOKIE_SECURE": "False",
                    "DJANGO_TRUST_PROXY_SSL_HEADER": "False",
                    "DJANGO_SETTINGS_MODULE": "config.performance_settings",
                    "HMS_PERFORMANCE_DATABASE_PATH": str(
                        temp_path / "benchmark.sqlite3"
                    ),
                    "HMS_PERFORMANCE_WORKER": "1",
                }
            )
            command = [
                sys.executable,
                str(settings.BASE_DIR / "manage.py"),
                "performance_check",
                "--requests",
                str(request_count),
                "--concurrency",
                str(concurrency),
                "--output",
                str(report_path),
            ]
            try:
                completed = subprocess.run(
                    command,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=(
                        WARMUP_REQUESTS_PER_ROUTE * 6 * 10
                        + request_count * 10 // concurrency
                        + 60
                    ),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CommandError(
                    "The isolated benchmark worker exceeded its time limit."
                ) from exc
            if not report_path.is_file():
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise CommandError(
                    "The isolated benchmark worker failed before saving its "
                    f"report. {detail}"
                )
            result = json.loads(report_path.read_text(encoding="utf-8"))

        report_path = self._write_report(result, options["output"])
        self._report_result(result, report_path)
        if completed.returncode != 0 or not result["passed"]:
            raise CommandError(
                "Performance check failed; inspect the retained report for "
                "HTTP errors or p90 values above the limit."
            )

    def _run_worker(self, request_count, concurrency):
        if (
            os.environ.get("DJANGO_SETTINGS_MODULE")
            != "config.performance_settings"
        ):
            raise CommandError(
                "The benchmark worker must use its isolated settings module."
            )
        database = settings.DATABASES["default"]
        database_path = Path(database["NAME"])
        if (
            database["ENGINE"] != "django.db.backends.sqlite3"
            or database_path.name != "benchmark.sqlite3"
            or not database_path.parent.name.startswith("hms-performance-")
        ):
            raise CommandError(
                "The benchmark worker database must be a temporary SQLite file."
            )

        call_command("migrate", interactive=False, verbosity=0)
        dataset = self._create_dataset()
        return self._run_benchmark(
            request_count=request_count,
            concurrency=concurrency,
            dataset=dataset,
        )

    def _write_report(self, result, output):
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = settings.BASE_DIR / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    def _report_result(self, result, report_path):
        self.stdout.write(f"Saved performance report to {report_path}")
        self.stdout.write(
            f"Overall p90: {result['overall']['p90_ms']} ms "
            f"(limit: {THRESHOLD_MS} ms)"
        )
        for name, summary in result["operations"].items():
            self.stdout.write(
                f"{name}: p90 {summary.get('p90_ms', 'n/a')} ms "
                f"({summary.get('count', 0)} requests)"
            )
        for failure in result["failures"] + result["warmup_failures"]:
            self.stderr.write(
                f"Request failure: {failure['operation']} returned "
                f"{failure['status']}: {failure['error']}"
            )
        if result["passed"]:
            self.stdout.write(self.style.SUCCESS("Performance check passed."))


    def _create_dataset(self):
        user_model = get_user_model()
        staff_user = user_model.objects.create_user(
            username="performance_staff",
            password=None,
            is_staff=True,
        )
        UserRole.objects.create(user=staff_user, role=UserRole.Role.WARDEN)

        hostels = [
            Hostel.objects.create(name=f"Benchmark Hostel {index:02d}")
            for index in range(1, 6)
        ]
        rooms = []
        for hostel_index, hostel in enumerate(hostels, start=1):
            for block_index in range(1, 3):
                block = Block.objects.create(
                    hostel=hostel,
                    name=f"Block {block_index}",
                )
                for room_index in range(1, 11):
                    rooms.append(
                        Room.objects.create(
                            block=block,
                            number=f"{room_index:03d}",
                            room_code=(
                                f"BENCH-{hostel_index}-{block_index}-"
                                f"{room_index:03d}"
                            ),
                            capacity=4,
                        )
                    )

        students = []
        for index in range(1, 101):
            user = user_model.objects.create_user(
                username=f"performance_student_{index:03d}",
                password=None,
            )
            students.append(
                Student.objects.create(
                    user=user,
                    student_id=f"PERF-{index:04d}",
                    full_name=f"Benchmark Student {index:03d}",
                    department="Computer Science",
                    year_of_study=2,
                )
            )

        for student, room in zip(students[:80], rooms[:80]):
            Allocation.objects.create(
                student=student,
                room=room,
                status=Allocation.Status.ACTIVE,
            )

        for index, student in enumerate(students[:20]):
            TransferRequest.objects.create(
                student=student,
                requested_room=rooms[80 + index],
                reason="Synthetic performance-check request.",
            )
            Complaint.objects.create(
                student=student,
                category="Facilities",
                description="Synthetic performance-check complaint.",
            )

        return {
            "staff_user": staff_user,
            "hostels": len(hostels),
            "blocks": len(hostels) * 2,
            "rooms": len(rooms),
            "students": len(students),
            "active_allocations": 80,
            "pending_transfers": 20,
            "open_complaints": 20,
        }

    def _run_benchmark(self, request_count, concurrency, dataset):
        routes = [
            ("staff_dashboard", reverse("dashboard")),
            ("student_list", reverse("student_list")),
            ("hostel_list", reverse("hostel_list")),
            ("allocation_list", reverse("allocation_list")),
            ("occupancy_report", reverse("occupancy_report")),
            ("pending_requests", reverse("pending_requests")),
        ]
        client = Client()
        client.force_login(dataset["staff_user"])
        session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
        if session_cookie is None:
            raise CommandError(
                "Could not create an authenticated benchmark session."
            )

        server = make_server(
            "127.0.0.1",
            0,
            get_wsgi_application(),
            server_class=ThreadedWSGIServer,
            handler_class=QuietWSGIRequestHandler,
        )
        port = server.server_port
        server_thread = threading.Thread(
            target=server.serve_forever,
            name="hms-performance-server",
            daemon=True,
        )
        server_thread.start()

        def request(route_name, path):
            started = time.perf_counter()
            connection = http.client.HTTPConnection(
                "127.0.0.1",
                port,
                timeout=10,
            )
            try:
                connection.request(
                    "GET",
                    path,
                    headers={
                        "Cookie": (
                            f"{settings.SESSION_COOKIE_NAME}="
                            f"{session_cookie.value}"
                        )
                    },
                )
                response = connection.getresponse()
                response.read()
                return {
                    "operation": route_name,
                    "status": response.status,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "error": None,
                }
            except (OSError, http.client.HTTPException) as exc:
                return {
                    "operation": route_name,
                    "status": None,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            finally:
                connection.close()

        warmup_failures = []
        samples = []
        try:
            for _ in range(WARMUP_REQUESTS_PER_ROUTE):
                for route_name, path in routes:
                    result = request(route_name, path)
                    if result["status"] != 200:
                        warmup_failures.append(result)

            measurement_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(request, *routes[index % len(routes)])
                    for index in range(request_count)
                ]
                for future in as_completed(futures):
                    samples.append(future.result())
            measurement_duration_seconds = (
                time.perf_counter() - measurement_started
            )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=10)

        values = [sample["latency_ms"] for sample in samples]
        operation_summaries = {}
        failures = [
            {
                "operation": sample["operation"],
                "status": sample["status"],
                "error": sample["error"],
            }
            for sample in samples
            if sample["status"] != 200
        ]
        for route_name, _path in routes:
            operation_samples = [
                sample["latency_ms"]
                for sample in samples
                if sample["operation"] == route_name and sample["status"] == 200
            ]
            operation_summaries[route_name] = summarize(operation_samples)

        overall = summarize(values)
        passed = (
            not failures
            and not warmup_failures
            and overall.get("p90_ms", 0) <= THRESHOLD_MS
            and all(
                summary.get("p90_ms", 0) <= THRESHOLD_MS
                for summary in operation_summaries.values()
            )
        )
        return {
            "schema_version": 1,
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "os": platform.platform(),
                "python": platform.python_version(),
                "django": django.get_version(),
                "logical_cpu_count": os.cpu_count(),
                "database": "SQLite in a temporary directory, deleted after run",
                "server": "Django WSGI handler on loopback (127.0.0.1)",
            },
            "load": {
                "measured_requests": request_count,
                "concurrency": concurrency,
                "warmup_requests_per_operation": WARMUP_REQUESTS_PER_ROUTE,
                "measurement_duration_seconds": round(
                    measurement_duration_seconds, 3
                ),
                "threshold_ms": THRESHOLD_MS,
            },
            "dataset": {
                key: value
                for key, value in dataset.items()
                if key != "staff_user"
            },
            "operations": operation_summaries,
            "overall": overall,
            "passed": passed,
            "failures": failures,
            "warmup_failures": warmup_failures,
            "samples": [
                {
                    "operation": sample["operation"],
                    "status": sample["status"],
                    "latency_ms": round(sample["latency_ms"], 3),
                    "error": sample["error"],
                }
                for sample in samples
            ],
        }
