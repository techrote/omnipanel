from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omnipanel.domain.contracts import (
    CandidateStatus,
    ComponentContractRef,
    EvidenceDescriptorRecord,
    EvidenceKind,
    EvidenceProducer,
    EvidenceProducerType,
    ProviderRequest,
    ResourceRequest,
    RunRecord,
    RunStatus,
    RunStrategy,
)
from omnipanel.execution_provider import (
    ExecutionProvider,
    ExecutionProviderError,
    FakeExecutionProvider,
    ProviderAvailability,
    ProviderCandidateLifecycle,
    ProviderCandidateRequest,
    ProviderDescription,
    ProviderEvidenceReceipt,
    ProviderFailureCode,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderMetadataItem,
    ProviderReservationState,
    ProviderWorkPurpose,
    attach_provider_evidence,
)

CLOCK = datetime(2026, 9, 14, 1, 30, tzinfo=UTC)
TOTAL = ResourceRequest(
    cpu_millicores=4000,
    memory_mib=8192,
    storage_mib=32768,
    wall_time_seconds=900,
    gpu_count=1,
)


def _description(
    *,
    provider_id: str = "provider-fake",
    provider_class: str = "general-worker",
    purposes: tuple[ProviderWorkPurpose, ...] = (
        ProviderWorkPurpose.EXECUTION,
        ProviderWorkPurpose.VALIDATION,
    ),
    guarantees: ProviderGuarantees | None = None,
) -> ProviderDescription:
    return ProviderDescription(
        identity=ProviderIdentity(
            provider_id=provider_id,
            provider_class=provider_class,
            implementation_version="fake-1.0",
            interface_contract=ComponentContractRef(
                component_id="fake-provider",
                contract_id="execution-provider",
                contract_version="1.0",
            ),
        ),
        capabilities=("build.python", "test.public"),
        supported_purposes=purposes,
        guarantees=guarantees
        or ProviderGuarantees(
            isolation=True,
            resource_limits=True,
            network_policy=True,
            filesystem_policy=True,
        ),
        metadata=(
            ProviderMetadataItem(key="os.family", value="linux"),
            ProviderMetadataItem(key="placement.kind", value="virtualized"),
        ),
    )


def _provider(
    *,
    description: ProviderDescription | None = None,
    availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
) -> FakeExecutionProvider:
    return FakeExecutionProvider(
        description or _description(),
        TOTAL,
        availability=availability,
        clock_start=CLOCK,
    )


def _request(
    *,
    provider_class: str = "general-worker",
    capabilities: tuple[str, ...] = ("build.python",),
    resources: ResourceRequest | None = None,
) -> ProviderRequest:
    return ProviderRequest(
        provider_class=provider_class,
        required_capability_handles=capabilities,
        resources=resources
        or ResourceRequest(
            cpu_millicores=1500,
            memory_mib=2048,
            storage_mib=4096,
            wall_time_seconds=300,
            gpu_count=0,
        ),
        writable_paths=("worktree",),
        network_access=False,
        isolation_required=True,
    )


def _start(
    provider: FakeExecutionProvider,
    *,
    purpose: ProviderWorkPurpose = ProviderWorkPurpose.EXECUTION,
):
    reservation = provider.reserve(run_id="run-014", request=_request())
    handle = provider.start(
        ProviderCandidateRequest(
            run_id="run-014",
            candidate_id="candidate-a",
            task_id="OP-014",
            purpose=purpose,
            reservation_id=reservation.reservation_id,
            payload_ref="payload-014",
        )
    )
    return reservation, handle


def _failure_code(exc: pytest.ExceptionInfo[ExecutionProviderError]) -> ProviderFailureCode:
    return exc.value.diagnostic.code


