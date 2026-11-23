"""Build a two-edit replay fixture and confirm that tampering is detected."""
import json
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from llme.audit import build
from llme.inference import render
from llme.journal import commits
from llme.run import PACKAGE, records


def demo(folder):
    folder.mkdir(parents=True, exist_ok=False)
    row = next(records(PACKAGE / "inputs/histories.jsonl"))
    sid, history = row["scope_id"], row["context_qas"]
    claims = [dict(holder="展示用", about="操作範例", source="範例起點", target=f"範例概念 {i}",
                   relation="示範連線", outcome="展示", condition=None, basis="inferred",
                   evidence_id=q["evidence_id"], quote=q["answer"], overrides=None)
              for i, q in enumerate(history[:2], 1)]
    proposal = {"claims": claims}
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf8"))
    chain = list(commits(sid, history, claims))
    with sqlite3.connect(folder / "events.sqlite") as db:
        db.execute("CREATE TABLE events (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        entries = {"config": [True, None, manifest["files"], "synthetic-demo"],
                   sid: {"user": json.dumps(history), "response": json.dumps(proposal)},
                   "snapshot/"+sid: render(proposal, history), "journal/"+sid: chain}
        db.executemany("INSERT INTO events VALUES (?,?)", [(k,json.dumps(v)) for k,v in entries.items()])
        db.commit()
        print(build(folder))
        chain[1]["parent"] = "tampered"
        db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(chain),"journal/"+sid))
        db.commit()
        try:
            build(folder)
        except ValueError as exc:
            assert "Journal mismatch" in str(exc)
        else:
            raise AssertionError("Modified parent accepted")
        db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(list(commits(sid,history,claims))),"journal/"+sid))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        demo(Path(sys.argv[1]))
    else:
        with TemporaryDirectory() as temp:
            demo(Path(temp)/"demo")
