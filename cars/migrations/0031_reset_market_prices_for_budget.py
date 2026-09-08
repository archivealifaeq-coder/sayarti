from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0030_marketcarprice_brand_en_marketcarprice_model_en_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MarketCarPrice',
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='exchange_rate_iqd_per_usd',
            field=models.PositiveIntegerField(default=1500, help_text='سعر السوق الموازي: كم دينار عراقي لكل 1 دولار. يُستخدم لحساب السعر الناقص عند استيراد أسعار شكد فلوسك.', verbose_name='سعر صرف الدولار مقابل الدينار'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='exchange_rate_source',
            field=models.CharField(blank=True, max_length=120, verbose_name='مصدر سعر الصرف'),
        ),
        migrations.CreateModel(
            name='MarketCarPrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180, verbose_name='اسم السيارة الكامل')),
                ('brand', models.CharField(max_length=100, verbose_name='الماركة عربي')),
                ('brand_en', models.CharField(blank=True, max_length=100, verbose_name='الماركة إنجليزي')),
                ('model', models.CharField(max_length=100, verbose_name='الموديل عربي')),
                ('model_en', models.CharField(blank=True, max_length=100, verbose_name='الموديل إنجليزي')),
                ('brand_norm', models.CharField(blank=True, db_index=True, default='', max_length=100)),
                ('model_norm', models.CharField(blank=True, db_index=True, default='', max_length=100)),
                ('year', models.IntegerField(validators=[MinValueValidator(1990), MaxValueValidator(2099)], verbose_name='السنة')),
                ('origin', models.CharField(choices=[('all', 'عام'), ('japanese', 'ياباني'), ('korean', 'كوري'), ('chinese', 'صيني'), ('american', 'أمريكي'), ('german', 'ألماني'), ('european', 'أوروبي'), ('iranian', 'إيراني')], db_index=True, default='all', max_length=20, verbose_name='المنشأ')),
                ('body_type', models.CharField(choices=[('all', 'عام'), ('sedan', 'سيدان'), ('suv', 'SUV / عائلي'), ('pickup', 'بيكب'), ('hatchback', 'هاتشباك'), ('van', 'فان'), ('coupe', 'كوبيه')], db_index=True, default='all', max_length=20, verbose_name='نوع الجسم')),
                ('condition', models.CharField(choices=[('used', 'مستعمل'), ('new', 'جديد')], db_index=True, default='used', max_length=10, verbose_name='الحالة')),
                ('price_iqd', models.PositiveBigIntegerField(db_index=True, verbose_name='السعر بالدينار')),
                ('price_usd', models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='السعر بالدولار')),
                ('engine', models.CharField(blank=True, max_length=80, verbose_name='المحرك')),
                ('fuel_economy', models.CharField(blank=True, default='جيد', max_length=50, verbose_name='صرف الوقود')),
                ('maintenance', models.CharField(blank=True, default='متوسطة', max_length=50, verbose_name='الصيانة')),
                ('pros', models.CharField(blank=True, max_length=240, verbose_name='سبب الترشيح')),
                ('source_name', models.CharField(blank=True, max_length=120, verbose_name='مصدر السعر')),
                ('source_url', models.URLField(blank=True, verbose_name='رابط المصدر')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='مفعل')),
                ('confidence', models.PositiveSmallIntegerField(default=80, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='درجة الثقة')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='آخر تحديث')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')),
            ],
            options={
                'verbose_name': 'سعر سيارة في السوق',
                'verbose_name_plural': 'أسعار السيارات في السوق',
                'ordering': ['-year', 'price_iqd', '-confidence', 'brand', 'model'],
                'indexes': [
                    models.Index(fields=['condition', 'origin', 'body_type', 'price_iqd'], name='cars_market_conditi_24e53a_idx'),
                    models.Index(fields=['condition', 'origin', 'body_type', 'price_usd'], name='cars_market_conditi_d29ab7_idx'),
                    models.Index(fields=['brand_norm', 'model_norm'], name='cars_market_brand_n_cec00c_idx'),
                ],
            },
        ),
    ]
