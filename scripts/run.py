"""Rate every item on both scale directions. Saves progress and resumes from the output file."""

import argparse
import collections
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from big5_bench.core import SCALES, call_model

SEED = 20261101

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", required=True, help="Such as openai/gpt-6.1-sol or openrouter/z-ai/glm-5.3")
parser.add_argument("--provider", help="Pin OpenRouter to this host")
parser.add_argument("--out", required=True)
parser.add_argument("--passes", type=int, default=3)
parser.add_argument("--sample", type=int, help="Use this many items per facet, for a test run")
parser.add_argument("--threads", type=int, default=30)
parser.add_argument("--rpm", type=float, help="Limit requests per minute")
args = parser.parse_args()

items = json.load(open("data/ipip_neo_300.json"))
if args.sample:
    # Takes both scoring directions from each facet, because items are listed by key.
    by_facet = collections.defaultdict(list)
    for item in items:
        by_facet[item["facet"]].append(item)
    items = [item for group in by_facet.values() for item in (group[: args.sample - args.sample // 2] + group[-(args.sample // 2) :] if args.sample > 1 else group[:1])]
by_text = {item["text"]: item for item in items}

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
done = set()
if out.exists():
    for line in out.read_text().splitlines():
        row = json.loads(line)
        done.add((row["item"], row["scale"], row["repeat"]))
jobs = [
    (item["text"], scale, repeat)
    for item in items
    for scale in SCALES
    for repeat in range(args.passes)
    if (item["text"], scale, repeat) not in done
]
random.Random(SEED).shuffle(jobs)
lock = threading.Lock()
rate_lock = threading.Lock()
next_call = [0.0]


def wait_for_rate_limit():
    if not args.rpm:
        return
    with rate_lock:
        now = time.monotonic()
        start = max(now, next_call[0])
        next_call[0] = start + 60 / args.rpm
    time.sleep(start - now)


def work(job):
    text, scale, repeat = job
    wait_for_rate_limit()
    try:
        row = call_model(args.model, by_text[text], scale, repeat, provider=args.provider)
    except Exception:  # noqa: BLE001 - API errors get re-queued
        return job
    with lock, out.open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    return None


for _ in range(5):
    if not jobs:
        break
    with ThreadPoolExecutor(args.threads) as pool:
        jobs = [result for result in pool.map(work, jobs) if result is not None]
print("still failing:", len(jobs))

rows = [json.loads(line) for line in out.read_text().splitlines()]
print("rows:", len(rows), "status:", dict(collections.Counter(row["status"] for row in rows)))
print("hosts:", dict(collections.Counter(row["provider"] for row in rows)))
print("returned:", dict(collections.Counter(row["returned_model"] for row in rows)))
