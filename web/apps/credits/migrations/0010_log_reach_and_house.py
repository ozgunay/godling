"""A log aimed past Godling's reach lands at its edge instead of being refused, and lands beside Godling's house, never
on it (ADR-029). The screen shows the row's words, so the Log's row says so: its description only if still as 0004
seeded it, and its rule only if it has none; words written in the admin stay."""
from django.db import migrations

OLD = "A log beam drops where you aim. Aimed at Godling, it lands at its feet; it never lands on its walls."
NEW = "A log beam drops where you aim, beside Godling's house and never on it. Aimed at Godling, it lands at its feet."
RULE = "Within 60 of Godling: an aim further out lands at the edge"  # main.lua sky.aim.REACH


def forward(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    Power.objects.filter(key="Log", description=OLD).update(description=NEW)
    Power.objects.filter(key="Log", rule="").update(rule=RULE)


def backward(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    Power.objects.filter(key="Log", description=NEW).update(description=OLD)
    Power.objects.filter(key="Log", rule=RULE).update(rule="")


class Migration(migrations.Migration):
    dependencies = [("credits", "0009_meteor_rule_with_the_storm")]
    operations = [migrations.RunPython(forward, backward)]
