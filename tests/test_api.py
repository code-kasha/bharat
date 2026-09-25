import pytest

from postal.importer import parse_csv, replace_dataset
from postal.models import PostOffice

pytestmark = pytest.mark.django_db


@pytest.fixture
def directory(csv_file):
    replace_dataset(parse_csv(csv_file()), source="test fixture")


def test_pin_returns_all_matching_offices(api, directory):
    response = api.get("/api/v1/pincodes/400001/")
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert {row["office_name"] for row in response.data["results"]} == {"Office A", "Office B"}
    assert response.data["results"][0]["pincode"] == "400001"


@pytest.mark.parametrize("pin,expected", [("bad", 400), ("000001", 400), ("999999", 404)])
def test_invalid_and_missing_pin(api, directory, pin, expected):
    assert api.get(f"/api/v1/pincodes/{pin}/").status_code == expected


def test_search_and_filters_combine(api, directory):
    response = api.get("/api/v1/offices/", {"search": "office a", "state": "state"})
    assert response.data["count"] == 1
    assert api.get("/api/v1/offices/", {"district": "elsewhere"}).data["count"] == 0


@pytest.mark.parametrize("params", [{"pincode": "bad"}, {"search": "x"}, {"page": "bad"}])
def test_query_validation(api, params):
    assert api.get("/api/v1/offices/", params).status_code == 400


def test_pagination_is_bounded_and_stable(api, directory):
    prototype = PostOffice.objects.first()
    for index in range(30):
        prototype.pk = None
        prototype.office_name = f"Extra {index:02}"
        prototype.save()
    response = api.get("/api/v1/offices/")
    second = api.get("/api/v1/offices/?page=2")
    assert response.data["count"] == 32
    assert len(response.data["results"]) == 25
    assert len(second.data["results"]) == 7
    assert not (
        {row["office_name"] for row in response.data["results"]}
        & {row["office_name"] for row in second.data["results"]}
    )


def test_metadata_and_empty_state(api, directory):
    response = api.get("/api/v1/dataset/")
    assert response.data["source"] == "test fixture"
    assert response.data["row_count"] == 2


def test_no_dataset_yet(api):
    assert api.get("/api/v1/dataset/").status_code == 404
    assert api.get("/api/v1/offices/").data["count"] == 0


@pytest.mark.parametrize(
    "url", ["/api/v1/offices/", "/api/v1/pincodes/400001/", "/api/v1/dataset/"]
)
def test_public_api_does_not_accept_writes(api, url):
    assert api.post(url, {}).status_code == 405


def test_health_and_schema(api):
    assert api.get("/health/").json() == {"status": "ok"}
    response = api.get("/api/schema/?format=json")
    assert response.status_code == 200
    assert "/api/v1/offices/" in response.json()["paths"]


def test_interactive_documentation_renders(api):
    response = api.get("/api/docs/")
    assert response.status_code == 200
    assert b"SwaggerUIBundle" in response.content
