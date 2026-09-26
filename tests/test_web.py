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
    """Contributor mode: uploads replace the saved directory."""
    settings.ALLOW_SOURCE_CHANGE = True
    settings.SAVE_UPLOADS = True


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


@pytest.fixture
def temporary(settings):
    """Production mode on a local clone: uploads are temporary and private to one browser."""
    settings.ALLOW_SOURCE_CHANGE = True
    settings.SAVE_UPLOADS = False


def stored(upload_dir):
    return sorted(upload_dir.glob("*.sqlite3")) if upload_dir.exists() else []


def test_temporary_upload_is_seen_only_by_this_browser(client, directory, temporary, upload_dir):
    from django.test import Client

    from postal.models import Dataset, PostOffice

    response = upload(client, GOOD, source_date="2025-06-30")
    assert response.status_code == 302 and response["Location"] == "/?updated=1"
    cookie = response.cookies["bharat_upload"]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert len(stored(upload_dir)) == 1
    # The saved directory is untouched.
    assert Dataset.objects.get().source == "test fixture"
    assert PostOffice.objects.filter(office_name="New Office").count() == 0

    html = client.get("/?updated=1").content.decode()
    assert "Temporary dataset loaded: 2 offices." in html
    assert "My survey" in html and "30 June 2025" in html and "Kept until" in html
    assert 'action="/source/default/"' in html and "Back to the default dataset" in html
    assert "New Office" in client.get("/", {"q": "560001"}).content.decode()
    assert "0 results" in client.get("/", {"q": "400001"}).content.decode()

    other = Client()
    assert "New Office" not in other.get("/", {"q": "560001"}).content.decode()
    assert "test fixture" in other.get("/").content.decode()
    assert client.get("/api/v1/pincodes/560001/").status_code == 404
    assert client.get("/api/v1/dataset/").json()["source"] == "test fixture"


def test_temporary_lookup_stays_one_request(client, directory, temporary, monkeypatch):
    from contextlib import contextmanager

    from django.db import connections

    from postal import uploads

    upload(client, GOOD)
    html = client.get("/", {"q": "560001"}).content.decode()
    assert not re.search(r"<script|<img|<link[^>]+stylesheet|@import|url\(", html)
    opened = []
    real_open = uploads._open

    @contextmanager
    def spy(alias, name):
        with real_open(alias, name) as opened_alias:
            connections[opened_alias].force_debug_cursor = True
            opened.append(connections[opened_alias])
            yield opened_alias

    monkeypatch.setattr(uploads, "_open", spy)
    client.get("/", {"q": "560001", "page": 1})
    # Dataset label, result count, one page of offices; the connection is closed afterwards.
    (connection,) = opened
    assert len(connection.queries) == 3 and connection.connection is None


def test_back_to_default_deletes_the_upload(client, directory, temporary, upload_dir):
    upload(client, GOOD)
    assert client.get("/source/default/").status_code == 405
    response = client.post("/source/default/")
    assert response.status_code == 302 and response["Location"] == "/"
    assert response.cookies["bharat_upload"].value == ""
    assert stored(upload_dir) == []
    html = client.get("/").content.decode()
    assert "test fixture" in html and "expired" not in html


def test_back_to_default_requires_csrf_token(directory, temporary, upload_dir):
    from django.test import Client

    strict = Client(enforce_csrf_checks=True)
    token = strict.get("/source/").cookies["csrftoken"].value
    upload(strict, GOOD, csrfmiddlewaretoken=token)
    assert strict.post("/source/default/").status_code == 403
    assert len(stored(upload_dir)) == 1


def test_expired_upload_falls_back_to_default(client, directory, temporary, upload_dir, settings):
    import os
    import time

    upload(client, GOOD)
    (path,) = stored(upload_dir)
    old = time.time() - settings.TEMPORARY_UPLOAD_HOURS * 3600 - 1
    os.utime(path, (old, old))
    response = client.get("/")
    html = response.content.decode()
    assert "test fixture" in html and "has expired or was removed" in html
    assert response.cookies["bharat_upload"].value == ""
    assert stored(upload_dir) == []


def test_tampered_cookie_is_ignored(client, directory, temporary, upload_dir):
    upload(client, GOOD)
    (path,) = stored(upload_dir)
    client.cookies["bharat_upload"] = path.stem
    assert "test fixture" in client.get("/").content.decode()


def test_new_upload_replaces_this_browsers_previous_one(client, directory, temporary, upload_dir):
    upload(client, GOOD)
    first = stored(upload_dir)
    upload(client, GOOD[2:], source="Second")
    assert len(stored(upload_dir)) == 1 and stored(upload_dir) != first
    assert "Second" in client.get("/").content.decode()


def test_uploads_are_capped(directory, temporary, upload_dir, settings):
    from django.test import Client

    settings.TEMPORARY_UPLOAD_LIMIT = 2
    browsers = [Client() for _ in range(3)]
    for number, browser in enumerate(browsers):
        upload(browser, GOOD, source=f"Browser {number}")
    assert len(stored(upload_dir)) == 2
    # The oldest upload made room for the newest.
    assert "test fixture" in browsers[0].get("/").content.decode()
    assert "Browser 2" in browsers[2].get("/").content.decode()


def test_rejected_temporary_upload_keeps_nothing(client, directory, temporary, upload_dir):
    response = upload(client, ["C,R,D,Bad,012345,HO,Delivery,X,Y"])
    assert response.status_code == 400 and "Nothing was changed" in response.content.decode()
    assert stored(upload_dir) == [] and "bharat_upload" not in response.cookies


