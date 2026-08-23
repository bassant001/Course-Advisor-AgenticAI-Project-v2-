from typing import Any, Dict

from src.schemas import QueryFilterSchema


class QueryParser:
    """
    Converts structured data produced by an LLM
    into a validated QueryFilterSchema.
    """

    def parse(self, data: Dict[str, Any]) -> QueryFilterSchema:
        """
        Validate and normalize LLM-generated structured data.

        Raises:
            pydantic.ValidationError:
                If the data does not match QueryFilterSchema.
        """

        return QueryFilterSchema.model_validate(data)