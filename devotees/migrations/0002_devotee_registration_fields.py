import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("volunteers", "0001_initial"),
        ("devotees", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devotee",
            name="full_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="devotee",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="devotee",
            name="middle_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="devotee",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="devotee",
            name="whatsapp",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="devotee",
            name="address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="devotee",
            name="pincode",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="devotee",
            name="pan_number",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="devotee",
            name="referred_by_volunteer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="referred_devotees",
                to="volunteers.volunteer",
            ),
        ),
        migrations.AddIndex(
            model_name="devotee",
            index=models.Index(fields=["mobile"], name="devotees_de_mobile_2f6b41_idx"),
        ),
    ]