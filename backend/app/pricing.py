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

    def __post_init__(self) -> None:
        long_fields = (self.long_prompt_over, self.long_input, self.long_output)
        if any(f is None for f in long_fields) and any(f is not None for f in long_fields):
            raise ValueError("Set all long-prompt fields together, or none of them")


# Source: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-11).
# - Haiku 5.5 is priced by prompt length: prompts over 100,000 input tokens pay the higher rates.
# - Sonnet 5.5 has no long-context tier; the full 1M context is billed at standard rates.
# - Claude in Microsoft Foundry bills these standard USD rates (converted to CCUs at $0.01 each).
#   Not modelled: the 1.1x US Data Zone multiplier, prompt caching and batch discounts.
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
    if settings.model_fast == settings.model_smart:
        raise ValueError("MODEL_FAST and MODEL_SMART must name different deployments")
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
