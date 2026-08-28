# -*- coding: utf-8 -*-
from django.db import migrations
from cars.services.textnorm import fold_ar, fold_engine


def backfill(apps, schema_editor):
    CarSpecification = apps.get_model('cars', 'CarSpecification')
    for car in CarSpecification.objects.all().iterator():
        car.brand_norm = fold_ar(car.brand_ar)
        car.model_norm = fold_ar(car.model_ar)
        car.engine_norm = fold_engine(car.engine)
        car.save(update_fields=['brand_norm', 'model_norm', 'engine_norm'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0017_carspecification_brand_norm_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]