"""Score one or more vote files. Domain scores run 1-5, where 3 is the midpoint."""

import argparse
import collections
import json
import random
import statistics

DOMAINS = {"O": "Openness", "C": "Conscientiousness", "E": "Extraversion", "A": "Agreeableness", "N": "Neuroticism"}
BOOTSTRAPS = 2000
SEED = 20261101


def item_means(rows):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["item"]].append(row["score"])
    return {item: statistics.mean(scores) for item, scores in grouped.items()}


def interval(values, rng):
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAPS))
    return means[int(0.025 * BOOTSTRAPS)], means[int(0.975 * BOOTSTRAPS)]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("files", nargs="+")
args = parser.parse_args()
rng = random.Random(SEED)

for path in args.files:
    all_rows = [json.loads(line) for line in open(path)]
    rows = [row for row in all_rows if row["status"] == "valid"]
    print(f"\n===== {all_rows[0]['model']} ({path})")
    print(f"  valid {len(rows)}/{len(all_rows)}; status {dict(collections.Counter(r['status'] for r in all_rows))}")
    for domain, name in DOMAINS.items():
        means = list(item_means([r for r in rows if r["domain"] == domain]).values())
        low, high = interval(means, rng)
        print(f"  {name}: {statistics.mean(means):.2f} (95% CI {low:.2f}-{high:.2f}, items {len(means)})")
    # Agreement is keyed out of domain scores, so these show what scoring would otherwise hide.
    accuracy = [r["rating"] if r["scale"] == "forward" else 6 - r["rating"] for r in rows]
    print(f"  mean claimed accuracy, all items: {statistics.mean(accuracy):.2f} (3 means no tendency to agree)")
    for key, label in ((1, "+ keyed"), (-1, "- keyed")):
        group = [r["rating"] if r["scale"] == "forward" else 6 - r["rating"] for r in rows if r["key"] == key]
        print(f"    {label}: {statistics.mean(group):.2f}")
    print("  raw rating by scale:", {s: round(statistics.mean(r["rating"] for r in rows if r["scale"] == s), 2) for s in ("forward", "reversed")})
    print("  raw ratings used:", dict(sorted(collections.Counter(r["rating"] for r in rows).items())))
    spreads = collections.defaultdict(list)
    for row in rows:
        spreads[(row["item"], row["scale"])].append(row["score"])
    same = [len(set(scores)) == 1 for scores in spreads.values() if len(scores) > 1]
    if same:
        print(f"  identical across passes: {sum(same)}/{len(same)} item-scale pairs")
    flips = collections.defaultdict(dict)
    for key, scores in spreads.items():
        flips[key[0]][key[1]] = statistics.mean(scores)
    gaps = [abs(pair["forward"] - pair["reversed"]) for pair in flips.values() if len(pair) == 2]
    if gaps:
        print(f"  mean gap between scale directions: {statistics.mean(gaps):.2f}")
