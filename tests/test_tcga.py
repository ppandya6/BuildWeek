"""Tests for strict TCGA parsing."""

import pytest

from slidelineage.errors import MalformedTcgaIdentifierError
from slidelineage.tcga import TCGA_PARSER_VERSION, parse_tcga_identifier


def test_participant_barcode() -> None:
    parsed = parse_tcga_identifier("TCGA-02-0001")
    assert parsed is not None
    assert parsed.derived_patient_id == "TCGA-02-0001"
    assert parsed.derived_specimen_id is None
    assert parsed.parser_version == TCGA_PARSER_VERSION


def test_sample_barcode() -> None:
    parsed = parse_tcga_identifier("TCGA-02-0001-01A")
    assert parsed is not None
    assert parsed.sample == "01"
    assert parsed.vial == "A"
    assert parsed.derived_specimen_id == "TCGA-02-0001-01A"


def test_portion_analyte_barcode() -> None:
    parsed = parse_tcga_identifier("TCGA-02-0001-01A-01D")
    assert parsed is not None
    assert parsed.portion == "01"
    assert parsed.analyte == "D"


def test_plate_center_barcode_and_lowercase_canonicalization() -> None:
    parsed = parse_tcga_identifier("tcga-02-0001-01a-01d-0001-01")
    assert parsed is not None
    assert parsed.raw_identifier == "TCGA-02-0001-01A-01D-0001-01"
    assert parsed.plate == "0001"
    assert parsed.center == "01"


def test_ordinary_non_tcga_input() -> None:
    assert parse_tcga_identifier("patient-1") is None


@pytest.mark.parametrize(
    "value",
    [
        "TCGA-02-001",
        "TCGA-02-0001-01@",
        "xx-TCGA-02-0001",
        "TCGA-02-0001-01A-extra",
        "TCGA-02-0001-01A-01D-0001-01-more",
    ],
)
def test_malformed_tcga_like_inputs(value: str) -> None:
    with pytest.raises(MalformedTcgaIdentifierError):
        parse_tcga_identifier(value)
