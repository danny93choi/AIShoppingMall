from dataclasses import dataclass
from decimal import Decimal

from commerce_agent.integrations.llm.errors import LLMBudgetExceededError


@dataclass(slots=True)
class CostBudgetGuard:
    maximum_usd: Decimal
    spent_usd: Decimal = Decimal("0")

    def reserve(self, estimated_usd: Decimal) -> None:
        if estimated_usd < 0:
            raise ValueError("estimated cost cannot be negative")
        if self.spent_usd + estimated_usd > self.maximum_usd:
            attempted = self.spent_usd + estimated_usd
            raise LLMBudgetExceededError(
                f"LLM run budget exceeded: {attempted} > {self.maximum_usd} USD"
            )
        self.spent_usd += estimated_usd
