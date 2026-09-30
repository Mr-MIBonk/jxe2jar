#!/usr/bin/env python3
"""Recover both capturing and static anonymous-class ownership."""

from pathlib import Path
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
JAVAC = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin/javac"


def test_repair_innerclasses():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        source = work / "Owner.java"
        source.write_text(
            "public class Owner { int value = 1; "
            "Runnable instance() { return new Runnable() { "
            "public void run() { System.out.println(value); } }; } "
            "static Runnable staticOne() { return new Runnable() { "
            "public void run() {} }; } }\n"
        )
        subprocess.run([str(JAVAC), "-source", "1.4", "-target", "1.4", str(source)],
                       check=True, capture_output=True, text=True)
        original = work / "input.jar"
        repaired = work / "output.jar"
        with zipfile.ZipFile(original, "w") as archive:
            for path in work.glob("*.class"):
                archive.write(path, path.name)
        result = subprocess.run(["bash", str(ROOT / "tools/innerclasses/repair.sh"),
                                 str(original), str(repaired)], check=True,
                                capture_output=True, text=True)
        assert "Owner$1 -> Owner" in result.stdout
        assert "Owner$2 -> Owner" in result.stdout
        with zipfile.ZipFile(original) as before, zipfile.ZipFile(repaired) as after:
            assert set(before.namelist()) == set(after.namelist())
            assert before.read("Owner$1.class") != after.read("Owner$1.class")
            assert before.read("Owner$2.class") != after.read("Owner$2.class")
        again = work / "again.jar"
        repeated = subprocess.run(["bash", str(ROOT / "tools/innerclasses/repair.sh"),
                                   str(repaired), str(again)], check=True,
                                  capture_output=True, text=True)
        assert "restored anonymous classes: 0" in repeated.stdout
        with zipfile.ZipFile(repaired) as before, zipfile.ZipFile(again) as after:
            assert all(before.read(name) == after.read(name) for name in before.namelist())


if __name__ == "__main__":
    test_repair_innerclasses()
