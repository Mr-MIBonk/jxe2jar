#!/usr/bin/env python3
"""Remove clone catches that the firmware-JCL compiler proves unreachable.

The original classes contain these handlers, but some firmware JCL releases
declare Object.clone() without a checked exception. This repair is driven by
the isolated compiler report, and only touches the reported catch clauses.
Run the isolated compile check again after applying it.
"""

import argparse
import json
import re
from pathlib import Path


DIAGNOSTIC = "exception java.lang.CloneNotSupportedException is never thrown"
CATCH = re.compile(
    r"}\s*catch\s*\(\s*(?:java\.lang\.)?CloneNotSupportedException\s+\w+\s*\)\s*{"
)


def repair(source: str, line: int) -> str:
    offset = sum(map(len, source.splitlines(keepends=True)[: line - 1]))
    match = CATCH.search(source, max(0, offset - 8), offset + 300)
    if match is None:
        raise ValueError(f"no clone catch near line {line}")
    closing_try = match.start()
    depth = 1
    cursor = closing_try - 1
    while cursor >= 0 and depth:
        if source[cursor] == "}":
            depth += 1
        elif source[cursor] == "{":
            depth -= 1
        cursor -= 1
    prefix = source[max(0, cursor - 10) : cursor + 1]
    opener = re.search(r"\btry\s*$", prefix)
    if depth or opener is None:
        raise ValueError(f"no matching try near line {line}")
    try_start = max(0, cursor - 10) + opener.start()
    opener_end = cursor + 1
    catch_open = match.end() - 1
    depth = 1
    cursor = catch_open + 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        raise ValueError(f"unclosed catch near line {line}")
    # Keep the try body as a normal block, preserving its local variable scope.
    return source[:try_start] + source[opener_end:closing_try + 1] + source[cursor:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    changed = 0
    for name, item in report["reported_failures"].items():
        diagnostics = [error for error in item["errors"] if DIAGNOSTIC in error]
        if not diagnostics:
            continue
        path = Path(name)
        source = path.read_text()
        for diagnostic in sorted(diagnostics, key=lambda error: int(error.split(":")[0]), reverse=True):
            source = repair(source, int(diagnostic.split(":")[0]))
        if args.apply:
            path.write_text(source)
        changed += 1
        print(path)
    print(f"{changed} file(s) {'repaired' if args.apply else 'would be repaired'}")


if __name__ == "__main__":
    main()
