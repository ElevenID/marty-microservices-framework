"""
Value objects for Morty service domain.

Value objects are immutable objects that represent descriptive aspects of the domain
with no conceptual identity. They are compared by their structural equality.
"""

import re


class ValueObject:
    """Base class for all value objects."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"


class Email(ValueObject):
    """Email value object with validation."""

    def __init__(self, value: str):
        if not value:
            raise ValueError("Email cannot be empty")

        # Basic email validation
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, value):
            raise ValueError(f"Invalid email format: {value}")

        self._value = value.lower().strip()

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value


class PhoneNumber(ValueObject):
    """Phone number value object with validation."""

    def __init__(self, value: str):
        if not value:
            raise ValueError("Phone number cannot be empty")

        # Remove all non-digit characters for validation
        digits_only = re.sub(r"\D", "", value)

        if len(digits_only) < 10:
            raise ValueError("Phone number must have at least 10 digits")

        self._value = value.strip()
        self._normalized = digits_only

    @property
    def value(self) -> str:
        return self._value

    @property
    def normalized(self) -> str:
        return self._normalized

    def __str__(self) -> str:
        return self._value


class PersonName(ValueObject):
    """Person name value object with first and last name."""

    def __init__(self, first_name: str, last_name: str):
        if not first_name or not first_name.strip():
            raise ValueError("First name cannot be empty")

        if not last_name or not last_name.strip():
            raise ValueError("Last name cannot be empty")

        self._first_name = first_name.strip()
        self._last_name = last_name.strip()

    @property
    def first_name(self) -> str:
        return self._first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"

    def __str__(self) -> str:
        return self.full_name


class TaskPriority(ValueObject):
    """Task priority value object with validation."""

    VALID_PRIORITIES = ["low", "medium", "high", "urgent"]

    def __init__(self, value: str):
        if not value:
            raise ValueError("Priority cannot be empty")

        normalized_value = value.lower().strip()
        if normalized_value not in self.VALID_PRIORITIES:
            raise ValueError(f"Priority must be one of: {self.VALID_PRIORITIES}")

        self._value = normalized_value

    @property
    def value(self) -> str:
        return self._value

    def is_higher_than(self, other: "TaskPriority") -> bool:
        """Check if this priority is higher than another."""
        priority_order = {p: i for i, p in enumerate(self.VALID_PRIORITIES)}
        return priority_order[self._value] > priority_order[other.value]

    def __str__(self) -> str:
        return self._value


class TaskStatus(ValueObject):
    """Task status value object with validation and state transitions."""

    VALID_STATUSES = ["pending", "in_progress", "completed", "cancelled"]

    VALID_TRANSITIONS = {
        "pending": ["in_progress", "cancelled"],
        "in_progress": ["completed", "pending", "cancelled"],
        "completed": [],  # Terminal state
        "cancelled": ["pending"],  # Can reopen cancelled tasks
    }

    def __init__(self, value: str):
        if not value:
            raise ValueError("Status cannot be empty")

        normalized_value = value.lower().strip()
        if normalized_value not in self.VALID_STATUSES:
            raise ValueError(f"Status must be one of: {self.VALID_STATUSES}")

        self._value = normalized_value

    @property
    def value(self) -> str:
        return self._value

    def can_transition_to(self, new_status: "TaskStatus") -> bool:
        """Check if this status can transition to a new status."""
        return new_status.value in self.VALID_TRANSITIONS[self._value]

    def is_terminal(self) -> bool:
        """Check if this is a terminal status (no further transitions allowed)."""
        return len(self.VALID_TRANSITIONS[self._value]) == 0

    def __str__(self) -> str:
        return self._value
