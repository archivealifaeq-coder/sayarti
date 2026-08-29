# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0019_sitesettings_ga4'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='ga4_property_id',
            field=models.CharField(blank=True, max_length=30, verbose_name='معرف الخاصية (Property ID)', help_text='من GA4 Admin → Property settings — مثال: 15522423744'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='ga_service_account_json',
            field=models.TextField(blank=True, verbose_name='مفتاح الخدمة (Service Account JSON)', help_text='الصق محتوى ملف JSON لخدمة الحساب بعد تفعيل Analytics Data API — يسمح بعرض عدد الزوار في لوحة الإدارة'),
        ),
    ]