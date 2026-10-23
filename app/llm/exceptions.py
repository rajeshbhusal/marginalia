class LLMError(Exception):
    """A model call failed. Messages are written to be shown to learners."""


class LLMConfigurationError(LLMError):
    """Missing or rejected credentials, unknown model, or a misconfigured provider."""


class LLMRateLimitError(LLMError):
    pass


class LLMRefusalError(LLMError):
    """The model (or its safety classifiers) declined the request."""


class LLMOutputError(LLMError):
    """The response was cut off or didn't match the requested format."""
