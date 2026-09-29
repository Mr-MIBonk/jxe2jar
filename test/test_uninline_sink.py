"""Late sink recovery restores contextual names without changing resource IDs."""

import pathlib
import subprocess
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tools/uninline/uninline.sh"


def test_late_sink_recovers_call_domains():
    sources = {
        "CL3Exception.java": """public class CL3Exception extends RuntimeException {
            public static final int VERSION = -2147483647;
            public static final int INVALID = -2147483643;
            public static final int PARAM = -2147483645;
            public CL3Exception(int reason) {}
        }""",
        "CL3.java": """public class CL3 {
            void fail() {
                new CL3Exception(-2147483643);
                new CL3Exception(-2147483645);
                new CL3Exception(-2147483647);
            }
        }""",
        "UnboundPartialPopupsPhone.java": """public class UnboundPartialPopupsPhone {
            public static final int HFP = 300164;
            public static final int SAP_OK = 300171;
            public static final int SAP_ERR = 300172;
        }""",
        "OtherPopup.java": """public class OtherPopup {
            public static final int COLLISION = 300164;
        }""",
        "PopupScreen.java": """public class PopupScreen {
            void removePopup(int id) {}
            void close() {
                removePopup(300171);
                removePopup(300172);
                removePopup(300164);
            }
        }""",
        "AppNameConst.java": """public class AppNameConst {
            public static final String APP_NAME_ADDRESSBOOK = "AddressBook";
            public static final String APP_NAME_MESSAGING = "Messaging";
            public static final String APP_NAME_PHONE = "Phone";
        }""",
        "CombiModulePhone.java": """public class CombiModulePhone {
            void addAppConnector(String name) {}
            void connect() {
                addAppConnector("AddressBook");
                addAppConnector("Messaging");
                addAppConnector("Phone");
            }
        }""",
        "ModelBank.java": """public class ModelBank {
            public static final int AUXHEATER_OFF_BUTTON = 600721;
            public static final int TITLE_LABEL = 602631;
            public static final int NEXT_LABEL = 602632;
            public static final int TITLE_CHOICE = 602633;
        }""",
        "CarScreenBag1.java": """public class CarScreenBag1 {
            void setBitmaps(int[] ids) {}
            void setLabelId(int id) {}
            void render() {
                setBitmaps(new int[] {600721, 600722, 600723});
                setLabelId(602631);
                setLabelId(602632);
                setLabelId(602633);
            }
        }""",
    }
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        for name, source in sources.items():
            (work / name).write_text(source)
        subprocess.run(["javac", "--release", "8", *sources], cwd=work, check=True)
        source_jar = work / "source.jar"
        result_jar = work / "result.jar"
        with zipfile.ZipFile(source_jar, "w") as jar:
            for name in sources:
                jar.write(work / name.replace(".java", ".class"), name.replace(".java", ".class"))
        subprocess.run([str(PIPELINE), "pipeline", str(source_jar), str(result_jar),
                        str(work / "doubtful.tsv")], check=True)

        def code(name):
            return subprocess.check_output(
                ["javap", "-c", "-p", "-classpath", str(result_jar), name], text=True
            )

        assert "CL3Exception.VERSION" in code("CL3")
        assert "UnboundPartialPopupsPhone.HFP" in code("PopupScreen")
        assert "AppNameConst.APP_NAME_PHONE" in code("CombiModulePhone")
        screen = code("CarScreenBag1")
        assert "int 600721" in screen
        assert "ModelBank.AUXHEATER_OFF_BUTTON" not in screen
        assert "ModelBank.TITLE_LABEL" in screen
        assert "ModelBank.NEXT_LABEL" in screen
        assert "int 602633" in screen
        assert "ModelBank.TITLE_CHOICE" not in screen


if __name__ == "__main__":
    test_late_sink_recovers_call_domains()
