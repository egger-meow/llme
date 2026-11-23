"""Exercise provider boundaries locally. Every model reply in this file is synthetic."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from unittest.mock import patch

from llme import inference, audit
from llme.run import ARMS, records


count_google_input = inference.count_input


class RunBoundaryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.package = root / "prepared"
        inputs = self.package / "inputs"
        inputs.mkdir(parents=True)
        histories, questions, prompts = [], [], []
        for i in (1, 2):
            sid, iid = f"s{i}", f"q{i}"
            qa = dict(evidence_id="e001", question="Support?", answer=f"Only on day {i}.")
            histories.append(dict(scope_id=sid, context_qas=[qa]))
            questions.append(dict(item_id=iid, scope_id=sid, prediction=dict(task_question="Score?",scale=[1,5])))
            prompts.append(dict(item_id=iid,messages=[{"content":"Return a number."},{"content":f'Q1: Support?\nA1: {qa["answer"]}\nScore?'}]))
        for name, rows in (("histories", histories),("questions",questions),("raw_prompts",prompts)):
            (inputs/f"{name}.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf8")
        files={f"inputs/{p.name}":hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
        (self.package/"manifest.json").write_text(json.dumps(dict(files=files,source={})),encoding="utf8")
        for obj, key, value in ((inference,"ROOT",root),(inference,"PACKAGE",self.package),(audit,"PACKAGE",self.package)):
            self.enterContext(patch.object(obj,key,value))
        self.enterContext(patch.dict(os.environ,GEMINI_API_KEY="local-test-only"))
        self.folder=root/"ref/experiments/test"
        self.policy = root/"policy.json"
        self.policy.write_text(json.dumps(dict(model="local",budget_usd=1,input_limit=10000,output_limit=8192,
                  input_usd_per_million=1,output_usd_per_million=1,price_source_date="fixture")))
        self.enterContext(patch.object(inference,"count_input",return_value=100))
        self.version="v1"
        self.sent=[]

    def provider(self,model,system,user,structured):
        self.sent.append(user)
        text="2"
        finish="STOP"
        if structured:
            qa=json.loads(user)[0]
            claim=dict(holder="self",about="self",source="day",relation="supports",target="proposal",
                       outcome="positive",condition="day 1",basis="explicit",overrides=None,**{"quote":qa["answer"],"evidence_id":"e001"})
            text=json.dumps({"claims":[claim]})
            if "day 2" in user:
                finish="MAX_TOKENS"
        return dict(text=text,finish=finish,version=self.version,usage={},request_id="test")

    def invoke(self,limit,provider=None,extra=()):
        argv=["inference","--run","test","--model","local","--policy",str(self.policy),"--max-calls",str(limit),*extra]
        with patch.object(sys,"argv",argv),patch.object(inference,"gemini",provider or self.provider):
            inference.main()

    def test_resume_reject_and_tamper(self):
        with self.assertRaises(SystemExit):
            self.invoke(1)
        self.invoke(8)
        self.assertEqual(len(self.sent),6)
        self.invoke(1)
        self.assertEqual(len(self.sent),6)
        for arm in ARMS:
            self.assertEqual([r["response"] for r in records(self.folder/f"{arm}.jsonl")],["2","2" if arm=="raw" else None])
        audit.build(self.folder)
        with closing(sqlite3.connect(self.folder/"events.sqlite")) as db, db:
            db.execute("UPDATE events SET payload=json_set(payload,'$.user','wrong scope') WHERE id='graph/q1'")
        with self.assertRaisesRegex(ValueError,"Prediction request mismatch"):
            audit.build(self.folder)

    def test_delivery_unknown_and_version_drift(self):
        def timeout(*_):
            raise TimeoutError
        with self.assertRaises(TimeoutError):
            self.invoke(1,timeout)
        with self.assertRaisesRegex(RuntimeError,"Uncertain delivery"):
            self.invoke(1)
        with self.assertRaises(SystemExit):
            self.invoke(1,extra=["--retry-uncertain","s1"])
        self.version="v2"
        with self.assertRaisesRegex(RuntimeError,"revision changed"):
            self.invoke(1)
        with self.assertRaisesRegex(RuntimeError,"Mixed provider revisions"):
            self.invoke(1)
    def test_capacity_and_cumulative_budget_before_generation(self):
        policy=json.loads(self.policy.read_text())
        policy.update(budget_usd=0.009)
        self.policy.write_text(json.dumps(policy))
        with patch.object(inference,"count_input",return_value=10001):
            with self.assertRaisesRegex(ValueError,"capacity"):
                self.invoke(2)
        self.assertEqual(self.sent,[])
        with self.assertRaisesRegex(SystemExit,"budget"):
            self.invoke(2)
        self.assertEqual(len(self.sent),1)
        with self.assertRaisesRegex(SystemExit,"budget"):
            self.invoke(2)
        self.assertEqual(len(self.sent),1)

    def test_both_renderers_keep_challenges_and_explicit_exception(self):
        history=[dict(evidence_id="e001",question="Policy?",answer="Usually yes, except on Fridays."),
                 dict(evidence_id="e002",question="Any doubts?",answer="Sometimes it fails.")]
        base=dict(holder="participant",about="self",source="policy",relation="supports",target="adoption",outcome="yes",
                  basis="explicit",evidence_id="e001",quote="Usually yes",condition=None,overrides=None,
                  additional_evidence=[dict(role="challenges",evidence_id="e002",quote="Sometimes it fails.")])
        child=dict(base,outcome="no",condition="Friday",quote="except on Fridays",overrides=1)
        for text in inference.render({"claims":[base,child]},history).values():
            for phrase in ("Sometimes it fails.","challenges this claim","Overrides claim 1","except on Fridays"):
                self.assertIn(phrase,text)
        with self.assertRaisesRegex(ValueError,"override"):
            inference.render({"claims":[base,dict(child,basis="inferred")]},history)
        with self.assertRaisesRegex(ValueError,"Unsupported additional"):
            inference.render({"claims":[dict(base,additional_evidence=[dict(role="challenges",evidence_id="e002",quote="invented")])]},history)
    def test_google_request_shape_and_truncated_reply(self):
        import io
        sent=[]
        def transport(req, timeout):
            sent.append((req.full_url,json.loads(req.data)))
            if req.full_url.endswith(":countTokens"):
                result={"totalTokens":42}
            else:
                result={"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[{"text":"partial"}]}}],
                        "modelVersion":"test-version","responseId":"test-request","usageMetadata":{"promptTokenCount":42}}
            return io.BytesIO(json.dumps(result).encode())
        with patch.object(inference,"urlopen",side_effect=transport):
            counted=count_google_input("local","system","user",True)
            reply=inference.gemini("local","system","user",True)
        self.assertEqual(counted,42)
        body=sent[0][1]["generateContentRequest"].copy()
        self.assertEqual(body.pop("model"),"models/local")
        self.assertEqual(body,sent[1][1])
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"],"system")
        self.assertEqual(body["generationConfig"]["responseMimeType"],"application/json")
        self.assertEqual((reply["finish"],reply["text"]),("MAX_TOKENS","partial"))
