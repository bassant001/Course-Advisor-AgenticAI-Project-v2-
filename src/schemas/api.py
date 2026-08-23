
from pydantic import BaseModel, Field

class AdviceRequest(BaseModel):
    # HTTP request received by the /advise endpoint.
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Natural-language course advising request."
    )

class HumanReviewRequest(BaseModel):
    # HTTP request for the academic advisor to approve or reject
    thread_id: str = Field(
        description="The unique ID of the paused graph thread."
    )
    decision: str = Field(
        description="Must be either 'APPROVED' or 'REJECTED'."
    )