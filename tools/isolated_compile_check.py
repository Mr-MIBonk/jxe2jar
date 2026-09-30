#!/usr/bin/env python3
"""Compile decompiled Java files independently against their original class JAR.

This is the round-trip source gate for corpora that cannot be passed to one
javac invocation: JVM class names can legally clash with Java package names,
and an error in one source can mask later errors in another. The optional
version-aware mode uses Java 1.4 plus the firmware JCL for classfile major
versions up to 48, and Java 1.5 with JDK 8's boot classes for major 49.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from recompile_check import DEF_JAVAC, DEF_OSGI, collect

HERE = Path(__file__).resolve().parent


def selected_files(paths, report):
    files = [Path(raw).resolve() for raw in collect(map(str, paths), 0)]
    if report:
        chosen = {Path(raw).resolve() for raw in json.loads(report.read_text())["reported_failures"]}
        files = [path for path in files if path in chosen]
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--jcl", type=Path)
    parser.add_argument("--libs", "--osgi", dest="libs", type=Path, default=Path(DEF_OSGI),
                        help="directory of supplemental compile-time JARs")
    parser.add_argument("--javac", default=DEF_JAVAC)
    parser.add_argument("--java", default=None, help="Java binary (defaults to sibling of --javac)")
    parser.add_argument("--source", default="1.4")
    parser.add_argument("--target", default=None)
    parser.add_argument("--version-aware", action="store_true")
    parser.add_argument("--from-report", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()

    tree, jar = args.tree.resolve(), args.jar.resolve()
    files = selected_files([tree], args.from_report)
    if args.limit:
        files = files[:args.limit]
    if not files:
        print("no .java files selected")
        return 2
    if args.jcl and not args.jcl.is_file():
        parser.error("--jcl does not exist")
    supplements = sorted(str(path.resolve()) for path in args.libs.glob("*.jar")
                         if "sources" not in path.name and "javadoc" not in path.name)
    classpath = os.pathsep.join([str(jar)] + supplements)
    levels = {}
    if args.version_aware:
        with zipfile.ZipFile(jar) as archive:
            for path in files:
                name = path.relative_to(tree).as_posix()[:-5] + ".class"
                try:
                    major = int.from_bytes(archive.read(name)[6:8], "big")
                except KeyError:
                    parser.error("missing class in JAR: " + name)
                levels[path] = "1.5" if major >= 49 else "1.4"
    else:
        levels = {path: args.source for path in files}

    java = args.java or str(Path(args.javac).with_name("java"))
    results = {}
    with tempfile.TemporaryDirectory(prefix="isolated_compile_check_") as directory:
        work = Path(directory)
        sourcepath = work / "empty_sourcepath"
        sourcepath.mkdir()
        output = work / "compiled"
        output.mkdir()
        runner = work / "runner"
        runner.mkdir()
        build = subprocess.run([str(args.javac), "-d", str(runner),
                                str(HERE / "IsolatedCompileRunner.java")],
                               capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError("cannot build IsolatedCompileRunner: " + build.stderr)
        # javac's file manager caches the bootclasspath. Keep Java 1.4/JCL and
        # Java 1.5/JDK-boot runs in separate processes so neither leaks into the other.
        for level in sorted(set(levels.values())):
            group = [path for path in files if levels[path] == level]
            target = level if args.version_aware else args.target or level
            input_rows = "".join("%s\t%s\t%s\n" % (level, target, path) for path in group)
            run = subprocess.run([java, "-Xmx4g", "-cp", str(runner), "IsolatedCompileRunner",
                                  str(args.jcl.resolve()) if args.jcl and level == "1.4" else "-",
                                  classpath, str(sourcepath), str(output)], input=input_rows,
                                 capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError("IsolatedCompileRunner failed: " + run.stderr[-2000:])
            rows = run.stdout.splitlines()
            if len(rows) != len(group):
                raise RuntimeError("IsolatedCompileRunner returned %d/%d results: %s" %
                                   (len(rows), len(group), run.stderr[-1000:]))
            for row in rows:
                status, raw, error = row.split("\t", 2)
                path = Path(raw)
                results[path] = {"source": level, "target": target,
                                 "passed": status == "OK", "errors": [error] if error else []}

    failures = {str(path): results[path] for path in files if not results[path]["passed"]}
    passed = len(files) - len(failures)
    print("isolated compile: %d/%d passed, %d failed" % (passed, len(files), len(failures)))
    if args.json_report:
        args.json_report.write_text(json.dumps({"files": len(files), "passed": passed,
                                               "reported_failures": failures}, indent=2) + "\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
