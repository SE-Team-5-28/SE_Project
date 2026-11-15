import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase

from core.management.commands.backup_database import Command as BackupCommand


class DatabaseBackupRestoreTests(TransactionTestCase):
    def test_backup_restores_user_data_to_a_new_database(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="backup-restore-check",
            email="backup-restore@example.com",
            password="test-only-password",
        )

        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory) / "backups"
            call_command("backup_database", output_dir=str(backup_dir))
            backups = list(backup_dir.glob("hms-sqlite-*.sqlite3"))
            self.assertEqual(len(backups), 1)

            restored_path = Path(directory) / "restored.sqlite3"
            call_command(
                "restore_database_backup",
                backup=str(backups[0]),
                target=str(restored_path),
            )

            with closing(sqlite3.connect(restored_path)) as restored:
                self.assertEqual(
                    restored.execute("PRAGMA integrity_check").fetchone(),
                    ("ok",),
                )
                self.assertEqual(
                    restored.execute(
                        "SELECT email FROM auth_user "
                        "WHERE username = ?",
                        ("backup-restore-check",),
                    ).fetchone(),
                    ("backup-restore@example.com",),
                )

    def test_restore_refuses_to_overwrite_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory) / "backups"
            call_command("backup_database", output_dir=str(backup_dir))
            backup_path = next(backup_dir.glob("hms-sqlite-*.sqlite3"))
            target_path = Path(directory) / "existing.sqlite3"
            target_path.write_bytes(b"preserve this file")

            with self.assertRaisesMessage(CommandError, "refusing to overwrite"):
                call_command(
                    "restore_database_backup",
                    backup=str(backup_path),
                    target=str(target_path),
                )

            self.assertEqual(target_path.read_bytes(), b"preserve this file")

    def test_restore_rejects_non_sqlite_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "not-a-database.sql"
            backup_path.write_text("not a SQLite backup", encoding="utf-8")
            target_path = Path(directory) / "restored.sqlite3"

            with self.assertRaisesMessage(CommandError, "not a SQLite database"):
                call_command(
                    "restore_database_backup",
                    backup=str(backup_path),
                    target=str(target_path),
                )

            self.assertFalse(target_path.exists())


class MySQLBackupCommandTests(SimpleTestCase):
    def test_password_is_supplied_in_a_temporary_option_file(self):
        database = {
            "HOST": "db.example",
            "PORT": "3307",
            "USER": "backup-user",
            "PASSWORD": "test-secret",
            "NAME": "hms_db",
        }

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "backup.sql"

            def write_dump(command, check, env):
                option_file = Path(command[1].split("=", 1)[1])
                self.assertEqual(
                    option_file.read_text(encoding="utf-8"),
                    '[client]\npassword="test-secret"\n',
                )
                self.assertNotIn("test-secret", command)
                self.assertNotIn("MYSQL_PWD", env)
                result_file = next(
                    argument.split("=", 1)[1]
                    for argument in command
                    if argument.startswith("--result-file=")
                )
                Path(result_file).write_text("test dump", encoding="utf-8")

            with (
                patch(
                    "core.management.commands.backup_database.connection",
                    SimpleNamespace(settings_dict=database),
                ),
                patch(
                    "core.management.commands.backup_database.shutil.which",
                    return_value="mysqldump",
                ),
                patch(
                    "core.management.commands.backup_database.subprocess.run",
                    side_effect=write_dump,
                ) as run,
            ):
                BackupCommand._backup_mysql(destination)

            command = run.call_args.args[0]
            option_file = Path(command[1].split("=", 1)[1])
            self.assertFalse(option_file.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "test dump")
