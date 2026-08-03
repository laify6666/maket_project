"""Portable launcher used by the PyInstaller build."""

import os
import sys
from pathlib import Path


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main():
    base = app_dir()
    if getattr(sys, "frozen", False):
        os.environ.setdefault(
            "DJANGO_SECRET_KEY", "portable-secret-change-before-production"
        )
        os.environ["DB_NAME"] = str(base / "db.sqlite3")
        os.environ["DJANGO_MEDIA_ROOT"] = str(base / "media")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shengcheng.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "migrate", "--noinput"])
    execute_from_command_line(["manage.py", "seed_demo"])
    execute_from_command_line(["manage.py", "runserver", "127.0.0.1:8000", "--noreload"])


if __name__ == "__main__":
    main()
