"""Build the offline researcher view from the pinned human release."""
import json
from pathlib import Path

from dataset import RELEASE, SOURCE, read_release


def main():
    items, scopes = read_release()
    payload = json.dumps(dict(items=items, scopes=scopes, source=SOURCE),
                         ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = Path(__file__).with_name("viewer.html").read_text(encoding="utf8")
    output = RELEASE / "index.html"
    output.write_text(template.replace("/*DATA*/null", payload), encoding="utf8")
    print(output)


if __name__ == "__main__":
    main()
