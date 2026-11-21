"""Prepare and verify the local round-one data. Uses only the Python standard library."""
import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from dataset import RELEASE, SOURCE, read_release, verified_bytes


DEST = RELEASE / "prepared"
SCORER = RELEASE / "hugagent_eval.py"
LICENSE = RELEASE / "data/LICENSE"
EXPERIENCE = {"2.2", "2.3", "2.4", "3.2", "3.3", "3.4"}
SCENARIO = {"1.2", "1.3", "1.4", "2.6", "2.7", "2.8", "3.6", "3.7", "3.8", "3.9"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fetch_missing():
    base = f"https://raw.githubusercontent.com/{SOURCE['repository']}/{SOURCE['revision']}/Benchmark/"
    files = {f"data/{name}": digest for name, digest in SOURCE["files"].items()}
    files.update({"data/LICENSE": SOURCE["license_sha256"], SCORER.name: SOURCE["scorer_sha256"]})
    RELEASE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=RELEASE) as tmp:
        for name, digest in files.items():
            dest = RELEASE / name
            if not dest.exists():
                with urlopen(base + name, timeout=45) as response:
                    staged = Path(tmp) / dest.name
                    staged.write_bytes(response.read())
                verified_bytes(staged, digest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                staged.replace(dest)
            verified_bytes(dest, digest)


def write_jsonl(path, rows):
    with path.open("w", encoding="utf8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path, rows):
    with path.open("w", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_index(path, key):
    with path.open(encoding="utf8") as stream:
        rows = list(map(json.loads, stream))
    index = {r[key]: r for r in rows}
    require(len(rows) == len(index), f"Duplicate {key} in {path.name}")
    return index


def survey_measure(row, baseline_ids):
    if row["question_type"] == "reason_evaluation":
        return "reason_influence"
    qid = row["question_id"]
    if qid == baseline_ids[row["topic"]]:
        return "baseline_stance"
    if qid in EXPERIENCE:
        return "experience_or_perception"
    require(qid in SCENARIO, f"Unclassified opinion question: {qid}")
    return "hypothetical_scenario"


def export_views(stage, items, scopes, baseline_ids):
    histories, questions, answers, routes = {}, [], [], []
    for item in items:
        row = item["row"]
        iid, pid, topic = row["item_id"], row["participant_id"], row["topic"]
        scope = item["scope"]
        if scope not in histories:
            history = scopes[scope]
            identity = [SOURCE["revision"], pid, topic, history]
            encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            histories[scope] = {
                "scope_id": sha256(encoded.encode("utf8")).hexdigest(),
                "context_qas": [
                    {"evidence_id": f"e{i:03d}", "question": qa["question"], "answer": qa["answer"]}
                    for i, qa in enumerate(history, 1)
                ],
            }
        sid = histories[scope]["scope_id"]
        prediction = {k: row[k] for k in ("demographics", "task_question")}
        if row["task_type"] == "belief_attribution":
            task, measure = "T1", "causal_direction"
            prediction["answer_options"] = row["answer_options"]
            gold = {k: row[k] for k in ("answer", "source_qa", "reasoning")}
            require(all(a in row["answer_options"] for a in row["answer"].split("/")), f"Invalid gold: {iid}")
        else:
            task, measure = "T2", survey_measure(row, baseline_ids)
            prediction.update({k: row[k] for k in ("question_type", "scale")})
            if row["question_type"] == "reason_evaluation":
                prediction["reason_text"] = row["reason_text"]
            gold = {"user_answer": row["user_answer"]}
            lo, hi = row["scale"]
            require(type(row["user_answer"]) is int and lo <= row["user_answer"] <= hi, f"Invalid score: {iid}")
        questions.append(dict(item_id=iid, scope_id=sid, task_type=row["task_type"], prediction=prediction))
        answers.append(dict(item_id=iid, **gold))
        routes.append(dict(item_id=iid, participant_id=pid, topic=topic, task=task, measure=measure,
                           question_id=row.get("question_id", ""), reason_code=row.get("reason_code", ""),
                           scope_id=sid, qa_count=len(scopes[scope]), source_file=item["file"], source_line=item["line"]))
    write_jsonl(stage / "inputs/histories.jsonl", histories.values())
    write_jsonl(stage / "inputs/questions.jsonl", questions)
    write_jsonl(stage / "scoring/answers.jsonl", answers)
    write_csv(stage / "items.csv", routes)
    return routes


def count_participants(stage, routes):
    groups = defaultdict(list)
    for row in routes:
        groups[row["participant_id"], row["topic"]].append(row)
    counts = []
    for (pid, topic), rows in sorted(groups.items()):
        tasks = Counter(r["task"] for r in rows)
        t1 = {r["scope_id"] for r in rows if r["task"] == "T1"}
        t2 = {r["scope_id"] for r in rows if r["task"] == "T2"}
        require(len(t2) == 1, f"Expected one T2 interview for {pid} / {topic}")
        counts.append(dict(participant_id=pid, topic=topic, t1=tasks["T1"], t2=tasks["T2"],
                           total=len(rows), histories=len(t1 | t2), shared_t1_t2_histories=len(t1 & t2)))
    write_csv(stage / "participant_counts.csv", counts)
    return len({pid for pid, topic in groups})


def export_pairs(stage, routes, answers):
    baselines, reasons = {}, defaultdict(list)
    for r in routes:
        person = r["participant_id"], r["topic"]
        if r["measure"] == "baseline_stance":
            require(person not in baselines, f"Duplicate baseline for {person}")
            baselines[person] = r["item_id"]
        if r["measure"] == "reason_influence":
            stem, code = r["question_id"].rsplit("r_", 1)
            require(code == r["reason_code"], f"Reason code mismatch: {r['item_id']}")
            reasons[(*person, stem)].append(r)

    direction = []
    for r in routes:
        base = baselines.get((r["participant_id"], r["topic"]))
        if base and r["measure"] in {"experience_or_perception", "hypothetical_scenario"}:
            direction.append(dict(baseline_item_id=base, comparison_item_id=r["item_id"], measure=r["measure"]))
    write_csv(stage / "scoring/direction_pairs.csv", direction)

    rank = []
    for (pid, topic, stem), group in sorted(reasons.items()):
        for left, right in combinations(group, 2):
            require(left["reason_code"] != right["reason_code"], f"Repeated reason in {pid} / {topic} / {stem}")
            a, b = left["item_id"], right["item_id"]
            delta = answers[a]["user_answer"] - answers[b]["user_answer"]
            rank.append(dict(participant_id=pid, topic=topic, question_stem=stem,
                             left_item_id=a, right_item_id=b, gold_sign=(delta > 0) - (delta < 0)))
    write_csv(stage / "scoring/rank_pairs.csv", rank)
    return dict(direction_pairs=len(direction), direction_by_measure=Counter(r["measure"] for r in direction),
                rank_pairs=len(rank), rank_ties=sum(r["gold_sign"] == 0 for r in rank),
                rank_participants=len({r["participant_id"] for r in rank}))


def verify_views(stage, items, scopes, official, answers):
    """Round-trip the serialized inputs through the unmodified official prompt and reference scorer."""
    questions = read_index(stage / "inputs/questions.jsonl", "item_id")
    histories = read_index(stage / "inputs/histories.jsonl", "scope_id")
    with (stage / "items.csv").open(encoding="utf8", newline="") as stream:
        routes = {r["item_id"]: r for r in csv.DictReader(stream)}
    ids = {item["row"]["item_id"] for item in items}
    require(len(ids) == len(items) and ids == questions.keys() == answers.keys() == routes.keys(), "Item IDs do not match")
    require({q["scope_id"] for q in questions.values()} == histories.keys(), "History references do not match")
    for sid, entry in histories.items():
        require(set(entry) == {"scope_id", "context_qas"}, f"Unexpected history fields: {sid}")
        for i, qa in enumerate(entry["context_qas"], 1):
            require(set(qa) == {"evidence_id", "question", "answer"} and qa["evidence_id"] == f"e{i:03d}",
                    f"Unexpected evidence fields or numbering: {sid}")
    scoring_rows, raw_prompts = [], []
    files = [f"{task}_{domain}.jsonl" for task in official["TASKS"] for domain in official["DOMAINS"]]
    for item in sorted(items, key=lambda x: (files.index(x["file"]), x["line"])):
        row = item["row"]
        iid = row["item_id"]
        q, route = questions[iid], routes[iid]
        require((route["source_file"], int(route["source_line"]), route["scope_id"]) ==
                (item["file"], item["line"], q["scope_id"]), f"Item route mismatch: {iid}")
        expected_fields = {"demographics", "task_question"}
        if row["task_type"] == "belief_attribution":
            expected_fields.add("answer_options")
            gold_fields = {"answer", "source_qa", "reasoning"}
        else:
            expected_fields.update(("question_type", "scale"))
            if row["question_type"] == "reason_evaluation":
                expected_fields.add("reason_text")
            gold_fields = {"user_answer"}
        require(set(q) == {"item_id", "scope_id", "task_type", "prediction"}
                and set(q["prediction"]) == expected_fields, f"Unexpected prediction fields: {iid}")
        require(set(answers[iid]) == gold_fields | {"item_id"}, f"Unexpected scoring fields: {iid}")
        history = histories[q["scope_id"]]["context_qas"]
        view = dict(task_type=q["task_type"], context_qas=history, **q["prediction"])
        original = dict(row, context_qas=scopes[item["scope"]])
        system, user = official["build_prompt"](view)
        require((system, user) == official["build_prompt"](original), f"Raw prompt mismatch: {iid}")
        raw_prompts.append(dict(item_id=iid, messages=[dict(role="system", content=system), dict(role="user", content=user)]))
        for k, value in answers[iid].items():
            require(row[k] == value, f"Scoring field mismatch: {iid} / {k}")
        scorer_row = {k: route[k] for k in ("participant_id", "topic", "question_id") if route[k]}
        scorer_row.update({k: view[k] for k in ("task_type", "scale", "question_type", "answer_options") if k in view})
        scoring_rows.append(dict(scorer_row, **answers[iid]))

    write_jsonl(stage / "inputs/raw_prompts.jsonl", raw_prompts)
    metrics = ["bsi_acc", "bdu_acc", "bdu_mae", "bdu_dir_acc", "ati"]
    baselines = {}
    for name, seeds, expected in [
        ("majority", 1, [63.64, 56.07, 1.73, 15.34, 0.76]),
        ("random", 5, [50.51, 44.44, 1.81, 47.93, 0.12]),
    ]:
        runs = []
        for seed in range(seeds):
            preds = official["baseline_preds"](scoring_rows, name, seed=seed)
            runs.append(official["score"](scoring_rows, preds)["overall"])
        scores = {k: round(sum(r[k] for r in runs) / seeds, 2) for k in metrics}
        require(list(scores.values()) == expected, f"Official {name} baseline mismatch: {scores}")
        baselines[name] = scores
    return len(questions), baselines


def build(stage):
    (stage / "inputs").mkdir()
    (stage / "scoring").mkdir()
    (stage / "LICENSE").write_bytes(verified_bytes(LICENSE, SOURCE["license_sha256"]))
    verified_bytes(SCORER, SOURCE["scorer_sha256"])
    official = runpy.run_path(str(SCORER))
    items, scopes = read_release()
    require({i["row"]["split"] for i in items} == {"test"}, "Unexpected source split")
    routes = export_views(stage, items, scopes, official["BASELINE_Q"])
    answers = read_index(stage / "scoring/answers.jsonl", "item_id")
    pairs = export_pairs(stage, routes, answers)
    prompt_matches, baselines = verify_views(stage, items, scopes, official, answers)
    measures = Counter(r["measure"] for r in routes)
    people = count_participants(stage, routes)
    t1 = {r["scope_id"] for r in routes if r["task"] == "T1"}
    t2 = {r["scope_id"] for r in routes if r["task"] == "T2"}
    require((people, len(t1), len(t2), len(t1 & t2)) == (54, 319, 162, 21), "Coverage mismatch")
    require(measures == dict(causal_direction=356, baseline_stance=77, experience_or_perception=155,
                             hypothetical_scenario=157, reason_influence=997), "Question counts differ")
    require((pairs["direction_pairs"], pairs["rank_pairs"], pairs["rank_ties"]) == (179, 994, 587), "Pair counts differ")
    manifest = dict(
        format_version=1, source=SOURCE, split="test", participants=people, items=len(routes), tasks=Counter(r["task"] for r in routes),
        tasks_by_topic={d: Counter(r["task"] for r in routes if r["topic"] == d) for d in official["DOMAINS"]},
        measures=measures, histories=len(scopes), t1_histories=len(t1), t2_histories=len(t2), shared_histories=len(t1 & t2),
        t1_dual_labels=sum(a.get("answer") == "A/B" for a in answers.values()),
        t1_held_out_qa_in_own_history=0,
        t1_held_out_qa_in_same_person_topic_t2=Counter(i["row"]["topic"] for i in items if "leak" in i),
        exact_official_raw_prompts=prompt_matches, official_baselines=baselines, **pairs,
        files={p.relative_to(stage).as_posix(): sha256(p.read_bytes()).hexdigest()
               for p in sorted(stage.rglob("*")) if p.is_file()},
    )
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fetch", action="store_true", help="download missing pinned source files, then prepare")
    mode.add_argument("--check", action="store_true", help="rebuild in temporary storage and compare to the local package")
    args = parser.parse_args()
    if args.fetch:
        fetch_missing()
    if not (LICENSE.is_file() and SCORER.is_file() and all((RELEASE / "data" / n).is_file() for n in SOURCE["files"])):
        parser.error("Missing local release files. Run prepare.py --fetch to retrieve the pinned release.")
    with TemporaryDirectory(dir=RELEASE) as tmp:
        stage = Path(tmp)
        manifest = build(stage)
        # Publish verified files first and the manifest last. A clean rerun writes nothing.
        for name in [*manifest["files"], "manifest.json"]:
            src, dest = stage / name, DEST / name
            if dest.is_file() and src.read_bytes() == dest.read_bytes():
                continue
            require(not args.check, f"Missing or changed prepared file: {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dest)
    print(f"{DEST / 'manifest.json'}: {manifest['items']} verified items, {manifest['histories']} histories")


if __name__ == "__main__":
    main()
