"""New accounts get 600 free credits, not 20 (the user's choice, 2026-11-09). The default changes, and so does the
site's own row, but only while it still says 20: a number set in the admin stays. Accounts welcomed already keep what
they got."""
from django.db import migrations, models

OLD, NEW = 20, 600


def forward(apps, schema_editor):
    apps.get_model("rules", "Rules").objects.filter(pk=1, welcome_credits=OLD).update(welcome_credits=NEW)


def backward(apps, schema_editor):
    apps.get_model("rules", "Rules").objects.filter(pk=1, welcome_credits=NEW).update(welcome_credits=OLD)


class Migration(migrations.Migration):
    dependencies = [("rules", "0005_feedback_rules")]
    operations = [
        migrations.AlterField(
            model_name="rules",
            name="welcome_credits",
            field=models.PositiveIntegerField(default=600, help_text="Free credits a new account gets on confirming its email, once per inbox (the user's choice: 600). A change counts for accounts confirmed from then on; those already welcomed keep what they got. 0 gives none."),
        ),
        migrations.RunPython(forward, backward),
    ]
