"""Shared pytest configuration and helpers for SlideLineage tests."""

from pathlib import Path

from slidelineage.config import AuditConfig


def audit_manifest(path: Path, patient: str, rid: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "img,patient,specimen,slide,site,label,rid\n"
        f"{rid}.png,{patient},S{rid},L{rid},I,A,{rid}\n",
        encoding="utf-8",
    )
    return path


def audit_config(
    tmp_path: Path, same_patient: bool = False, repair: bool = False
) -> AuditConfig:
    train = audit_manifest(tmp_path / "train.csv", "P1", "R1")
    test = audit_manifest(tmp_path / "test.csv", "P1" if same_patient else "P2", "R2")
    return AuditConfig(
        train_manifest=train,
        test_manifest=test,
        output_dir=tmp_path / "out",
        image_column="img",
        patient_column="patient",
        specimen_column="specimen",
        slide_column="slide",
        institution_column="site",
        label_column="label",
        record_id_column="rid",
        repair=repair,
    )
