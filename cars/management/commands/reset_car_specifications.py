from django.core.cache import cache
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cars.models import CarSpecification
from cars.services.excel_importer import import_cars_from_excel


class Command(BaseCommand):
    help = "Replace all CarSpecification rows from an Excel file without changing schema or search logic."

    def add_arguments(self, parser):
        parser.add_argument("excel_path", help="Path to the Excel file to import.")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm deleting existing CarSpecification rows before import.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("This deletes CarSpecification rows. Re-run with --yes to confirm.")

        excel_path = options["excel_path"]

        with transaction.atomic():
            deleted_count, _ = CarSpecification.objects.all().delete()
            with open(excel_path, "rb") as raw_file:
                excel_file = File(raw_file, name=excel_path)
                result = import_cars_from_excel(excel_file)
            if not result.get("success") or result.get("failed"):
                raise CommandError(
                    "Import failed after delete; transaction rolled back. "
                    f"Result: {result}"
                )

        cache.delete("lookup_data")

        self.stdout.write(self.style.SUCCESS(
            f"Replaced CarSpecification data: deleted={deleted_count}, "
            f"created={result['created']}, updated={result['updated']}, "
            f"total_rows={result['total_rows']}"
        ))
