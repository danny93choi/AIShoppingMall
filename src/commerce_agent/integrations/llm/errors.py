class LLMError(Exception):
    """Base error for provider-independent LLM failures."""


class LLMConfigurationError(LLMError):
    pass


class LLMStructuredOutputError(LLMError):
    pass


class LLMBudgetExceededError(LLMError):
    pass
