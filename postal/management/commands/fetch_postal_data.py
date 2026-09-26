import os

from django.core.management.base import BaseCommand, CommandError

from postal.importer import (
    API_ROOT,
    DEFAULT_RESOURCE,
    ImportFailure,
    fetch_snapshot,
    parse_records,
    replace_dataset,
)


class Command(BaseCommand):
    help = "Download the official data.gov.in PIN directory and atomically replace the database."

    def add_arguments(self, parser):
        parser.add_argument("--resource", default=DEFAULT_RESOURCE, help="OGD resource ID")
        parser.add_argument("--page-size", type=int, default=1000)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        # Read from the environment so the key stays out of shell history and process lists.
        api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
        if not api_key:
            raise CommandError("Set DATA_GOV_IN_API_KEY to your data.gov.in API key.")
        if not 1 <= options["page_size"] <= 10000:
            raise CommandError("Page size must be between 1 and 10000.")
        source = f"{API_ROOT}{options['resource']}"
        try:
            snapshot = fetch_snapshot(api_key, options["resource"], page_size=options["page_size"])
            parsed = parse_records(snapshot.records, source_date=snapshot.source_date)
        except ImportFailure as exc:
            raise CommandError(str(exc)) from exc
        if options["dry_run"]:
            action = "Validated (dry run)"
        else:
            action = "Imported" if replace_dataset(parsed, source=source) else "Unchanged"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}: {len(parsed.offices)} offices, {parsed.duplicates} duplicates, "
                f"{parsed.repeated_identities} offices listed more than once (kept), "
                f"0 rejected records. Source date {parsed.source_date or 'not reported'}. "
                f"SHA256 {parsed.checksum}"
            )
        )
