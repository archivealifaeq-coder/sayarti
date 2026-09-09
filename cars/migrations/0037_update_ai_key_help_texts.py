from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0036_marketcarprice_trim'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='deepseek_api_key',
            field=models.CharField(blank=True, help_text='مفتاح API من platform.deepseek.com — يستخدم كخيار ثانٍ في شكد فلوسك بعد قاعدة الأسعار', max_length=100, verbose_name='مفتاح DeepSeek API (الأساسي)'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='gemini_api_key',
            field=models.CharField(blank=True, help_text='من aistudio.google.com — احتياطي في شكد فلوسك إذا لم تجد القاعدة نتيجة وتعطل DeepSeek', max_length=200, verbose_name='مفتاح Gemini (احتياطي)'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='groq_api_key',
            field=models.CharField(blank=True, help_text='من console.groq.com — يستخدم في ميزات البحث الأخرى، وليس fallback شكد فلوسك الحالي', max_length=200, verbose_name='مفتاح Groq (حائط صد أخير)'),
        ),
    ]
