"""Resource arrays and menu argument families stay distinct after the full pipeline."""

import pathlib
import subprocess
import tempfile
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tools/uninline/uninline.sh"


def test_text_ids_and_menu_entries():
    sources = {
        "ICoreCarModelBank.java": """public class ICoreCarModelBank {
            public static final int SIA_RESET_OIL_DISTANCE_CONF_CHOICE = 602091;
        }""",
        "LabelController.java": """public class LabelController {
            void setTextIds(int[] ids) {}
            void setModelID(int id) {}
        }""",
        "CarScreenBag1.java": """public class CarScreenBag1 {
            void render(LabelController label) {
                label.setTextIds(new int[] {602091});
                int[] later = new int[] {602091};
                label.setTextIds(later);
                label.setModelID(602091);
            }
        }""",
        "CarEvoMenuEntryIDs.java": """public interface CarEvoMenuEntryIDs {
            int CAR_FUNC_CHARISMA = 600159;
            int CAR_FUNC_SETTINGS = 600161;
            int CAR_FUNC_AUX_AC = 10;
            int CAR_FUNC_AUX_COMBINED = 11;
            int CAR_FUNC_SPORT = 12;
            int CAR_MAIN = 1;
            int AUX_AC_UNLOCK_CLIMATING = 600815;
            int ACC_SPEED_LIMIT_OFFSET = 600773;
            int SEAT_CODRIVER_PRELOAD_DEVICE = 600739;
        }""",
        "IEvoCarModelBank.java": """public class IEvoCarModelBank {
            public static final int CHARISMA_AVAILABLE_CHOICE = 600815;
            public static final int MAIN_MENU_SETTINGS_AVAILABLE_CHOICE = 601010;
            public static final int MAIN_MENU_AUX_AC_AVAILABLE_CHOICE = 601006;
            public static final int MAIN_MENU_AUX_COMBINED_AVAILABLE_CHOICE = 601007;
            public static final int MAIN_MENU_SPORT_AVAILABLE_CHOICE = 602119;
            public static final int CAR_MAIN_AVAILABLE_CHOICE = 600773;
            public static final int AWV_AVAILABLE_CHOICE = 600739;
            public static final int INT_LIGHT_PROFILE3_AVAILABLE_CHOICE = 601080;
            public static final int ITEM_ALPHA_AVAILABLE_CHOICE = 601101;
            public static final int ITEM_BETA_AVAILABLE_CHOICE = 601103;
            public static final int ITEM_GAMMA_AVAILABLE_CHOICE = 601105;
            public static final int ITEM_DELTA_AVAILABLE_CHOICE = 601107;
            public static final int ITEM_EPSILON_AVAILABLE_CHOICE = 601109;
            public static final int ITEM_ZETA_AVAILABLE_CHOICE = 601111;
            public static final int ITEM_ETA_AVAILABLE_CHOICE = 601113;
            public static final int ITEM_THETA_AVAILABLE_CHOICE = 601115;
            public static final int ITEM_IOTA_AVAILABLE_CHOICE = 601117;
            public static final int ITEM_KAPPA_AVAILABLE_CHOICE = 601119;
            public static final int ITEM_LAMBDA_AVAILABLE_CHOICE = 601121;
            public static final int ITEM_MU_AVAILABLE_CHOICE = 601123;
        }""",
        "EvoMenuEntryFactory.java": """public class EvoMenuEntryFactory {
            void createMenuEntry(int id, String name, int availability) {}
        }""",
        "CarEvoMenuEntryStructure.java": """public class CarEvoMenuEntryStructure
                implements CarEvoMenuEntryIDs {
            void build(EvoMenuEntryFactory factory) {
                factory.createMenuEntry(600159, "CAR_FUNC_CHARISMA", 600815);
                factory.createMenuEntry(600161, "CAR_FUNC_SETTINGS", 601010);
                factory.createMenuEntry(10, "CAR_FUNC_AUX_AC)", 601006);
                factory.createMenuEntry(11, "CAR_FUNC_AUX_COMBINED)", 601007);
                factory.createMenuEntry(12, "CAR_FUNC_SPORT", 602119);
                factory.createMenuEntry(1, "CAR_MAIN", 600773);
                factory.createMenuEntry(600741, "PRESENSE_AWV", 600739);
                factory.createMenuEntry(600751, "INTLIGHT_PROFILE_3", 601080);
                factory.createMenuEntry(1001, "ITEM_ALPHA", 601101);
                factory.createMenuEntry(1003, "ITEM_BETA", 601103);
                factory.createMenuEntry(1005, "ITEM_GAMMA", 601105);
                factory.createMenuEntry(1007, "ITEM_DELTA", 601107);
                factory.createMenuEntry(1009, "ITEM_EPSILON", 601109);
                factory.createMenuEntry(1011, "ITEM_ZETA", 601111);
                factory.createMenuEntry(1013, "ITEM_ETA", 601113);
                factory.createMenuEntry(1015, "ITEM_THETA", 601115);
                factory.createMenuEntry(1017, "ITEM_IOTA", 601117);
                factory.createMenuEntry(1019, "ITEM_KAPPA", 601119);
                factory.createMenuEntry(1021, "ITEM_LAMBDA", 601121);
                factory.createMenuEntry(1023, "ITEM_MU", 601123);
            }
        }""",
    }
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        for name, source in sources.items():
            (work / name).write_text(source)
        subprocess.run(["javac", "--release", "8", *sources], cwd=work, check=True)
        source_jar, result_jar = work / "source.jar", work / "result.jar"
        with zipfile.ZipFile(source_jar, "w") as jar:
            for name in sources:
                jar.write(work / name.replace(".java", ".class"), name.replace(".java", ".class"))
        subprocess.run([str(PIPELINE), "pipeline", str(source_jar), str(result_jar),
                        str(work / "doubtful.tsv")], check=True)

        def code(name):
            return subprocess.check_output(
                ["javap", "-c", "-p", "-classpath", str(result_jar), name], text=True
            )

        screen = code("CarScreenBag1")
        assert screen.count("int 602091") == 2
        assert "ICoreCarModelBank.SIA_RESET_OIL_DISTANCE_CONF_CHOICE" in screen

        menu = code("CarEvoMenuEntryStructure")
        assert "IEvoCarModelBank.CHARISMA_AVAILABLE_CHOICE" in menu
        assert "CarEvoMenuEntryIDs.AUX_AC_UNLOCK_CLIMATING" not in menu
        assert "IEvoCarModelBank.MAIN_MENU_SETTINGS_AVAILABLE_CHOICE" in menu
        assert "IEvoCarModelBank.CAR_MAIN_AVAILABLE_CHOICE" in menu
        assert "IEvoCarModelBank.AWV_AVAILABLE_CHOICE" in menu
        assert "IEvoCarModelBank.INT_LIGHT_PROFILE3_AVAILABLE_CHOICE" in menu
        assert "CarEvoMenuEntryIDs.ACC_SPEED_LIMIT_OFFSET" not in menu
        assert "CarEvoMenuEntryIDs.SEAT_CODRIVER_PRELOAD_DEVICE" not in menu
        for name in ("CAR_FUNC_AUX_AC", "CAR_FUNC_AUX_COMBINED", "CAR_FUNC_SPORT", "CAR_MAIN"):
            assert f"CarEvoMenuEntryIDs.{name}" in menu


if __name__ == "__main__":
    test_text_ids_and_menu_entries()
