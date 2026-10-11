"""Read-only document consistency checks; this is not the v2 completion check."""
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
FILES = [f"{category}-requirements.md" for category in
         ("performance", "security", "scalability", "reliability", "observability")]
FILES.append("tech-stack-decisions.md")


def main():
    texts = {name: (HERE / name).read_text() for name in FILES}
    definitions = Counter()
    links = 0
    for name, text in texts.items():
        assert "\ufffd" not in text and "\x00" not in text, name
        rows = re.findall(r"^\| (NFR\d+\.\d+) \|(.+)$", text, re.M)
        assert rows, f"No derived requirements in {name}"
        for identifier, rest in rows:
            definitions[identifier] += 1
            assert len(rest.split("|")) >= 3, (name, identifier)
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = unquote(target.split("#", 1)[0])
            assert (HERE / path).exists(), (name, target)
            links += 1
    assert all(count == 1 for count in definitions.values()), definitions
    refs = set(re.findall(r"\bNFR\d+\.\d+\b", "\n".join(texts.values())))
    assert refs <= definitions.keys(), refs - definitions.keys()
    trace = json.loads((HERE / "traceability.json").read_text())
    assert trace["stage"] == "nfr-requirements"
    assert trace["unit"] == "u1-integrated-paper-journey"
    upstream = (HERE / "../../../inception/requirements-analysis/requirements.md").read_text()
    parents = set(re.findall(r"^\| (NFR\d+) \|", upstream, re.M))
    assert parents and set(trace["upstream_ids"]) == parents
    coverage = trace["coverage"]
    assert len(coverage) == len(parents)
    assert {row["id"] for row in coverage} == parents
    mapped = []
    for row in coverage:
        assert row["status"] == "OK", row
        targets = [item.strip() for item in row["target"].split(",")]
        assert targets and all(item.startswith(row["id"] + ".") for item in targets)
        mapped.extend(targets)
    assert len(mapped) == len(set(mapped))
    assert set(mapped) == definitions.keys(), (set(mapped) ^ definitions.keys())
    # Exact numbered local workflow/check references must resolve upstream.
    fd = HERE / "../functional-design"
    sources = "\n".join((fd / name).read_text() for name in
                        ("functional-spec.md", "rules.md", "frontend-components.md"))
    pattern = r"\b(?:WF\d+|LC\d+|BR\d+\.\d+|FUI-\d+)\b"
    cited = set(re.findall(pattern, "\n".join(texts.values())))
    known = set(re.findall(pattern, sources))
    assert cited <= known, cited - known
    print(f"PASS: {len(FILES)} documents, {len(parents)} parent NFRs, "
          f"{len(definitions)} unique derived requirements, {len(cited)} local design "
          f"references, {links} local links; all traceability targets resolve.")
    print("Limits: semantic fit, operating feasibility and application behavior require "
          "independent review and executable evidence; no runtime checks ran.")


if __name__ == "__main__":
    main()
