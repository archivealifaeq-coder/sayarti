# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0018_backfill_norm_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='ga4_id',
            field=models.CharField(blank=True, max_length=20, verbose_name='معرف تحليلات Google (GA4)', help_text='من analytics.google.com — مثال: G-ABC123XYZ — يسجّل زوار الموقع والصفحات والدول'),
        ),
    ]