def test_fake_satisfies_generic_provider_shape_and_happy_lifecycle() -> None:
    provider = _provider()
    generic: ExecutionProvider = provider
    assert generic.describe().identity.provider_id == "provider-fake"

    before = provider.inventory()
    assert before.availability is ProviderAvailability.AVAILABLE
    assert before.available == TOTAL

    reservation, handle = _start(provider)
    assert reservation.state is ProviderReservationState.RESERVED
    running = provider.observe(handle)
    assert running.lifecycle is ProviderCandidateLifecycle.RUNNING
    assert running.sequence == 1

    during = provider.inventory()
    assert during.available.cpu_millicores == 2500
    assert during.available.memory_mib == 6144
    assert during.available.storage_mib == 28672
    assert during.available.wall_time_seconds == TOTAL.wall_time_seconds
    assert during.available.gpu_count == 1

    terminal = provider.finish(handle, ProviderCandidateLifecycle.SUCCEEDED)
    assert terminal.lifecycle is ProviderCandidateLifecycle.SUCCEEDED
    assert terminal.sequence == 2
    assert len(terminal.evidence_ids) == 1

    receipts = provider.collect_evidence(handle)
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.provider == provider.describe().identity
    assert receipt.task_id == "OP-014"
    assert receipt.descriptor.producer.producer_type is EvidenceProducerType.PROVIDER
    assert receipt.descriptor.producer.producer_id == "provider-fake"
    assert "/fake-1.0/" in receipt.descriptor.location

    run = RunRecord(
        run_id="run-014",
        task_id="OP-014",
        master_id="master-014",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.RUNNING,
    )
    with_evidence = attach_provider_evidence(run, receipts)
    assert with_evidence.evidence_ids == (receipt.descriptor.evidence_id,)
    assert with_evidence.status is RunStatus.RUNNING
    assert with_evidence.selected_candidate_id is None
    assert ProviderCandidateLifecycle.SUCCEEDED.value != CandidateStatus.ELIGIBLE.value

    released = provider.release(reservation.reservation_id)
    assert released.state is ProviderReservationState.RELEASED
    assert provider.inventory().available == TOTAL


def test_wall_time_is_ceiling_not_fungible_capacity() -> None:
    provider = _provider()
    first = provider.reserve(run_id="run-a", request=_request())
    second = provider.reserve(run_id="run-b", request=_request())
    inventory = provider.inventory()
    assert inventory.available.cpu_millicores == 1000
    assert inventory.available.wall_time_seconds == 900
    provider.release(first.reservation_id)
    provider.release(second.reservation_id)


def test_resource_overcommit_fails_explicitly_and_release_restores_capacity() -> None:
    provider = _provider()
    reservation = provider.reserve(
        run_id="run-large",
        request=_request(
            resources=ResourceRequest(
                cpu_millicores=3500,
                memory_mib=7000,
                storage_mib=30000,
                wall_time_seconds=900,
                gpu_count=1,
            )
        ),
    )
    with pytest.raises(ExecutionProviderError) as exc:
        provider.reserve(run_id="run-overcommit", request=_request())
    assert _failure_code(exc) is ProviderFailureCode.RESOURCES_UNAVAILABLE
    provider.release(reservation.reservation_id)
    assert provider.inventory().available == TOTAL


def test_unsupported_capability_and_provider_class_fail_closed() -> None:
    provider = _provider()
    with pytest.raises(ExecutionProviderError) as capability_exc:
        provider.reserve(
            run_id="run-capability",
            request=_request(capabilities=("build.python", "gpu.cuda")),
        )
    assert _failure_code(capability_exc) is ProviderFailureCode.CAPABILITY_UNSUPPORTED
    assert capability_exc.value.diagnostic.missing_capability_handles == ("gpu.cuda",)

    with pytest.raises(ExecutionProviderError) as class_exc:
        provider.reserve(
            run_id="run-class",
            request=_request(provider_class="validation-worker"),
        )
    assert _failure_code(class_exc) is ProviderFailureCode.PROVIDER_CLASS_MISMATCH


@pytest.mark.parametrize(
    ("guarantees", "expected"),
    [
        (
            ProviderGuarantees(
                isolation=False,
                resource_limits=True,
                network_policy=True,
                filesystem_policy=True,
            ),
            ProviderFailureCode.ISOLATION_UNSUPPORTED,
        ),
        (
            ProviderGuarantees(
                isolation=True,
                resource_limits=True,
                network_policy=False,
                filesystem_policy=True,
            ),
            ProviderFailureCode.NETWORK_POLICY_UNSUPPORTED,
        ),
        (
            ProviderGuarantees(
                isolation=True,
                resource_limits=True,
                network_policy=True,
                filesystem_policy=False,
            ),
            ProviderFailureCode.FILESYSTEM_POLICY_UNSUPPORTED,
        ),
        (
            ProviderGuarantees(
                isolation=True,
                resource_limits=False,
                network_policy=True,
                filesystem_policy=True,
            ),
            ProviderFailureCode.RESOURCE_ENFORCEMENT_UNSUPPORTED,
        ),
    ],
)
def test_missing_provider_guarantees_are_not_emulated(
    guarantees: ProviderGuarantees,
    expected: ProviderFailureCode,
) -> None:
    provider = _provider(description=_description(guarantees=guarantees))
    with pytest.raises(ExecutionProviderError) as exc:
        provider.reserve(run_id="run-guarantee", request=_request())
    assert _failure_code(exc) is expected


