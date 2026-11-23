"""Export the score overview as a standalone page and CSV."""
import csv
from html import escape

from .run import ARMS


def export_summary(folder, data):
    questions = [q for row in data["rows"] for q in row["questions"]]
    total = len(questions)
    labels = ("有答案", "缺答", "T1 正確率 (%)", "T2 官方正確率 (%)", "T2 平均絕對誤差 ↓")
    rows = []
    for arm in ARMS:
        answered = sum(bool((q["answers"].get(arm) or "").strip()) for q in questions)
        scores = data["scores"][arm]
        rows.append((arm.title(), answered, total - answered,
                     scores.get("bsi_acc"), scores.get("bdu_acc"), scores.get("bdu_mae")))

    with (folder / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("組別", *labels))
        writer.writerows(rows)

    def display(value):
        if value is None:
            return "—"
        return f"{value:.3f}" if isinstance(value, float) else str(value)

    charts = []
    for index in (1, 3, 4, 5):
        maximum = {1: total, 3: 100, 4: 100}.get(index)
        maximum = maximum or max((row[index] or 0 for row in rows), default=0) or 1
        bars = "".join(
            f'<div class="row"><span>{row[0]}</span><meter aria-label="{row[0]} {labels[index-1]}" '
            f'max="{maximum}" value="{row[index]}"></meter><b>{display(row[index])}</b></div>'
            for row in rows if row[index] is not None
        )
        if bars:
            charts.append(f"<section><h2>{labels[index-1]}</h2>{bars}</section>")
    headings = "".join(f'<th scope="col">{label}</th>' for label in ("組別", *labels))
    tbody = "".join(
        f'<tr><th scope="row">{row[0]}</th>'
        + "".join(f"<td>{display(value)}</td>" for value in row[1:]) + "</tr>"
        for row in rows
    )
    title = f"{escape(folder.name)} 實驗結果"
    path = folder / "summary.html"
    path.write_text(f"""<!doctype html>
<html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{font: 17px system-ui; color: #172d35; max-width: 880px; margin: 36px auto; padding: 0 18px}}
section {{border-top: 1px solid #ccc; padding-bottom: 16px}}
.row {{display: grid; grid-template-columns: 60px 1fr 72px; align-items: center; gap: 12px}}
meter {{width: 100%; height: 24px}}
th, td {{padding: 8px; border-bottom: 1px solid #ccc; text-align: right}}
.table {{overflow-x: auto}}
</style>
<h1>{title}</h1>
<p>{escape(data["model"])} · {total} 題 · {len(data["rows"])} 份訪談</p>
<p><a href="summary.csv">下載 CSV</a> · <a href="audit.html">查看逐題與建圖紀錄</a></p>
<h2>結果總表</h2>
<div class="table"><table><thead><tr>{headings}</tr></thead><tbody>{tbody}</tbody></table></div>
{"".join(charts)}
</html>
""", encoding="utf8")
    return path
