"""Circuit breaker implementation to prevent hammering failing targets."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    failure_threshold: int = 5
    cooldown: float = 60.0
    half_open_trials: int = 1


class CircuitBreaker:
    """Tracks failures and opens the circuit to prevent cascading failures."""

    def __init__(
        self,
        policy: CircuitPolicy | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.policy = policy or CircuitPolicy()
        self.clock = clock or (lambda: __import__("time").time())

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_state_change = self.clock()
        self._half_open_successes = 0

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self.clock() - self._last_state_change >= self.policy.cooldown
        ):
            self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        self._state = new_state
        self._last_state_change = self.clock()
        if new_state == CircuitState.CLOSED:
            self._failures = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_successes = 0

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.policy.half_open_trials:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            self._failures = 0

    def record_failure(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            self._failures += 1
            if self._failures >= self.policy.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN
