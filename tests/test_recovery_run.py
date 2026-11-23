import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from llme.recovery_run import seed_run


class SeedRunTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.source = base / "source"
        self.target = base / "target"
        for folder in (self.source, self.target):
            folder.mkdir()
            with closing(sqlite3.connect(folder / "events.sqlite")) as db, db:
                db.executescript(
                    "CREATE TABLE events (id TEXT PRIMARY KEY, payload TEXT);"
                    "CREATE TABLE attempts (seq INTEGER PRIMARY KEY,job,started,finished,status,reserved_micro_usd,input_tokens);"
                    "CREATE TABLE capacity (request_hash TEXT PRIMARY KEY,tokens INTEGER);"
                )
                provenance = dict(source={}, policy={"budget_usd": 2 if folder == self.target else 1},
                                  model="m", fixture=False, exercise_failures=False, endpoint="test",
                                  builder_prompt="prompt", builder_generation={}, predictor_generation={})
                events = dict(config=[False, "m", {}, folder.name], provenance=provenance, selection=["q"],
                              git_origin={"commit": folder.name})
                if folder == self.source:
                    events.update({"s": {"response": "original"}, "raw/q": {"response": "1"},
                                   "reject/s": "bad shape", "snapshot/s": {}, "journal/s": [],
                                   "model_revision": "m"})
                    db.execute("INSERT INTO attempts VALUES(1,'graph/q',1,NULL,'pending',25,10)")
                    db.execute("INSERT INTO capacity VALUES('hash',10)")
                db.executemany("INSERT INTO events VALUES (?,?)", [(k,json.dumps(v)) for k,v in events.items()])
        self.db = self.enterContext(closing(sqlite3.connect(self.target / "events.sqlite")))

    def seed(self):
        seed_run(self.db, self.target, "source", {"s"}, {"q"})

    def test_reuse_and_resume_only_once(self):
        original = (self.source / "events.sqlite").read_bytes()
        self.seed()
        self.seed()
        rows = dict(self.db.execute("SELECT id,payload FROM events"))
        self.assertEqual(json.loads(rows["s"])["response"], "original")
        self.assertEqual(json.loads(rows["recovered_from"])["exchanges"], 2)
        self.assertFalse({"reject/s","snapshot/s","journal/s"} & rows.keys())
        self.assertEqual(self.db.execute("SELECT status,reserved_micro_usd FROM attempts").fetchall(), [("pending",25)])
        self.assertEqual(self.db.execute("SELECT * FROM capacity").fetchall(), [("hash",10)])
        self.assertEqual((self.source / "events.sqlite").read_bytes(), original)

    def test_selection_mismatch_leaves_no_imports(self):
        with self.db:
            self.db.execute("UPDATE events SET payload='[]' WHERE id='selection'")
        with self.assertRaisesRegex(ValueError, "selection"):
            self.seed()
        self.assertEqual(self.db.execute("SELECT count(*) FROM attempts").fetchone()[0], 0)
        self.assertIsNone(self.db.execute("SELECT 1 FROM events WHERE id='s'").fetchone())
