import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *


database_path = os.environ.get("HMS_PERFORMANCE_DATABASE_PATH")
if not database_path:
    raise ImproperlyConfigured(
        "HMS_PERFORMANCE_DATABASE_PATH is required for benchmark settings."
    )

database_path = Path(database_path).resolve()
if (
    database_path.name != "benchmark.sqlite3"
    or not database_path.parent.name.startswith("hms-performance-")
):
    raise ImproperlyConfigured(
        "Benchmark settings require a temporary hms-performance directory."
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(database_path),
        "OPTIONS": {"timeout": 30},
        "CONN_MAX_AGE": 0,
    }
}
