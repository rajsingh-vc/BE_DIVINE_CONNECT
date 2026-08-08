from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devotees', '0001_initial'),
        ('donations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='donor_address',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='donation',
            name='donor_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='donation',
            name='donor_mobile',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='donation',
            name='donor_pan',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='donation',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='donation',
            name='payment_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='donation',
            name='platform_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='donation',
            name='razorpay_order_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='donation',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='donation',
            name='razorpay_signature',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='donation',
            name='receipt_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='donation',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='donation',
            name='want_80g_receipt',
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name='donation',
            index=models.Index(fields=['payment_status'], name='donations_d_payment_453297_idx'),
        ),
    ]