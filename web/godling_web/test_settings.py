"""The settings a deployment gives through the environment (GODLING_*): each branch, read afresh from settings.py."""
import os
import runpy
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SETTINGS = Path(__file__).resolve().parent / "settings.py"


def settings_with(**env):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GODLING_")}
    with mock.patch.dict(os.environ, {**clean, **env}, clear=True):
        return runpy.run_path(str(SETTINGS))


class SettingsTests(SimpleTestCase):
    def test_development_defaults(self):
        s = settings_with()
        self.assertTrue(s["DEBUG"])
        self.assertEqual(s["SECRET_KEY"], "dev-only-not-secret-godling")
        self.assertEqual(s["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(s["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend")
        self.assertFalse(s["SESSION_COOKIE_SECURE"])

    def test_production_needs_a_secret(self):
        with self.assertRaisesRegex(RuntimeError, "Set GODLING_SECRET_KEY"):
            settings_with(GODLING_DEBUG="0")

    def test_production(self):
        s = settings_with(GODLING_DEBUG="0", GODLING_SECRET_KEY="s3cret", GODLING_DB_HOST="db", GODLING_DB_NAME="g",
                          GODLING_EMAIL_HOST="smtp.example", GODLING_EMAIL_PORT="465", GODLING_EMAIL_SSL="1",
                          GODLING_EMAIL_TLS="0", GODLING_HOSTS="godling.example,", GODLING_HSTS_SECONDS="60",
                          GODLING_TRUSTED_PROXIES="1", GODLING_PANEL_URL="http://panel:8081/")
        self.assertFalse(s["DEBUG"])
        self.assertEqual(s["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(s["DATABASES"]["default"]["NAME"], "g")
        self.assertEqual((s["EMAIL_HOST"], s["EMAIL_PORT"], s["EMAIL_USE_SSL"], s["EMAIL_USE_TLS"]),
                         ("smtp.example", 465, True, False))
        self.assertEqual(s["ALLOWED_HOSTS"], ["godling.example"])
        self.assertEqual(s["SECURE_HSTS_SECONDS"], 60)
        self.assertEqual(s["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(s["ALLAUTH_TRUSTED_PROXY_COUNT"], 1)
        self.assertEqual(s["GODLING_PANEL_URL"], "http://panel:8081")
        self.assertTrue(s["CSRF_COOKIE_SECURE"])

    def test_the_wsgi_application(self):
        from godling_web import wsgi
        self.assertTrue(callable(wsgi.application))
