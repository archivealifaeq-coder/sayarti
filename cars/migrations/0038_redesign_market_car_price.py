from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def copy_old_market_price_data(apps, schema_editor):
    MarketCarPrice = apps.get_model('cars', 'MarketCarPrice')
    for row in MarketCarPrice.objects.all().iterator():
        row.spec_region = 'all'
        row.price_min_iqd = row.price_iqd or 1
        row.price_max_iqd = row.price_iqd or 1
        row.description = (row.pros or '')[:240]
        row.save(update_fields=['spec_region', 'price_min_iqd', 'price_max_iqd', 'description'])


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0037_update_ai_key_help_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketcarprice',
            name='spec_region',
            field=models.CharField(choices=[('all', 'عام'), ('american', 'أمريكي'), ('gcc', 'خليجي'), ('chinese', 'صيني'), ('european', 'أوروبي'), ('iraqi', 'عراقي / وكيل محلي')], db_index=True, default='all', max_length=20, verbose_name='المواصفات'),
        ),
        migrations.AddField(
            model_name='marketcarprice',
            name='price_min_iqd',
            field=models.PositiveBigIntegerField(db_index=True, default=1, verbose_name='السعر من (دينار)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='marketcarprice',
            name='price_max_iqd',
            field=models.PositiveBigIntegerField(db_index=True, default=1, verbose_name='السعر إلى (دينار)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='marketcarprice',
            name='description',
            field=models.CharField(blank=True, max_length=240, verbose_name='الوصف'),
        ),
        migrations.RunPython(copy_old_market_price_data, migrations.RunPython.noop),
        migrations.RemoveIndex(model_name='marketcarprice', name='cars_market_conditi_24e53a_idx'),
        migrations.RemoveIndex(model_name='marketcarprice', name='cars_market_conditi_d29ab7_idx'),
        migrations.RemoveField(model_name='marketcarprice', name='name'),
        migrations.RemoveField(model_name='marketcarprice', name='origin'),
        migrations.RemoveField(model_name='marketcarprice', name='condition'),
        migrations.RemoveField(model_name='marketcarprice', name='price_iqd'),
        migrations.RemoveField(model_name='marketcarprice', name='price_usd'),
        migrations.RemoveField(model_name='marketcarprice', name='engine'),
        migrations.RemoveField(model_name='marketcarprice', name='fuel_economy'),
        migrations.RemoveField(model_name='marketcarprice', name='maintenance'),
        migrations.RemoveField(model_name='marketcarprice', name='pros'),
        migrations.RemoveField(model_name='marketcarprice', name='source_name'),
        migrations.RemoveField(model_name='marketcarprice', name='source_url'),
        migrations.RemoveField(model_name='marketcarprice', name='is_active'),
        migrations.RemoveField(model_name='marketcarprice', name='confidence'),
        migrations.AlterField(
            model_name='marketcarprice',
            name='model',
            field=models.CharField(max_length=100, verbose_name='النوع عربي'),
        ),
        migrations.AlterField(
            model_name='marketcarprice',
            name='model_en',
            field=models.CharField(blank=True, max_length=100, verbose_name='النوع إنجليزي'),
        ),
        migrations.AlterField(
            model_name='marketcarprice',
            name='body_type',
            field=models.CharField(choices=[('all', 'الكل'), ('sedan', 'سيدان'), ('suv', 'SUV'), ('pickup', 'بيكب'), ('hatchback', 'هاتشباك'), ('van', 'فان'), ('coupe', 'كوبيه')], db_index=True, default='all', max_length=20, verbose_name='نوع الجسم'),
        ),
        migrations.AlterModelOptions(
            name='marketcarprice',
            options={'ordering': ['-year', 'price_min_iqd', 'brand', 'model'], 'verbose_name': 'سعر سيارة في السوق', 'verbose_name_plural': 'أسعار السيارات في السوق'},
        ),
        migrations.AddIndex(
            model_name='marketcarprice',
            index=models.Index(fields=['spec_region', 'body_type', 'price_min_iqd', 'price_max_iqd'], name='cars_market_spec_re_00ae2d_idx'),
        ),
    ]
