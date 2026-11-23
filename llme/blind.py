"""Export evaluator materials separately from the unblinding key."""
import csv
import json
import random
from collections import defaultdict

from .run import PACKAGE, records


def packets(stage, claims, routes, review):
    rng = random.Random(20261123)
    histories = {r["scope_id"]: r["context_qas"] for r in records(PACKAGE/"inputs/histories.jsonl")}
    questions = {r["item_id"]: r["prediction"]["task_question"] for r in records(PACKAGE/"inputs/questions.jsonl")}
    topics = {r["scope_id"]: r["topic"] for r in routes.values()}
    eligible = defaultdict(list)
    for sid in sorted(claims):
        eligible[topics[sid]].append(sid)
    panels = []
    for domain, ids in sorted(eligible.items()):
        for sid in rng.sample(ids,min(10,len(ids))):
            history = histories[sid]
            for i in rng.sample(range(len(claims[sid])),min(2,len(claims[sid]))):
                c = claims[sid][i]
                # Include preceding claims needed to interpret an explicit override.
                chain = []
                parent = c["overrides"]
                while parent:
                    ancestor = claims[sid][parent-1]
                    chain.append([parent,ancestor])
                    parent = ancestor["overrides"]
                panels.append(("support",sid,None,None,dict(history=history, claim=c, defaults=chain),i+1))
            for qa in rng.sample(history,min(2,len(history))):
                panels.append(("coverage",sid,None,None,dict(qa=qa,claims=claims[sid]),qa["evidence_id"]))
    for iid,sid,task,outcome in review:
        panels.append(("case",sid,iid,outcome,dict(question=questions[iid],history=histories[sid],claims=claims.get(sid,[])),None))
    rng.shuffle(panels)
    dest=stage/"reviewer"
    dest.mkdir()
    with (dest/"phase1.jsonl").open("w",encoding="utf8") as first, (dest/"phase2.jsonl").open("w",encoding="utf8") as second, (dest/"ratings.csv").open("w",newline="",encoding="utf8") as ratings, (stage/"unblinding.csv").open("w",newline="",encoding="utf8") as key:
        score, lookup = csv.writer(ratings),csv.writer(key)
        score.writerow(["case","task","judgment","notes"])
        lookup.writerow(["case","task","scope_id","item_id","stratum","source"])
        for n,(kind,sid,iid,outcome,body,source) in enumerate(panels,1):
            case=f"R{n:03}"
            def emit(out, payload):
                out.write(json.dumps(dict(case=case,task=kind,**payload),ensure_ascii=False)+"\n")
            if kind=="coverage":
                emit(first,dict(qa=body["qa"]))
                emit(second,body)
            else:
                emit(first,body)
            score.writerow([case,kind,"",""])
            lookup.writerow([case,kind,sid,iid,outcome,source])
    (dest/"README.txt").write_text(
        "兩位評者各自保留一份 ratings.csv。先讀 phase1。support 評有支持／部分／缺支持／資訊不足。"
        "coverage 先寫下問答內重要判斷，再開 phase2 標保留／部分／遺漏／無可判定主張。"
        "case 對照原話、考題與主張，記錄漏抽、主體、條件、程度、或無法判定。"
        "完成各自評分後交回，再由研究者使用 unblinding.csv 對應。",encoding="utf8")
