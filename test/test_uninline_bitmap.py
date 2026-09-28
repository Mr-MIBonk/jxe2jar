"""Regression: bitmap resource IDs must not acquire unrelated constant names."""

import pathlib
import subprocess
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/uninline/uninline.jar"


def test_bitmap_array_elements_stay_numeric():
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        (work / "ModelBank.java").write_text(
            "public class ModelBank { public static final int AUXHEATER_OFF_BUTTON = 600721; }\n"
        )
        (work / "Screen.java").write_text(
            """public class Screen {
    public void setBitmaps(int[] ids) {}
    public void setModelID(int id) {}
    public void render() {
        setBitmaps(new int[] {600721, 600722});
        int[] later = new int[] {600721};
        setBitmaps(later);
        setModelID(600721);
    }
}
"""
        )
        subprocess.run(["javac", "--release", "8", "ModelBank.java", "Screen.java"], cwd=work, check=True)
        source = work / "source.jar"
        result = work / "result.jar"
        with zipfile.ZipFile(source, "w") as jar:
            for name in ("ModelBank.class", "Screen.class"):
                jar.write(work / name, name)
        subprocess.run(["java", "-cp", str(TOOL), "Uninliner", str(source), str(result), "100"], check=True)
        code = subprocess.check_output(["javap", "-c", "-classpath", str(result), "Screen"], text=True)
        render = code.split("public void render();", 1)[1]
        assert render.count("int 600721") == 2
        assert render.count("ModelBank.AUXHEATER_OFF_BUTTON") == 1


if __name__ == "__main__":
    test_bitmap_array_elements_stay_numeric()
