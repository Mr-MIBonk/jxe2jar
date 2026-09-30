#!/usr/bin/env python3
"""JVM class/package collisions need a per-source compiler classpath."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
JAVAC = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin/javac"


def test_class_package_collision():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        tree = work / "source"
        parent = work / "build/p/a.java"
        child = work / "build/p/a/C.java"
        parent.parent.mkdir(parents=True)
        child.parent.mkdir(parents=True)
        empty_sourcepath = work / "empty_sourcepath"
        empty_sourcepath.mkdir()
        parent.write_text("package p; public class a { public int value() { return 1; } }\n")
        child.write_text("package p.a; public class C { public int value() { return 2; } }\n")
        tree_child = tree / "p/a/C.java"
        tree_child.parent.mkdir(parents=True)
        tree_child.write_text(child.read_text())
        jar = work / "classes.jar"
        libs = work / "libs"
        libs.mkdir()
        with zipfile.ZipFile(jar, "w") as archive:
            for source in (parent, child):
                output = work / ("compiled_" + source.stem)
                output.mkdir()
                subprocess.run([str(JAVAC), "-source", "1.4", "-target", "1.4",
                                "-sourcepath", str(empty_sourcepath),
                                "-d", str(output), str(source)],
                               check=True, capture_output=True, text=True)
                for generated in output.rglob("*.class"):
                    archive.write(generated, generated.relative_to(output))
        report = work / "report.json"
        command = [sys.executable, str(ROOT / "tools/isolated_compile_check.py"),
                   str(tree), "--jar", str(jar), "--libs", str(libs),
                   "--json-report", str(report)]
        default = subprocess.run(command, capture_output=True, text=True)
        assert default.returncode == 1
        failure = json.loads(report.read_text())["reported_failures"][str(tree_child.resolve())]
        assert "clashes with class of same name" in failure["errors"][0]
        filtered = subprocess.run(command + ["--filter-clashing-classes"],
                                  capture_output=True, text=True)
        assert filtered.returncode == 0, filtered.stderr + filtered.stdout + report.read_text()
        assert json.loads(report.read_text())["filtered_classpaths"] == 1


if __name__ == "__main__":
    test_class_package_collision()
