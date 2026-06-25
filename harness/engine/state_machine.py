from __future__ import annotations

from enum import Enum, auto


class EngineState(Enum):
    WAITING_INPUT = auto()
    WAITING_CONFIRMATION = auto()
    WAITING_INTERRUPT = auto()   # paused for a user interrupt (e.g. ask_user)
    RUNNING = auto()
    COMPLETED = auto()
    ERROR = auto()


# Legal transitions: from_state -> set of allowed to_states
_TRANSITIONS: dict[EngineState, set[EngineState]] = {
    EngineState.WAITING_INPUT: {
        EngineState.RUNNING,
        EngineState.ERROR,
    },
    EngineState.WAITING_CONFIRMATION: {
        EngineState.RUNNING,
        EngineState.WAITING_INPUT,
        EngineState.ERROR,
    },
    EngineState.WAITING_INTERRUPT: {
        EngineState.RUNNING,   # user replied, resume
        EngineState.WAITING_INPUT,  # user skipped, drop the partial round
        EngineState.ERROR,
    },
    EngineState.RUNNING: {
        EngineState.WAITING_INPUT,
        EngineState.WAITING_CONFIRMATION,
        EngineState.WAITING_INTERRUPT,
        EngineState.COMPLETED,
        EngineState.ERROR,
    },
    EngineState.COMPLETED: {
        EngineState.WAITING_INPUT,   # session reuse: start a new task
    },
    EngineState.ERROR: {
        EngineState.WAITING_INPUT,   # recovery
    },
}


class IllegalTransitionError(RuntimeError):
    pass


class StateMachine:
    def __init__(self, initial: EngineState = EngineState.WAITING_INPUT) -> None:
        self._state = initial

    @property
    def state(self) -> EngineState:
        return self._state

    def transition(self, to: EngineState) -> None:
        allowed = _TRANSITIONS.get(self._state, set())
        if to not in allowed:
            raise IllegalTransitionError(
                f"Illegal transition: {self._state.name} -> {to.name}"
            )
        self._state = to

    def is_terminal(self) -> bool:
        return self._state in (EngineState.COMPLETED, EngineState.ERROR)
