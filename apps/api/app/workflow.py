from collections.abc import Callable
from typing import NotRequired

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from app.graph.graph import ExtractionState, Search, build_graph
from app.llm import LLMHelper
from app.schemas import Requirement
from app.stories import Story, critique, open_questions, validate_stories, write_stories


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stories: list[Story] = Field(max_length=30)


class WorkflowState(ExtractionState):
    stories: NotRequired[list[Story]]
    questions: NotRequired[list[str]]
    critic_feedback: NotRequired[list[str]]
    revision_count: NotRequired[int]
    approved: NotRequired[bool]
    tickets: NotRequired[list[dict]]


def build_workflow(
    helper: LLMHelper,
    search: Search,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    create_tickets: Callable[[list[Story], list[Requirement]], list[dict]]
    | None = None,
) -> CompiledStateGraph:
    def generate(state: WorkflowState) -> dict:
        feedback = state.get("critic_feedback", [])
        return {
            "stories": write_stories(
                helper, state["requirements"], feedback, state.get("stories")
            ),
            "questions": open_questions(state["requirements"]),
            "revision_count": state.get("revision_count", 0) + bool(feedback),
        }

    def critic(state: WorkflowState) -> dict:
        return {
            "critic_feedback": critique(helper, state["requirements"], state["stories"])
        }

    def after_critic(state: WorkflowState) -> str:
        if state["critic_feedback"] and state["revision_count"] < 1:
            return "write_stories"
        return "human_review"

    def human_review(state: WorkflowState) -> dict:
        payload = interrupt(
            {
                "stories": [item.model_dump() for item in state["stories"]],
                "questions": state["questions"],
                "critic_feedback": state["critic_feedback"],
            }
        )
        approval = Approval.model_validate(payload)
        return {
            "stories": validate_stories(approval.stories, state["requirements"]),
            "approved": True,
        }

    def tickets(state: WorkflowState) -> dict:
        if not state.get("approved"):
            raise ValueError("Ticket creation requires human approval")
        if create_tickets is None:
            raise ValueError("Ticket creation is not configured")
        return {"tickets": create_tickets(state["stories"], state["requirements"])}

    graph = StateGraph(WorkflowState)
    graph.add_node("discovery", build_graph(helper, search))
    graph.add_node("write_stories", generate)
    graph.add_node("critic", critic)
    graph.add_node("human_review", human_review)
    graph.add_node("create_tickets", tickets)
    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "write_stories")
    # A revision is final: its critique would reach no reader and cost a call.
    graph.add_conditional_edges(
        "write_stories",
        lambda state: "human_review" if state["revision_count"] else "critic",
    )
    graph.add_conditional_edges("critic", after_critic)
    graph.add_edge("human_review", "create_tickets")
    graph.add_edge("create_tickets", END)
    return graph.compile(checkpointer=checkpointer)
