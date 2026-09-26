import gzip
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from postal.export import filename, stream
from postal.models import Dataset


class Command(BaseCommand):
    help = "Write the whole directory as gzipped JSON: the same document /api/v1/export/ serves."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=".", help="folder for the .json.gz file")

    def handle(self, *args, **options):
        dataset = Dataset.objects.filter(pk=1).first()
        if dataset is None:
            raise CommandError("No dataset has been imported.")
        path = Path(options["output_dir"]) / f"{filename(dataset)}.gz"
        # mtime=0 keeps the file byte-identical for the same dataset, so its SHA256 is stable.
        with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out:
            for piece in stream(dataset):
                out.write(piece.encode())
        self.stdout.write(str(path))
