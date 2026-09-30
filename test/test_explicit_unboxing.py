#!/usr/bin/env python3
"""Repair javac-located implicit unboxing without changing unrelated source."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from explicit_unboxing import repair


ROOT = Path(__file__).resolve().parents[1]
JDK8 = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin"


def test_explicit_unboxing():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        tree = work / "source"
        tree.mkdir()
        source = tree / "Example.java"
        original = ("public class Example { // 😀 UTF-16 offset\n"
                    "  int value() { return Integer.valueOf(7).intValue(); }\n}\n")
        source.write_text(original)
        subprocess.run([str(JDK8 / "javac"), "-source", "1.4", "-target", "1.4", str(source)],
                       check=True, capture_output=True)
        jar = work / "classes.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            archive.write(tree / "Example.class", "Example.class")
        source.write_text(original.replace(".intValue()", ""))
        report = work / "compile.json"
        check = [sys.executable, str(ROOT / "tools/isolated_compile_check.py"),
                 str(tree), "--jar", str(jar), "--json-report", str(report)]
        assert subprocess.run(check, capture_output=True).returncode == 1
        assert "Integer cannot be converted to int" in json.loads(report.read_text())["reported_failures"][str(source.resolve())]["errors"][0]
        fix = [sys.executable, str(ROOT / "tools/explicit_unboxing.py"),
               str(tree), str(jar), str(report), "--libs", str(work)]
        dry = subprocess.run(fix, check=True, capture_output=True, text=True)
        assert "explicit wrapper conversions: 1/1" in dry.stdout
        assert ".intValue()" not in source.read_text()
        applied = subprocess.run(fix + ["--apply"], check=True, capture_output=True, text=True)
        assert "explicit wrapper conversions: 1/1" in applied.stdout
        assert source.read_text() == original.replace("Integer.valueOf(7).intValue()",
                                                      "(Integer.valueOf(7)).intValue()")
        assert subprocess.run(check, capture_output=True).returncode == 0


def test_repair_expression_shapes():
    source = "switch(map.getKey()) { default: break; }"
    start = source.index("(")
    end = source.index("))", start) + 2
    message = "%d:%d:%d:%d: incompatible types: java.lang.Object cannot be converted to int" % (1, 7, start, end)
    assert repair(source, message) == "switch(((Integer)(map.getKey())).intValue()) { default: break; }"

    source = "consume(flag);"
    start, end = source.index("flag"), source.index("flag") + len("flag")
    message = "%d:%d:%d:%d: incompatible types: boolean cannot be converted to java.lang.Object" % (1, 1, start, end)
    assert repair(source, message) == "consume(Boolean.valueOf(flag));"


if __name__ == "__main__":
    test_explicit_unboxing()
    test_repair_expression_shapes()
