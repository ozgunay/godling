"""The site rules as they were in settings, and the blocked words as they were in code (the guest panel's note words
and the username words), so the admin starts from what the site did before."""
from django.db import migrations

WORDS = {
    "fuck": "both", "shit": "both", "cunt": "both", "bitch": "both", "whore": "both", "nigg": "both",
    "retard": "both", "fag": "notes", "rape": "notes", "kill yourself": "notes", "nazi": "usernames",
    "hitler": "usernames",
}  # as apps/rules/words.py SEED


def seed(apps, schema_editor):
    apps.get_model("rules", "Rules").objects.get_or_create(pk=1)
    BlockedWord = apps.get_model("rules", "BlockedWord")
    for word, applies in WORDS.items():
        BlockedWord.objects.get_or_create(word=word, defaults={"applies_to": applies})


class Migration(migrations.Migration):
    dependencies = [("rules", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
