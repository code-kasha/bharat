import re

import pytest
from conftest import office

from postal.importer import parse_records, replace_dataset

pytestmark = pytest.mark.django_db


@pytest.fixture
def directory(records):
    records += [office(f"Market {index:02}", pincode="110001") for index in range(30)]
    replace_dataset(parse_records(records), source="test fixture")


def test_empty_form_shows_provenance_without_results(client, directory):
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert '<label for="q">' in html
    assert "test fixture" in html
    assert "Not recorded" in html
    assert "<table" not in html


def test_pin_lookup_lists_every_office(client, directory):
    html = client.get("/", {"q": "400001"}).content.decode()
    assert "2 results for" in html
    assert "Office A" in html and "Office B" in html


def test_search_paginates_and_keeps_the_query(client, directory):
    html = client.get("/", {"q": "market"}).content.decode()
    assert "30 results" in html
    assert "Page 1 of 2" in html
    assert 'href="?q=market&amp;page=2"' in html
    assert "Market 25" in client.get("/", {"q": "market", "page": 2}).content.decode()


@pytest.mark.parametrize("query", ["012345", "12345", "x", "a" * 101])
def test_invalid_input_is_explained_accessibly(client, directory, query):
    response = client.get("/", {"q": query})
    html = response.content.decode()
    assert response.status_code == 400
    assert "<title>Error:" in html
    assert 'aria-invalid="true"' in html
    assert 'aria-describedby="q-hint q-error"' in html


def test_no_matches_and_no_dataset(client):
    html = client.get("/", {"q": "nowhere"}).content.decode()
    assert "0 results" in html
    assert "No dataset has been loaded" in html


def test_query_is_escaped(client, directory):
    html = client.get("/", {"q": "<script>alert(1)</script>"}).content.decode()
    assert "<script>" not in html


def test_page_is_self_contained(client, directory):
    """Each lookup costs one HTTP request: no scripts, stylesheets, images or fonts."""
    html = client.get("/", {"q": "market"}).content.decode()
    assert not re.search(r"<script|<img|<link[^>]+stylesheet|@import|url\(", html)
    assert '<link rel="icon" href="data:,">' in html


def test_lookup_uses_three_queries(client, directory, django_assert_num_queries):
    # Dataset label, result count, one page of offices.
    with django_assert_num_queries(3):
        client.get("/", {"q": "market", "page": 2})


def test_favicon_is_cached_and_empty(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 204
    assert "immutable" in response["Cache-Control"]


HEADER = (
    "Circle Name,Region Name,Division Name,Office Name,Pincode,"
    "OfficeType,Delivery,District,StateName"
)


def upload(client, rows, **fields):
    from django.core.files.uploadedfile import SimpleUploadedFile

    body = "\n".join([HEADER, *rows]).encode("utf-8-sig")
    data = {"file": SimpleUploadedFile("mine.csv", body, "text/csv"), "source": "My survey"}
    return client.post("/source/", data | fields)


GOOD = [
    "C,R,D,New Office,560001,HO,Delivery,Bengaluru,Karnataka",
    "C,R,D,New Office,560001,HO,Delivery,Bengaluru,Karnataka",
    "C,,D,Other Office,560002,SO,Non Delivery,Bengaluru,Karnataka",
]


@pytest.fixture
def local(settings):
    settings.ALLOW_SOURCE_CHANGE = True


def test_home_links_to_change_source_only_when_allowed(client, directory, settings):
    settings.ALLOW_SOURCE_CHANGE = True
    assert 'href="/source/">change source</a>' in client.get("/").content.decode()
    settings.ALLOW_SOURCE_CHANGE = False
    assert "/source/" not in client.get("/").content.decode()
    assert client.get("/source/").status_code == 404


def test_upload_replaces_directory_and_records_provenance(client, directory, local):
    from postal.models import Dataset, PostOffice

    response = upload(client, GOOD, source_period="2024–2025")
    assert response.status_code == 302 and response["Location"] == "/?updated=1"
    assert set(PostOffice.objects.values_list("office_name", flat=True)) == {
        "New Office",
        "Other Office",
    }
    dataset = Dataset.objects.get()
    assert (dataset.source, dataset.source_date, dataset.source_period) == (
        "My survey",
        None,
        "2024–2025",
    )
    assert (dataset.row_count, dataset.duplicate_count) == (2, 1)
    html = client.get("/?updated=1").content.decode()
    assert "Source updated: 2 offices loaded." in html
    assert "2024–2025" in html


def test_exact_source_date_is_shown(client, local):
    upload(client, GOOD, source_date="2025-06-30")
    assert "30 June 2025" in client.get("/").content.decode()


@pytest.mark.parametrize(
    "rows,fields,message",
    [
        (["C,R,D,Bad,012345,HO,Delivery,X,Y"], {}, "PIN must contain six digits"),
        (["C,R,D,Short"], {}, "different number of fields"),
        ([], {}, "no offices"),
        (GOOD, {"source": ""}, "Say where the data came from"),
        (GOOD, {"source_date": "2025-01-01", "source_period": "2024"}, "not both"),
        (
            ["C,R,D,Same,560001,HO,Delivery,X,Y", "C,R,D,Same,560001,SO,Delivery,X,Y"],
            {},
            "conflicting",
        ),
    ],
)
def test_bad_upload_changes_nothing(client, directory, local, rows, fields, message):
    from postal.models import Dataset

    response = upload(client, rows, **fields)
    html = response.content.decode()
    assert response.status_code == 400
    assert "<title>Error:" in html and "Nothing was changed" in html
    assert message in html
    assert Dataset.objects.get().source == "test fixture"


def test_non_utf8_upload_is_explained(client, local):
    from django.core.files.uploadedfile import SimpleUploadedFile

    body = (HEADER + "\nC,R,D,Café,560001,HO,Delivery,X,Y").encode("latin-1")
    response = client.post("/source/", {"file": SimpleUploadedFile("x.csv", body), "source": "s"})
    assert "not UTF-8" in response.content.decode()


def test_upload_requires_csrf_token(directory, local):
    from django.test import Client

    strict = Client(enforce_csrf_checks=True)
    assert "csrfmiddlewaretoken" in strict.get("/source/").content.decode()
    assert upload(strict, GOOD).status_code == 403


def test_upload_errors_point_to_csv_lines(client, local):
    rows = ["C,R,D,Fine,560001,HO,Delivery,X,Y", "C,R,D,Bad,012345,HO,Delivery,X,Y"]
    assert "line 3: PIN must contain" in upload(client, rows).content.decode()
