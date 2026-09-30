#!/usr/bin/env python3
"""A compiler-gated CFR fallback must replace only a broken source."""

import json
import pathlib
import subprocess
import sys
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
JDK8 = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin"


def test_compiler_gated_fallback():
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        tree = work / "source"
        tree.mkdir()
        source = tree / "Example.java"
        source.write_text("public class Example { public int value() { return 7; } }\n")
        subprocess.run([str(JDK8 / "javac"), "-source", "1.4", "-target", "1.4", str(source)],
                       cwd=work, check=True, capture_output=True, text=True)
        jar = work / "example.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            archive.write(tree / "Example.class", "Example.class")
        source.write_text("public class Example { public int value() { return missing; } }\n")
        report = work / "errors.json"
        check = [sys.executable, str(ROOT / "tools/recompile_check.py"), str(tree),
                 "--jar", str(jar), "--osgi", str(work), "--json-report", str(report)]
        broken = subprocess.run(check, capture_output=True, text=True)
        assert broken.returncode == 1
        assert str(source) in json.loads(report.read_text())["reported_failures"]
        fallback = [sys.executable, str(ROOT / "tools/cfr_compile_fallback.py"), str(tree),
                    str(jar), str(report), "--osgi", str(work)]
        dry = subprocess.run(fallback, check=True, capture_output=True, text=True)
        assert "CFR compilable: 1/1" in dry.stdout
        assert "return missing" in source.read_text()
        failing_javac = work / "failing-javac"
        failing_javac.write_text("#!/bin/sh\nexit 1\n")
        failing_javac.chmod(0o755)
        rejected = subprocess.run(fallback + ["--javac", str(failing_javac), "--apply"],
                                  check=True, capture_output=True, text=True)
        assert "CFR compilable: 0/1" in rejected.stdout
        assert "return missing" in source.read_text()
        applied = subprocess.run(fallback + ["--apply"], check=True, capture_output=True, text=True)
        assert "CFR compilable: 1/1" in applied.stdout
        assert "return missing" not in source.read_text()
        assert subprocess.run(check, capture_output=True, text=True).returncode == 0


if __name__ == "__main__":
    test_compiler_gated_fallback()
