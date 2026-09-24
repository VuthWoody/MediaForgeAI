"""Exception hierarchy for MediaForge AI."""


class MediaForgeError(Exception):
    """Base exception for all MediaForge AI errors."""

    def __init__(self, message: str = "", *args: object) -> None:
        super().__init__(message, *args)
        self.message = message


class CancelledError(MediaForgeError):
    """Raised when an operation is cancelled via CancellationToken."""


class EngineUnavailableError(MediaForgeError):
    """Raised when a requested engine or backend model is not available."""


class EngineError(MediaForgeError):
    """Raised when an internal processing engine fails execution."""


class ProviderError(MediaForgeError):
    """Raised when an external AI provider (Gemini, DeepSeek, Qwen, etc.) fails."""


class NetworkError(MediaForgeError):
    """Raised when a network operation or download fails."""


class ValidationError(MediaForgeError):
    """Raised when input parameters, configurations, or schemas fail validation."""
