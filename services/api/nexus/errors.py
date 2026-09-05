"""Domain exceptions for Nexus.

Every failure that crosses a subsystem boundary is one of these. Bare ``Exception``
is never raised and never caught.
"""


class NexusError(Exception):
    """Base class for every Nexus domain error."""


class SpecValidationError(NexusError):
    """A PipelineSpec is structurally invalid and cannot be compiled."""


class CompilationError(NexusError):
    """A valid spec could not be compiled onto the requested target."""


class UnsupportedTargetError(CompilationError):
    """The requested vendor combination has no registered compiler."""


class PolicyViolation(NexusError):
    """An action was blocked by the policy engine.

    Carries the action and the level that would have been required, so the UI can
    explain precisely why something did not run.
    """

    def __init__(self, action: str, required_level: int, granted_level: int) -> None:
        self.action = action
        self.required_level = required_level
        self.granted_level = granted_level
        super().__init__(
            f"action {action!r} requires autonomy level {required_level}, "
            f"environment is at level {granted_level}"
        )
