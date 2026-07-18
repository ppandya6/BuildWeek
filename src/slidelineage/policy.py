"""Deterministic SplitPolicy contracts and profile registry."""

from pydantic import BaseModel, ConfigDict, Field

from slidelineage.errors import UnknownPolicyProfileError

DEFAULT_POLICY_PROFILE = "patient_independent_pathology_benchmark"
_AVAILABLE_POLICY_PROFILES: tuple[str, ...] = (DEFAULT_POLICY_PROFILE,)


class SplitPolicy(BaseModel):
    """Policy settings used to evaluate factual relationships across partitions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        default=DEFAULT_POLICY_PROFILE, description="Policy profile name."
    )
    patient_disjoint: bool = True
    specimen_disjoint: bool = True
    slide_disjoint: bool = True
    exact_byte_content_disjoint: bool = True
    exact_pixel_content_disjoint: bool = True
    institution_disjoint: bool = False
    similarity_candidates_fail_audit: bool = False


def available_policy_profiles() -> tuple[str, ...]:
    """Return available policy profile names in deterministic order."""

    return _AVAILABLE_POLICY_PROFILES


def get_policy_profile(name: str = DEFAULT_POLICY_PROFILE) -> SplitPolicy:
    """Return a fresh validated SplitPolicy for a known profile name."""

    if name != DEFAULT_POLICY_PROFILE:
        available = ", ".join(available_policy_profiles())
        raise UnknownPolicyProfileError(
            f"Unknown SplitPolicy profile {name!r}. Available profiles: {available}."
        )
    return SplitPolicy()
