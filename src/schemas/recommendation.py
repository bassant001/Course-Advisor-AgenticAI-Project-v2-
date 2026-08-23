from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator
from .query import COURSE_CODE_PATTERN


class Recommendation(BaseModel):
    """
    A validated course recommendation.

    The recommendation should only be created after
    hard constraints have been checked by the pipeline.
    """

    course_code: str = Field(
        min_length=1,
        description="Recommended course code."
    )

    course_title: str = Field(
        min_length=1,
        description="Official course title."
    )

    satisfies: List[str] = Field(
        default_factory=list,
        description=(
            "Reasons explaining why the course satisfies "
            "the student's request."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Recommendation confidence between 0 and 1."
    )

    @field_validator("course_code")
    @classmethod
    def validate_course_code_format(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not COURSE_CODE_PATTERN.match(cleaned):
            raise ValueError(
                f"'{cleaned}' is not a valid course code format "
                "(expected e.g. 'CS101', 'MATH104')"
            )
        return cleaned


# NEW
class AdviceMetrics(BaseModel):
    latency_ms: float = Field(
        ge=0,
        description="Total pipeline latency in milliseconds."
    )

    input_tokens: int = Field(
        ge=0,
        description="Number of input tokens used."
    )

    output_tokens: int = Field(
        ge=0,
        description="Number of output tokens generated."
    )

    estimated_cost: float = Field(
        ge=0,
        description="Estimated execution cost."
    )

    retries: int = Field(
        ge=0,
        description="Number of retries during execution."
    )

    agent_steps: int = Field(
        ge=0,
        description="Number of agent/graph execution steps."
    )


class AdviceResponse(BaseModel):
    """
    Final structured response returned by the advisor.
    """

    recommendations: List[Recommendation] = Field(
        default_factory=list
    )

    violations: List[str] = Field(
        default_factory=list,
        description="Detected hard-constraint violations."
    )

    requires_human_review: bool = Field(
        default=False,
        description="Whether a human advisor must review the result."
    )

    message: str = Field(
        min_length=1,
        description="Human-readable explanation of the result."
    )

    # NEW
    metrics: AdviceMetrics | None = Field(
        default=None,
        description="Execution metrics for the recommendation pipeline."
    )

    @model_validator(mode="after")
    def enforce_human_review_on_violations(self):
        if self.violations and not self.requires_human_review:
            self.requires_human_review = True
        return self