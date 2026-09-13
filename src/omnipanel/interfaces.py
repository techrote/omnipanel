"""Exact, fail-closed component interface negotiation."""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import Field, model_validator

from omnipanel.domain.contracts import (
    CommitSha,
    ComponentContractIdentityRecord,
    ComponentContractRef,
    ContractModel,
    ContractVersion,
    DisplayText,
    OpaqueId,
)
from omnipanel.storage import StateStore


class RegistryConfigurationError(ValueError):
    pass


class CompatibilityOutcome(StrEnum):
    QUALIFIED = "qualified"
    INCOMPATIBLE = "incompatible"


class IncompatibilityCode(StrEnum):
    COMPONENT_UNSUPPORTED = "component-unsupported"
    CONTRACT_UNSUPPORTED = "contract-unsupported"
    VERSION_UNQUALIFIED = "version-unqualified"
    OBSERVATION_UNQUALIFIED = "observation-unqualified"


class AdapterContractQualification(ContractModel):
    adapter_id: OpaqueId
    component_id: OpaqueId
    contract_id: OpaqueId
    contract_version: ContractVersion
    qualification_evidence_ids: tuple[OpaqueId, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _valid(self) -> AdapterContractQualification:
        if len(self.qualification_evidence_ids) != len(set(self.qualification_evidence_ids)):
            raise ValueError("qualification_evidence_ids must be unique")
        return self


class CompatibilityDiagnostic(ContractModel):
    code: IncompatibilityCode
    summary: DisplayText
    supported_contract_versions: tuple[ContractVersion, ...] = Field(max_length=64)


class CompatibilityDecision(ContractModel):
    adapter_id: OpaqueId
    observed: ComponentContractRef
    observed_source_commit: CommitSha
    outcome: CompatibilityOutcome
    component_qualification_evidence_ids: tuple[OpaqueId, ...] = Field(max_length=64)
    adapter_qualification_evidence_ids: tuple[OpaqueId, ...] = Field(max_length=64)
    diagnostic: CompatibilityDiagnostic | None = None

    @model_validator(mode="after")
    def _consistent(self) -> CompatibilityDecision:
        if self.outcome is CompatibilityOutcome.QUALIFIED:
            if self.diagnostic is not None:
                raise ValueError("qualified decision cannot include diagnostic")
            if not self.component_qualification_evidence_ids:
                raise ValueError("qualified decision requires component evidence")
            if not self.adapter_qualification_evidence_ids:
                raise ValueError("qualified decision requires adapter evidence")
        elif self.diagnostic is None:
            raise ValueError("incompatible decision requires diagnostic")
        return self


class InterfaceRegistry:
    def __init__(self, qualifications: tuple[AdapterContractQualification, ...]) -> None:
        keys: set[tuple[str, str, str, str]] = set()
        for item in qualifications:
            key = (item.adapter_id, item.component_id, item.contract_id, item.contract_version)
            if key in keys:
                raise RegistryConfigurationError("duplicate exact adapter qualification")
            keys.add(key)
        self._qualifications = qualifications

    @property
    def qualifications(self) -> tuple[AdapterContractQualification, ...]:
        return self._qualifications

    def negotiate(
        self, adapter_id: str, observed: ComponentContractIdentityRecord
    ) -> CompatibilityDecision:
        component = tuple(
            item
            for item in self._qualifications
            if item.adapter_id == adapter_id and item.component_id == observed.ref.component_id
        )
        if not component:
            return self._deny(
                adapter_id,
                observed,
                IncompatibilityCode.COMPONENT_UNSUPPORTED,
                "adapter has no explicit qualification for this component",
                (),
            )
        contract = tuple(item for item in component if item.contract_id == observed.ref.contract_id)
        if not contract:
            return self._deny(
                adapter_id,
                observed,
                IncompatibilityCode.CONTRACT_UNSUPPORTED,
                "observed contract identity is unsupported",
                (),
            )
        versions = tuple(sorted({item.contract_version for item in contract}))
        exact = next(
            (item for item in contract if item.contract_version == observed.ref.contract_version),
            None,
        )
        if exact is None:
            return self._deny(
                adapter_id,
                observed,
                IncompatibilityCode.VERSION_UNQUALIFIED,
                "observed contract version lacks exact qualification",
                versions,
            )
        if not observed.qualification_evidence_ids:
            return self._deny(
                adapter_id,
                observed,
                IncompatibilityCode.OBSERVATION_UNQUALIFIED,
                "observed component contract lacks qualification evidence",
                versions,
            )
        return CompatibilityDecision(
            adapter_id=adapter_id,
            observed=observed.ref,
            observed_source_commit=observed.source_commit,
            outcome=CompatibilityOutcome.QUALIFIED,
            component_qualification_evidence_ids=observed.qualification_evidence_ids,
            adapter_qualification_evidence_ids=exact.qualification_evidence_ids,
        )

    def persist_qualification(
        self, store: StateStore, item: AdapterContractQualification
    ) -> str:
        if item not in self._qualifications:
            raise RegistryConfigurationError("qualification is not registered")
        observation_id = _observation_id(
            "qualification",
            item.adapter_id,
            item.component_id,
            item.contract_id,
            item.contract_version,
        )
        store.save_component_observation(
            item.component_id, observation_id, item.model_dump(mode="json")
        )
        return observation_id

    @staticmethod
    def load_qualification(
        store: StateStore, component_id: str, observation_id: str
    ) -> AdapterContractQualification:
        return AdapterContractQualification.model_validate(
            store.load_component_observation(component_id, observation_id)
        )

    def persist_decision(self, store: StateStore, decision: CompatibilityDecision) -> str:
        observation_id = _observation_id(
            "decision",
            decision.adapter_id,
            decision.observed.component_id,
            decision.observed.contract_id,
            decision.observed.contract_version,
            decision.observed_source_commit,
        )
        store.save_component_observation(
            decision.observed.component_id,
            observation_id,
            decision.model_dump(mode="json"),
        )
        return observation_id

    @staticmethod
    def load_decision(
        store: StateStore, component_id: str, observation_id: str
    ) -> CompatibilityDecision:
        return CompatibilityDecision.model_validate(
            store.load_component_observation(component_id, observation_id)
        )

    @staticmethod
    def _deny(
        adapter_id: str,
        observed: ComponentContractIdentityRecord,
        code: IncompatibilityCode,
        summary: str,
        versions: tuple[str, ...],
    ) -> CompatibilityDecision:
        return CompatibilityDecision(
            adapter_id=adapter_id,
            observed=observed.ref,
            observed_source_commit=observed.source_commit,
            outcome=CompatibilityOutcome.INCOMPATIBLE,
            component_qualification_evidence_ids=observed.qualification_evidence_ids,
            adapter_qualification_evidence_ids=(),
            diagnostic=CompatibilityDiagnostic(
                code=code,
                summary=summary,
                supported_contract_versions=versions,
            ),
        )


def _observation_id(kind: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode()).hexdigest()[:32]
    return f"interface-{kind}-{digest}"
