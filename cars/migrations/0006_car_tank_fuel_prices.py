from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0005_remove_sitesettings_deepseek_api_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='carspecification',
            name='tank',
            field=models.DecimalField(blank=True, decimal_places=1, help_text='مثال: 60، ويستخدم في حاسبة الأوكتان عند اختيار السيارة', max_digits=5, null=True, verbose_name='سعة خزان الوقود (لتر)'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='premium_fuel_price_iqd',
            field=models.PositiveIntegerField(default=0, help_text='مثال: 850. اتركه 0 لإخفاء حساب تكلفة التفويلة.', verbose_name='سعر لتر البنزين المحسن بالدينار'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='regular_fuel_price_iqd',
            field=models.PositiveIntegerField(default=0, help_text='مثال: 450. اتركه 0 لإخفاء حساب تكلفة التفويلة.', verbose_name='سعر لتر البنزين العادي بالدينار'),
        ),
    ]
