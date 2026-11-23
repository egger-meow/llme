"""Content-addressed edits for one validated builder response."""
import hashlib
import json


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf8")).hexdigest()


def commits(scope, history, claims):
    parent = digest([scope, history])
    for claim in claims:
        edit = {"parent": parent, "operation": "add_claim", "claim": claim}
        parent = digest(edit)
        yield {"id": parent, **edit}
