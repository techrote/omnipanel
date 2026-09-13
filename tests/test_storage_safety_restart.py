from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import ModelAssessmentRecord, SafetyState
from omnipanel.storage import StateStore

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


@pytest.mark.parametrize("safety_state", [SafetyState.QUARANTINED, SafetyState.VERBOTEN])
def test_restrictive_model_safety_state_survives_restart(
    tmp_path: Path,
    safety_state: SafetyState,
) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = dict(fixture["model_assessment"])
    payload["safety_state"] = safety_state.value
    assessment = ModelAssessmentRecord.model_validate(payload)
    config = AppConfig(data_dir=(tmp_path / "safety state").absolute())

    with StateStore(config) as store:
        key = store.put_record(assessment)

    with StateStore(config) as reopened:
        loaded = reopened.get_typed_record(ModelAssessmentRecord, key)
        assert loaded.safety_state is safety_state
        assert not loaded.is_automatically_schedulable()
