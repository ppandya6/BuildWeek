"""Tests for SplitPolicy defaults and profile registry."""

import pytest

from slidelineage.errors import UnknownPolicyProfileError
from slidelineage.policy import available_policy_profiles, get_policy_profile


def test_default_policy_profile_values() -> None:
    policy = get_policy_profile()

    assert policy.name == "patient_independent_pathology_benchmark"
    assert policy.patient_disjoint is True
    assert policy.specimen_disjoint is True
    assert policy.slide_disjoint is True
    assert policy.exact_byte_content_disjoint is True
    assert policy.exact_pixel_content_disjoint is True
    assert policy.institution_disjoint is False
    assert policy.similarity_candidates_fail_audit is False


def test_policy_factory_returns_fresh_instances() -> None:
    first = get_policy_profile()
    second = get_policy_profile()

    assert first == second
    assert first is not second


def test_unknown_policy_profile_rejected() -> None:
    with pytest.raises(UnknownPolicyProfileError, match="Available profiles"):
        get_policy_profile("unknown")


def test_available_policy_names() -> None:
    assert available_policy_profiles() == ("patient_independent_pathology_benchmark",)
