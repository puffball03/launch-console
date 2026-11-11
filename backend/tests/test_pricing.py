from decimal import Decimal

import pytest

from app.pricing import cost_usd


def test_haiku_cost_is_exact():
    # 1,000 in x $0.10/M + 500 out x $0.50/M
    assert cost_usd("claude-haiku-5-5", input_tokens=1000, output_tokens=500) == Decimal("0.00035")


def test_sonnet_cost_is_exact():
    # 1,000 in x $2/M + 500 out x $10/M
    assert cost_usd("claude-sonnet-5-5", input_tokens=1000, output_tokens=500) == Decimal("0.007")


def test_cost_is_a_decimal_not_a_float():
    assert isinstance(cost_usd("claude-sonnet-5-5", input_tokens=3, output_tokens=7), Decimal)


def test_sonnet_one_million_tokens_each_way_costs_the_list_price():
    assert cost_usd("claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=1_000_000) == Decimal("12.00")


def test_haiku_one_million_output_tokens_costs_the_list_price():
    # Input kept at the 100K threshold so the base rate applies: $0.01 + $0.50
    assert cost_usd("claude-haiku-5-5", input_tokens=100_000, output_tokens=1_000_000) == Decimal("0.51")


def test_zero_tokens_cost_nothing():
    assert cost_usd("claude-sonnet-5-5", input_tokens=0, output_tokens=0) == Decimal("0")


def test_unknown_model_is_an_error_not_free():
    from app.pricing import UnknownModelError

    with pytest.raises(UnknownModelError, match="gpt-4"):
        cost_usd("gpt-4", input_tokens=10, output_tokens=10)


@pytest.mark.parametrize(("inp", "out"), [(-1, 0), (0, -1)])
def test_negative_token_counts_are_rejected(inp, out):
    with pytest.raises(ValueError):
        cost_usd("claude-haiku-5-5", input_tokens=inp, output_tokens=out)


def test_foundry_deployment_names_resolve_to_their_model():
    aliases = {"mc-fast": "claude-haiku-5-5", "mc-smart": "claude-sonnet-5-5"}

    assert cost_usd("mc-fast", input_tokens=1000, output_tokens=500, aliases=aliases) == Decimal("0.00035")
    assert cost_usd("mc-smart", input_tokens=1000, output_tokens=500, aliases=aliases) == Decimal("0.007")


def test_aliases_from_settings_cover_both_deployments(make_settings):
    from app.pricing import aliases_from_settings

    settings = make_settings(MODEL_FAST="mc-fast", MODEL_SMART="mc-smart")

    assert aliases_from_settings(settings) == {
        "mc-fast": "claude-haiku-5-5",
        "mc-smart": "claude-sonnet-5-5",
    }


def test_haiku_prompt_of_exactly_100k_tokens_uses_the_base_rate():
    # 100,000 x $0.10/M + 1,000 x $0.50/M
    assert cost_usd("claude-haiku-5-5", input_tokens=100_000, output_tokens=1000) == Decimal("0.0105")


def test_haiku_prompt_over_100k_tokens_uses_the_long_prompt_rate():
    # 200,000 x $0.50/M + 1,000 x $2.50/M
    assert cost_usd("claude-haiku-5-5", input_tokens=200_000, output_tokens=1000) == Decimal("0.1025")


def test_report_total_is_the_sum_of_its_step_costs():
    from app.pricing import total_cost

    # As stored per trace step: model calls plus $0 code steps.
    steps = ["0.00035", "0", Decimal("0.007"), "0.00035"]

    assert total_cost(steps) == Decimal("0.0077")


def test_report_with_no_steps_costs_nothing():
    from app.pricing import total_cost

    assert total_cost([]) == Decimal("0")


def test_total_refuses_floats_so_rounding_errors_cannot_creep_in():
    from app.pricing import total_cost

    with pytest.raises(TypeError):
        total_cost([0.1, 0.2])


def test_sonnet_has_no_long_prompt_rate():
    # 200,000 x $2/M, verified against the pricing page: no long-context tier for Sonnet 5.5
    assert cost_usd("claude-sonnet-5-5", input_tokens=200_000, output_tokens=0) == Decimal("0.4")


def test_same_deployment_name_for_both_models_is_rejected():
    from app.config import Settings
    from app.pricing import aliases_from_settings

    settings = Settings(
        llm_provider="fake",
        foundry_api_key="",
        foundry_resource="",
        model_fast="mc-shared",
        model_smart="mc-shared",
        db_path="unused.db",
    )

    with pytest.raises(ValueError, match="MODEL_FAST and MODEL_SMART"):
        aliases_from_settings(settings)


@pytest.mark.parametrize(
    "partial",
    [
        {"long_prompt_over": 100_000},
        {"long_prompt_over": 100_000, "long_input": Decimal("0.5")},
        {"long_input": Decimal("0.5"), "long_output": Decimal("2.5")},
    ],
)
def test_long_prompt_fields_must_be_set_together(partial):
    from app.pricing import Price

    with pytest.raises(ValueError, match="long-prompt"):
        Price(input=Decimal("0.1"), output=Decimal("0.5"), **partial)
