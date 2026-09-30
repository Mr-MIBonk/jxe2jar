"""T1 must not emit a field owner inaccessible from the use-site package."""

import pathlib
import subprocess
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/uninline/uninline.jar"


def test_inherited_package_private_constant():
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        (work / "p").mkdir()
        (work / "q").mkdir()
        (work / "p/Hidden.java").write_text(
            'package p; interface Hidden { String VALUE_CHARSET = "UTF-8"; }\n'
        )
        (work / "p/Exposed.java").write_text(
            "package p; public interface Exposed extends Hidden {}\n"
        )
        (work / "p/LocalUse.java").write_text(
            'package p; public class LocalUse implements Exposed { '
            'public String value() { return "UTF-8"; } }\n'
        )
        (work / "q/Use.java").write_text(
            'package q; public class Use implements p.Exposed { '
            'public String value() { return "UTF-8"; } }\n'
        )
        subprocess.run(
            ["javac", "--release", "8", "p/Hidden.java", "p/Exposed.java",
             "p/LocalUse.java", "q/Use.java"],
            cwd=work, check=True,
        )
        source, result = work / "source.jar", work / "result.jar"
        with zipfile.ZipFile(source, "w") as archive:
            for path in work.rglob("*.class"):
                archive.write(path, path.relative_to(work).as_posix())
        subprocess.run(
            ["java", "-cp", str(TOOL), "Uninliner", str(source), str(result), "100"],
            check=True, capture_output=True, text=True,
        )
        external = subprocess.check_output(
            ["javap", "-c", "-classpath", str(result), "q.Use"], text=True
        )
        local = subprocess.check_output(
            ["javap", "-c", "-classpath", str(result), "p.LocalUse"], text=True
        )
        assert "String UTF-8" in external
        assert "Hidden.VALUE_CHARSET" not in external
        assert "Hidden.VALUE_CHARSET" in local


if __name__ == "__main__":
    test_inherited_package_private_constant()
