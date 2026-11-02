"""The cache table every gunicorn worker shares (settings CACHES), made with migrate so no extra step is needed."""
from django.core.management import call_command
from django.db import migrations


def make_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("rules", "0002_seed_rules_and_words")]
    operations = [migrations.RunPython(make_cache_table, migrations.RunPython.noop)]
