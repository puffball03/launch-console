from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings

PER_MILLION = Decimal(1_000_000)
FAST_MODEL = "claude-haiku-5-5"
SMART_MODEL = "claude-sonnet-5-5"


class UnknownModelError(KeyError):
    pass


@dataclass(frozen=True)
class Price:
    """USD per million tokens. Above `long_prompt_over` input tokens, the long-prompt rates apply."""

    input: Decimal
    output: Decimal
    long_prompt_over: int | None = None
    long_input: Decimal | None = None
    long_output: Decimal | None = None


# Anthropic list prices; Claude on Microsoft Foundry bills at the same standard rates.
PRICES: dict[str, Price] = {
    FAST_MODEL: Price(
        input=Decimal("0.10"),
        output=Decimal("0.50"),
        long_prompt_over=100_000,
        long_input=Decimal("0.50"),
        long_output=Decimal("2.50"),
    ),
    SMART_MODEL: Price(input=Decimal("2.00"), output=Decimal("10.00")),
}


def aliases_from_settings(settings: Settings) -> dict[str, str]:
    """Foundry deployment names map back to the model they serve."""
    return {settings.model_fast: FAST_MODEL, settings.model_smart: SMART_MODEL}


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    aliases: Mapping[str, str] | None = None,
) -> Decimal:
    """Cost of one model call in USD, computed exactly with Decimal."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")

    resolved = (aliases or {}).get(model, model)
    if resolved not in PRICES:
        raise UnknownModelError(f"No price for model {model!r}")
    price = PRICES[resolved]

    in_rate, out_rate = price.input, price.output
    if price.long_prompt_over is not None and input_tokens > price.long_prompt_over:
        in_rate, out_rate = price.long_input, price.long_output
    return (input_tokens * in_rate + output_tokens * out_rate) / PER_MILLION


def total_cost(step_costs: Iterable[Decimal | str]) -> Decimal:
    """A report's cost is the sum of its steps. Floats are refused so rounding can't creep in."""
    total = Decimal(0)
    for cost in step_costs:
        if isinstance(cost, float):
            raise TypeError("Step costs must be Decimal or decimal strings, not float")
        total += Decimal(cost)
    return total
