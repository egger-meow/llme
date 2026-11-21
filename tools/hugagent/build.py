"""Build the offline researcher view from the pinned upstream JSONL files."""
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ref/HugAgent/data"
source = json.loads(Path(__file__).with_name("source.json").read_text(encoding="utf-8-sig"))
items, scopes, scope_ids = [], [], {}
t2_by_person = defaultdict(list)
for name, digest in sorted(source["files"].items()):
    raw = (DATA / name).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"Unexpected file hash: {name}")
    for line, record in enumerate(raw.splitlines(), 1):
        row = json.loads(record)
        history = row.pop("context_qas")
        person = row["participant_id"], row["topic"]
        key = (*person, json.dumps(history, sort_keys=True))
        if key not in scope_ids:
            scope_ids[key] = len(scopes)
            scopes.append(history)
        item = dict(row=row, scope=scope_ids[key], file=name, line=line)
        items.append(item)
        if "user_answer" in row:
            t2_by_person[person].append(item)

def words(qa):
    return qa["question"], qa["answer"]

for item in items:
    row = item["row"]
    if "source_qa" in row:
        target = words(row["source_qa"])
        if target in map(words, scopes[item["scope"]]):
            raise ValueError(row["item_id"])
        for other in t2_by_person[row["participant_id"], row["topic"]]:
            match = next((i for i,q in enumerate(scopes[other["scope"]]) if words(q)==target), None)
            if match is not None:
                item["leak"] = [other["row"]["item_id"], match]
                break

assert (len(items), len(scopes), sum("leak" in x for x in items)) == (1742,460,271)
payload = json.dumps(dict(items=items, scopes=scopes, source=source), ensure_ascii=False, separators=(",",":")).replace("<","\\u003c")
template = Path(__file__).with_name("viewer.html").read_text(encoding="utf8")
output = DATA.parent / "index.html"
output.write_text(template.replace("/*DATA*/null",payload), encoding="utf8")
print(output)

