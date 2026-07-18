import pytest

from slidelineage.errors import NormalizationError
from slidelineage.normalization import (
    normalize_header,
    normalize_identifier_candidate,
    normalize_missing_value,
    normalize_optional_text,
)


def test_normalize_header_examples_and_nfkc() -> None:
    assert normalize_header(" Patient ID ") == "patient_id"
    assert normalize_header("Case-Submitter/ID") == "case_submitter_id"
    assert normalize_header(r"Image\Path") == "image_path"
    assert normalize_header("Tissue Source Site") == "tissue_source_site"
    assert normalize_header("ＰＡＴＩＥＮＴ　ＩＤ") == "patient_id"


def test_normalize_header_punctuation_casefold_and_collapse() -> None:
    assert normalize_header("  CASE---ID!!! ") == "case_id"
    assert normalize_header("Straße ID") == "strasse_id"
    assert normalize_header("a///b---c___d") == "a_b_c_d"


def test_normalize_header_rejects_empty_result() -> None:
    with pytest.raises(NormalizationError):
        normalize_header(" -- / ")


@pytest.mark.parametrize("value", [None, "", "   "])
def test_normalize_optional_text_blank(value: str | None) -> None:
    assert normalize_optional_text(value) is None


def test_normalize_optional_text_preserves_case_and_internal_text() -> None:
    assert normalize_optional_text("  Tumor Label  ") == "Tumor Label"
    assert normalize_optional_text("Ａ_B.7") == "A_B.7"


@pytest.mark.parametrize("value", ["", " NA ", "n/a", "Null", "NONE"])
def test_normalize_missing_value_approved_tokens(value: str) -> None:
    assert normalize_missing_value(value) is None


@pytest.mark.parametrize("value", ["0", "false", "unknown", "not available", "nan"])
def test_normalize_missing_value_preserves_non_missing_tokens(value: str) -> None:
    assert normalize_missing_value(value) == value


def test_normalize_identifier_candidate_is_conservative() -> None:
    assert normalize_identifier_candidate("  PAT-001 ") == "pat-001"
    assert normalize_identifier_candidate("00123") == "00123"
    assert normalize_identifier_candidate("A_B.7") == "a_b.7"
    assert normalize_identifier_candidate("A   B") == "a b"
    assert normalize_identifier_candidate("N/A") is None
