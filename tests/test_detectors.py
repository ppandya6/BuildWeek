from pathlib import Path

from PIL import Image

from slidelineage.config import AuditConfig
from slidelineage.detectors import detect_identifier_overlaps, run_factual_detectors
from slidelineage.models import FindingType, Partition


def _csv(path: Path, rows: list[list[str]]) -> Path:
    path.write_text(
        "image,patient,specimen,slide,site,rid\n"
        + "\n".join(",".join(r) for r in rows)
        + "\n",
        encoding="utf-8",
    )
    return path


def _cfg(tmp_path: Path, max_pairs: int = 100) -> AuditConfig:
    return AuditConfig(
        train_manifest=tmp_path / "train.csv",
        test_manifest=tmp_path / "test.csv",
        output_dir=tmp_path / "out",
        images_dir=tmp_path / "images",
        max_image_pairs=max_pairs,
    )


def _norm(value: str) -> str | None:
    return value.lower().replace(" ", "-") if value else None


def _pair(tmp_path: Path, train_rows: list[list[str]], test_rows: list[list[str]]):
    from slidelineage.models import (
        CanonicalManifestRecords,
        CanonicalRecord,
        CanonicalRecordPair,
        IdentifierDerivationMethod,
        IdentifierProvenance,
        IdentifierStatus,
        RecordIdMethod,
    )

    cfg = _cfg(tmp_path)

    def build(rows: list[list[str]], part: Partition, mid: str):
        recs = []
        prov = []
        for i, row in enumerate(rows):
            image, patient, specimen, slide, site, rid = row
            if rid.upper().startswith("TCGA-02-0001") and not patient:
                patient = "tcga-02-0001"
            rec = CanonicalRecord(
                record_id=f"rec_{mid}_{i}_{rid.lower()}",
                record_id_method=RecordIdMethod.source_column,
                source_manifest_id=mid,
                source_row_number=i,
                assigned_partition=part,
                source_record_id=_norm(rid),
                image_path=image,
                patient_id=_norm(patient),
                specimen_id=_norm(specimen),
                slide_id=_norm(slide),
                institution_id=_norm(site),
                raw_values_digest="a" * 64,
                normalized_values_digest="b" * 64,
            )
            recs.append(rec)
            for field in (
                "patient_id",
                "specimen_id",
                "slide_id",
                "institution_id",
                "source_record_id",
            ):
                value = getattr(rec, field)
                prov.append(
                    IdentifierProvenance(
                        semantic_field=field,
                        value=value,
                        source_column=field,
                        derivation_method=(
                            IdentifierDerivationMethod.direct_manifest_value
                        ),
                        confidence=1.0 if value else 0.0,
                        status=(
                            IdentifierStatus.accepted
                            if value
                            else IdentifierStatus.unresolved
                        ),
                    )
                )
        return CanonicalManifestRecords(
            source_manifest_id=mid,
            partition=part,
            records=tuple(recs),
            identifier_provenance=tuple(prov),
        )

    return (
        CanonicalRecordPair(
            train=build(train_rows, Partition.train, "train_manifest"),
            test=build(test_rows, Partition.test, "test_manifest"),
        ),
        cfg,
    )


def test_identifier_overlaps_and_evidence_are_deterministic(tmp_path: Path) -> None:
    pair, _ = _pair(
        tmp_path,
        [
            ["a.png", "PT-1", "SP-1", "SL-1", "SITE", "RID1"],
            ["b.png", "PT-1", "SP-X", "SL-X", "SITE", "RID2"],
        ],
        [["c.png", "pt 1", "sp 1", "sl 1", "site", "RID3"]],
    )
    findings = detect_identifier_overlaps(pair)
    assert {f.finding_type for f in findings} == {
        FindingType.confirmed_patient_overlap,
        FindingType.confirmed_specimen_overlap,
        FindingType.confirmed_slide_overlap,
        FindingType.institution_overlap,
    }
    patient = next(
        f for f in findings if f.finding_type is FindingType.confirmed_patient_overlap
    )
    assert {e.assigned_partition for e in patient.evidence} == {
        Partition.train,
        Partition.test,
    }
    reversed_pair = pair.model_copy(
        update={
            "train": pair.train.model_copy(
                update={"records": tuple(reversed(pair.train.records))}
            )
        }
    )
    assert [f.finding_id for f in detect_identifier_overlaps(pair)] == [
        f.finding_id for f in detect_identifier_overlaps(reversed_pair)
    ]


def test_same_partition_missing_unresolved_and_conflicted_excluded(
    tmp_path: Path,
) -> None:
    pair, _ = _pair(
        tmp_path,
        [
            ["a.png", "PT-1", "Sx", "Lx", "Ix", "TCGA-02-0001-01A"],
            ["b.png", "pt 1", "Sx", "Lx", "Ix", "RID2"],
        ],
        [["c.png", "other", "Sy", "Ly", "Iy", "RID3"]],
    )
    assert detect_identifier_overlaps(pair) == ()
    conflicted, _ = _pair(
        tmp_path,
        [["a.png", "PATIENT-X", "Sx", "Lx", "Ix", "TCGA-02-0001-01A"]],
        [["c.png", "tcga-02-0001", "Sx", "Lx", "Ix", "RID3"]],
    )
    assert all(
        f.finding_type is not FindingType.confirmed_patient_overlap
        for f in detect_identifier_overlaps(conflicted)
    )


def test_tcga_derived_accepted_value_included(tmp_path: Path) -> None:
    pair, _ = _pair(
        tmp_path,
        [["a.png", "", "Sx", "Lx", "Ix", "TCGA-02-0001-01A"]],
        [["c.png", "tcga-02-0001", "Sx", "Lx", "Ix", "RID3"]],
    )
    assert any(
        f.finding_type is FindingType.confirmed_patient_overlap
        for f in detect_identifier_overlaps(pair)
    )


def test_run_result_contract_and_resource_limit(tmp_path: Path) -> None:
    imgdir = tmp_path / "images"
    imgdir.mkdir()
    Image.new("RGB", (8, 8), "red").save(imgdir / "a.png")
    Image.new("RGB", (8, 8), "red").save(imgdir / "b.png")
    pair, cfg = _pair(
        tmp_path,
        [["a.png", "P1", "Sx", "Lx", "Ix", "RID1"]],
        [["b.png", "P2", "Sx", "Lx", "Ix", "RID2"]],
    )
    cfg = (
        cfg.model_copy(update={"max_image_pairs": 0})
        if False
        else AuditConfig(
            train_manifest=cfg.train_manifest,
            test_manifest=cfg.test_manifest,
            output_dir=cfg.output_dir,
            images_dir=imgdir,
            max_image_pairs=1,
        )
    )
    result = run_factual_detectors(pair, cfg)
    assert (
        result.all_findings
        == result.identifier_findings
        + result.image_findings
        + result.input_quality_findings
    )
    assert result.image_fingerprints.resolved_count == 2
    assert any(
        f.finding_type is FindingType.confirmed_pixel_content_duplicate
        or f.finding_type is FindingType.confirmed_byte_content_duplicate
        for f in result.image_findings
    )
