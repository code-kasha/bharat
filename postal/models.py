from django.db import models


class Dataset(models.Model):
    """Single current snapshot; replacement and metadata update share a transaction."""

    source = models.CharField(max_length=500)
    source_date = models.DateField(null=True, blank=True)
    # Approximate provenance ("On or before June 2023") when no exact date is known.
    source_period = models.CharField(max_length=100, blank=True)
    checksum = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now=True)
    row_count = models.PositiveIntegerField()
    duplicate_count = models.PositiveIntegerField(default=0)


class PostOffice(models.Model):
    pincode = models.CharField(max_length=6, db_index=True)
    office_name = models.CharField(max_length=200)
    district = models.CharField(max_length=200, db_index=True)
    state = models.CharField(max_length=200, db_index=True)
    circle = models.CharField(max_length=200)
    region = models.CharField(max_length=200, blank=True)
    division = models.CharField(max_length=200)
    office_type = models.CharField(max_length=30)
    delivery = models.CharField(max_length=30)
    # As published by the source; unparseable values are null and some points are known wrong.
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        # Not unique: the stored legacy snapshot lists three offices twice with differing details.
        ordering = ["pincode", "state", "district", "office_name", "id"]
