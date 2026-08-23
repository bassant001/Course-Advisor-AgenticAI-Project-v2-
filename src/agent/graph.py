import os
import sys
import sqlite3

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.state import AgentState
from src.agent.nodes import (
    parse_query_node,
    retrieve_courses_node,
    constraint_critic_node,
    generate_recommendation_node
)


# Human-in-the-loop node
def human_review_node(state: AgentState):
    print("🧑 [Node] Human review completed.")

    decision = state.get("human_decision", "NO_DECISION")

    print(f"✅ [Node] Human decision recorded: {decision}")

    return {
        "human_decision": decision
    }


# Decide whether human review is required
# AFTER the recommendation has already been generated.
def route_after_recommendation(state: AgentState) -> str:

    violations = state.get("violations", [])

    # Human review is required ONLY when
    # there are actual constraint violations.
    if violations:
        print(
            "[Router] Real constraint violations detected. "
            "Routing to Human Review..."
        )

        return "human_review_node"

    # No violations -> return recommendation directly.
    print(
        "[Router] No constraint violations. "
        "Returning recommendation directly."
    )

    return END


# Decide what happens after human review
def route_after_human(state: AgentState) -> str:

    decision = state.get("human_decision")

    if decision in ["APPROVED", "MODIFIED"]:

        print(
            f"[Router] Human decided: {decision}. "
            "Finalizing recommendation..."
        )

        return END

    print(
        f"[Router] Human decided: {decision}. "
        "Ending workflow without recommendation."
    )

    return END


def build_course_advisor_graph():

    print("⚙️ [Builder] Assembling LangGraph architecture...")

    builder = StateGraph(AgentState)

    # -------------------------
    # Nodes
    # -------------------------

    builder.add_node(
        "parse_query_node",
        parse_query_node
    )

    builder.add_node(
        "retrieve_courses_node",
        retrieve_courses_node
    )

    builder.add_node(
        "constraint_critic_node",
        constraint_critic_node
    )

    builder.add_node(
        "generate_recommendation_node",
        generate_recommendation_node
    )

    builder.add_node(
        "human_review_node",
        human_review_node
    )

    # -------------------------
    # Main pipeline
    # -------------------------

    builder.add_edge(
        START,
        "parse_query_node"
    )

    builder.add_edge(
        "parse_query_node",
        "retrieve_courses_node"
    )

    builder.add_edge(
        "retrieve_courses_node",
        "constraint_critic_node"
    )

    # Always generate the recommendation first.
    builder.add_edge(
        "constraint_critic_node",
        "generate_recommendation_node"
    )

    # -------------------------
    # After recommendation
    # -------------------------

    builder.add_conditional_edges(
        "generate_recommendation_node",
        route_after_recommendation,
        {
            "human_review_node": "human_review_node",
            END: END
        }
    )

    # -------------------------
    # After human review
    # -------------------------

    builder.add_conditional_edges(
        "human_review_node",
        route_after_human,
        {
            END: END
        }
    )

    # -------------------------
    # Persistence
    # -------------------------

    db_path = os.path.join(
        project_root,
        "checkpoints.sqlite"
    )

    conn = sqlite3.connect(
        db_path,
        check_same_thread=False
    )

    memory = SqliteSaver(conn)

    # Pause BEFORE human review.
    graph = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_review_node"]
    )

    return graph