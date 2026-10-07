class InvestigationError(Exception):
    """Base class for expected investigation failures."""


class GroundingViolation(InvestigationError):
    """The report cites evidence that the tools did not return."""


class ToolCallError(InvestigationError):
    """The model asked for an unknown tool or passed invalid arguments."""


class LoopLimitExceeded(InvestigationError):
    """The model kept requesting tools past the configured limits."""


class InvalidStructuredOutput(InvestigationError):
    """The report model did not return a valid InvestigationReport."""


class DeadlineExceeded(InvestigationError):
    """The whole investigation ran past its deadline."""


class ProviderFailure(InvestigationError):
    """The model provider could not be reached or failed to answer."""
