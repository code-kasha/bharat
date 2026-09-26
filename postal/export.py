import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, StreamingHttpResponse
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import condition
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view

from postal.models import Dataset, PostOffice
from postal.serializers import DatasetSerializer, OfficeSerializer

FIELDS = list(OfficeSerializer().fields)
CHUNK = 5000


def _dataset():
    return Dataset.objects.filter(pk=1).first()


def _etag(request):
    # The checksum identifies the snapshot, so an unchanged directory is never resent.
    dataset = _dataset()
    return dataset.checksum if dataset else None


def filename(dataset):
    date = dataset.source_date.isoformat() if dataset.source_date else "undated"
    return f"post-offices-{date}-{dataset.checksum[:12]}.json"


def stream(dataset):
    """Yield the export document in pieces: dataset metadata, then every office."""
    meta = json.dumps(DatasetSerializer(dataset).data, cls=DjangoJSONEncoder)
    yield f'{{"dataset":{meta},"offices":['
    rows = PostOffice.objects.order_by("pincode", "state", "district", "office_name", "id")
    batch = []
    for index, row in enumerate(rows.values_list(*FIELDS).iterator(chunk_size=CHUNK)):
        batch.append(("," if index else "") + json.dumps(dict(zip(FIELDS, row, strict=True))))
        if len(batch) == CHUNK:
            yield "".join(batch)
            batch = []
    yield "".join(batch) + "]}"


@extend_schema(
    summary="Download the whole directory as one file",
    description=(
        "Streams dataset metadata and every office in a single JSON document, gzip-compressed "
        "when the client accepts it. The ETag is the dataset SHA256; send it back in "
        "If-None-Match to receive 304 Not Modified instead of the file."
    ),
    responses={
        (200, "application/json"): OpenApiResponse(OpenApiTypes.OBJECT),
        304: OpenApiResponse(description="The client already has this dataset version."),
        404: OpenApiResponse(description="No dataset has been imported."),
    },
)
@api_view(["GET"])
def export(request):
    dataset = _dataset()
    if dataset is None:
        raise Http404("No dataset has been imported.")
    response = StreamingHttpResponse(stream(dataset), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{filename(dataset)}"'
    response["Cache-Control"] = "no-cache"
    return response


export = gzip_page(condition(etag_func=_etag)(export))
