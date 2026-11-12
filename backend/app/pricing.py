from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

PER_MILLION = Decimal(1_000_000)
FAST_MODEL = "claude-haiku-5-5"
SMART_MODEL = "claude-sonnet-5-5"

# Each pipeline step runs in one role. Cost comes from the role, not the Foundry
# deployment name, so one deployment may serve both roles without ambiguity.
MODEL_FOR_ROLE = {"fast": FAST_MODEL, "smart": SMART_MODEL}


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


def cost_usd(model: str, *, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost of one model call in USD, computed exactly with Decimal."""
    if isinstance(input_tokens, bool) or isinstance(output_tokens, bool):
        raise TypeError("Token counts must be integers, not bool")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")

    if model not in PRICES:
        raise UnknownModelError(f"No price for model {model!r}")
    price = PRICES[model]

    in_rate, out_rate = price.input, price.output
    if price.long_prompt_over is not None and input_tokens > price.long_prompt_over:
        in_rate, out_rate = price.long_input, price.long_output
    return (input_tokens * in_rate + output_tokens * out_rate) / PER_MILLION


def cost_for_role(role: str, *, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost of one call made in the fast or smart role."""
    if role not in MODEL_FOR_ROLE:
        raise ValueError(f"Unknown model role {role!r}; expected one of {sorted(MODEL_FOR_ROLE)}")
    return cost_usd(MODEL_FOR_ROLE[role], input_tokens=input_tokens, output_tokens=output_tokens)


def total_cost(step_costs: Iterable[Decimal | str]) -> Decimal:
    """A report's cost is the sum of its steps. Only Decimal or decimal text is accepted,
    so floats can't add rounding error and bools or ints can't sneak in as dollars."""
    total = Decimal(0)
    for cost in step_costs:
        if not isinstance(cost, (Decimal, str)):
            raise TypeError(f"Step costs must be Decimal or decimal strings, got {type(cost).__name__}")
        value = Decimal(cost)
        if not value.is_finite() or value < 0:
            raise ValueError(f"Step cost must be a finite, non-negative amount, got {cost!r}")
        total += value
    return total
