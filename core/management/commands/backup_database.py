import os
import shutil
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Create a consistent, private backup of the configured database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=os.getenv("DB_BACKUP_DIR", str(settings.BASE_DIR / "backups")),
            help="Directory for backups (default: DB_BACKUP_DIR or ./backups).",
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=30,
            help="Delete older matching backups after a successful backup.",
        )

    def handle(self, *args, **options):
        keep_days = options["keep_days"]
        if keep_days < 1:
            raise CommandError("--keep-days must be at least 1.")

        vendor = connection.vendor
        if vendor not in {"sqlite", "mysql"}:
            raise CommandError(
                f"Database backend {vendor!r} is not supported for backups."
            )

        output_dir = Path(options["output_dir"]).expanduser().resolve()
        try:
            output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as error:
            raise CommandError(f"Cannot create backup directory: {error}") from error

        suffix = ".sqlite3" if vendor == "sqlite" else ".sql"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = output_dir / f"hms-{vendor}-{timestamp}{suffix}"
        if backup_path.exists():
            raise CommandError(f"Backup already exists: {backup_path}")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".hms-backup-", suffix=suffix, dir=output_dir
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            try:
                os.chmod(temporary_path, 0o600)
            except OSError as error:
                raise CommandError(
                    f"Cannot restrict temporary backup access: {error}"
                ) from error

            if vendor == "sqlite":
                self._backup_sqlite(temporary_path)
            else:
                self._backup_mysql(temporary_path)

            if temporary_path.stat().st_size == 0:
                raise CommandError("The database backup is empty.")
            os.replace(temporary_path, backup_path)
            self._prune_old_backups(output_dir, vendor, suffix, keep_days)
        except (OSError, sqlite3.Error) as error:
            raise CommandError(f"Database backup failed: {error}") from error
        finally:
            temporary_path.unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f"Database backup created: {backup_path}"))

    @staticmethod
    def _backup_sqlite(destination_path):
        connection.ensure_connection()
        if connection.connection is None:
            raise CommandError("Could not open the configured SQLite database.")

        with closing(sqlite3.connect(destination_path)) as destination:
            connection.connection.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise CommandError(f"SQLite backup integrity check failed: {result}")
            violations = destination.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise CommandError(
                    f"SQLite backup has foreign-key violations: {len(violations)}."
                )

    @staticmethod
    def _backup_mysql(destination_path):
        database = connection.settings_dict
        executable = shutil.which("mysqldump")
        if executable is None:
            raise CommandError(
                "mysqldump is required for MySQL backups and must be on PATH."
            )

        command = [
            executable,
            "--single-transaction",
            "--quick",
            "--routines",
            "--events",
            "--triggers",
            f"--host={database['HOST'] or 'localhost'}",
            f"--port={database['PORT'] or '3306'}",
            f"--user={database['USER']}",
            f"--result-file={destination_path}",
            str(database["NAME"]),
        ]
        environment = os.environ.copy()
        environment.pop("MYSQL_PWD", None)
        options_path = None
        password = database.get("PASSWORD", "")
        if password:
            if any(character in password for character in ("\0", "\r", "\n")):
                raise CommandError("The MySQL password contains unsupported control characters.")
            descriptor, options_name = tempfile.mkstemp(
                prefix="hms-mysql-client-", suffix=".cnf"
            )
            options_path = Path(options_name)
            escaped_password = password.replace("\\", "\\\\").replace('"', '\\"')
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as options_file:
                    options_file.write(
                        f'[client]\npassword="{escaped_password}"\n'
                    )
                os.chmod(options_path, 0o600)
            except OSError:
                options_path.unlink(missing_ok=True)
                raise
            command.insert(1, f"--defaults-extra-file={options_path}")

        try:
            subprocess.run(command, check=True, env=environment)
        except FileNotFoundError as error:
            raise CommandError("mysqldump could not be started.") from error
        except subprocess.CalledProcessError as error:
            raise CommandError(
                f"mysqldump failed with exit code {error.returncode}."
            ) from error
        finally:
            if options_path is not None:
                options_path.unlink(missing_ok=True)

    @staticmethod
    def _prune_old_backups(output_dir, vendor, suffix, keep_days):
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        pattern = f"hms-{vendor}-*{suffix}"
        for path in output_dir.glob(pattern):
            if path.is_symlink() or not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified < cutoff:
                path.unlink()
