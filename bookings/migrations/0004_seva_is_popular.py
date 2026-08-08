from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0003_booking_payment_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='seva',
            name='is_popular',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='seva',
            index=models.Index(fields=['is_popular'], name='bookings_se_is_popu_idx'),
        ),
    ]
