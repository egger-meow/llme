"""Export an offline progress and replay viewer for a saved inference run."""
import argparse
import json
import sqlite3
from pathlib import Path

from .inference import render
from .journal import commits
from .run import ARMS, PACKAGE, records, verify


def build(folder):
    database = folder / "events.sqlite"
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        events = {k: json.loads(v) for k, v in db.execute("select id,payload from events")}
    fixture, model, files, code = events["config"]
    for name in ("inputs/histories.jsonl", "inputs/questions.jsonl"):
        verify(PACKAGE / name, files[name])
    rows = []
    for row in records(PACKAGE / "inputs/histories.jsonl"):
        sid, qa = row["scope_id"], row["context_qas"]
        snapshot = events.get("snapshot/" + sid)
        result = dict(id=sid, status="等待建圖", edits=[], questions=[], history=qa)
        if sid in events and json.loads(events[sid]["user"]) != qa:
            raise ValueError(f"Builder input mismatch: {sid}")
        if snapshot is not None:
            claims = json.loads(events[sid]["response"])["claims"]
            edits = list(commits(sid, qa, claims))
            journal = events.get("journal/" + sid)
            if journal is not None and journal != edits:
                raise ValueError(f"Journal mismatch: {sid}")
            if render({"claims": [e["claim"] for e in edits]}, qa) != snapshot:
                raise ValueError(f"Snapshot mismatch: {sid}")
            result.update(status="已重播", edits=edits, legacy=journal is None)
        elif "reject/" + sid in events:
            result.update(status="建圖未通過", error=events["reject/" + sid])
        rows.append(result)
    scopes = {r["id"]: r for r in rows}
    completed = 0
    for q in records(PACKAGE / "inputs/questions.jsonl"):
        iid = q["item_id"]
        answers = {a: events[a+"/"+iid]["response"] for a in ARMS if a+"/"+iid in events}
        completed += len(answers)
        scopes[q["scope_id"]]["questions"].append(dict(id=iid, prompt=q["prediction"]["task_question"], answers=answers))
    scores = {}
    report = folder / "report"
    if (report/"index.html").is_file():
        for arm in ARMS:
            score = json.loads((report/f"{arm}-scores.json").read_text(encoding="utf8"))
            verify(folder/f"{arm}.jsonl", score["responses_sha256"])
            expected = {q["id"]: q["answers"].get(arm) for row in rows for q in row["questions"]}
            if {r["item_id"]: r["response"] for r in records(folder/f"{arm}.jsonl")} != expected:
                raise ValueError(f"Prediction export mismatch: {arm}")
            scores[arm] = score["overall"]
    data = dict(model="離線固定答案驗證" if fixture else model, code=code, rows=rows, completed=completed, scores=scores)
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
