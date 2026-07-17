"""Generic parser for CSV bank statements."""

import csv
import io
from typing import Any


def parse_generic_statement(uploaded_file: Any) -> list[dict[str, str]]:
    """Parse an uploaded CSV into a list of transaction dictionaries."""
    raw_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    decoded = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    return [dict(row) for row in reader]

