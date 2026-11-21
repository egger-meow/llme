"""Read the pinned human release and resolve the exact interview attached to each item."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path


RELEASE = Path(__file__).resolve().parents[2] / "ref/HugAgent"
SOURCE = json.loads(Path(__file__).with_name("source.json").read_text(encoding="utf-8-sig"))


def verified_bytes(path, digest):
    data = path.read_bytes()
    if sha256(data).hexdigest() != digest:
        raise ValueError(f"SHA-256 mismatch: {path}")
    return data


def qa_text(qa):
    return qa["question"], qa["answer"]


def read_release():
    items, histories, scope_ids = [], [], {}
    t2_by_person = defaultdict(list)
    for name, digest in sorted(SOURCE["files"].items()):
        data = verified_bytes(RELEASE / "data" / name, digest)
        for line, record in enumerate(data.splitlines(), 1):
            row = json.loads(record)
            history = row.pop("context_qas")
            person = row["participant_id"], row["topic"]
            key = (*person, json.dumps(history, sort_keys=True))
            if key not in scope_ids:
                scope_ids[key] = len(histories)
                histories.append(history)
            item = dict(row=row, scope=scope_ids[key], file=name, line=line)
            items.append(item)
            if "user_answer" in row:
                t2_by_person[person].append(item)

    for item in items:
        row = item["row"]
        if "source_qa" not in row:
            continue
        target = qa_text(row["source_qa"])
        if target in map(qa_text, histories[item["scope"]]):
            raise ValueError(f"Held-out QA is visible in {row['item_id']}")
        for other in t2_by_person[row["participant_id"], row["topic"]]:
            history = histories[other["scope"]]
            match = next((i for i, qa in enumerate(history) if qa_text(qa) == target), None)
            if match is not None:
                item["leak"] = [other["row"]["item_id"], match]
                break

    counts = len(items), len(histories), sum("leak" in item for item in items)
    if counts != (1742, 460, 271):
        raise ValueError(f"Unexpected item, history or cross-item match count: {counts}")
    return items, histories
