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
            "public class ModelBank {"
            " public static final int AUXHEATER_OFF_BUTTON = 600721;"
            " public static final int TITLE_LABEL = 600722;"
            " public static final int TITLE_LABEL_CHOICE = 600723; }\n"
        )
        (work / "Screen.java").write_text(
            """public class Screen {
    public void setBitmaps(int[] ids) {}
    public void setModelID(int id) {}
    public void setLabelId(int id) {}
    public void render() {
        setBitmaps(new int[] {600721, 600722});
        int[] later = new int[] {600721};
        setBitmaps(later);
        setModelID(600721);
        setLabelId(600721);
        int label = 600721;
        setLabelId(label);
        setLabelId(600722);
        setLabelId(600723);
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
        assert render.count("int 600721") == 4
        assert render.count("ModelBank.AUXHEATER_OFF_BUTTON") == 1
        assert render.count("ModelBank.TITLE_LABEL") == 1
        assert render.count("int 600723") == 1
        assert "ModelBank.TITLE_LABEL_CHOICE" not in render

        scoped = work / "scoped.jar"
        subprocess.run(
            ["java", "-cp", str(TOOL), "Uninliner", str(source), str(scoped), "100", "--scoped"],
            check=True,
        )
        scoped_code = subprocess.check_output(["javap", "-c", "-classpath", str(scoped), "Screen"], text=True)
        scoped_render = scoped_code.split("public void render();", 1)[1]
        assert scoped_render.count("int 600721") == 5
        assert "ModelBank.AUXHEATER_OFF_BUTTON" not in scoped_render
        assert scoped_render.count("int 600722") == 2
        assert scoped_render.count("int 600723") == 1

        pipeline = work / "pipeline.jar"
        doubtful = work / "doubtful.tsv"
        subprocess.run(
            [str(ROOT / "tools/uninline/uninline.sh"), "pipeline",
             str(source), str(pipeline), str(doubtful), "100"],
            check=True,
        )
        pipeline_code = subprocess.check_output(
            ["javap", "-c", "-classpath", str(pipeline), "Screen"], text=True
        )
        pipeline_render = pipeline_code.split("public void render();", 1)[1]
        assert pipeline_render.count("int 600721") == 4
        assert pipeline_render.count("ModelBank.AUXHEATER_OFF_BUTTON") == 1
        assert pipeline_render.count("ModelBank.TITLE_LABEL") == 1
        assert pipeline_render.count("int 600723") == 1
        assert "ModelBank.TITLE_LABEL_CHOICE" not in pipeline_render

        scoped_pipeline = work / "scoped-pipeline.jar"
        subprocess.run(
            [str(ROOT / "tools/uninline/uninline.sh"), "scoped-pipeline",
             str(source), str(scoped_pipeline), str(doubtful), "100"],
            check=True,
        )
        scoped_pipeline_code = subprocess.check_output(
            ["javap", "-c", "-classpath", str(scoped_pipeline), "Screen"], text=True
        )
        scoped_pipeline_render = scoped_pipeline_code.split("public void render();", 1)[1]
        assert scoped_pipeline_render.count("int 600721") == 5
        assert scoped_pipeline_render.count("int 600722") == 2
        assert scoped_pipeline_render.count("int 600723") == 1


if __name__ == "__main__":
    test_bitmap_array_elements_stay_numeric()
