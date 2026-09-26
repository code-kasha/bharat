from io import StringIO

import pytest
from conftest import office

from postal.importer import parse_records, replace_dataset
from postal.models import PostOffice

pytestmark = pytest.mark.django_db


@pytest.fixture
def directory(records):
    records.append(office("Office C", pincode="110001", district="Other", statename="Another"))
    replace_dataset(parse_records(records), source="test fixture")


def test_pin_returns_all_matching_offices(api, directory):
    response = api.get("/api/v1/pincodes/400001/")
    assert response.status_code == 200
    assert response.data["count"] == 2
    assert {row["office_name"] for row in response.data["results"]} == {"Office A", "Office B"}
    assert response.data["results"][0]["pincode"] == "400001"
    assert response.data["results"][0]["latitude"] == 18.93
    assert response.data["results"][1]["longitude"] is None


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
    assert response.data["count"] == 33
    assert len(response.data["results"]) == 25
    assert len(second.data["results"]) == 8
    assert not (
        {row["office_name"] for row in response.data["results"]}
        & {row["office_name"] for row in second.data["results"]}
    )


def test_metadata_and_empty_state(api, directory):
    response = api.get("/api/v1/dataset/")
    assert response.data["source"] == "test fixture"
    assert response.data["row_count"] == 3


def test_states_are_listed_with_office_counts(api, directory):
    response = api.get("/api/v1/states/")
    assert response.data["results"] == [
        {"state": "Another", "office_count": 1},
        {"state": "State", "office_count": 2},
    ]


def test_districts_filter_by_state(api, directory):
    assert api.get("/api/v1/districts/").data["count"] == 2
    response = api.get("/api/v1/districts/", {"state": "state"})
    assert response.data["results"] == [
        {"state": "State", "district": "District", "office_count": 2}
    ]
    assert api.get("/api/v1/districts/", {"page": "0"}).status_code == 400


def test_no_dataset_yet(api):
    assert api.get("/api/v1/dataset/").status_code == 404
    assert api.get("/api/v1/offices/").data["count"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/offices/",
        "/api/v1/pincodes/400001/",
        "/api/v1/states/",
        "/api/v1/districts/",
        "/api/v1/dataset/",
        "/api/v1/export/",
    ],
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


def test_export_is_one_complete_versioned_file(api, directory):
    import gzip
    import json

    response = api.get("/api/v1/export/")
    assert response.status_code == 200
    body = json.loads(b"".join(response.streaming_content))
    assert body["dataset"]["row_count"] == 3
    assert [row["office_name"] for row in body["offices"]] == ["Office C", "Office A", "Office B"]
    assert body["offices"][0].keys() == api.get("/api/v1/offices/").data["results"][0].keys()
    checksum = body["dataset"]["checksum"]
    assert response["ETag"] == f'"{checksum}"'
    assert f"post-offices-undated-{checksum[:12]}.json" in response["Content-Disposition"]

    compressed = api.get("/api/v1/export/", HTTP_ACCEPT_ENCODING="gzip")
    assert compressed["Content-Encoding"] == "gzip"
    assert json.loads(gzip.decompress(b"".join(compressed.streaming_content))) == body


@pytest.mark.parametrize("etag", ['"{}"', 'W/"{}"'])
def test_export_is_not_resent_to_a_client_that_has_it(api, directory, etag):
    checksum = api.get("/api/v1/dataset/").data["checksum"]
    response = api.get("/api/v1/export/", HTTP_IF_NONE_MATCH=etag.format(checksum))
    assert response.status_code == 304


def test_export_before_import(api):
    assert api.get("/api/v1/export/").status_code == 404


def test_docs_page_pins_swagger_ui(api):
    html = api.get("/api/docs/").content.decode()
    assert "swagger-ui-dist@5.33.0/swagger-ui-bundle.js" in html
    assert "@latest" not in html


def test_export_command_writes_the_served_document(api, records, tmp_path):
    import gzip
    import hashlib

    from django.core.management import call_command

    replace_dataset(parse_records(records), source="fixture")
    served = b"".join(api.get("/api/v1/export/").streaming_content)
    call_command("export_directory", "--output-dir", str(tmp_path), stdout=StringIO())
    (path,) = tmp_path.iterdir()
    assert path.name.startswith("post-offices-undated-") and path.name.endswith(".json.gz")
    assert gzip.decompress(path.read_bytes()) == served
    # Byte-identical on a second run, so the release's SHA256SUMS is reproducible.
    first = hashlib.sha256(path.read_bytes()).hexdigest()
    call_command("export_directory", "--output-dir", str(tmp_path), stdout=StringIO())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first


def test_export_command_needs_a_dataset(tmp_path):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="No dataset"):
        call_command("export_directory", "--output-dir", str(tmp_path))


def test_api_version_matches_the_package(api):
    import tomllib
    from pathlib import Path

    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    schema = api.get("/api/schema/", {"format": "json"}).json()
    assert schema["info"]["version"] == project["project"]["version"] == "1.0.0"
