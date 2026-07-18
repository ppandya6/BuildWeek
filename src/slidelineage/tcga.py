"""Strict deterministic TCGA barcode parsing."""

import re
from typing import Final

from slidelineage.errors import MalformedTcgaIdentifierError
from slidelineage.models import TcgaLineage

TCGA_PARSER_VERSION: Final[str] = "tcga-barcode-strict-v1"
_TCGA_RE: Final[re.Pattern[str]] = re.compile(
    r"^TCGA-([A-Z0-9]{2})-([A-Z0-9]{4})(?:-([0-9]{2})([A-Z]))?(?:-([0-9]{2})([A-Z]))?(?:-([A-Z0-9]{4})-([A-Z0-9]{2}))?$"
)


def parse_tcga_identifier(value: str) -> TcgaLineage | None:
    """Parse supported full TCGA barcodes, returning None for ordinary inputs.

    Supported full-string forms are participant, sample, portion/analyte, and
    plate/center. Malformed values beginning with TCGA are rejected instead of
    interpreted as ordinary identifiers.
    """

    cleaned = value.strip().upper()
    if not cleaned.startswith("TCGA"):
        if "TCGA" in cleaned:
            raise MalformedTcgaIdentifierError(
                "TCGA substring is not a full identifier"
            )
        return None
    match = _TCGA_RE.fullmatch(cleaned)
    if match is None:
        raise MalformedTcgaIdentifierError("malformed TCGA-like identifier")
    tss, participant, sample, vial, portion, analyte, plate, center = match.groups()
    if (plate is not None or center is not None) and (
        portion is None or analyte is None
    ):
        raise MalformedTcgaIdentifierError("TCGA plate/center requires portion/analyte")
    derived_patient_id = f"TCGA-{tss}-{participant}"
    sample_segment = (
        f"{sample}{vial}" if sample is not None and vial is not None else None
    )
    derived_specimen_id = (
        f"{derived_patient_id}-{sample_segment}" if sample_segment is not None else None
    )
    return TcgaLineage(
        raw_identifier=cleaned,
        project="TCGA",
        tissue_source_site=tss,
        participant=participant,
        sample=sample,
        vial=vial,
        portion=portion,
        analyte=analyte,
        plate=plate,
        center=center,
        derived_patient_id=derived_patient_id,
        derived_specimen_id=derived_specimen_id,
        parser_version=TCGA_PARSER_VERSION,
    )
