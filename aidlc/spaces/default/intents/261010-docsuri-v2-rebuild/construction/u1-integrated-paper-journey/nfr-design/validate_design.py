"""Read-only NFR design document checks, never the v2 completion command."""
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
FILES = [f"{name}-design.md" for name in
         ("performance", "security", "scalability", "reliability", "observability")]
FILES.append("logical-components.md")
REQ = HERE / "../nfr-requirements"


def main():
    upstream = json.loads((REQ / "traceability.json").read_text())
    expected = [item.strip() for row in upstream["coverage"]
                for item in row["target"].split(",")]
    assert len(expected) == len(set(expected)), "Duplicate upstream requirement"
    req_files = [f"{name}-requirements.md" for name in
                 ("performance", "security", "scalability", "reliability", "observability")]
    req_files.append("tech-stack-decisions.md")
    defined = Counter(identifier for name in req_files for identifier in
                      re.findall(r"^\| (NFR\d+\.\d+) \|", (REQ / name).read_text(), re.M))
    assert set(defined) == set(expected) and all(n == 1 for n in defined.values())
    texts = {name: (HERE / name).read_text() for name in FILES}
    assignments = {}
    solutions = {}
    local_links = 0
    for name, text in texts.items():
        assert "\ufffd" not in text and "\x00" not in text, name
        assert not re.search(r"^\s*```", text, re.M), f"Unexpected code/diagram fence: {name}"
        headings = re.findall(r"^### ((?:P|SEC|SC|REL|OBS|LOG)\d{2}) — .+$", text, re.M)
        assert headings and len(headings) == len(set(headings)), (name, headings)
        for identifier in headings:
            assert identifier not in solutions, identifier
            solutions[identifier] = name
        rows = re.findall(r"^\| (NFR\d+\.\d+) \| ((?:P|SEC|SC|REL|OBS|LOG)\d{2}) \|", text, re.M)
        assert rows, name
        for requirement, solution in rows:
            assert requirement not in assignments, requirement
            assert solution in headings, (name, requirement, solution)
            assignments[requirement] = f"{name}: {solution}"
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = unquote(target.split("#", 1)[0])
            assert (HERE / path).is_file(), (name, target)
            local_links += 1
    assert set(assignments) == set(expected), set(assignments) ^ set(expected)
    refs = set(re.findall(r"\bNFR\d+\.\d+\b", "\n".join(texts.values())))
    assert refs <= set(expected), refs - set(expected)
    trace = json.loads((HERE / "traceability.json").read_text())
    assert trace["stage"] == "nfr-design"
    assert trace["unit"] == "u1-integrated-paper-journey"
    assert len(trace["upstream_ids"]) == len(expected)
    assert set(trace["upstream_ids"]) == set(expected)
    assert len(trace["coverage"]) == len(expected)
    assert len({row["id"] for row in trace["coverage"]}) == len(expected)
    for row in trace["coverage"]:
        assert row["status"] == "OK", row
        assert row["target"] == assignments[row["id"]], row
    fd = HERE / "../functional-design"
    sources = "\n".join((fd / name).read_text() for name in
                        ("functional-spec.md", "rules.md", "frontend-components.md"))
    pattern = r"\b(?:WF\d+|LC\d+|BR\d+\.\d+|FUI-\d+)\b"
    cited = set(re.findall(pattern, "\n".join(texts.values())))
    assert cited <= set(re.findall(pattern, sources)), cited - set(re.findall(pattern, sources))
    print(f"PASS: {len(FILES)} documents, {len(expected)} upstream requirements, "
          f"{len(solutions)} named solutions, {local_links} local file links, "
          f"{len(cited)} exact functional references; traceability resolves.")
    print("Limits: link fragments and semantic adequacy require review; no application, "
          "model, capacity, security or recovery check ran.")


if __name__ == "__main__":
    main()
