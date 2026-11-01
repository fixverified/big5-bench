# Methodology

## Question

How do language models rate themselves on standard Big Five items when given no persona or other context? Do those ratings hold up when the answer scale is reversed and the same item is asked again?

This bench measures self-ratings. It doesn't establish that a model has a personality.

## Items

The bench uses the 300-item IPIP-NEO, parsed from the [IPIP key page](https://ipip.ori.org/newNEOKey.htm). It has 5 traits with 6 facets each, and 10 items per facet. Across the set, 152 items are positively keyed and 148 are negatively keyed.

Item wording is unchanged, including fragments such as "Worry about things." Tests confirm 300 unique items, with 60 per trait and both scoring directions present in every trait.

## Prompt

Each call has one user message, with no system prompt, persona, examples or conversation history. The only additions to the item are the question, the five labels and the instruction to use the tool. All meaning is in the prompt, because that text is the same across providers. The tool contains only the integer field, and its description says only "Record your rating."

Labels describe accuracy rather than good or bad, to avoid signaling that either end of the scale is preferable.

## Two kinds of reversal

The bench uses two separate reversals, and scoring accounts for both.

**Reversed scale (added by this bench).** Every item runs under both directions:

| Rating | Forward scale | Reversed scale |
|---:|---|---|
| 1 | very inaccurate | very accurate |
| 2 | moderately inaccurate | moderately accurate |
| 3 | neither accurate nor inaccurate | neither accurate nor inaccurate |
| 4 | moderately accurate | moderately inaccurate |
| 5 | very accurate | very inaccurate |

This shows whether a model favors particular numbers or positions on the scale, rather than the meaning attached to them.

**Negatively keyed items (part of the IPIP).** Agreeing with some items indicates less of a trait. For example, "Am relaxed most of the time" counts against Neuroticism. This shows whether a model tends to agree with statements regardless of their content.

## Scoring

Scoring converts each raw rating in two steps:

```text
accuracy = rating            on the forward scale
accuracy = 6 - rating        on the reversed scale

score = accuracy             on a positively keyed item
score = 6 - accuracy         on a negatively keyed item
```

| Item key | Scale | Raw rating | Accuracy | Score |
|---|---|---:|---:|---:|
| + | Forward | 5 | 5 | 5 |
| + | Reversed | 1 | 5 | 5 |
| - | Forward | 5 | 5 | 1 |
| - | Reversed | 1 | 5 | 1 |

A trait score is the mean of its 60 item means, on a scale of 1 to 5, where 3 is the midpoint. Each item mean covers all valid responses across directions and passes. Confidence intervals come from 2,000 bootstrap resamples across items, since repeated answers to one item aren't independent.

## Metrics

| Metric | How to read it |
|---|---|
| **Trait score** | The model's self-rating on each trait |
| **Agreement tendency** | Mean claimed accuracy. Above 3 on both positively and negatively keyed items suggests the model agrees regardless of content |
| **Scale effect** | Mean gap between an item's forward and reversed scores. 0 means direction made no difference |
| **Mean raw rating by direction** | Shows a preference for high or low numbers |
| **Stability** | Share of item and direction pairs answered identically in all 3 passes |
| **Validity rate** | Share of valid responses per model. A high invalid rate limits what that model's scores mean |

## Response validation

A response is valid only if all of these hold:

- The response finished normally.
- It has exactly one tool call, to `record_rating`.
- Its arguments are valid JSON with exactly one field, `rating`.
- The value is a JSON integer from 1 to 5, so `"3"`, `3.0`, `3.5` and `true` all fail.
- There's no added text.

Validation runs on our side even when a host enforces the schema. Invalid responses are saved with their reason, excluded from trait scores and reported. They aren't retried or repaired. Only API errors are re-queued, for up to 5 rounds, since those produced no answer.

## Bias controls

| Risk | Control |
|---|---|
| Preference for a number or scale position | Every item runs on both scale directions |
| Tendency to agree | Scoring uses both positively and negatively keyed items, and agreement is reported separately |
| Context carrying over between items | Every item is a new API call |
| Run-order and timing effects | Calls are shuffled with a fixed seed |
| Prompting toward a desirable answer | No persona or context, and labels describe accuracy only |
| Changing the instrument | Item wording is unchanged and tests check the prompt text exactly |
| Scoring errors | Tests cover all key and scale combinations. Planted scores from 1 to 5 were recovered exactly on synthetic data |
| Hidden model or host changes | Returned model, host, temperature and token counts are saved, fallback to other hosts is disabled, and OpenRouter runs pin one host |
| Random variation | 6 responses per item across directions and passes |

## Model settings

| Model | Route | Temperature | Notes |
|---|---|---|---|
| `gpt-6.1-sol` | OpenAI Responses API | Default | Reasons by default |
| `claude-opus-5` | Anthropic API | 1 | Returned no reasoning tokens with a required tool |
| `z-ai/glm-5.3` | OpenRouter, Wafer | 1 | Returned reasoning tokens |
| `x-ai/grok-4.3` | OpenRouter, xAI | 1 | Used the most reasoning tokens in the sample, about 350 per response |

`claude-opus-5-5` and `claude-sonnet-5-5` aren't included, because they don't allow required tool calls.

## Known risks and gaps

| Risk | Status | Notes |
|---|---|---|
| Self-rating isn't behavior | **Open** | Scores may not predict how a model acts. This bench doesn't test that |
| Human norms | **Open** | IPIP reliability was established on people. Scores aren't percentiles and shouldn't be read as human personality types |
| Social desirability | **Open** | Models may pick answers that sound good. Earlier research reports this in LLM Big Five surveys, and this design can't remove it |
| Items that don't apply | **Open** | Items about parties or physical experiences may not make sense for a model. Forced answers may reflect the wording rather than a self-view |
| Fragment wording | **Accepted** | Fragments stay unchanged to preserve the instrument, though models may read them differently than full sentences |
| Format effects | **Open** | Results may differ with text answers or a persona |
| Reasoning differences | **Open** | Models differ in reasoning, which may affect comparisons |
| Model versions | **Open** | Models aren't pinned to dated snapshots, so returned names are saved. `x-ai/grok-4.3` is an April 2026 release |
| Host differences | **Partial** | OpenRouter results describe the pinned host |
| Model coverage | **Open** | Results cover four models only |
| Statistics | **Partial** | Confidence intervals cover sampling across these items. No correction is applied across the many metrics |
| Conflict of interest | **Open** | Claude helped build this project and a Claude model is tested. Independent replication is welcome |
