"""Offline HugAgent run planning and scoring. Run from any working directory."""
import argparse
import csv
import hashlib
import json
import runpy
import platform
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "ref/HugAgent"
PACKAGE = RELEASE / "prepared"
ARMS = ("raw", "graph", "flat")


def records(path):
    with path.open(encoding="utf8") as stream:
        for line in stream:
            yield json.loads(line)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf8")


def verify(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Input fingerprint mismatch: {path}")


def create_plan(stage, manifest):
    inputs = PACKAGE / "inputs"
    histories = {row["scope_id"] for row in records(inputs / "histories.jsonl")}
    questions = list(records(inputs / "questions.jsonl"))
    raw_ids = [row["item_id"] for row in records(inputs / "raw_prompts.jsonl")]
    ids = [row["item_id"] for row in questions]
    if (len(histories) != manifest["histories"] or len(set(ids)) != manifest["items"]
            or len(ids) != len(set(ids)) or len(raw_ids) != len(ids) or set(ids) != set(raw_ids)
            or {row["scope_id"] for row in questions} != histories):
        raise ValueError("Incomplete question or scope routing")
    with (stage / "jobs.csv").open("w", newline="", encoding="utf8") as file:
        writer = csv.writer(file)
        writer.writerow(("item_id", "scope_id", "arm"))
        for row in questions:
            for arm in ARMS:
                writer.writerow((row["item_id"], row["scope_id"], arm))
    write_json(stage / "manifest.json", {
        "kind": "offline-plan", "source": manifest["source"], "prepared_files": manifest["files"],
        "scopes": sorted(histories), "prediction_slots": len(ids) * len(ARMS),
        "arms": ARMS, "exception_policy": "explicit_overrides_only",
    })


def score(stage, responses, manifest):
    scorer = RELEASE / "hugagent_eval.py"
    verify(scorer, manifest["source"]["scorer_sha256"])
    for name, digest in manifest["source"]["files"].items():
        verify(RELEASE / "data" / name, digest)
    official = runpy.run_path(str(scorer))
    items = [item for name in sorted(manifest["source"]["files"]) for item in records(RELEASE / "data" / name)]
    by_id = {item["item_id"]: item for item in items}
    predictions, strict = {}, {}
    for arm in ARMS:
        parsed = {}
        strict[arm] = {}
        source = responses / f"{arm}.jsonl"
        for row in records(source):
            iid, value = row["item_id"], row["response"]
            if iid not in by_id or iid in parsed or not (value is None or isinstance(value, str)):
                raise ValueError(f"Invalid response in {source}: {iid}")
            parsed[iid] = official["extract"](by_id[iid], value)
            item = by_id[iid]
            token = value.strip() if isinstance(value, str) else ""
            if item["task_type"] == "belief_attribution":
                strict[arm][iid] = token if token in item["answer_options"] else None
            else:
                lo, hi = item["scale"]
                strict[arm][iid] = int(token) if token in {str(i) for i in range(lo, hi+1)} else None
        if parsed.keys() != by_id.keys():
            raise ValueError(f"Incomplete response set for {arm}")
        report = official["score"](items, parsed)
        predictions[arm] = parsed
        report["responses_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        write_json(stage / f"{arm}-scores.json", report)
    from .report import export
    export(stage, items, predictions, strict)
    from .diagnostics import diagnostics
    diagnostics(stage, responses, items, predictions, strict)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    sub.add_parser("score").add_argument("--responses", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf8"))
    for name, digest in manifest["files"].items():
        verify(PACKAGE / name, digest)
    dest = args.output.resolve()
    if dest.exists():
        parser.error("Choose a new output directory")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dest.parent) as temp:
        stage = Path(temp) / "output"
        stage.mkdir()
        create_plan(stage, manifest)
        if args.command == "score":
            score(stage, args.responses, manifest)
            if (args.responses/"events.sqlite").is_file():
                from .audit import inspect_run
                inspect_run(args.responses,stage)
        artifacts = {f.relative_to(stage).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
                     for f in sorted(stage.rglob("*")) if f.is_file()}
        write_json(stage/"artifacts.json", {"run": args.responses.resolve().name if args.command=="score" else None,
                  "python": platform.python_version(), "artifact_sha256": artifacts,
                  "analysis_code": {f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                                    for f in sorted(Path(__file__).parent.glob("*.py"))}})
        stage.rename(dest)
    print(dest)


if __name__ == "__main__":
    main()
