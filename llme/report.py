"""Paired results from saved responses; no model access."""
import csv
import random
from collections import defaultdict
from statistics import mean

from .run import ARMS, PACKAGE


def export(stage, items, predictions, strict):
    cells = defaultdict(lambda: [0, 0.0])
    differences = []
    with (stage / "item_results.csv").open("w", encoding="utf8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("item_id", "person", "domain", "task", "arm", "parsed", "correct_or_error"))
        for item in items:
            iid, person, domain = (item[k] for k in ("item_id", "participant_id", "topic"))
            task = "T1" if "answer_options" in item and item["task_type"] == "belief_attribution" else "T2"
            for arm in ARMS:
                answer = predictions[arm][iid]
                if task == "T1":
                    value = 100 * int(answer in item["answer"].split("/"))
                else:
                    value = 6 if answer is None else abs(answer-item["user_answer"]) / (2 if item["scale"][1]==10 else 1)
                writer.writerow((iid, person, domain, task, arm, answer, value))
                cell = cells[task, domain, arm, person]
                cell[0] += 1
                cell[1] += value
    people = sorted({item["participant_id"] for item in items})
    domains = sorted({item["topic"] for item in items})
    for task in ("T1","T2"):
        for left,right in (("graph","raw"),("graph","flat"),("flat","raw")):
            blocks = [[(cells[task,d,left,p][0], cells[task,d,left,p][1]-cells[task,d,right,p][1]) for p in people] for d in domains]
            def effect(indices):
                return mean(sum(block[i][1] for i in indices)/sum(block[i][0] for i in indices) for block in blocks)
            indices = range(len(people))
            rng = random.Random(20261123)
            draws = sorted(effect(rng.choices(indices,k=len(people))) for _ in range(5000))
            differences.append((task,left,right,effect(indices),draws[124],draws[4874]))
    with (stage/"paired_differences.csv").open("w",newline="",encoding="utf8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("task","left","right","difference","lower95","upper95"))
        writer.writerows(differences)
    lines = ["<!doctype html><html lang='zh-Hant'><meta charset=utf-8><title>配對結果</title>",
             "<h1>同一批訪談的配對結果</h1><p>T1 為正確率差（百分點），越高越好。T2 為平均誤差差，越低越好。橫線為受訪者配對重抽的 95% 區間。</p>"]
    for task in ("T1","T2"):
        subset = [r for r in differences if r[0]==task]
        limit = max(0.01,max(abs(v) for row in subset for v in row[3:]))
        lines.append(f"<h2>{task}</h2>")
        for _,left,right,point,low,high in subset:
            lines.append(f'<p>{left} − {right}　{point:.3f} [{low:.3f}, {high:.3f}]</p><svg width="300" height="22"><path d="M150 0v22" stroke="gray"/><path d="M{150+140*low/limit} 11 H{150+140*high/limit}" stroke="teal"/><circle cx="{150+140*point/limit}" cy="11" r="4" fill="teal"/></svg>')
    (stage/"index.html").write_text("\n".join(lines), encoding="utf8")
    with (PACKAGE/"scoring/rank_pairs.csv").open(encoding="utf8") as source, (stage/"rank_results.csv").open("w",newline="",encoding="utf8") as target:
        writer = csv.writer(target)
        writer.writerow(("left_item","right_item","gold_sign","arm","predicted_sign","hit"))
        for row in csv.DictReader(source):
            left,right = row["left_item_id"],row["right_item_id"]
            for arm in ARMS:
                a,b = strict[arm][left],strict[arm][right]
                sign = (a>b)-(a<b) if a in range(1,6) and b in range(1,6) else None
                writer.writerow((left,right,row["gold_sign"],arm,sign,int(sign==int(row["gold_sign"]))))
