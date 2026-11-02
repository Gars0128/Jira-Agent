from collections.abc import Callable

import pytest
from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.memory import InMemorySaver
from test_workflow import draft, new_requirement, search

from app.run_service import RunService, hydrate_cache
from app.stories import Story, StoryDraft, validate_stories
from app.workflow import build_workflow


class OfflineStore:
    def __init__(self) -> None:
        self.saved = []
        self.events = []

    def save(self, run_id: str, result: dict, *, settle: bool = False) -> None:
        self.saved.append((run_id, result, settle))

    def event(self, run_id: str, kind: str, **data: object) -> None:
        self.events.append((run_id, kind, data))


def cached_state() -> dict:
    requirement = new_requirement()
    return jsonable_encoder(
        {
            "transcript": "Nora: Show monthly counts.",
            "requirements": [requirement],
            "dropped_requirement_ids": [],
            "stories": validate_stories(
                [StoryDraft.model_validate(draft())], [requirement]
            ),
            "questions": [],
            "retrieved": {},
            "critic_feedback": [],
            "revision_count": 1,
        }
    )


@pytest.mark.parametrize(
    "stage", ["before_interrupt", "awaiting_review", "done", "ambiguous"]
)
def test_restart_recovers_safe_checkpoints_without_paid_replay(
    helper_factory: Callable, stage: str
) -> None:
    helper, requests = helper_factory("must never be called")
    service = RunService(helper.settings)
    store = OfflineStore()
    service.store = store
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": stage}}
    graph = build_workflow(helper, search, checkpointer=saver)
    state = hydrate_cache(cached_state())
    if stage == "done":
        state.update(approved=True, tickets=[{"key": "PREVIEW-1", "dry_run": True}])
        graph.update_state(config, state, as_node="create_tickets")
    elif stage == "ambiguous":
        graph.update_state(config, state, as_node="discovery")
    else:
        graph.update_state(config, state, as_node="critic")
        if stage == "awaiting_review":
            graph.invoke(None, config)
    # Rebuild graph to exercise restored checkpoints, not the old runtime object.
    restored = build_workflow(helper, search, checkpointer=saver)
    result = {
        "status": "running",
        "error": None,
        "transcript": "must not leak into public result",
        "usage": {"cost_usd": "0.01", "calls": 4},
    }
    recovered = service._recover(stage, result, restored, config)
    expected = (
        "error"
        if stage == "ambiguous"
        else "done"
        if stage == "done"
        else "awaiting_review"
    )
    assert recovered["status"] == expected
    assert recovered["usage"]["cost_usd"] is None
    assert "transcript" not in recovered
    assert store.saved[0][2] is False  # Retain the maximum daily reservation.
    assert store.events[0][1] == expected
    assert requests == []
    if expected == "awaiting_review":
        assert restored.get_state(config).tasks[0].interrupts
        assert recovered["stories"][0]["id"] == "S1"


def test_cache_hydration_restores_models_without_mutating_cached_json() -> None:
    cached = cached_state()
    cached["approved"] = True
    cached["tickets"] = [{"key": "must-not-reuse"}]
    state = hydrate_cache(cached)
    assert isinstance(state["stories"][0], Story)
    assert state["approved"] is False
    assert state["tickets"] == []
    assert isinstance(cached["stories"][0], dict)
    assert cached["approved"] is True
