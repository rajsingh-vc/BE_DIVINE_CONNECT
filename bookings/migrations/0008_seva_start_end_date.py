from django.db import migrations, models


def backfill_start_end_date(apps, schema_editor):
    """Existing Sevas only ever had a single `seva_date`. Treat that as both
    the start and end date so old records keep working after this migration
    (they'll still need an admin to set proper start/end DATES to remain
    bookable — see Sec.15)."""
    Seva = apps.get_model("bookings", "Seva")
    for seva in Seva.objects.filter(seva_date__isnull=False):
        seva.start_date = seva.seva_date
        seva.end_date = seva.seva_date
        seva.save(update_fields=["start_date", "end_date"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0007_seva_end_time_seva_seva_date_seva_start_time"),
    ]

    operations = [
        migrations.RenameField(
            model_name="seva",
            old_name="seva_date",
            new_name="start_date",
        ),
        migrations.AddField(
            model_name="seva",
            name="seva_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="seva",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="seva",
            index=models.Index(fields=["start_date"], name="bookings_se_start_d_idx"),
        ),
        migrations.AddIndex(
            model_name="seva",
            index=models.Index(fields=["is_active"], name="bookings_se_is_acti_idx"),
        ),
        migrations.RunPython(backfill_start_end_date, noop_reverse),
    ]