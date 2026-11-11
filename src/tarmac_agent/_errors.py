class TarmacToolError(Exception):
    """Raised when a Tarmac tool call or API request fails.

    ``code`` is stable (e.g. ``INVALID_INPUT``, ``UNSUPPORTED_TOKEN``, ``TOOL_LIMIT``,
    ``RUN_NOT_ACTIVE``, ``AUTH_REQUIRED``); ``message`` is human-readable.
    """

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
