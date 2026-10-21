"""The generated Pydantic models must accept the LLD examples and forbid anything extra."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.models.abridged_payload_schema import AbridgedPayload
from app.models.analysis_result_schema import AnalysisResult
from app.models.donation_record_schema import DonationRecord
from app.models.narrative_schema import Narrative

EXAMPLES = Path(__file__).resolve().parents[2] / "schemas" / "examples"


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(
    ("model", "name"),
    [
        (AbridgedPayload, "abridged_payload"),
        (AnalysisResult, "analysis_result"),
        (AnalysisResult, "analysis_result.degraded"),
        (Narrative, "narrative"),
        (DonationRecord, "donation_record"),
    ],
)
def test_lld_examples_validate(model: type[BaseModel], name: str) -> None:
    doc = example(name)
    assert model.model_validate(doc).model_dump(mode="json", exclude_unset=True) == doc


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("metrics", "self"),
        ("metrics", "pair"),
        ("milestones", 0),
        ("milestones", 0, "excerpts", 0),
    ],
)
def test_payload_forbids_extra_keys(path: tuple[str | int, ...]) -> None:
    doc = copy.deepcopy(example("abridged_payload"))
    target: Any = doc
    for key in path:
        target = target[key]
    target["participant_name"] = "Riya"
    with pytest.raises(ValidationError, match="extra"):
        AbridgedPayload.model_validate(doc)


def test_payload_rejects_long_excerpt() -> None:
    doc = example("abridged_payload")
    doc["milestones"][0]["excerpts"][0]["text"] = "x" * 81
    with pytest.raises(ValidationError):
        AbridgedPayload.model_validate(doc)
