from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0035_delete_ai_budget_market_prices'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketcarprice',
            name='trim',
            field=models.CharField(blank=True, max_length=80, verbose_name='الفئة / الكلاس'),
        ),
    ]
