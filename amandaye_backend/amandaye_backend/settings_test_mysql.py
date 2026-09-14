"""Opt-in isolated MySQL test database. Never reuse application DB credentials."""
import os
from django.core.exceptions import ImproperlyConfigured
from .settings_test import *  # noqa: F403

test_database = os.environ.get("TEST_MYSQL_DATABASE", "test_amandaye_security")
if not test_database.startswith("test_amandaye_"):
    raise ImproperlyConfigured("TEST_MYSQL_DATABASE must start with test_amandaye_.")
test_user = os.environ.get("TEST_MYSQL_USER", "")
test_password = os.environ.get("TEST_MYSQL_PASSWORD", "")
if not test_user or not test_password or test_user.lower() in {"root", "amandaye_app"}:
    raise ImproperlyConfigured("Configure a dedicated TEST_MYSQL_USER and TEST_MYSQL_PASSWORD.")

DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": test_database,
    "USER": test_user,
    "PASSWORD": test_password,
    "HOST": os.environ.get("TEST_MYSQL_HOST", "127.0.0.1"),
    "PORT": os.environ.get("TEST_MYSQL_PORT", "3306"),
    "CONN_MAX_AGE": 0,
    "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    "TEST": {"NAME": test_database},
}}
