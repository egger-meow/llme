"""Standalone meeting figures rebuilt from scored items."""
import csv
from collections import defaultdict
from html import escape
import json
from statistics import mean

from .run import ARMS, PACKAGE

LABELS={"baseline_stance":"基準立場","experience_or_perception":"經驗或感受",
        "hypothetical_scenario":"假設情境","reason_influence":"理由影響"}
COLORS={"raw":"#56646b","graph":"#067466","flat":"#af5720"}


def figure(path,title,context,rows):
    width=760
    height=115+26*len(rows)
    limit=max([abs(value) for label,value,color in rows]+[0.01])
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="system-ui,sans-serif" fill="#193431">',
           f'<text x="16" y="30" font-size="21">{escape(title)}</text>',
           f'<text x="16" y="56" font-size="13">{escape(context)}</text>',
           f'<path d="M470 72V{height-25}" stroke="#9ba9a5"/>']
    for i,(label,value,color) in enumerate(rows):
        y=88+26*i
        x=470+165*value/limit
        lines.extend([f'<text x="16" y="{y+5}" font-size="14">{escape(label)}</text>',
                      f'<path d="M470 {y}H{x}" stroke="{color}" stroke-width="9"/>',
                      f'<text x="680" y="{y+5}" font-size="14">{value:.2f}</text>'])
    path.write_text("".join(lines)+"</g></svg>",encoding="utf8")


def meeting(stage,run,label,routes,scores):
    by_measure=defaultdict(list)
    by_person=defaultdict(list)
    for iid,r in routes.items():
        for arm in ARMS:
            if r["task"]=="T2":
                by_measure[r["measure"],arm].append(scores[iid,arm])
        by_person[r["participant_id"],r["task"],r["topic"]].append(scores[iid,"graph"]-scores[iid,"raw"])
    charts=[]
    data=[]
    rows=[]
    for measure,caption in LABELS.items():
        for arm in ARMS:
            vals=by_measure[measure,arm]
            data.append(("measure",measure,"T2",arm,len(vals),mean(vals)))
            rows.append((f"{caption} · {arm} · {len(vals)} 題",mean(vals),COLORS[arm]))
    charts.append(("t2-measures","四類 T2 的平均誤差","逐題平均，越低越準",rows))
    for task,unit in (("T1","正確率差，百分點"),("T2","平均誤差差，五分尺度")):
        rows=[]
        for p in sorted({k[0] for k in by_person}):
            groups=[v for (person,t,d),v in by_person.items() if person==p and t==task]
            if groups:
                value=mean(mean(v) for v in groups)
                n=sum(map(len,groups))
                rows.append((f"{p} · {len(groups)} 域 · {n} 題",value,COLORS["graph"]))
                data.append(("person",p,task,"graph-raw",n,value))
        charts.append((f"person-{task}",f"{task} 每人 Graph − Raw",unit+"，個人內各有題領域等權",rows))
    with (stage/"meeting_points.csv").open("w",encoding="utf8",newline="") as out:
        writer=csv.writer(out)
        writer.writerow(("group","id","task","method","items","value"))
        writer.writerows(data)
    html=['<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>會議結果</title>',
          '<style>body{max-width:800px;margin:auto;padding:20px;font:16px/1.6 system-ui}img{width:100%}td,th{padding:5px 12px;text-align:right}</style>',
          f'<p>{escape(run)} · {label}</p><h1>同一份訪談，哪種表示預測得準？</h1>',
          '<table><tr><th>方法</th><th>T1 正確率 ↑</th><th>T2 誤差 ↓</th></tr>']
    baseline=json.loads((PACKAGE/"manifest.json").read_text(encoding="utf8"))["official_baselines"]
    methods=[("固定 A／1",baseline["majority"]),("隨機 · 5 個 seed",baseline["random"])]
    methods.extend((arm,json.loads((stage/f"{arm}-scores.json").read_text(encoding="utf8"))["overall"]) for arm in ARMS)
    for name,m in methods:
        html.append(f'<tr><td>{name}</td><td>{m["bsi_acc"]:.2f}%</td><td>{m["bdu_mae"]:.2f}</td></tr>')
    html.append('</table><p>356 道 T1、1,386 道 T2，三域等權。 <a href="official_scores.csv">三組官方分數</a></p>')
    for name,title,unit,values in charts:
        figure(stage/f"{name}.svg",title,f"{run} · {label} · {unit}",values)
        html.append(f'<img src="{name}.svg" alt="{escape(title)}"><p><a href="meeting_points.csv">圖上數值</a> · <a href="item_results.csv">逐題來源</a></p>')
    (stage/"meeting.html").write_text("".join(html),encoding="utf8")
