import re

from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView

from postal.models import Dataset, PostOffice
from postal.serializers import DatasetSerializer, OfficeQuerySerializer, OfficeSerializer


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


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
            result = result.filter(Q(office_name__icontains=term) | Q(district__icontains=term))
        return result


class PinLookupView(ListAPIView):
    serializer_class = OfficeSerializer
    queryset = PostOffice.objects.all()

    def get_queryset(self):
        pincode = self.kwargs["pincode"]
        if not re.fullmatch(r"[1-9][0-9]{5}", pincode):
            raise ValidationError({"pincode": "Expected a six-digit Indian PIN."})
        result = super().get_queryset().filter(pincode=pincode)
        if not result.exists():
            raise NotFound("PIN not found in the imported dataset.")
        return result


class DatasetView(RetrieveAPIView):
    serializer_class = DatasetSerializer
    queryset = Dataset.objects.all()

    def get_object(self):
        dataset = Dataset.objects.filter(pk=1).first()
        if dataset is None:
            raise NotFound("No dataset has been imported.")
        return dataset
