"""What came before ADR-014, in its terms: the welcome gifts already given, one per inbox (the first account of each
inbox keeps its place), and each paid pack's credits as granted, so reconciling it later moves nothing it already did."""
from django.db import migrations
from django.db.models import F


def fill(apps, schema_editor):
    Entry = apps.get_model("credits", "Entry")
    Welcome = apps.get_model("credits", "Welcome")
    User = apps.get_model("users", "User")
    Payment = apps.get_model("credits", "Payment")
    seen = set(Welcome.objects.values_list("email_key", flat=True))
    for user_id in Entry.objects.filter(kind="welcome").order_by("created", "id").values_list("user_id", flat=True):
        key = User.objects.filter(pk=user_id).values_list("email_key", flat=True).first()
        if key and key not in seen:
            Welcome.objects.create(email_key=key, user_id=user_id)
            seen.add(key)
    Payment.objects.filter(status="paid").update(granted=F("credits"))


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0006_refunds_disputes_and_queued_powers'),
        ('users', '0004_user_email_key'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
