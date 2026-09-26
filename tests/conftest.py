import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api():
    return APIClient()


def office(name="Office A", pincode="400001", **overrides):
    """A synthetic record shaped like a data.gov.in API response row."""
    return {
        "circlename": "Circle",
        "regionname": "Region",
        "divisionname": "Division",
        "officename": name,
        "pincode": pincode,
        "officetype": "HO",
        "delivery": "Delivery",
        "district": "District",
        "statename": "State",
        "latitude": "18.93",
        "longitude": "72.83",
    } | overrides


@pytest.fixture
def records():
    return [office(), office("Office B", officetype="SO", latitude="NA", longitude="")]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Tests must not reach data.gov.in")

    monkeypatch.setattr("postal.importer.urlopen", refuse)
