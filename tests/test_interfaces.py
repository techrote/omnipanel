from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import ComponentContractIdentityRecord
from omnipanel.interfaces import (
    AdapterContractQualification,
    CompatibilityOutcome,
    IncompatibilityCode,
    InterfaceRegistry,
    RegistryConfigurationError,
)
from omnipanel.storage import StateStore

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op006_compatibility.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _qualifications() -> tuple[AdapterContractQualification, ...]:
    items = _fixture()["qualifications"]
    assert isinstance(items, list)
    return tuple(AdapterContractQualification.model_validate(item) for item in items)


def _observation(name: str) -> ComponentContractIdentityRecord:
    observations = _fixture()["observations"]
    assert isinstance(observations, dict)
    return ComponentContractIdentityRecord.model_validate(observations[name])


def _registry() -> InterfaceRegistry:
    return InterfaceRegistry(_qualifications())


def test_exact_supported_version_is_qualified() -> None:
    decision = _registry().negotiate("ansible-adapter", _observation("ansible_v1"))
    assert decision.outcome is CompatibilityOutcome.QUALIFIED
    assert decision.diagnostic is None
    assert decision.adapter_qualification_evidence_ids == ("evidence-adapter-ansible-1.0",)


def test_multiple_explicit_versions_support_migration_window() -> None:
    observed = _observation("ansible_v1")
    observed = observed.model_copy(
        update={
            "ref": observed.ref.model_copy(update={"contract_version": "1.1"}),
            "source_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "qualification_evidence_ids": ("evidence-observed-ansible-1.1",),
        }
    )
    decision = _registry().negotiate("ansible-adapter", observed)
    assert decision.outcome is CompatibilityOutcome.QUALIFIED
    assert decision.adapter_qualification_evidence_ids == ("evidence-adapter-ansible-1.1",)


def test_unsupported_version_fails_closed_with_supported_versions() -> None:
    decision = _registry().negotiate("ansible-adapter", _observation("ansible_v2"))
    assert decision.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert decision.diagnostic is not None
    assert decision.diagnostic.code is IncompatibilityCode.VERSION_UNQUALIFIED
    assert decision.diagnostic.supported_contract_versions == ("1.0", "1.1")


def test_patch_version_is_not_guessed_compatible() -> None:
    observed = _observation("ansible_v1")
    observed = observed.model_copy(
        update={"ref": observed.ref.model_copy(update={"contract_version": "1.0.1"})}
    )
    decision = _registry().negotiate("ansible-adapter", observed)
    assert decision.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert decision.diagnostic is not None
    assert decision.diagnostic.code is IncompatibilityCode.VERSION_UNQUALIFIED


def test_source_revision_does_not_replace_contract_identity() -> None:
    observed = _observation("ansible_v1").model_copy(
        update={"source_commit": "cccccccccccccccccccccccccccccccccccccccc"}
    )
    decision = _registry().negotiate("ansible-adapter", observed)
    assert decision.outcome is CompatibilityOutcome.QUALIFIED
    assert decision.observed.contract_version == "1.0"
    assert decision.observed_source_commit == "c" * 40


def test_changed_contract_identity_fails_closed() -> None:
    observed = _observation("ansible_v1")
    observed = observed.model_copy(
        update={"ref": observed.ref.model_copy(update={"contract_id": "execution-v2"})}
    )
    decision = _registry().negotiate("ansible-adapter", observed)
    assert decision.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert decision.diagnostic is not None
    assert decision.diagnostic.code is IncompatibilityCode.CONTRACT_UNSUPPORTED


def test_unqualified_observation_fails_closed() -> None:
    observed = _observation("ansible_v1").model_copy(update={"qualification_evidence_ids": ()})
    decision = _registry().negotiate("ansible-adapter", observed)
    assert decision.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert decision.diagnostic is not None
    assert decision.diagnostic.code is IncompatibilityCode.OBSERVATION_UNQUALIFIED


def test_incompatible_component_does_not_disable_independent_component() -> None:
    registry = _registry()
    bad = registry.negotiate("ansible-adapter", _observation("ansible_v2"))
    good = registry.negotiate("interloc-adapter", _observation("interloc_v1"))
    assert bad.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert good.outcome is CompatibilityOutcome.QUALIFIED


def test_unknown_component_adapter_pair_fails_closed() -> None:
    decision = _registry().negotiate("unknown-adapter", _observation("ansible_v1"))
    assert decision.outcome is CompatibilityOutcome.INCOMPATIBLE
    assert decision.diagnostic is not None
    assert decision.diagnostic.code is IncompatibilityCode.COMPONENT_UNSUPPORTED


def test_qualification_requires_evidence() -> None:
    payload = _qualifications()[0].model_dump(mode="json")
    payload["qualification_evidence_ids"] = []
    with pytest.raises(ValidationError):
        AdapterContractQualification.model_validate(payload)


def test_duplicate_exact_qualification_is_rejected() -> None:
    qualification = _qualifications()[0]
    with pytest.raises(RegistryConfigurationError, match="duplicate exact"):
        InterfaceRegistry((qualification, qualification))


def test_qualification_and_decision_persist_across_restart(tmp_path: Path) -> None:
    registry = _registry()
    qualification = registry.qualifications[0]
    decision = registry.negotiate("ansible-adapter", _observation("ansible_v1"))
    config = AppConfig(data_dir=(tmp_path / "interface state 東京").absolute())

    with StateStore(config) as store:
        qualification_id = registry.persist_qualification(store, qualification)
        decision_id = registry.persist_decision(store, decision)

    with StateStore(config) as reopened:
        loaded_qualification = registry.load_qualification(
            reopened, qualification.component_id, qualification_id
        )
        loaded_decision = registry.load_decision(
            reopened, decision.observed.component_id, decision_id
        )

    assert loaded_qualification == qualification
    assert loaded_decision == decision
