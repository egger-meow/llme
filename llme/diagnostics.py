"""Diagnostic tables computed only after prediction has finished."""
import csv
from html import escape
import json
import random
import sqlite3
from contextlib import closing
from collections import defaultdict
from statistics import mean
from .run import ARMS, PACKAGE


def table(stage, name, header, rows):
    with (stage / (name+".csv")).open("w", newline="", encoding="utf8") as out:
        writer = csv.writer(out)
        writer.writerow(header.split())
        writer.writerows(rows)


def diagnostics(stage, responses, items, predictions, strict):
    by_id = {it["item_id"]: it for it in items}
    with (PACKAGE/"items.csv").open(encoding="utf8") as stream:
        routes = {r["item_id"]:r for r in csv.DictReader(stream)}
    with (stage/"item_results.csv").open(encoding="utf8") as stream:
        scores = {(r["item_id"],r["arm"]):float(r["correct_or_error"]) for r in csv.DictReader(stream)}
    cells, changes, transitions, calibration = defaultdict(list), [], defaultdict(list), defaultdict(int)
    for iid,r in routes.items():
        for arm in ARMS:
            value = scores[iid,arm]
            for group in ("participant_id","measure"):
                cells[group,r[group],r["topic"],r["task"],arm].append(value)
            if r["task"]=="T2":
                it=by_id[iid]
                calibration[arm,it["scale"][1],it["user_answer"],predictions[arm][iid]] += 1
        raw,graph = scores[iid,"raw"],scores[iid,"graph"]
        signed=(graph-raw)*(1 if r["task"]=="T1" else -1)
        direction="equal" if signed==0 else "graph_better" if signed>0 else "raw_better"
        transitions[r["task"],direction].append(iid)
        changes.append((iid,r["task"],r["measure"],raw,graph,direction))
    table(stage,"item_changes","item_id task measure raw graph outcome",changes)
    table(stage,"person_domain_results","group dimension domain task arm n mean",((*k,len(v),mean(v)) for k,v in cells.items()))
    table(stage,"calibration","arm scale_max gold parsed n",((*k,v) for k,v in calibration.items()))
    with (PACKAGE/"scoring/direction_pairs.csv").open(encoding="utf8") as src:
        rows=[]
        for r in csv.DictReader(src):
            a,b=r["baseline_item_id"],r["comparison_item_id"]
            for arm in ARMS:
                x,y=predictions[arm][a],predictions[arm][b]
                rows.append((a,b,r["measure"],arm,by_id[b]["user_answer"]-by_id[a]["user_answer"],None if None in (x,y) else y-x))
    table(stage,"direction_results","baseline comparison measure arm gold_delta predicted_delta",rows)
    rank=defaultdict(list)
    with (stage/"rank_results.csv").open(encoding="utf8") as src:
        for r in csv.DictReader(src):
            for group in ("all","tie" if r["gold_sign"]=="0" else "ordered"):
                rank[r["arm"],group].append(r)
    table(stage,"rank_summary","arm group n valid hits predicted_ties",((*k,len(v),sum(r["predicted_sign"]!="" for r in v),sum(int(r["hit"]) for r in v),sum(r["predicted_sign"]=="0" for r in v)) for k,v in rank.items()))
    confusion = defaultdict(int)
    valid_methods = defaultdict(set)
    for arm in ARMS:
        for r in rank[arm,"all"]:
            confusion[arm,r["gold_sign"],r["predicted_sign"] or "invalid"] += 1
            if r["predicted_sign"]:
                valid_methods[r["left_item"],r["right_item"]].add(arm)
    table(stage,"rank_confusion","arm gold predicted pairs",((*k,v) for k,v in sorted(confusion.items())))
    common=[]
    for arm in ARMS:
        for group in ("all","tie","ordered"):
            subset=[r for r in rank[arm,group] if len(valid_methods[r["left_item"],r["right_item"]])==len(ARMS)]
            common.append((arm,group,len(subset),sum(int(r["hit"]) for r in subset)))
    table(stage,"rank_common_valid","arm group pairs hits",common)
    from .paired import rank_intervals, amortized, metered
    table(stage,"rank_intervals","group left right pairs people difference_pp lower95 upper95 draws",rank_intervals(rank,routes))
    official=[]
    for arm in ARMS:
        s=json.loads((stage/f"{arm}-scores.json").read_text(encoding="utf8"))
        for group,m in {"overall":s["overall"],**s["per_domain"]}.items():
            official.extend((arm,group,k,v) for k,v in m.items())
    table(stage,"official_scores","arm domain metric value",official)
    database=responses/"events.sqlite"
    if not database.is_file():
        return
    with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)) as db:
        events={k:json.loads(v) for k,v in db.execute("select id,payload from events")}
        attempt_rows=[]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='attempts'").fetchone():
            fields={r[1] for r in db.execute("PRAGMA table_info(attempts)")}
            if "reserved_micro_usd" in fields:
                attempt_rows=list(db.execute("SELECT seq,job,status,reserved_micro_usd,input_tokens FROM attempts ORDER BY seq"))
        table(stage,"generation_attempts","attempt job status reserved_micro_usd counted_input_tokens",attempt_rows)
    scope_rows=[]
    scopes=defaultdict(list)
    for iid,r in routes.items():
        scopes[r["scope_id"]].append(iid)
    for sid,ids in scopes.items():
        accepted="snapshot/"+sid in events
        claims=json.loads(events[sid]["response"])["claims"] if accepted else []
        quotes={c["evidence_id"] for c in claims}
        quotes.update(ref["evidence_id"] for c in claims for ref in c.get("additional_evidence",[]))
        scope_rows.append((sid,len(ids),routes[ids[0]]["qa_count"],"accepted" if accepted else "failed",len(claims),len(quotes),
                           sum(c["basis"]=="inferred" for c in claims),sum(c["overrides"] is not None for c in claims)))
    table(stage,"scope_quality","scope items passages status claims cited_passages inferred overrides",scope_rows)
    table(stage,"scope_amortization","scope arm planned_items calls complete cold_tokens metered_tokens tokens_per_item upper_rate_usd upper_rate_usd_per_item",amortized(scopes,events))
    costs=[]
    for key,e in events.items():
        if not isinstance(e,dict) or "system" not in e:
            continue
        arm,iid=key.split("/",1) if "/" in key else ("build",key)
        usage=e["usage"]
        costs.append((arm,key,routes[iid]["scope_id"] if arm!="build" else iid,e.get("version"),e.get("finish"),e.get("elapsed_seconds"),usage.get("promptTokenCount"),usage.get("candidatesTokenCount"),usage.get("thoughtsTokenCount"),usage.get("totalTokenCount")))
    table(stage,"scope_costs","stage job scope model finish seconds input_tokens candidate_tokens thought_tokens total_tokens",costs)
    accounts=[]
    policy=events.get("provenance",{}).get("policy")
    for name in ("build",*ARMS,"research_total"):
        selected=[row for row in costs if name=="research_total" or row[0]==name]
        keys={row[1] for row in selected}
        attempts=[a for a in attempt_rows if name=="research_total" or (name=="build" and "/" not in a[1]) or a[1].startswith(name+"/")]
        metering=[metered(events[key],policy) for key in keys]
        seconds=sorted(row[5] for row in selected if row[5] is not None and not events["config"][0])
        accounts.append((name,len(selected),len(attempts),sum(a[3] for a in attempts),sum(a[1] not in keys or a[2]=="delivery_unknown" or a[2].startswith("HTTP ") for a in attempts),
                        sum(v[0] for v in metering) if all(v[0] is not None for v in metering) else None,
                        sum(v[1] for v in metering) if all(v[1] is not None for v in metering) else None,
                        seconds[(len(seconds)-1)//2] if seconds else None,seconds[int(.95*(len(seconds)-1))] if seconds else None))
    table(stage,"research_costs","stage saved_calls attempts reserved_micro_usd unmetered_attempts metered_tokens upper_rate_usd latency_p50_s latency_p95_s",accounts)
    rng=random.Random(20261123)
    review=[]
    for (task,outcome),ids in sorted(transitions.items()):
        for iid in rng.sample(sorted(ids),min(5,len(ids))):
            review.append((iid,routes[iid]["scope_id"],task,outcome))
    table(stage,"audit_samples","item_id scope_id task stratum",review)

    from .blind import packets
    packets(stage, events, routes, review)

    label = "離線合成回覆驗證" if events["config"][0] else "正式模型作答"
    links = ["official_scores", "paired_differences", "item_results", "item_changes",
             "person_domain_results", "direction_results", "calibration", "rank_summary",
             "rank_results", "rank_intervals", "scope_amortization", "scope_costs", "scope_quality", "research_costs", "generation_attempts", "rank_common_valid", "rank_confusion", "audit_samples"]
    from .meeting import meeting
    meeting(stage,responses.resolve().name,label,routes,scores)
    page = stage/"index.html"
    title = f"<p>{label} ｜ {escape(responses.resolve().name)} ｜ {len(items)} 道考題</p>"
    html = page.read_text(encoding="utf8").replace("<h1>", title+"<h1>",1)
    html += "<h2>Graph 與 Raw 哪些題目有差？</h2>"
    html+='<p><a href="meeting.html">會議結果與可下載的圖</a></p>'
    groups={"graph_better":"Graph 較準","equal":"兩組同分","raw_better":"Raw 較準"}
    for task in ("T1","T2"):
        count=sum(len(transitions[task,k]) for k in groups)
        html+=f"<h3>{task} · {count} 題</h3>"
        for k,caption in groups.items():
            ids=transitions[task,k]
            html+=f'<details><summary>{caption}　{len(ids)} / {count}　<meter min="0" max="{count}" value="{len(ids)}"></meter></summary>'
            html+=" ".join(f'<a href="../audit.html#{escape(iid)}">{escape(iid)}</a>' for iid in ids)+"</details>"
    page.write_text(html+"<h2>來源表</h2>"+"".join(f'<p><a href="{n}.csv">{n}.csv</a></p>' for n in links),encoding="utf8")
