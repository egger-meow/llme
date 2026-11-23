"""Export an offline progress and replay viewer for a saved inference run."""
import argparse
import csv
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .inference import render
from .journal import commits
from .run import ARMS, PACKAGE, records, verify


def inspect_run(folder, report):
    database = folder / "events.sqlite"
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        events = {k: json.loads(v) for k, v in db.execute("select id,payload from events")}
    fixture, model, files, code = events["config"]
    for name in ("inputs/histories.jsonl", "inputs/questions.jsonl", "inputs/raw_prompts.jsonl"):
        verify(PACKAGE / name, files[name])
    rows = []
    selected = set(events["selection"]) if "selection" in events else None
    questions = [q for q in records(PACKAGE / "inputs/questions.jsonl")
                 if selected is None or q["item_id"] in selected]
    selected_scopes = {q["scope_id"] for q in questions}
    for row in records(PACKAGE / "inputs/histories.jsonl"):
        sid, qa = row["scope_id"], row["context_qas"]
        if sid not in selected_scopes:
            continue
        snapshot = events.get("snapshot/" + sid)
        result = dict(id=sid, status="等待建圖", edits=[], questions=[], history=qa)
        if sid in events and json.loads(events[sid]["user"]) != qa:
            raise ValueError(f"Builder input mismatch: {sid}")
        builder_prompt = events.get("provenance",{}).get("builder_prompt")
        if sid in events and builder_prompt and events[sid]["system"] != builder_prompt:
            raise ValueError(f"Builder instructions mismatch: {sid}")
        if snapshot is not None and "reject/"+sid in events:
            raise ValueError(f"Conflicting scope outcomes: {sid}")
        if snapshot is not None:
            claims = json.loads(events[sid]["response"])["claims"]
            edits = list(commits(sid, qa, claims))
            journal = events.get("journal/" + sid)
            if (journal is not None or "provenance" in events) and journal != edits:
                raise ValueError(f"Journal mismatch: {sid}")
            if render({"claims": [e["claim"] for e in edits]}, qa) != snapshot:
                raise ValueError(f"Snapshot mismatch: {sid}")
            result.update(status="已重播", edits=edits, legacy=journal is None, views=snapshot)
        elif "reject/" + sid in events:
            try:
                render(json.loads(events[sid]["response"]),qa)
            except (ValueError,KeyError,TypeError) as error:
                if str(error)!=events["reject/"+sid]:
                    raise ValueError(f"Rejection reason mismatch: {sid}") from error
            else:
                raise ValueError(f"Accepted proposal marked rejected: {sid}")
            result.update(status="建圖未通過", error=events["reject/" + sid])
        rows.append(result)
    scopes = {r["id"]: r for r in rows}
    if "invalid_revision" in events:
        raise ValueError("Mixed provider revisions")
    prompts = {r["item_id"]: r["messages"] for r in records(PACKAGE / "inputs/raw_prompts.jsonl")}
    blocks = {r["id"]: "\n\n".join(f'Q{i}: {qa["question"]}\nA{i}: {qa["answer"]}' for i,qa in enumerate(r["history"],1)) for r in rows}
    completed = 0
    for q in questions:
        iid = q["item_id"]
        answers = {a: events[a+"/"+iid]["response"] for a in ARMS if a+"/"+iid in events}
        system, raw = (m["content"] for m in prompts[iid])
        sid = q["scope_id"]
        if raw.count(blocks[sid]) != 1:
            raise ValueError(f"Unexpected official prompt: {iid}")
        for arm in answers:
            event = events[arm+"/"+iid]
            expected = raw if arm == "raw" else raw.replace(blocks[sid], events["snapshot/"+sid][arm])
            if (event["system"], event["user"]) != (system, expected):
                raise ValueError(f"Prediction request mismatch: {arm}/{iid}")
        completed += len(answers)
        before, after = raw.split(blocks[sid])
        scopes[sid]["questions"].append(dict(id=iid, prompt=q["prediction"]["task_question"], answers=answers,
                 system=system,before=before,after=after))
    scores = {}
    if (report/"index.html").is_file():
        if (report/"artifacts.json").is_file():
            archive = json.loads((report/"artifacts.json").read_text(encoding="utf8"))
            for name,fingerprint in archive["artifact_sha256"].items():
                verify(report/name,fingerprint)
        question_index = {q["id"]:q for r in rows for q in r["questions"]}
        with (report/"item_results.csv").open(encoding="utf8") as stream:
            for result in csv.DictReader(stream):
                question_index[result["item_id"]].setdefault("metrics",{})[result["arm"]] = result["correct_or_error"]
        for arm in ARMS:
            score = json.loads((report/f"{arm}-scores.json").read_text(encoding="utf8"))
            verify(folder/f"{arm}.jsonl", score["responses_sha256"])
            for row in rows:
                if arm == "raw" or row["status"] != "建圖未通過":
                    if any(arm not in q["answers"] for q in row["questions"]):
                        raise ValueError(f"Missing prediction event: {arm}/{row['id']}")
            expected = {q["id"]: q["answers"].get(arm) for row in rows for q in row["questions"]}
            if {r["item_id"]: r["response"] for r in records(folder/f"{arm}.jsonl")} != expected:
                raise ValueError(f"Prediction export mismatch: {arm}")
            scores[arm] = score["overall"]
    return dict(model="離線合成回覆驗證" if fixture else model, code=code, rows=rows, completed=completed, scores=scores)


def build(folder):
    data = inspect_run(folder, folder/"report")
    pilot = folder/"pilot-scores.json"
    if pilot.is_file():
        data["pilot"] = True
        data["scores"] = {arm:s["overall"] for arm,s in json.loads(pilot.read_text(encoding="utf8")).items()}
    template = Path(__file__).with_name("audit.html").read_text(encoding="utf8")
    path = folder / "audit.html"
    tmp = path.with_suffix(".html.tmp")
    tmp.write_text(template.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("<",r"\u003c")), encoding="utf8")
    tmp.replace(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    print(build(parser.parse_args().folder))
