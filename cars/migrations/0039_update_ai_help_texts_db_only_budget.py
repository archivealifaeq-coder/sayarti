from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0038_redesign_market_car_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='deepseek_api_key',
            field=models.CharField(blank=True, help_text='مفتاح API من platform.deepseek.com — يستخدم في ميزات البحث الأخرى فقط، ولا يُستخدم في شكد فلوسك', max_length=100, verbose_name='مفتاح DeepSeek API (الأساسي)'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='gemini_api_key',
            field=models.CharField(blank=True, help_text='من aistudio.google.com — يستخدم في ميزات البحث الأخرى فقط، ولا يُستخدم في شكد فلوسك', max_length=200, verbose_name='مفتاح Gemini (احتياطي)'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='groq_api_key',
            field=models.CharField(blank=True, help_text='من console.groq.com — يستخدم في ميزات البحث الأخرى فقط، ولا يُستخدم في شكد فلوسك', max_length=200, verbose_name='مفتاح Groq (حائط صد أخير)'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='exchange_rate_iqd_per_usd',
            field=models.PositiveIntegerField(default=1500, help_text='سعر السوق الموازي: كم دينار عراقي لكل 1 دولار. شكد فلوسك يعتمد الدينار في الجدول والاستيراد.', verbose_name='سعر صرف الدولار مقابل الدينار'),
        ),
    ]
