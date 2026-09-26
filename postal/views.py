from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView

from postal.models import Dataset, PostOffice
from postal.queries import is_pin, offices_for_pin, search_offices
from postal.serializers import (
    DatasetSerializer,
    DistrictQuerySerializer,
    DistrictSerializer,
    OfficeQuerySerializer,
    OfficeSerializer,
    StateSerializer,
)


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse(
        {"status": "ok", "version": settings.VERSION, "revision": settings.REVISION}
    )


@extend_schema(parameters=[OfficeQuerySerializer])
class OfficeListView(ListAPIView):
    serializer_class = OfficeSerializer
    queryset = PostOffice.objects.all()

    def get_queryset(self):
        query = OfficeQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        result = super().get_queryset()
        for key in ("pincode", "state", "district"):
            if value := query.validated_data.get(key):
                lookup = key if key == "pincode" else f"{key}__iexact"
                result = result.filter(**{lookup: value})
        if term := query.validated_data.get("search"):
            result = result & search_offices(term)
        return result


class PinLookupView(ListAPIView):
    serializer_class = OfficeSerializer
    queryset = PostOffice.objects.all()

    def get_queryset(self):
        pincode = self.kwargs["pincode"]
        if not is_pin(pincode):
            raise ValidationError({"pincode": "Expected a six-digit Indian PIN."})
        result = offices_for_pin(pincode)
        if not result.exists():
            raise NotFound("PIN not found in the imported dataset.")
        return result


class StateListView(ListAPIView):
    serializer_class = StateSerializer

    def get_queryset(self):
        return (
            PostOffice.objects.values("state").annotate(office_count=Count("id")).order_by("state")
        )


@extend_schema(parameters=[DistrictQuerySerializer])
class DistrictListView(ListAPIView):
    serializer_class = DistrictSerializer

    def get_queryset(self):
        query = DistrictQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        result = PostOffice.objects.all()
        if state := query.validated_data.get("state"):
            result = result.filter(state__iexact=state)
        return (
            result.values("state", "district")
            .annotate(office_count=Count("id"))
            .order_by("state", "district")
        )


class DatasetView(RetrieveAPIView):
    serializer_class = DatasetSerializer
    queryset = Dataset.objects.all()

    def get_object(self):
        dataset = Dataset.objects.filter(pk=1).first()
        if dataset is None:
            raise NotFound("No dataset has been imported.")
        return dataset
