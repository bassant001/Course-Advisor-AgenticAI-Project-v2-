import os
import sys
import sqlite3

# force python to read the main project directory
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



# human-in-the-loop escalation node
def human_review_node(state: AgentState):
    # this node executes AFTER the human resumes the graph
    print("🧑 [Node] Human review completed. Processing human decision...")
    decision = state.get("human_decision", "NO_DECISION")
    print(f"✅ [Node] Human decision recorded: {decision}")
    return {"human_decision": decision}

# router to determine if we need human intervention after the critic evaluates constraints
def route_after_critic(state: AgentState) -> str:
    if state.get("requires_human_review"):
        print("[Router] Violations detected. Routing to Human Escalation (Interrupt)...")
        return "human_review_node"
    
    print("[Router] All constraints met. Routing to Recommendation...")
    return "generate_recommendation_node"

# router to determine the next step based on the human advisor's decision
def route_after_human(state: AgentState) -> str:
    decision = state.get("human_decision")
    
    # if the human approves or modifies the constraints we proceed to give a recommendation
    if decision in ["APPROVED", "MODIFIED"]:
        print(f"[Router] Human decided: {decision}. Proceeding to Recommendation...")
        return "generate_recommendation_node"
    
    # if rejected or no valid decision is made we end the workflow immediately
    print(f"[Router] Human decided: {decision}. Ending workflow without recommendation.")
    return END



# graph builder and architecture definition
def build_course_advisor_graph():
    print("⚙️ [Builder] Assembling LangGraph architecture...")
    builder = StateGraph(AgentState)

    # add all nodes to the graph
    builder.add_node("parse_query_node", parse_query_node)
    builder.add_node("retrieve_courses_node", retrieve_courses_node)
    builder.add_node("constraint_critic_node", constraint_critic_node)
    builder.add_node("generate_recommendation_node", generate_recommendation_node)
    builder.add_node("human_review_node", human_review_node)

    # define mandatory sequential edges
    builder.add_edge(START, "parse_query_node")
    builder.add_edge("parse_query_node", "retrieve_courses_node")
    builder.add_edge("retrieve_courses_node", "constraint_critic_node")

    # conditional routing after the critic checks for violations
    builder.add_conditional_edges(
        "constraint_critic_node",
        route_after_critic,
        {
            "human_review_node": "human_review_node",
            "generate_recommendation_node": "generate_recommendation_node"
        }
    )

    # conditional routing after the human advisor makes a decision
    builder.add_conditional_edges(
        "human_review_node",
        route_after_human,
        {
            "generate_recommendation_node": "generate_recommendation_node",
            END: END
        }
    )

    # the recommendation node always leads to the end of the graph
    builder.add_edge("generate_recommendation_node", END)

    # initialize true persistence using sqlite database to store conversational state
    db_path = os.path.join(project_root, "checkpoints.sqlite")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    
    # compile the graph and set the hard interrupt before the human review node
    graph = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_review_node"]
    )
    
    return graph