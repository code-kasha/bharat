from rest_framework import serializers

from postal.models import Dataset, PostOffice


class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostOffice
        exclude = ["id"]


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        exclude = ["id"]


class OfficeQuerySerializer(serializers.Serializer):
    pincode = serializers.RegexField(r"^[1-9][0-9]{5}$", required=False)
    state = serializers.CharField(max_length=200, required=False)
    district = serializers.CharField(max_length=200, required=False)
    search = serializers.CharField(min_length=2, max_length=100, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
