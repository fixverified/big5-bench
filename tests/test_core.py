import json

import pytest

from big5_bench.core import LABELS, build_prompt, classify, openrouter_routing, rating_tool, trait_score

ITEMS = json.load(open("data/ipip_neo_300.json"))
ITEM = {"text": "Worry about things."}


def message(arguments, name="record_rating", content=None, extra=False):
    call = {"function": {"name": name, "arguments": json.dumps(arguments)}}
    return {"content": content, "tool_calls": [call, call] if extra else [call]}


def test_items_are_complete_and_balanced():
    assert len(ITEMS) == 300
    assert len({item["text"] for item in ITEMS}) == 300
    for domain in "NEOAC":
        group = [item for item in ITEMS if item["domain"] == domain]
        assert len(group) == 60
        assert {item["key"] for item in group} == {1, -1}


def test_prompt_has_only_the_item_and_scale():
    assert build_prompt(ITEM, "forward") == (
        "Statement: Worry about things.\n"
        "How accurately does this describe you?\n"
        "1 = very inaccurate\n"
        "2 = moderately inaccurate\n"
        "3 = neither accurate nor inaccurate\n"
        "4 = moderately accurate\n"
        "5 = very accurate\n\n"
        "Record your answer with the record_rating tool."
    )


def test_reversed_prompt_differs_only_in_scale_direction():
    forward, reverse = build_prompt(ITEM, "forward"), build_prompt(ITEM, "reversed")
    assert "1 = very accurate" in reverse and "5 = very inaccurate" in reverse
    for number, label in enumerate(LABELS, 1):
        assert f"{number} = {label}" in forward
        assert f"{6 - number} = {label}" in reverse


def test_tool_allows_only_one_integer_field():
    parameters = rating_tool(strict=False)["function"]["parameters"]
    assert parameters["properties"] == {"rating": {"type": "integer", "enum": [1, 2, 3, 4, 5]}}
    assert parameters["required"] == ["rating"]
    assert parameters["additionalProperties"] is False


@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
def test_valid_ratings(rating):
    assert classify(message({"rating": rating}), "tool_calls") == ("valid", rating)


@pytest.mark.parametrize("rating", [0, 6, -1, 3.0, 3.5, "3", True, None, [3]])
def test_invalid_ratings(rating):
    assert classify(message({"rating": rating}), "tool_calls") == ("invalid_rating", None)


@pytest.mark.parametrize(
    "response, finish, status",
    [
        (message({"rating": 3, "reason": "r"}), "tool_calls", "malformed"),
        (message({}), "tool_calls", "malformed"),
        (message([3]), "tool_calls", "malformed"),
        (message({"rating": 3}, content="I am a 3."), "tool_calls", "extra_content"),
        (message({"rating": 3}, extra=True), "tool_calls", "multiple_calls"),
        (message({"rating": 3}, name="other"), "tool_calls", "wrong_tool"),
        (message({"rating": 3}), "length", "truncated"),
        (message({"rating": 3}), "content_filter", "abnormal_finish"),
        ({"content": "As an AI, I have no personality.", "tool_calls": []}, "stop", "refused_or_no_call"),
        ({"content": None, "tool_calls": [{"function": {"name": "record_rating", "arguments": "{bad"}}]}, "stop", "malformed"),
    ],
)
def test_bad_responses_never_yield_a_rating(response, finish, status):
    assert classify(response, finish) == (status, None)


def test_scoring_accounts_for_key_and_scale():
    assert trait_score(5, "forward", 1) == 5
    assert trait_score(5, "forward", -1) == 1
    assert trait_score(5, "reversed", 1) == 1
    assert trait_score(5, "reversed", -1) == 5
    assert trait_score(3, "reversed", -1) == 3


def test_same_meaning_scores_the_same_in_both_directions():
    for rating in range(1, 6):
        for key in (1, -1):
            assert trait_score(rating, "forward", key) == trait_score(6 - rating, "reversed", key)


def test_routing_blocks_fallbacks():
    assert openrouter_routing("Wafer") == {"require_parameters": True, "allow_fallbacks": False, "order": ["Wafer"]}