@pytest.mark.parametrize(
    "availability",
    [ProviderAvailability.UNAVAILABLE, ProviderAvailability.INDETERMINATE],
)
def test_unavailable_or_indeterminate_provider_rejects_new_work(
    availability: ProviderAvailability,
) -> None:
    provider = _provider(availability=availability)
    with pytest.raises(ExecutionProviderError) as exc:
        provider.reserve(run_id="run-unavailable", request=_request())
    assert _failure_code(exc) is ProviderFailureCode.PROVIDER_UNAVAILABLE


def test_degraded_provider_remains_explicit_but_can_accept_supported_work() -> None:
    provider = _provider(availability=ProviderAvailability.DEGRADED)
    assert provider.inventory().availability is ProviderAvailability.DEGRADED
    reservation = provider.reserve(run_id="run-degraded", request=_request())
    assert reservation.state is ProviderReservationState.RESERVED


def test_validation_only_provider_rejects_execution_but_accepts_validation() -> None:
    description = _description(
        provider_id="provider-validation",
        provider_class="validation-worker",
        purposes=(ProviderWorkPurpose.VALIDATION,),
    ).model_copy(update={"capabilities": ("test.windows",)})
    provider = _provider(description=description)
    request = _request(
        provider_class="validation-worker",
        capabilities=("test.windows",),
    )
    reservation = provider.reserve(run_id="run-validation", request=request)

    with pytest.raises(ExecutionProviderError) as exc:
        provider.start(
            ProviderCandidateRequest(
                run_id="run-validation",
                candidate_id="candidate-validation",
                task_id="OP-014",
                purpose=ProviderWorkPurpose.EXECUTION,
                reservation_id=reservation.reservation_id,
                payload_ref="payload-validation",
            )
        )
    assert _failure_code(exc) is ProviderFailureCode.PURPOSE_UNSUPPORTED

    handle = provider.start(
        ProviderCandidateRequest(
            run_id="run-validation",
            candidate_id="candidate-validation",
            task_id="OP-014",
            purpose=ProviderWorkPurpose.VALIDATION,
            reservation_id=reservation.reservation_id,
            payload_ref="payload-validation",
        )
    )
    assert handle.purpose is ProviderWorkPurpose.VALIDATION


def test_release_rejects_live_job_and_cancel_makes_it_releasable() -> None:
    provider = _provider()
    reservation, handle = _start(provider)
    with pytest.raises(ExecutionProviderError) as exc:
        provider.release(reservation.reservation_id)
    assert _failure_code(exc) is ProviderFailureCode.RESERVATION_STATE_INVALID

    cancelled = provider.cancel(handle, reason="race sibling won")
    assert cancelled.lifecycle is ProviderCandidateLifecycle.CANCELLED
    assert provider.collect_evidence(handle)
    assert provider.release(reservation.reservation_id).state is ProviderReservationState.RELEASED

    with pytest.raises(ExecutionProviderError) as repeat_exc:
        provider.cancel(handle, reason="repeat")
    assert _failure_code(repeat_exc) is ProviderFailureCode.CANDIDATE_STATE_INVALID


def test_indeterminate_job_holds_resources_until_reconciled() -> None:
    provider = _provider()
    reservation, handle = _start(provider)
    indeterminate = provider.finish(handle, ProviderCandidateLifecycle.INDETERMINATE)
    assert indeterminate.lifecycle is ProviderCandidateLifecycle.INDETERMINATE
    assert (
        provider.reservation(reservation.reservation_id).state
        is ProviderReservationState.INDETERMINATE
    )
    held = provider.inventory().available
    assert held.cpu_millicores == 2500
    assert held.memory_mib == 6144

    with pytest.raises(ExecutionProviderError) as release_exc:
        provider.release(reservation.reservation_id)
    assert _failure_code(release_exc) is ProviderFailureCode.RESERVATION_STATE_INVALID

    reconciled = provider.finish(handle, ProviderCandidateLifecycle.SUCCEEDED)
    assert reconciled.lifecycle is ProviderCandidateLifecycle.SUCCEEDED
    assert len(reconciled.evidence_ids) == 2
    assert len(provider.collect_evidence(handle)) == 2
    assert provider.reservation(reservation.reservation_id).state is ProviderReservationState.ACTIVE
    assert provider.release(reservation.reservation_id).state is ProviderReservationState.RELEASED
    assert provider.inventory().available == TOTAL


