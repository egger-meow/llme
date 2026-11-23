"""Seed a derived run with immutable provider exchanges from a prior run."""
import hashlib
import json
import sqlite3
from contextlib import closing


def seed_run(db, folder, name, scopes, item_ids):
    source_path = (folder.parent / name / "events.sqlite").resolve()
    if source_path == (folder / "events.sqlite").resolve():
        raise ValueError("--recover-from requires a different destination run")
    with db:
        db.execute("BEGIN IMMEDIATE")
        lineage = db.execute("SELECT payload FROM events WHERE id='recovered_from'").fetchone()
        if lineage:
            if json.loads(lineage[0])["run"] != name:
                raise ValueError("This run was already seeded from a different source")
            return
        existing = db.execute("SELECT 1 FROM events WHERE id NOT IN ('config','selection','provenance','git_origin') LIMIT 1").fetchone()
        if existing or db.execute("SELECT 1 FROM attempts LIMIT 1").fetchone():
            raise ValueError("--recover-from requires a new destination run")
        if not source_path.is_file():
            raise ValueError(f"Recovery source does not exist: {source_path}")
        with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source:
            source.execute("BEGIN")

            def metadata(connection, key):
                row = connection.execute("SELECT payload FROM events WHERE id=?", (key,)).fetchone()
                if row is None:
                    raise ValueError(f"Incomplete run metadata: {key}")
                return json.loads(row[0])

            if source.execute("SELECT 1 FROM events WHERE id='invalid_revision'").fetchone():
                raise ValueError("Recovery source contains mixed provider revisions")
            if metadata(db, "selection") != metadata(source, "selection"):
                raise ValueError("Recovery source selection differs")
            old_config = metadata(source, "config")
            if metadata(db, "config")[:3] != old_config[:3]:
                raise ValueError("Recovery source model, fixture mode or dataset differs")
            current, original = metadata(db, "provenance"), metadata(source, "provenance")
            # A new destination may explicitly set a new cumulative budget. Rates
            # and capacity stay frozen for the imported accounting and requests.
            def accounting(policy):
                return {k: v for k, v in (policy or {}).items() if k != "budget_usd"}

            if accounting(current["policy"]) != accounting(original["policy"]):
                raise ValueError("Recovery source rates or capacity policy differs")
            for field in ("source", "model", "fixture", "exercise_failures", "endpoint",
                          "builder_prompt", "builder_generation", "predictor_generation"):
                if current[field] != original.get(field):
                    raise ValueError(f"Recovery source differs in {field}")
            keep = scopes | {f"{arm}/{iid}" for arm in ("raw", "graph", "flat") for iid in item_ids}
            fingerprint = hashlib.sha256()
            copied = 0
            for key, payload in source.execute("SELECT id,payload FROM events ORDER BY id"):
                if key in keep or key == "model_revision":
                    db.execute("INSERT INTO events VALUES (?,?)", (key, payload))
                    fingerprint.update(json.dumps([key, payload]).encode())
                    copied += int(key in keep)
            # Carry over all reservations, including pending deliveries. They remain
            # subject to the ordinary run budget and explicit duplicate-retry guard.
            db.executemany("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                           source.execute("SELECT seq,job,started,finished,status,reserved_micro_usd,input_tokens FROM attempts"))
            db.executemany("INSERT INTO capacity VALUES (?,?)",
                           source.execute("SELECT request_hash,tokens FROM capacity"))
            ancestor = source.execute("SELECT payload FROM events WHERE id='recovered_from'").fetchone()
            lineage = dict(run=name, exchanges=copied, sha256=fingerprint.hexdigest(), config=old_config,
                           provenance=original, git_origin=metadata(source, "git_origin"))
            if ancestor:
                lineage["ancestor"] = json.loads(ancestor[0])["run"]
            db.execute("INSERT INTO events VALUES ('recovered_from',?)", (json.dumps(lineage, sort_keys=True),))
    print(f"Recovered {copied} saved model exchanges from {name}. Replaying builds.", flush=True)
