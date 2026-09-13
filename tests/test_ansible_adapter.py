from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omnipanel.ansible_adapter import (
    AnsibleAdapterError,
    AnsibleAdapterErrorCode,
    CapabilityDiscovery,
    EvidenceReport,
    JobLifecycle,
    JobProposal,
    JobResult,
    JobStatus,
    ResourceProviderSummary,
    StatusCompleteness,
    SyntheticAnsibleAdapter,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op012_ansible_synthetic.json"


def _fixtures() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _payload(name: str) -> dict[str, object]:
    value = _fixtures()[name]
    assert isinstance(value, dict)
    return copy.deepcopy(value)


def test_supported_fixture_inventory_decodes_without_live_ansible() -> None:
    adapter = SyntheticAnsibleAdapter()
    expected = {
        "capability_discovery": CapabilityDiscovery,
        "resource_summary": ResourceProviderSummary,
        "job_proposal": JobProposal,
        "status_running": JobStatus,
        "status_partial": JobStatus,
        "job_result": JobResult,
        "evidence_report": EvidenceReport,
    }
    for name, model in expected.items():
        assert isinstance(adapter.decode(_payload(name)), model)


def test_unknown_contract_version_fails_closed() -> None:
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(_payload("unsupported_discovery"))
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.INCOMPATIBLE_CONTRACT
    assert "supported synthetic" in caught.value.diagnostic.summary


def test_contract_identity_change_fails_closed() -> None:
    payload = _payload("capability_discovery")
    contract = payload["contract"]
    assert isinstance(contract, dict)
    contract["contract_id"] = "accidental-slot-v1"
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(payload)
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.INCOMPATIBLE_CONTRACT


def test_malformed_payload_is_typed_and_operator_readable() -> None:
    payload = _payload("job_proposal")
    payload.pop("job_id")
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(payload)
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD
    assert caught.value.diagnostic.message_type == "job-proposal"
    assert "schema validation" in caught.value.diagnostic.summary


def test_malformed_message_type_cannot_break_typed_error_boundary() -> None:
    for bad_type in ("", " bad type !!! ", "x" * 200):
        payload = _payload("job_proposal")
        payload["message_type"] = bad_type
        with pytest.raises(AnsibleAdapterError) as caught:
            SyntheticAnsibleAdapter().decode(payload)
        assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD
        assert caught.value.diagnostic.message_type == "unknown"


def test_non_object_payload_is_typed_error() -> None:
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(["not", "an", "object"])
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD


def test_stale_and_duplicate_status_sequences_are_rejected() -> None:
    adapter = SyntheticAnsibleAdapter()
    status = adapter.decode_status(_payload("status_running"), previous_sequence=1)
    assert status.sequence == 2
    for previous in (2, 3):
        with pytest.raises(AnsibleAdapterError) as caught:
            adapter.decode_status(_payload("status_running"), previous_sequence=previous)
        assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.STALE_STATUS


def test_partial_running_status_is_explicitly_representable() -> None:
    status = SyntheticAnsibleAdapter().decode_status(_payload("status_partial"))
    assert status.lifecycle is JobLifecycle.RUNNING
    assert status.completeness is StatusCompleteness.PARTIAL


def test_partial_terminal_status_is_malformed_not_success() -> None:
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(_payload("status_partial_terminal"))
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD


def test_success_result_requires_evidence() -> None:
    payload = _payload("job_result")
    payload["evidence_ids"] = []
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(payload)
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD


def test_nonterminal_result_is_rejected() -> None:
    payload = _payload("job_result")
    payload["lifecycle"] = "running"
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(payload)
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD


def test_resource_availability_cannot_exceed_total() -> None:
    payload = _payload("resource_summary")
    available = payload["available"]
    assert isinstance(available, dict)
    available["memory_mib"] = 99999
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode(payload)
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD


def test_wrong_message_kind_is_rejected_by_status_entrypoint() -> None:
    with pytest.raises(AnsibleAdapterError) as caught:
        SyntheticAnsibleAdapter().decode_status(_payload("job_result"))
    assert caught.value.diagnostic.code is AnsibleAdapterErrorCode.MALFORMED_PAYLOAD
    assert "expected job-status" in caught.value.diagnostic.summary


def test_evidence_report_reuses_canonical_evidence_schema() -> None:
    report = SyntheticAnsibleAdapter().decode(_payload("evidence_report"))
    assert isinstance(report, EvidenceReport)
    assert report.evidence[0].evidence_id == "evidence-op012-001"
    assert report.evidence[0].test_summary is not None
    assert report.evidence[0].test_summary.passed == 5
