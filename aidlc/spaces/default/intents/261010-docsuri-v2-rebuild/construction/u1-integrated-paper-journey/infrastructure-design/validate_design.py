"""Read-only infrastructure document checks, never the v2 completion command."""
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
FILES = ("infrastructure-specification.md", "cicd-pipeline.md", "monitoring-design.md")
UPSTREAM = HERE.parent / "nfr-design" / "traceability.json"
NFR = re.compile(r"NFR\d+\.\d+\Z")
NAMED = re.compile(r"^#{2,6}\s+((?:INFRA|PIPE|MON)\d{2})\s+—\s+.+$", re.M)
REQUIRED_SECTIONS = {
    "infrastructure-specification.md": {f"INFRA{i:02}" for i in range(1, 11)},
    "cicd-pipeline.md": {f"PIPE{i:02}" for i in range(1, 7)},
    "monitoring-design.md": {f"MON{i:02}" for i in range(1, 7)},
}
REQUIRED_TABLES = {
    "infrastructure-specification.md": [
        ("Facet", "Choice", "Rationale"),
        ("Service", "Role", "Configuration", "Notes"),
        ("Shared Resource", "Owner Unit", "Consumer Units", "Access Boundary"),
    ],
    "cicd-pipeline.md": [
        ("Workload", "Proposed execution binding", "Enablement / trust conditions"),
        ("Order / stage", "Inputs and work", "Gate / retained evidence"),
        ("Lane / fixture", "Required checks and observations", "Distinct evidentiary limit"),
        ("Item", "Packaging / storage design", "Verification and retention boundary"),
        ("Boundary", "Promotion rule", "Evidence / behavior"),
        ("Trigger / phase", "Authorized procedure in the selected environment", "Verification / stop condition"),
    ],
    "monitoring-design.md": [
        ("Resource / interface", "Concrete design binding", "Access, failure and ownership boundary"),
        ("Metric", "Source", "Threshold", "Why it matters"),
        ("Alert", "Condition", "Severity", "Routes to"),
        ("SLI", "SLO target", "Measurement window"),
        ("Record class", "Concrete format and protection", "Retention / failure treatment"),
        ("Bound", "Candidate experiment value", "Enforcement / stop behavior"),
        ("Check / scope", "What the installed check must inspect", "Pass/expiry rule and recovery evidence"),
    ],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    require(path.is_file(), f"Missing required file: {path}")
    text = path.read_text(encoding="utf-8", errors="strict")
    bad = [character for character in text
           if character == "\ufffd" or
           (unicodedata.category(character) == "Cc" and character not in "\t\n\r")]
    require(not bad, f"Invalid replacement/control character: {path}")
    return text


def without_fences(text, path):
    """Check balanced fences and return prose for link/heading/table parsing."""
    result = []
    opened = None
    contents = 0
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opened:
            closes = marker and marker[1][0] == opened[0] and len(marker[1]) >= opened[1] and not marker[2].strip()
            if closes:
                require(contents <= 15, f"Fence exceeds 15 content lines: {path}:{opened[2]} ({contents})")
                opened = None
            else:
                contents += 1
            result.append("")
        elif marker:
            opened = (marker[1][0], len(marker[1]), number)
            contents = 0
            result.append("")
        else:
            result.append(line)
    require(opened is None, f"Unclosed fence: {path}:{opened[2] if opened else ''}")
    return "\n".join(result)


def cells(line):
    return tuple(cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|")))


def tables(prose, path):
    lines = prose.splitlines()
    found = []
    for index in range(len(lines) - 1):
        if not lines[index].strip().startswith("|"):
            continue
        separator = cells(lines[index + 1])
        if not separator or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
            continue
        header = cells(lines[index])
        require(len(header) == len(separator), f"Malformed table header: {path}:{index + 1}")
        rows = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].strip().startswith("|"):
            row = cells(lines[cursor])
            require(len(row) == len(header), f"Unescaped pipe or unequal table columns: {path}:{cursor + 1}")
            rows.append(row)
            cursor += 1
        require(rows, f"Empty table: {path}:{index + 1}")
        found.append((header, rows))
    return found


def anchors(prose):
    """GFM-like heading slugs plus explicit HTML anchor IDs for this stage."""
    result = set()
    occurrences = Counter()
    for heading in re.findall(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", prose, re.M):
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower(), flags=re.UNICODE).replace(" ", "-")
        count = occurrences[slug]
        occurrences[slug] += 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    result.update(re.findall(r"\b(?:id|name)=[\"']([^\"']+)[\"']", prose))
    return result


def local_links(proses):
    count = 0
    fragments = 0
    for path, prose in proses.items():
        destinations = re.findall(r"\]\((<[^>]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\)", prose)
        destinations += re.findall(r"^ {0,3}\[[^]]+\]:\s*(<[^>]+>|\S+)(?:\s+[\"'][^\n]*?[\"'])?\s*$", prose, re.M)
        for destination in destinations:
            target = destination.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            linked = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            require(linked.is_file(), f"Missing local link: {path.relative_to(HERE)} -> {target}")
            count += 1
            if parsed.fragment and linked in proses:
                require(unquote(parsed.fragment) in anchors(proses[linked]),
                        f"Missing stage fragment: {path.relative_to(HERE)} -> {target}")
                fragments += 1
    return count, fragments


def unique_ids(values, label, expected=None):
    require(isinstance(values, list) and all(isinstance(value, str) for value in values), f"Invalid IDs: {label}")
    counts = Counter(values)
    require(len(values) == 37 and len(counts) == 37, f"Expected 37 unique IDs: {label}; count={len(values)}, duplicates={[value for value, count in counts.items() if count > 1]}")
    require(all(NFR.fullmatch(value) for value in values), f"Malformed NFR ID: {label}")
    if expected is not None:
        require(set(values) == expected, f"NFR mismatch in {label}: missing={sorted(expected - set(values))}, extra={sorted(set(values) - expected)}")
    return set(values)


def main():
    upstream = json.loads(read(UPSTREAM))
    require(upstream.get("stage") == "nfr-design" and upstream.get("unit") == "u1-integrated-paper-journey", "Wrong upstream stage/unit")
    expected = unique_ids(upstream["upstream_ids"], "upstream upstream_ids")
    unique_ids([row["id"] for row in upstream["coverage"]], "upstream coverage", expected)
    for name in FILES:
        read(HERE / name)
    trace = json.loads(read(HERE / "traceability.json"))
    require(trace.get("stage") == "infrastructure-design", "Wrong traceability stage")
    require(trace.get("unit") == "u1-integrated-paper-journey", "Wrong traceability unit")
    unique_ids(trace["upstream_ids"], "infrastructure upstream_ids", expected)
    unique_ids([row["id"] for row in trace["coverage"]], "infrastructure coverage", expected)

    paths = sorted(path.resolve() for path in HERE.rglob("*.md")
                   if path.name != "memory.md" and "reviews" not in path.relative_to(HERE).parts)
    texts = {path: read(path) for path in paths}
    proses = {path: without_fences(text, path.relative_to(HERE)) for path, text in texts.items()}
    assignments = {}
    named = {}
    table_count = 0
    for name in FILES:
        prose = proses[(HERE / name).resolve()]
        identifiers = NAMED.findall(prose)
        require(len(identifiers) == len(set(identifiers)), f"Duplicate named section in {name}")
        require(set(identifiers) == REQUIRED_SECTIONS[name], f"Named sections differ in {name}: {set(identifiers) ^ REQUIRED_SECTIONS[name]}")
        named[name] = set(identifiers)
        found = tables(prose, name)
        require(found, f"No required design tables: {name}")
        table_count += len(found)
        headers = [header for header, rows in found]
        for header in REQUIRED_TABLES[name]:
            require(header in headers, f"Missing required table in {name}: {header}")
        for header, rows in found:
            for row in rows:
                if not NFR.fullmatch(row[0]):
                    continue
                requirement, target = row[0], row[1]
                require(requirement not in assignments, f"Duplicate mapped requirement: {requirement}")
                require(target in named[name], f"Unresolved mapping: {name}: {requirement} -> {target}")
                assignments[requirement] = f"{name}: {target}"
    require(set(assignments) <= expected, f"Unknown mapped requirements: {sorted(set(assignments) - expected)}")
    refs = set(re.findall(r"\bNFR\d+\.\d+\b", "\n".join(texts.values())))
    require(refs <= expected, f"Unknown NFR references: {sorted(refs - expected)}")
    for row in trace["coverage"]:
        require(row.get("status") == "OK", f"Unresolved traceability status: {row}")
        target = row.get("target", "")
        match = re.fullmatch(r"([^:]+\.md):\s+((?:INFRA|MON|PIPE)\d{2})", target)
        require(match is not None, f"Malformed named traceability target: {row}")
        name, identifier = match.groups()
        require(name in named and identifier in named[name], f"Unresolved named traceability target: {row}")
        if row["id"] in assignments:
            require(target == assignments[row["id"]], f"Traceability target does not match explicit requirement table: {row}")
    for path, prose in proses.items():
        if path.name not in FILES:
            tables(prose, path.relative_to(HERE))
    links, fragments = local_links(proses)
    print(f"PASS: {len(FILES)} required documents, {len(proses)} stage Markdown files, "
          f"37 unique upstream NFRs, {sum(len(values) for values in named.values())} named sections, "
          f"{table_count} required-document tables, {links} local links, {fragments} stage fragments; traceability resolves.")
    print("Limits: document structure only; external links, upstream fragments and semantic adequacy require review. "
          "No application, model, capacity, security, recovery or completion check ran.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
