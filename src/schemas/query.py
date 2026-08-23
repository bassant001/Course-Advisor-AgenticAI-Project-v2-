from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re

VALID_LEVELS = {100, 200, 300, 400}

VALID_COURSE_TYPES = {
    "core",
    "elective",
    "any",
}

VALID_DAYS = {
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun",
}

DAY_MAPPING = {
    "monday": "Mon",
    "mon": "Mon",

    "tuesday": "Tue",
    "tue": "Tue",
    "tues": "Tue",

    "wednesday": "Wed",
    "wed": "Wed",

    "thursday": "Thu",
    "thu": "Thu",
    "thur": "Thu",
    "thurs": "Thu",

    "friday": "Fri",
    "fri": "Fri",

    "saturday": "Sat",
    "sat": "Sat",

    "sunday": "Sun",
    "sun": "Sun",
}
MAX_SANE_CREDITS_PER_COURSE = 6
MAX_CREDITS_PER_SEMESTER = 18
COURSE_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}[0-9]{3}$")
VALID_FORMATS = {"json", "markdown"}

class TimeRange(BaseModel):
    """
    Represents a time interval in 24-hour HH:MM format.
    """

    start: Optional[str] = None
    end: Optional[str] = None

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        try:
            hours, minutes = value.split(":")

            hours = int(hours)
            minutes = int(minutes)

            if not (0 <= hours <= 23):
                raise ValueError

            if not (0 <= minutes <= 59):
                raise ValueError

        except (ValueError, AttributeError):
            raise ValueError(
                "Time must use HH:MM format, for example '08:00' or '14:30'"
            )

        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.start is not None and self.end is not None:
            if self.start >= self.end:
                raise ValueError(
                    "Time range start must be earlier than end"
                )

        return self


class QueryFilterSchema(BaseModel):
    """
    Structured representation of a student's course request.

    This schema is produced by the Query Parser and is later
    consumed by the metadata filter and retrieval pipeline.
    """
    topic: Optional[str] = Field(
        default=None,
        description="Subject or topic the student wants to study."
    )

    course_code: Optional[str] = Field(
        default=None,
        description="Specific course code if explicitly requested."
    )

    level: Optional[int] = Field(
        default=None,
        description="Course level: 100, 200, 300, or 400."
    )

    department: Optional[str] = Field(
        default=None,
        description="Academic department requested by the student."
    )

    min_credits: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_SANE_CREDITS_PER_COURSE,
        description="Minimum acceptable course credits."
    )

    max_credits: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_SANE_CREDITS_PER_COURSE,
        description="Maximum acceptable course credits."
    )

    course_type: Optional[str] = Field(
        default=None,
        description="Whether the student wants core, elective, or any course."
    )

    completed_courses: List[str] = Field(
        default_factory=list,
        description="Courses already completed by the student."
    )

    current_courses: List[str] = Field(
        default_factory=list,
        description="Courses currently being taken."
    )

    current_credits: Optional[int] = Field(
        default=None,
        ge=0,
        le=MAX_CREDITS_PER_SEMESTER,
        description="Credits already taken this semester."
    )

    unavailable_days: List[str] = Field(
        default_factory=list,
        description="Days when the student cannot attend courses."
    )

    unavailable_time: Optional[TimeRange] = Field(
        default=None,
        description="Time range when the student cannot attend courses."
    )

    available_days: List[str] = Field(
        default_factory=list,
        description="Days when the student is available."
    )

    student_year: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Student's academic year."
    )

    graduating_soon: bool = Field(
        default=False,
        description="Whether the student indicates they are close to graduation."
    )

    requested_format: Optional[str] = Field(
        default=None,
        description="Requested output format such as JSON or Markdown."
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value not in VALID_LEVELS:
            raise ValueError(
                "level must be one of 100, 200, 300, or 400"
            )

        return value

    @field_validator("course_type")
    @classmethod
    def validate_course_type(
        cls,
        value: Optional[str]
    ) -> Optional[str]:

        if value is None:
            return value

        value = value.lower().strip()

        if value not in VALID_COURSE_TYPES:
            raise ValueError(
                "course_type must be one of: core, elective, any"
            )

        return value
    
    @field_validator("requested_format")
    @classmethod
    def validate_requested_format(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.lower().strip()
        if value not in VALID_FORMATS:
            raise ValueError(
                f"requested_format must be one of: {sorted(VALID_FORMATS)}"
            )
        return value

    @field_validator(
        "unavailable_days",
        "available_days"
    )
    @classmethod
    def validate_days(
        cls,
        values: List[str]
    ) -> List[str]:

        normalized = []

        for day in values:
            cleaned_day = day.strip().lower()

            if cleaned_day not in DAY_MAPPING:
                raise ValueError(
                    f"Invalid day '{day}'. "
                    "Please enter a valid day of the week."
                )

            normalized.append(DAY_MAPPING[cleaned_day])

        return normalized

    @field_validator(
        "completed_courses",
        "current_courses"
    )
    @classmethod
    def normalize_course_codes(
        cls,
        values: List[str]
    ) -> List[str]:

        normalized = []
        for value in values:
            cleaned = value.strip().upper()
            if not cleaned:
                continue

            if not COURSE_CODE_PATTERN.match(cleaned):
                raise ValueError(
                    f"'{cleaned}' is not a valid course code format "
                    "(expected e.g. 'CS101', 'MATH104')"
                )
            normalized.append(cleaned)

        return normalized

    @field_validator("course_code")
    @classmethod
    def normalize_course_code(
        cls,
        value: Optional[str]
    ) -> Optional[str]:

        if value is None:
            return value

        cleaned = value.strip().upper()
        if not COURSE_CODE_PATTERN.match(cleaned):
            raise ValueError(
                f"'{cleaned}' is not a valid course code format "
                "(expected e.g. 'CS101', 'MATH104')"
            )
        return cleaned

    @model_validator(mode="after")
    def validate_credit_range(self):

        if (
            self.min_credits is not None
            and self.max_credits is not None
            and self.min_credits > self.max_credits
        ):
            raise ValueError(
                "min_credits cannot be greater than max_credits"
            )

        return self
