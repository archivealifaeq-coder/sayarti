from django.db import migrations


def delete_ai_budget_prices(apps, schema_editor):
    MarketCarPrice = apps.get_model('cars', 'MarketCarPrice')
    MarketCarPrice.objects.filter(source_name__in=[
        'DeepSeek - شكد فلوسك',
        'Gemini - شكد فلوسك',
        'Groq - شكد فلوسك',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0034_alter_sitesettings_groq_api_key'),
    ]

    operations = [
        migrations.RunPython(delete_ai_budget_prices, migrations.RunPython.noop),
    ]
