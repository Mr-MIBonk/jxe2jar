#!/usr/bin/env python3
"""Use CFR only where its replacement source passes an isolated javac check.

Candidates come from recompile_check.py --json-report. The source tree is changed
only with --apply; every accepted file is decompiled from the supplied JAR.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from recompile_check import DEF_JAVAC, DEF_OSGI


HERE = Path(__file__).resolve().parent


def candidates(tree, report):
    data = json.loads(Path(report).read_text())
    paths = []
    for raw in data["reported_failures"]:
        path = Path(raw).resolve()
        try:
            rel = path.relative_to(tree)
        except ValueError:
            continue
        if rel.suffix == ".java" and path.is_file():
            paths.append((path, rel))
    return sorted(paths, key=lambda item: str(item[1]))


def cfr_source(archive, entries, rel, jar, java, cfr, work, variant, flags):
    base = rel.as_posix()[:-5]
    direct = base + ".class"
    if direct not in entries:
        return None, "no class in JAR"
    classes = work / "classes"
    for name in entries:
        if name == direct or (name.startswith(base + "$") and name.endswith(".class")):
            path = classes / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
    output = work / variant
    command = [java, "-Xmx3g", "-jar", str(cfr), str(classes / direct),
               "--outputdir", str(output), "--comments", "false", "--showversion", "false",
               "--silent", "true", "--extraclasspath", str(jar)] + flags
    run = subprocess.run(command, capture_output=True, text=True)
    source = output / rel
    if run.returncode or not source.is_file():
        return None, "CFR failed: " + (run.stderr.strip() or run.stdout.strip())[:200]
    return source, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("jar", type=Path)
    parser.add_argument("diagnostics", help="JSON from recompile_check.py --json-report")
    parser.add_argument("--source", default="1.4")
    parser.add_argument("--target", default=None)
    parser.add_argument("--jcl", type=Path, help="firmware JCL for -bootclasspath")
    parser.add_argument("--osgi", type=Path, default=Path(DEF_OSGI))
    parser.add_argument("--javac", default=DEF_JAVAC)
    parser.add_argument("--java", default="java")
    parser.add_argument("--cfr", type=Path, default=HERE / "cfr-0.152.jar")
    parser.add_argument("--result", type=Path, help="write per-candidate result JSON")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    tree, jar = args.tree.resolve(), args.jar.resolve()
    selected = candidates(tree, args.diagnostics)
    classpath = str(jar)
    if args.osgi.is_dir():
        osgi_jars = [
            str(path) for path in sorted(args.osgi.glob("org.osgi*.jar"))
            if "sources" not in path.name and "javadoc" not in path.name
        ]
        if osgi_jars:
            classpath += os.pathsep + os.pathsep.join(osgi_jars)
    results = {}
    with zipfile.ZipFile(jar) as archive:
        entries = set(archive.namelist())
        for original, rel in selected:
            with tempfile.TemporaryDirectory(prefix="cfr_compile_fallback_") as temp:
                work = Path(temp)
                variants = [("default", []), ("no_boxing", ["--sugarboxing", "false"])]
                for variant, flags in variants:
                    source, error = cfr_source(archive, entries, rel, jar, args.java, args.cfr, work, variant, flags)
                    if error:
                        results[rel.as_posix()] = {"status": "skipped", "reason": error}
                        continue
                    compiled = work / ("compiled_" + variant)
                    compiled.mkdir()
                    command = [args.javac, "-nowarn", "-proc:none", "-source", args.source,
                               "-target", args.target or args.source]
                    if args.jcl:
                        command += ["-bootclasspath", str(args.jcl)]
                    command += ["-cp", classpath, "-d", str(compiled), str(source)]
                    run = subprocess.run(command, capture_output=True, text=True)
                    if run.returncode:
                        errors = re.findall(r": error: (.*)", run.stderr)
                        results[rel.as_posix()] = {"status": "skipped", "reason": errors[:2] or [run.stderr[:200]]}
                        continue
                    if args.apply:
                        original.write_bytes(source.read_bytes())
                    results[rel.as_posix()] = {"status": "applied" if args.apply else "would_apply",
                                               "variant": variant}
                    break
    accepted = sum(value["status"] != "skipped" for value in results.values())
    print(f"CFR compilable: {accepted}/{len(results)} candidate(s); "
          + ("applied" if args.apply else "dry-run"))
    for rel, value in results.items():
        print(value["status"], rel, value.get("reason", ""))
    if args.result:
        args.result.write_text(json.dumps({"tree": str(tree), "jar": str(jar),
                                           "source": args.source, "target": args.target or args.source,
                                           "results": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
