"""Wells Fargo statement parser wrapper."""

from typing import Any

from .generic import parse_generic_statement


def parse_wells_fargo_statement(uploaded_file: Any) -> list[dict[str, str]]:
    return parse_generic_statement(uploaded_file)

