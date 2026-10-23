"""Offline tests for the circuit breaker."""

from __future__ import annotations

from aiprobe.core.circuit_breaker import CircuitBreaker, CircuitPolicy, CircuitState


class FakeClock:
    def __init__(self) -> None:
        self.time = 0.0

    def __call__(self) -> float:
        return self.time


def test_circuit_breaker_transitions() -> None:
    clock = FakeClock()
    policy = CircuitPolicy(failure_threshold=2, cooldown=10.0, half_open_trials=1)
    cb = CircuitBreaker(policy, clock)

    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    clock.time = 11.0
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
