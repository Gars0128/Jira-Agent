import json
from collections.abc import Callable

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.jira.client import JiraClient
from app.rag.retrieve import RetrievedChunk
from app.schemas import Requirement
from app.stories import StoryDraft, idempotency_key, validate_stories
from app.workflow import Approval, build_workflow

USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def new_requirement() -> Requirement:
    return Requirement(
        id="R1",
        text="Show monthly counts.",
        quote="Show monthly counts.",
        speaker="Nora",
        type="functional",
        priority="must",
        status="new",
    )


def draft() -> dict:
    return {
        "id": "S1",
        "title": "Show monthly counts",
        "as_a": "coordinator",
        "i_want": "see monthly reservation counts",
        "so_that": "I can report usage",
        "acceptance_criteria": [
            "Given reservations in two months, when I open the report, "
            "then I see one matching count per month."
        ],
        "requirement_ids": ["R1"],
    }


def responses(critic_issues: bool = False) -> list[str]:
    extraction = new_requirement().model_dump(exclude={"status", "note", "spec_refs"})
    result = [
        json.dumps({"requirements": [extraction]}),
        json.dumps(
            {
                "classifications": [
                    {
                        "id": "R1",
                        "status": "new",
                        "spec_refs": ["HD-REPORTS"],
                        "note": "Not specified.",
                    }
                ]
            }
        ),
        json.dumps({"stories": [draft()]}),
        json.dumps({"issues": ["Make counts explicit"] if critic_issues else []}),
    ]
    if critic_issues:
        result += [json.dumps({"stories": [draft()]})]
    return result


def search(queries: list[str]) -> list[list[RetrievedChunk]]:
    return [
        [
            RetrievedChunk(
                id="HD-REPORTS",
                heading="Reports",
                text="Reports show an overall count.",
                distance=0.1,
            )
        ]
        for _ in queries
    ]


def test_idempotency_normalization_and_content_changes() -> None:
    assert idempotency_key(" Monthly   COUNTS ", ["R2", "R1"]) == idempotency_key(
        "monthly counts", ["r1", "r2"]
    )
    assert idempotency_key("monthly counts", ["R1"]) != idempotency_key(
        "monthly totals", ["R1"]
    )


@pytest.mark.parametrize("change", ["unknown", "missing", "duplicate", "conflict"])
def test_story_links_reject_invalid_scope(change: str) -> None:
    requirement = new_requirement()
    stories = [StoryDraft.model_validate(draft())]
    if change == "unknown":
        stories[0].requirement_ids = ["R99"]
    elif change == "missing":
        stories = []
    elif change == "duplicate":
        stories += [stories[0].model_copy(update={"id": "S2"})]
    else:
        requirement.status = "conflict"
    with pytest.raises(ValueError):
        validate_stories(stories, [requirement])


def test_graph_pauses_before_creation_and_resumes_after_rebuild(
    helper_factory: Callable,
) -> None:
    helper, requests = helper_factory(responses(), USAGE)
    saver = InMemorySaver()
    writes = []

    def tickets(stories: list, requirements: list) -> list[dict]:
        writes.append(stories)
        return JiraClient().create_tickets(stories)

    config = {"configurable": {"thread_id": "test-restart"}}
    graph = build_workflow(helper, search, checkpointer=saver, create_tickets=tickets)
    result = graph.invoke({"transcript": "Nora: Show monthly counts."}, config)
    assert result["__interrupt__"]
    assert writes == []
    assert graph.get_state(config).next == ("human_review",)
    stories = [item.model_dump() for item in result["stories"]]
    stories[0]["title"] = "Monthly reservation totals"
    old_key = stories[0]["idempotency_key"]

    restored = build_workflow(
        helper, search, checkpointer=saver, create_tickets=tickets
    )
    approved = restored.invoke(Command(resume={"stories": stories}), config)
    assert len(writes) == 1
    assert approved["approved"] is True
    assert approved["stories"][0].idempotency_key != old_key
    assert approved["tickets"][0]["fields"]["summary"] == "Monthly reservation totals"
    assert len(requests) == 4
    restored.invoke(None, config)
    assert len(writes) == 1


def test_critic_can_request_only_one_revision(helper_factory: Callable) -> None:
    helper, requests = helper_factory(responses(True), USAGE)
    graph = build_workflow(helper, search, checkpointer=InMemorySaver())
    result = graph.invoke(
        {"transcript": "Nora: Show monthly counts."},
        {"configurable": {"thread_id": "critic-bound"}},
    )
    assert result["revision_count"] == 1
    assert result["critic_feedback"] == ["Make counts explicit"]
    assert result["__interrupt__"]
    assert len(requests) == 5
    revision_input = json.loads(requests[4]["messages"][1]["content"])
    assert revision_input["previous_stories"][0]["id"] == "S1"
    assert revision_input["revision_feedback"] == ["Make counts explicit"]


def test_cached_review_state_reaches_interrupt_without_model_calls(
    helper_factory: Callable,
) -> None:
    helper, requests = helper_factory("unused", USAGE)
    graph = build_workflow(helper, search, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "cached-review"}}
    requirement = new_requirement()
    graph.update_state(
        config,
        {
            "transcript": "Nora: Show monthly counts.",
            "requirements": [requirement],
            "dropped_requirement_ids": [],
            "stories": validate_stories(
                [StoryDraft.model_validate(draft())], [requirement]
            ),
            "questions": [],
            "revision_count": 1,
            "critic_feedback": [],
        },
        as_node="critic",
    )
    result = graph.invoke(None, config)
    assert result["__interrupt__"]
    assert requests == []


def test_empty_input_requirements_skip_story_and_critic_calls(
    helper_factory: Callable,
) -> None:
    helper, requests = helper_factory('{"requirements": []}', USAGE)
    graph = build_workflow(helper, search, checkpointer=InMemorySaver())
    result = graph.invoke(
        {"transcript": "Nora: Hello."},
        {"configurable": {"thread_id": "empty"}},
    )
    assert result["stories"] == []
    assert result["questions"] == []
    assert len(requests) == 1
    assert result["__interrupt__"]


def test_approval_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        Approval.model_validate({"stories": [], "approved": True})
