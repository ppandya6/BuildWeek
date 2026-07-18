import hashlib
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from slidelineage.config import AuditConfig
from slidelineage.detectors import detect_image_relationships
from slidelineage.image_fingerprints import fingerprint_record_images
from slidelineage.models import (
    FindingType,
    ImageFingerprint,
    ImageReadStatus,
    Partition,
)


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


def test_path_resolution_failures_and_source_preserved(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    pair, cfg = _pair(
        tmp_path,
        [
            ["missing.png", "P1", "Sx", "Lx", "Ix", "RID1"],
            ["../x.png", "P2", "Sx", "Lx", "Ix", "RID2"],
        ],
        [["C:\\outside.png", "P3", "Sx", "Lx", "Ix", "RID3"]],
    )
    fps = fingerprint_record_images(pair, cfg)
    assert [f.source_image_path for f in fps.fingerprints] == [
        "missing.png",
        "../x.png",
        "C:\\outside.png",
    ]
    assert {f.status for f in fps.fingerprints} >= {
        ImageReadStatus.missing,
        ImageReadStatus.outside_root,
    }
    no_root = cfg.model_copy(update={"images_dir": None})
    assert fingerprint_record_images(pair, no_root).warnings


def test_fingerprints_known_hash_pixel_equality_and_validation(tmp_path: Path) -> None:
    imgdir = tmp_path / "images"
    imgdir.mkdir()
    Image.new("RGB", (8, 6), (1, 2, 3)).save(imgdir / "a.png")
    Image.new("RGB", (8, 6), (1, 2, 3)).save(imgdir / "b.bmp")
    pair, cfg = _pair(
        tmp_path,
        [["a.png", "P1", "Sx", "Lx", "Ix", "RID1"]],
        [["b.bmp", "P2", "Sx", "Lx", "Ix", "RID2"]],
    )
    fps = fingerprint_record_images(pair, cfg)
    a, b = fps.fingerprints
    assert a.byte_sha256 == hashlib.sha256((imgdir / "a.png").read_bytes()).hexdigest()
    assert a.byte_sha256 != b.byte_sha256
    assert a.canonical_pixel_sha256 == b.canonical_pixel_sha256
    assert a.width == 8 and a.height == 6 and a.image_format == "PNG"
    assert len(a.phash or "") == 16 and len(a.dhash or "") == 16
    assert fingerprint_record_images(pair, cfg).model_dump(
        mode="json"
    ) == fps.model_dump(mode="json")
    with pytest.raises(ValidationError):
        ImageFingerprint(
            record_id="r",
            assigned_partition=Partition.train,
            source_manifest_id="m",
            source_row_number=0,
            source_image_path="x",
            status=ImageReadStatus.resolved,
            detector_version="v",
        )


def test_unreadable_oversized_and_unsupported(tmp_path: Path) -> None:
    imgdir = tmp_path / "images"
    imgdir.mkdir()
    (imgdir / "bad.png").write_text("not an image", encoding="utf-8")
    Image.new("RGB", (10, 10), "blue").save(imgdir / "big.png")
    (imgdir / "note.txt").write_text("hello", encoding="utf-8")
    pair, cfg = _pair(
        tmp_path,
        [
            ["bad.png", "P1", "Sx", "Lx", "Ix", "RID1"],
            ["big.png", "P2", "Sx", "Lx", "Ix", "RID2"],
        ],
        [["note.txt", "P3", "Sx", "Lx", "Ix", "RID3"]],
    )
    cfg = AuditConfig(
        train_manifest=cfg.train_manifest,
        test_manifest=cfg.test_manifest,
        output_dir=cfg.output_dir,
        images_dir=imgdir,
        image_max_pixels=50,
    )
    statuses = {f.status for f in fingerprint_record_images(pair, cfg).fingerprints}
    assert (
        ImageReadStatus.unreadable in statuses
        and ImageReadStatus.unsafe_image in statuses
    )


def test_byte_pixel_similarity_and_resource_limit(tmp_path: Path) -> None:
    imgdir = tmp_path / "images"
    imgdir.mkdir()
    Image.new("RGB", (16, 16), "red").save(imgdir / "a.png")
    (imgdir / "copy.png").write_bytes((imgdir / "a.png").read_bytes())
    Image.new("RGB", (16, 16), "red").save(imgdir / "same.bmp")
    Image.new("RGB", (16, 16), (250, 0, 0)).save(imgdir / "near.png")
    pair, cfg = _pair(
        tmp_path,
        [["a.png", "P1", "Sx", "Lx", "Ix", "RID1"]],
        [
            ["copy.png", "P2", "Sx", "Lx", "Ix", "RID2"],
            ["same.bmp", "P3", "Sx", "Lx", "Ix", "RID3"],
            ["near.png", "P4", "Sx", "Lx", "Ix", "RID4"],
        ],
    )
    fps = fingerprint_record_images(pair, cfg)
    findings = detect_image_relationships(pair, fps, cfg)
    assert any(
        f.finding_type is FindingType.confirmed_byte_content_duplicate for f in findings
    )
    assert any(
        f.finding_type is FindingType.confirmed_pixel_content_duplicate
        for f in findings
    )
    assert all(
        not (
            f.finding_type is FindingType.image_similarity_candidate
            and set(f.record_ids)
            == {pair.train.records[0].record_id, pair.test.records[0].record_id}
        )
        for f in findings
    )
    limited = fingerprint_record_images(pair, _cfg(tmp_path, max_pairs=2))
    assert limited.pair_limit_exceeded
    assert any(
        f.finding_type is FindingType.resource_limit_exceeded
        for f in detect_image_relationships(pair, limited, _cfg(tmp_path, max_pairs=2))
    )
