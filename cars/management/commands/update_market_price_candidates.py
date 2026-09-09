from django.core.management.base import BaseCommand, CommandError

from cars.services.online_market_scraper import BRANDS, run_online_update


class Command(BaseCommand):
    help = 'جلب أسعار سيارات من الإنترنت وحفظها في جدول المراجعة فقط.'

    def add_arguments(self, parser):
        parser.add_argument('--source', default='opensooq', choices=['opensooq'])
        parser.add_argument('--brands', nargs='*', default=['toyota', 'hyundai', 'kia', 'nissan', 'chevrolet'])
        parser.add_argument('--max-pages', type=int, default=2)
        parser.add_argument('--optional-fields', nargs='*', default=['trim', 'engine', 'price_usd', 'body_type', 'pros'])

    def handle(self, *args, **options):
        unknown = [brand for brand in options['brands'] if brand not in BRANDS]
        if unknown:
            raise CommandError('ماركات غير مدعومة: ' + ', '.join(unknown))
        if options['max_pages'] < 1 or options['max_pages'] > 10:
            raise CommandError('--max-pages يجب أن يكون بين 1 و 10')

        summary = run_online_update(
            source=options['source'],
            brands=options['brands'],
            max_pages=options['max_pages'],
            optional_fields=options['optional_fields'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'تم الجلب: {summary.fetched} | جديد: {summary.saved} | محدث: {summary.updated} | متروك: {summary.skipped} | فشل: {summary.failed}'
        ))