def test_change_source_page_explains_the_mode(client, temporary, settings):
    html = client.get("/source/").content.decode()
    assert "Upload and use in this browser" in html and "DJANGO_DEBUG=true" in html
    settings.SAVE_UPLOADS = True
    assert "Upload and replace directory" in client.get("/source/").content.decode()


def test_saved_upload_offers_to_share_the_dataset(client, directory, local):
    upload(client, GOOD, source="Survey's; rm -rf /", source_date="2025-06-30")
    html = client.get("/?updated=1").content.decode()
    assert "Share this dataset" in html
    assert 'href="https://github.com/code-kasha/bharat-post-dir"' in html
    assert "may not be reviewed" in html and "publish your fork" in html
    from postal.models import Dataset

    dataset = Dataset.objects.get()
    branch = f"dataset-{dataset.checksum[:12]}"
    assert f"git switch -c {branch}\ngit add db.sqlite3\n" in html
    # The source is shell-quoted in the commit command (and HTML-escaped on the page).
    assert (
        "git commit -m &#x27;Update dataset: Survey&#x27;&quot;&#x27;&quot;&#x27;s; rm -rf /&#x27;"
        in html
    )
    assert f"- SHA256 of the imported data: {dataset.checksum}" in html
    assert "- Source date: 2025-06-30" in html
    assert "- Offices: 2 (1 exact repeated rows merged)" in html
    # Only right after saving.
    assert "Share this dataset" not in client.get("/").content.decode()


def test_share_note_copies_a_database_kept_elsewhere(client, directory, local, settings, tmp_path):
    settings.DATABASE_PATH = tmp_path / "my data.sqlite3"
    upload(client, GOOD)
    html = client.get("/?updated=1").content.decode()
    assert f"cp &#x27;{tmp_path}/my data.sqlite3&#x27; db.sqlite3\ngit add db.sqlite3" in html


def test_temporary_upload_points_to_saving_instead_of_sharing(client, directory, temporary):
    upload(client, GOOD)
    html = client.get("/?updated=1").content.decode()
    assert "Share this dataset" not in html
    assert (
        "To save it and share it with others, run Bharat with <code>DJANGO_DEBUG=true</code>"
        in html
    )


REPEATED = GOOD + ["C,R,D,New Office,560001,SO,Non Delivery,Bengaluru,Karnataka"]


@pytest.mark.parametrize("mode", ["local", "temporary"])
def test_repeated_offices_are_kept_and_reported(client, directory, mode, request):
    request.getfixturevalue(mode)
    assert upload(client, REPEATED).status_code == 302
    html = client.get("/?updated=1").content.decode()
    assert "3 offices" in html
    assert (
        "1 office is listed more than once with different details; every version was kept." in html
    )
    assert "<dt>Listed more than once</dt>" in html
    results = client.get("/", {"q": "560001"}).content.decode()
    assert results.count('<th scope="row">New Office</th>') == 2


def test_repeated_offices_are_in_the_api_and_share_note(client, directory, local):
    upload(client, REPEATED)
    assert client.get("/api/v1/dataset/").json()["repeated_identity_count"] == 1
    assert client.get("/api/v1/pincodes/560001/").json()["count"] == 2
    html = client.get("/?updated=1").content.decode()
    assert "- Offices listed more than once with different details (kept): 1" in html


def test_single_listings_do_not_mention_repeats(client, directory, local):
    upload(client, GOOD)
    html = client.get("/?updated=1").content.decode()
    assert "every version was kept" not in html and "<dt>Listed more than once</dt>" not in html


def upload_file(client, body, name="data.json", **fields):
    from django.core.files.uploadedfile import SimpleUploadedFile

    data = {"file": SimpleUploadedFile(name, body), "source": ""} | fields
    return client.post("/source/", data)


def test_bharat_export_round_trips_with_its_provenance(client, directory, local):
    from postal.models import Dataset, PostOffice

    Dataset.objects.update(source_period="On or before June 2023")
    before = list(PostOffice.objects.values_list("pincode", "office_name", "latitude"))
    export = b"".join(client.get("/api/v1/export/").streaming_content)
    response = upload_file(client, export)
    assert response.status_code == 302
    dataset = Dataset.objects.get()
    assert (dataset.source, dataset.source_period) == ("test fixture", "On or before June 2023")
    assert list(PostOffice.objects.values_list("pincode", "office_name", "latitude")) == before


def test_typed_source_details_override_the_export(client, directory, local):
    from postal.models import Dataset

    export = b"".join(client.get("/api/v1/export/").streaming_content)
    upload_file(client, export, source="Mine", source_period="2024")
    dataset = Dataset.objects.get()
    assert (dataset.source, dataset.source_period) == ("Mine", "2024")


def test_json_without_provenance_needs_a_source(client, directory, local):
    import json

    body = json.dumps({"records": [{"officename": "X"}]}).encode()
    html = upload_file(client, body).content.decode()
    assert "record 1: missing fields" in html
    body = json.dumps(
        [
            {"pincode": "560001"}
            | dict.fromkeys(
                [
                    "officename",
                    "district",
                    "statename",
                    "circlename",
                    "regionname",
                    "divisionname",
                    "officetype",
                    "delivery",
                ],
                "V",
            )
        ]
    ).encode()
    response = upload_file(client, body)
    assert (
        response.status_code == 400 and "Say where the data came from." in response.content.decode()
    )
    assert upload_file(client, body, source="Survey").status_code == 302
