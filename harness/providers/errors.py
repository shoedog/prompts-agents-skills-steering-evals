"""Shared exception type for the CLI-wrapping providers."""


class ProviderError(Exception):
    """Raised when a provider CLI invocation fails or times out.

    Carries the tail of the subprocess's stderr (if any) so callers can log
    or surface the underlying CLI failure without re-running the process.
    """

    def __init__(self, message: str, stderr_tail: str = ""):
        super().__init__(message)
        self.stderr_tail = stderr_tail
