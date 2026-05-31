class ProviderUnavailableError(Exception):
    """Raised when the AI provider cannot fulfill a request (quota, auth, etc.)."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code
