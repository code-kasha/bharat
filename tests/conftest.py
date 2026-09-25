import csv

import pytest
from rest_framework.test import APIClient

from postal.importer import HEADERS


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def csv_file(tmp_path):
    def write(rows=None, headers=None):
        path = tmp_path / "postal.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers or HEADERS)
            writer.writerows(
                rows
                if rows is not None
                else [
                    [
                        "Circle",
                        "Region",
                        "Division",
                        "Office A",
                        "400001",
                        "HO",
                        "Delivery",
                        "District",
                        "State",
                    ],
                    [
                        "Circle",
                        "Region",
                        "Division",
                        "Office B",
                        "400001",
                        "SO",
                        "Delivery",
                        "District",
                        "State",
                    ],
                ]
            )
        return path

    return write
