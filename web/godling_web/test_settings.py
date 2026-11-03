"""The settings a deployment gives through the environment (GODLING_*): each branch, read afresh from settings.py."""
import os
import runpy
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SETTINGS = Path(__file__).resolve().parent / "settings.py"


def settings_with(command="runserver", **env):
    """settings.py as `manage.py <command>` reads it, with only these GODLING_* variables set."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GODLING_")}
    with mock.patch.dict(os.environ, {**clean, **env}, clear=True), \
            mock.patch.object(sys, "argv", ["manage.py", command]):
        return runpy.run_path(str(SETTINGS))


class SettingsTests(SimpleTestCase):
    def test_development(self):
        s = settings_with(GODLING_DEBUG="1")
        self.assertTrue(s["DEBUG"])
        self.assertEqual(s["SECRET_KEY"], "dev-only-not-secret-godling")
        self.assertEqual(s["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(s["CACHES"]["default"]["BACKEND"], "django.core.cache.backends.db.DatabaseCache")
        self.assertEqual((s["CELERY_BROKER_URL"], s["CELERY_TASK_ALWAYS_EAGER"]), ("memory://", True))
        self.assertEqual(s["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend")
        self.assertEqual(s["STORAGES"]["staticfiles"]["BACKEND"],
                         "django.contrib.staticfiles.storage.StaticFilesStorage")
        self.assertFalse(s["SESSION_COOKIE_SECURE"])
        self.assertNotIn("ACCOUNT_RATE_LIMITS", s)

    def test_tests_need_no_secret_and_no_rate_limits(self):
        s = settings_with("test")
        self.assertFalse(s["DEBUG"])
        self.assertEqual(s["SECRET_KEY"], "dev-only-not-secret-godling")
        self.assertEqual(s["ACCOUNT_RATE_LIMITS"], {})

    def test_production_needs_a_secret(self):
        with self.assertRaisesRegex(RuntimeError, "Set GODLING_SECRET_KEY"):
            settings_with()  # debug is off unless asked for

    def test_production(self):
        s = settings_with(GODLING_SECRET_KEY="s3cret", GODLING_DB_HOST="db", GODLING_DB_NAME="g",
                          GODLING_REDIS_URL="redis://redis:6379/0", GODLING_EMAIL_HOST="smtp.example",
                          GODLING_EMAIL_PORT="465", GODLING_EMAIL_SSL="1", GODLING_EMAIL_TLS="0",
                          GODLING_HOSTS="godling.example,", GODLING_HSTS_SECONDS="60", GODLING_TRUSTED_PROXIES="1",
                          GODLING_PANEL_URL="http://panel:8081/", GODLING_ADMIN_TWO_FACTOR="0")
        self.assertFalse(s["DEBUG"])
        self.assertEqual(s["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(s["DATABASES"]["default"]["NAME"], "g")
        self.assertEqual(s["CACHES"]["default"], {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                                                  "LOCATION": "redis://redis:6379/0", "KEY_PREFIX": "godling"})
        # Powers go to the island from the worker, never from a viewer's request (apps.screen.tasks).
        self.assertEqual((s["CELERY_BROKER_URL"], s["CELERY_TASK_ALWAYS_EAGER"]), ("redis://redis:6379/0", False))
        self.assertEqual((s["EMAIL_HOST"], s["EMAIL_PORT"], s["EMAIL_USE_SSL"], s["EMAIL_USE_TLS"]),
                         ("smtp.example", 465, True, False))
        self.assertEqual(s["ALLOWED_HOSTS"], ["godling.example"])
        self.assertEqual(s["SECURE_HSTS_SECONDS"], 60)
        self.assertEqual(s["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(s["ALLAUTH_TRUSTED_PROXY_COUNT"], 1)
        self.assertEqual(s["GODLING_PANEL_URL"], "http://panel:8081")
        self.assertEqual(s["STORAGES"]["staticfiles"]["BACKEND"],
                         "whitenoise.storage.CompressedManifestStaticFilesStorage")
        self.assertTrue(s["CSRF_COOKIE_SECURE"])
        self.assertFalse(s["GODLING_ADMIN_TWO_FACTOR"])

    def test_the_wsgi_application_and_the_worker(self):
        from godling_web import celery, wsgi
        self.assertTrue(callable(wsgi.application))
        self.assertEqual(celery.app.main, "godling_web")