def test_request_and_handle_identity_mismatches_fail_closed() -> None:
    provider = _provider()
    reservation = provider.reserve(run_id="run-014", request=_request())
    with pytest.raises(ExecutionProviderError) as request_exc:
        provider.start(
            ProviderCandidateRequest(
                run_id="run-other",
                candidate_id="candidate-a",
                task_id="OP-014",
                purpose=ProviderWorkPurpose.EXECUTION,
                reservation_id=reservation.reservation_id,
                payload_ref="payload-014",
            )
        )
    assert _failure_code(request_exc) is ProviderFailureCode.REQUEST_MISMATCH

    handle = provider.start(
        ProviderCandidateRequest(
            run_id="run-014",
            candidate_id="candidate-a",
            task_id="OP-014",
            purpose=ProviderWorkPurpose.EXECUTION,
            reservation_id=reservation.reservation_id,
            payload_ref="payload-014",
        )
    )
    other_identity = handle.provider.model_copy(update={"implementation_version": "fake-2.0"})
    wrong_provider = handle.model_copy(update={"provider": other_identity})
    with pytest.raises(ExecutionProviderError) as identity_exc:
        provider.observe(wrong_provider)
    assert _failure_code(identity_exc) is ProviderFailureCode.PROVIDER_IDENTITY_MISMATCH

    missing_job = handle.model_copy(update={"provider_job_id": "job-missing"})
    with pytest.raises(ExecutionProviderError) as missing_exc:
        provider.observe(missing_job)
    assert _failure_code(missing_exc) is ProviderFailureCode.CANDIDATE_NOT_FOUND


def test_provider_evidence_receipt_validates_producer_identity() -> None:
    identity = _description().identity
    descriptor = EvidenceDescriptorRecord(
        evidence_id="evidence-wrong-provider",
        kind=EvidenceKind.PROVENANCE,
        producer=EvidenceProducer(
            producer_type=EvidenceProducerType.PROVIDER,
            producer_id="provider-other",
        ),
        location="provider://provider-other/fake-1.0/job-1/result",
        created_at=CLOCK,
    )
    with pytest.raises(ValueError, match="producer_id must match"):
        ProviderEvidenceReceipt(
            provider=identity,
            provider_job_id="job-1",
            run_id="run-014",
            task_id="OP-014",
            candidate_id="candidate-a",
            descriptor=descriptor,
        )


def test_attach_provider_evidence_rejects_cross_run_task_and_candidate_receipts() -> None:
    provider = _provider()
    _, handle = _start(provider)
    provider.finish(handle, ProviderCandidateLifecycle.SUCCEEDED)
    receipt = provider.collect_evidence(handle)[0]
    run = RunRecord(
        run_id="run-014",
        task_id="OP-014",
        master_id="master-014",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.RUNNING,
    )

    with pytest.raises(ValueError, match="different run"):
        attach_provider_evidence(run, (receipt.model_copy(update={"run_id": "run-other"}),))
    with pytest.raises(ValueError, match="different task"):
        attach_provider_evidence(run, (receipt.model_copy(update={"task_id": "OP-999"}),))
    with pytest.raises(ValueError, match="outside the run"):
        attach_provider_evidence(
            run,
            (receipt.model_copy(update={"candidate_id": "candidate-other"}),),
        )


def test_fake_ids_and_timestamps_are_deterministic_for_same_operation_sequence() -> None:
    left = _provider()
    right = _provider()
    left_reservation, left_handle = _start(left)
    right_reservation, right_handle = _start(right)
    assert left_reservation == right_reservation
    assert left_handle == right_handle
    assert left.finish(left_handle, ProviderCandidateLifecycle.FAILED) == right.finish(
        right_handle,
        ProviderCandidateLifecycle.FAILED,
    )
    assert left.collect_evidence(left_handle) == right.collect_evidence(right_handle)
