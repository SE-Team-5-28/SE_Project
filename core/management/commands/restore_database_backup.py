import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


def _configured_sqlite_path():
    if connection.vendor != "sqlite":
        return None

    name = connection.settings_dict["NAME"]
    if not isinstance(name, (str, os.PathLike)) or str(name).startswith("file:"):
        return None
    if str(name) == ":memory:":
        return None
    return Path(name).expanduser().resolve()


class Command(BaseCommand):
    help = (
        "Restore a SQLite backup to a new disposable file and verify its integrity. "
        "Existing files are never overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument("--backup", required=True, help="SQLite backup file to restore.")
        parser.add_argument(
            "--target",
            required=True,
            help="Path for a new SQLite database file; it must not already exist.",
        )

    def handle(self, *args, **options):
        backup_path = Path(options["backup"]).expanduser().resolve()
        target_path = Path(options["target"]).expanduser().resolve()
        configured_path = _configured_sqlite_path()

        if not backup_path.is_file():
            raise CommandError(f"Backup file does not exist: {backup_path}")
        if backup_path == target_path:
            raise CommandError("The restore target must differ from the backup file.")
        if configured_path is not None and target_path == configured_path:
            raise CommandError(
                "The restore target must not be the configured application database."
            )
        if target_path.exists():
            raise CommandError(
                f"Restore target already exists; refusing to overwrite: {target_path}"
            )
        if not target_path.parent.is_dir():
            raise CommandError("The restore target directory must already exist.")

        try:
            with backup_path.open("rb") as backup_file:
                if backup_file.read(16) != b"SQLite format 3\x00":
                    raise CommandError("The backup is not a SQLite database.")

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".hms-restore-", suffix=".sqlite3", dir=target_path.parent
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            try:
                os.chmod(temporary_path, 0o600)
                with closing(sqlite3.connect(backup_path)) as source, closing(
                    sqlite3.connect(temporary_path)
                ) as destination:
                    source.backup(destination)
                    integrity = destination.execute(
                        "PRAGMA integrity_check"
                    ).fetchone()
                    if integrity != ("ok",):
                        raise CommandError(
                            f"Restored database integrity check failed: {integrity}"
                        )
                    violations = destination.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall()
                    if violations:
                        raise CommandError(
                            "Restored database has "
                            f"{len(violations)} foreign-key violations."
                        )

                os.link(temporary_path, target_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        except FileExistsError as error:
            raise CommandError(
                f"Restore target already exists; refusing to overwrite: {target_path}"
            ) from error
        except (OSError, sqlite3.Error) as error:
            raise CommandError(f"Database restore failed: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(f"SQLite backup restored and verified: {target_path}")
        )
