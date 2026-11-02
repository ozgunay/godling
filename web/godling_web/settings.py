"""Godling's public site: viewer accounts, credits and moderation in front of the viewer screen (ADR-012, ADR-013).

Accounts are django-allauth, set up as in AgentOp (C:/Work/agentop, config/base.py): sign in by email, username and
email and password to sign up, mandatory email verification, unique emails, no telling who is registered. The screen
and its API are apps/screen, which relays powers and notes to the guest panel (tools/guest_panel.py) on the account's
behalf. Everything a deployment changes comes from the environment (GODLING_*).
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # web/
REPO_DIR = BASE_DIR.parent
VIEWER_DIR = REPO_DIR / "world" / "viewer"  # the screen's page, served as it is

TESTING = "test" in sys.argv[1:2]
# Off unless asked for (GODLING_DEBUG=1, development only): debug pages show settings, and with no Stripe keys debug
# opens the test checkout, which credits packs for nothing (apps.credits.views).
DEBUG = os.environ.get("GODLING_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("GODLING_SECRET_KEY", "")
if not SECRET_KEY:
    if not (DEBUG or TESTING):
        raise RuntimeError("Set GODLING_SECRET_KEY: the site signs sessions with it.")
    SECRET_KEY = "dev-only-not-secret-godling"
ALLOWED_HOSTS = [h for h in os.environ.get("GODLING_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("GODLING_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",  # authentication, registration, email verification
    "allauth.account",  # email/password accounts + email confirmation
    "allauth.mfa",  # two-factor sign-in (an authenticator app, recovery codes): staff need it for the admin
    "apps.users",
    "apps.rules",
    "apps.credits",
    "apps.notes",
    "apps.screen",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # the admin's own files, served by the site itself
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # required by django-allauth
    "apps.users.middleware.AdminNeedsTwoFactor",  # staff set up two-factor sign-in before the admin opens
]

ROOT_URLCONF = "godling_web.urls"
WSGI_APPLICATION = "godling_web.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Postgres in production (deploy/docker-compose.yml, as AgentOp runs it); SQLite in development.
if os.environ.get("GODLING_DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["GODLING_DB_HOST"],
            "PORT": os.environ.get("GODLING_DB_PORT", "5432"),
            "NAME": os.environ.get("GODLING_DB_NAME", "godling"),
            "USER": os.environ.get("GODLING_DB_USER", "godling"),
            "PASSWORD": os.environ.get("GODLING_DB_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("GODLING_DB", str(BASE_DIR / "db.sqlite3")),
        }
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# One cache for every gunicorn worker and the Celery worker: an admin change clears the blocked words or the disposable
# domains for all of them, allauth's rate limits count across them, and the island's news is fetched once a second for
# every viewer (apps.screen.island). Redis in production (deploy/: GODLING_REDIS_URL); otherwise a table, made by
# migrate (rules 0003), which is enough for development and a small site.
REDIS_URL = os.environ.get("GODLING_REDIS_URL", "")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL,
                          "KEY_PREFIX": "godling"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "godling_cache"}}

# Celery (as AgentOp runs it): powers go to the island from a worker, never from a viewer's request, so a slow island
# holds no web thread (apps.screen.tasks). Without Redis, in development and tests, a task runs at once, in the request.
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_TASK_ALWAYS_EAGER = TESTING or not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True  # results live in the database (PowerCall)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
# The worker's own clock (deploy/: `worker --beat`): powers nobody will take are given up and refunded on the server,
# not only when their viewer's page asks (apps.screen.tasks.expire_stale_powers).
CELERY_BEAT_SCHEDULE = {"expire-stale-powers": {"task": "apps.screen.tasks.expire_stale_powers", "schedule": 60.0}}

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# django-allauth, as AgentOp has it (email-first authentication, registration, verification)
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",  # the admin
    "allauth.account.auth_backends.AuthenticationBackend",  # sign-in by email
]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # no signing in until the email is confirmed
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_PREVENT_ENUMERATION = True  # don't tell who is registered
ACCOUNT_ADAPTER = "apps.users.adapter.AccountAdapter"  # reserved usernames, disposable domains
ACCOUNT_LOGOUT_ON_GET = False  # sign out only by POST
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Godling] "
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
# The proxies in front of the site (deploy/: Caddy, so 1). allauth then reads the viewer's address from
# X-Forwarded-For; without it every sign-in comes from Caddy's address and all viewers share one rate limit.
ALLAUTH_TRUSTED_PROXY_COUNT = int(os.environ.get("GODLING_TRUSTED_PROXIES", "0"))
if TESTING:
    ACCOUNT_RATE_LIMITS = {}  # repeated sign-ups and sign-ins in tests are not abuse
# Two-factor sign-in (allauth.mfa): an authenticator app's codes, and recovery codes for a lost phone. Staff must have
# it to open the admin (apps.users.middleware); viewers may turn it on for themselves at /accounts/2fa/.
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Godling"
GODLING_ADMIN_TWO_FACTOR = os.environ.get("GODLING_ADMIN_TWO_FACTOR", "1") == "1"

# Email: printed to the console in development; SMTP when GODLING_EMAIL_HOST is set.
DEFAULT_FROM_EMAIL = os.environ.get("GODLING_FROM_EMAIL", "Godling <noreply@localhost>")
if os.environ.get("GODLING_EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["GODLING_EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("GODLING_EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("GODLING_EMAIL_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("GODLING_EMAIL_PASSWORD", "")
    EMAIL_USE_TLS = os.environ.get("GODLING_EMAIL_TLS", "1") == "1"
    EMAIL_USE_SSL = os.environ.get("GODLING_EMAIL_SSL", "0") == "1"  # port 465 providers
    EMAIL_TIMEOUT = 20
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# The guest panel this site relays to, and the key it asks for (tools/guest_panel.py --key). The panel trusts the
# names and limits this site sends, so it must not be reachable from outside.
GODLING_PANEL_URL = os.environ.get("GODLING_PANEL_URL", "http://127.0.0.1:8081").rstrip("/")
GODLING_PANEL_KEY = os.environ.get("GODLING_PANEL_KEY", "")

# Credits (ADR-013). Prices, credit packs and the site's rules (welcome credits, test mode, pace, note length,
# reports) are rows the admin edits (apps.credits, apps.rules); these are what a deployment sets.
GODLING_CURRENCY = os.environ.get("GODLING_CURRENCY", "eur")
GODLING_STRIPE_SECRET_KEY = os.environ.get("GODLING_STRIPE_SECRET_KEY", "")
GODLING_STRIPE_WEBHOOK_SECRET = os.environ.get("GODLING_STRIPE_WEBHOOK_SECRET", "")
# The island as the public reaches it, on its own origin (ADR-014), e.g.
# https://island.godling.example/island?spectator_token=… (no slash after /island: that is where the world serves
# its page under a base path); empty, the panel's own.
GODLING_VIEW_URL = os.environ.get("GODLING_VIEW_URL", "")
# The live run, for the admin's log viewer (apps.users.log_views).
GODLING_RUN_DIR = os.environ.get("GODLING_RUN_DIR", "")

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or TESTING
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Behind Caddy in production (deploy/Caddyfile), which terminates HTTPS.
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # A year, the island's subdomain included (Caddy serves both over HTTPS). Not on the preload list: that cannot
    # be taken back quickly.
    SECURE_HSTS_SECONDS = int(os.environ.get("GODLING_HSTS_SECONDS", str(365 * 24 * 3600)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("GODLING_HSTS_SUBDOMAINS", "1") == "1"
    # check --deploy, answered: Caddy sends plain HTTP to HTTPS itself (W008), and the preload list is left alone
    # on purpose (W021, above).
    SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W021"]
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
