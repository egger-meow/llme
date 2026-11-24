"""Build the local meeting report from the completed HugAgent participant runs."""
import csv
import json
import random
import runpy
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean

from .audit import inspect_run
from .run import ARMS, PACKAGE, RELEASE, ROOT, records, verify

RUNS = {f"P{n:02}": f"P{n:02}" for n in [*range(1, 11), 44]}
RUNS.update(P01="P01-resumed", P07="p07-recovered")
EXPERIMENTS = ROOT / "ref/experiments"
OUTPUT = EXPERIMENTS / "cohort"
ASSETS = Path(__file__).with_name("explorer")


def read_json(path):
    return json.loads(path.read_text(encoding="utf8"))


def get_sources():
    manifest = read_json(PACKAGE / "manifest.json")
    verify(PACKAGE / "items.csv", manifest["files"]["items.csv"])
    with (PACKAGE / "items.csv").open(encoding="utf8") as file:
        routes = {r["item_id"]: r for r in csv.DictReader(file)}
    source = manifest["source"]
    scorer = RELEASE / "hugagent_eval.py"
    verify(scorer, source["scorer_sha256"])
    items = {}
    for name, digest in source["files"].items():
        path = RELEASE / "data" / name
        verify(path, digest)
        items.update((r["item_id"], r) for r in records(path))
    return routes, items, runpy.run_path(str(scorer))


def paired_intervals(questions):
    """Domain-macro differences, resampling whole participants with all arms together."""
    people = sorted({q["person"] for q in questions})
    rng = random.Random(20261123)
    draws = [rng.choices(people, k=len(people)) for _ in range(5000)]
    result = []
    for task, metric in (("T1", "hit"), ("T2", "error")):
        subset = [q for q in questions if q["task"] == task]
        domains = sorted({q["topic"] for q in subset})
        for left, right in combinations(("graph", "flat", "raw"), 2):
            cells = defaultdict(list)
            for q in subset:
                cells[q["topic"], q["person"]].append(q["arms"][left][metric] - q["arms"][right][metric])
            totals = {k: (sum(values), len(values)) for k, values in cells.items()}
            def effect(draw):
                means = []
                for domain in domains:
                    pairs = [totals.get((domain, person), (0, 0)) for person in draw]
                    count = sum(n for _, n in pairs)
                    if not count:
                        return None
                    means.append(sum(v for v, _ in pairs) / count)
                return mean(means) * (100 if metric == "hit" else 1)
            values = sorted(v for draw in draws if (v := effect(draw)) is not None)
            result.append(dict(task=task, left=left, right=right, delta=effect(people),
                               lo=values[int(.025*len(values))], hi=values[int(.975*len(values))-1],
                               draws=len(values)))
    return result


def collect():
    routes, items, official = get_sources()
    questions, scopes, runs = [], {}, {}
    predictions = {arm: {} for arm in ARMS}
    for person, name in RUNS.items():
        folder = EXPERIMENTS / name
        audit = inspect_run(folder, folder / "report")
        usage = read_json(folder / "usage.json")
        if usage["offline_fixture"] or audit["model"] == "離線合成回覆驗證":
            raise ValueError(f"Fixture in cohort: {name}")
        selected = [it for it in items.values() if it["participant_id"] == person]
        expected = {it["item_id"] for it in selected}
        observed = [q["id"] for s in audit["rows"] for q in s["questions"]]
        if set(observed) != expected or len(observed) != len(expected):
            raise ValueError(f"Different participant or incomplete selection: {name}")
        stored = read_json(folder / "pilot-scores.json")
        for arm in ARMS:
            saved = {q["id"]: q["answers"].get(arm) for s in audit["rows"] for q in s["questions"]}
            exported = list(records(folder / f"{arm}.jsonl"))
            if len(exported) != len(saved) or {r["item_id"]: r["response"] for r in exported} != saved:
                raise ValueError(f"Response export mismatch: {name}/{arm}")
            values = {iid: official["extract"](items[iid], text) for iid, text in saved.items()}
            if official["score"](selected, values) != stored[arm]:
                raise ValueError(f"Pilot scores differ: {name}/{arm}")
            predictions[arm].update(values)
        runs[person] = dict(name=name, model=audit["model"], usage=usage)
        for s in audit["rows"]:
            sid = s["id"]
            if sid in scopes:
                raise ValueError(f"Scope reused across participants: {sid}")
            topic = routes[s["questions"][0]["id"]]["topic"]
            scopes[sid] = dict(person=person, topic=topic, history=s["history"], edits=s["edits"],
                               status=s.get("recovery", {}).get("status", s["status"]),
                               issues=s.get("recovery", {}).get("issues", []))
            for q in s["questions"]:
                iid = q["id"]
                it, route = items[iid], routes[iid]
                t1 = route["task"] == "T1"
                arms = {}
                for arm in ARMS:
                    value = predictions[arm][iid]
                    single = official["score"]([it], {iid: value})["overall"]
                    arms[arm] = dict(text=q["answers"].get(arm), parsed=value,
                                     original=q["delivery"].get(arm, {}).get("text"),
                                     finish=q["delivery"].get(arm, {}).get("finish"),
                                     hit=bool(single["bsi_acc" if t1 else "bdu_acc"]),
                                     error=single.get("bdu_mae"))
                questions.append(dict(id=iid, person=person, topic=topic, task=route["task"],
                                      measure=route["measure"], scope=sid, prompt=q["prompt"],
                                      options=it.get("answer_options"), scale=it.get("scale"),
                                      gold=it["answer"] if t1 else it["user_answer"], arms=arms))
    cohort = [items[q["id"]] for q in questions]
    scores = {arm: official["score"](cohort, values) for arm, values in predictions.items()}
    return dict(runs=runs, questions=questions, scopes=scopes, scores=scores,
                paired=paired_intervals(questions))


def build():
    data = collect()
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / "index.html"
    html = (ASSETS / "index.html").read_text(encoding="utf8")
    for filename in ("report.css", "report.js", "structure.js"):
        html = html.replace("__" + filename + "__", (ASSETS / filename).read_text(encoding="utf8"))
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(html.replace("__DATA__", payload.replace("<", r"\u003c")), encoding="utf8")
    tmp.replace(path)
    return path


if __name__ == "__main__":
    print(build())
