"""Lookup rules shared by the JSON API and the HTML lookup page."""

import re

from django.db.models import Q

from postal.models import PostOffice

PIN_RE = re.compile(r"[1-9][0-9]{5}")


def is_pin(value):
    return bool(PIN_RE.fullmatch(value))


def offices_for_pin(pincode, using=None):
    return PostOffice.objects.using(using).filter(pincode=pincode)


def search_offices(term, using=None):
    return PostOffice.objects.using(using).filter(
        Q(office_name__icontains=term) | Q(district__icontains=term)
    )
