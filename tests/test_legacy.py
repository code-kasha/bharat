from pathlib import Path
from unittest.mock import patch

from tools.helpers import get_offices


def test_legacy_export_does_not_include_header():
    with patch("tools.helpers.save") as save:
        get_offices(Path(__file__).resolve().parent.parent / "data" / "sample.csv")
    rows, filename = save.call_args.args
    assert filename == "offices.json"
    assert len(rows) == 3
    assert ("District", "Office Name") not in rows
