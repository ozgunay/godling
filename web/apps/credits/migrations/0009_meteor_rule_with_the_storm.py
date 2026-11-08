"""The Storm can hit Godling too (ADR-023), so the Meteor's rule no longer says it is the only power that can. The
screen shows the row's words, not its own, so the row is changed; only a rule still as 0004 seeded it: words written in
the admin stay."""
from django.db import migrations

OLD = "The only power that can hit Godling or its walls · one a minute · never while Godling is weak"
NEW = "Can hit Godling and its walls · one a minute · never while Godling is weak"


def forward(apps, schema_editor):
    apps.get_model("credits", "Power").objects.filter(key="Meteor", rule=OLD).update(rule=NEW)


def backward(apps, schema_editor):
    apps.get_model("credits", "Power").objects.filter(key="Meteor", rule=NEW).update(rule=OLD)


class Migration(migrations.Migration):
    dependencies = [("credits", "0008_the_storm")]
    operations = [migrations.RunPython(forward, backward)]
