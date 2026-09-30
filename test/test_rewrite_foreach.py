#!/usr/bin/env python3
"""The Java 1.4 loop rewrite must leave unresolved iterable types intact."""

import pathlib
import subprocess
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/foreach1_4"
JDK8 = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin"


def test_rewrite_foreach():
    known = """import java.util.List;
class Known {
    static int count(List items) {
        int result = 0;
        for (Object item : items) { if (item != null) result++; }
        return result;
    }
    public static void main(String[] args) {
        if (count(java.util.Arrays.asList(new String[]{"a", "b"})) != 2)
            throw new AssertionError();
    }
}
"""
    unknown = """class Unknown {
    void run(MissingType items) {
        for (Object item : items) { System.out.println(item); }
    }
}
"""
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        jar = work / "empty.jar"
        with zipfile.ZipFile(jar, "w"):
            pass
        known_file = work / "Known.java"
        unknown_file = work / "Unknown.java"
        known_file.write_text(known)
        unknown_file.write_text(unknown)
        result = subprocess.run(
            ["java", "-cp", f"{TOOL}/*:{TOOL}", "RewriteForeach", str(jar), str(work),
             str(known_file), str(unknown_file)],
            check=True, capture_output=True, text=True,
        )
        assert "loops rewritten: 1" in result.stdout
        assert "unresolved loops left unchanged: 1" in result.stdout
        assert known_file.read_text() != known
        assert unknown_file.read_text() == unknown
        subprocess.run(
            [str(JDK8 / "javac"), "-source", "1.4", "-target", "1.4", str(known_file)],
            cwd=work, check=True, capture_output=True, text=True,
        )
        subprocess.run([str(JDK8 / "java"), "Known"], cwd=work, check=True)


if __name__ == "__main__":
    test_rewrite_foreach()
