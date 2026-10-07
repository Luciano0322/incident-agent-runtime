class InvestigationError(Exception):
    """Base class for expected investigation failures."""


class GroundingViolation(InvestigationError):
    """The report cites evidence that the tools did not return."""
