import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from src.schemas import QueryFilterSchema, AdviceResponse

class AgentState(TypedDict):
    """
    the shared memory that moves between nodes in the graph
    """
    # chat history + add the old on new messages to remember the context
    messages: Annotated[list, add_messages]
    
    # student query
    user_query: str
    
    # turn the query into our json schema
    parsed_filters: Optional[QueryFilterSchema]
    
    # the courses we retrieved from the retrieval function
    retrieved_courses: List[Dict[str, Any]]
    
    # if the student was rejected for some reason, it writes it
    violations: List[str]
    
    # human in the loop interfere
    # if the student is rejected -> true else false
    requires_human_review: bool

    human_decision: Optional[str]
    parsing_failed: bool
    integrity_flags: List[str]
    
    # no conflict or rejection -> agent response
    final_advice: Optional[AdviceResponse]

    total_input_tokens: Annotated[int, operator.add]
    total_output_tokens: Annotated[int, operator.add]