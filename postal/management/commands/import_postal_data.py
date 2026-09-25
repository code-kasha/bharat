import csv
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from postal.importer import parse_csv, replace_dataset


class Command(BaseCommand):
    help = "Validate and atomically replace the postal directory from a CSV snapshot."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--source", required=True, help="Source URL or honest provenance label")
        parser.add_argument("--source-date", type=date.fromisoformat)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        source = options["source"].strip()
        if not source or len(source) > 500:
            raise CommandError("Source must contain 1–500 characters.")
        try:
            parsed = parse_csv(options["path"])
        except (OSError, UnicodeError, ValueError, csv.Error) as exc:
            raise CommandError(str(exc)) from exc
        if options["dry_run"]:
            action = "Validated (dry run)"
        else:
            changed = replace_dataset(parsed, source=source, source_date=options["source_date"])
            action = "Imported" if changed else "Unchanged"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}: {len(parsed.offices)} offices, {parsed.duplicates} duplicates, "
                f"0 rejected rows. SHA256 {parsed.checksum}"
            )
        )
