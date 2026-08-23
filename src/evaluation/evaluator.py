from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.schemas import AdviceResponse


@dataclass
class EvaluationResult:
    """
    Stores evaluation metrics for the Course Advisor.
    """

    total_queries: int
    correct_queries: int

    true_positives: int
    false_positives: int
    false_negatives: int

    hard_constraint_violations: int

    precision: float
    recall: float

    @property
    def accuracy(self) -> float:
        if self.total_queries == 0:
            return 0.0

        return self.correct_queries / self.total_queries


class CourseAdvisorEvaluator:
    """
    Evaluates Course Advisor recommendations against
    the expected recommendations in queries.json.
    """

    def __init__(
        self,
        advisor_function: Callable[[str], AdviceResponse],
    ):
        """
        advisor_function:
            Receives a natural-language query and returns
            an AdviceResponse.
        """

        self.advisor_function = advisor_function

    def evaluate(
        self,
        queries: list[dict],
    ) -> EvaluationResult:

        total_queries = len(queries)

        correct_queries = 0

        true_positives = 0
        false_positives = 0
        false_negatives = 0

        hard_constraint_violations = 0

        for query in queries:

            nl_query = query["nl_query"]

            expected = set(
                query.get("should_recommend", [])
            )

            forbidden = set(
                query.get("should_not_recommend", [])
            )

            response = self.advisor_function(nl_query)

            actual = {
                recommendation.course_code
                for recommendation in response.recommendations
            }

            # -------------------------
            # Precision / Recall
            # -------------------------

            true_positives += len(
                actual & expected
            )

            false_positives += len(
                actual - expected
            )

            false_negatives += len(
                expected - actual
            )

            # -------------------------
            # Hard constraint violations
            # -------------------------

            violations = actual & forbidden

            hard_constraint_violations += len(
                violations
            )

            # -------------------------
            # Query-level correctness
            # -------------------------

            if actual == expected:
                correct_queries += 1

        precision_denominator = (
            true_positives + false_positives
        )

        recall_denominator = (
            true_positives + false_negatives
        )

        precision = (
            true_positives / precision_denominator
            if precision_denominator > 0
            else 0.0
        )

        recall = (
            true_positives / recall_denominator
            if recall_denominator > 0
            else 0.0
        )

        return EvaluationResult(
            total_queries=total_queries,
            correct_queries=correct_queries,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            hard_constraint_violations=hard_constraint_violations,
            precision=precision,
            recall=recall,
        )