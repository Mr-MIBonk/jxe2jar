"""Remaining source repairs must yield executable Java 1.4."""

import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from fix_vf_artifacts import fix_text  # noqa: E402


def test_remaining_repairs_compile_and_run():
    outer = """import java.util.List;
interface Event { int value(); }
class Navigation {}
public class Outer {
    Navigation navigation;
    Outer(Navigation navigation) { this.navigation = navigationx; }
    void accept(Void void) {}
    String cast(Object value) { return (String & String)value; }
    String[] array(List list) { return list.toArray(new String[0]); }
    Class literal() { return class$("java.lang.String"); }
    Class cache() { return (class$java$lang$String == null
        ? (class$java$lang$String = class$("java.lang.String")) : class$java$lang$String); }
    static String classNameFromPackageName(Class type) { return type.getName(); }
    String nestedCache() { return classNameFromPackageName(
        class$java$lang$Integer == null
            ? (class$java$lang$Integer = class$("java.lang.Integer")) : class$java$lang$Integer
    ); }
    public static void main(String[] args) {
        Outer outer = new Outer(new Navigation());
        if (outer.navigation == null || outer.literal() != String.class || outer.cache() != String.class
                || !outer.nestedCache().equals("java.lang.Integer")
                || !outer.cast("ok").equals("ok") || outer.array(java.util.Arrays.asList(new String[]{"ok"})).length != 1
                || new Outer$1(outer).value() != 7)
            throw new AssertionError("source repair changed behavior");
    }
    final int number = 7;
}
"""
    orphan = """class Outer$1 implements Event {
    Outer$1(Outer outer) { this.this$0 = outer; }
    public int value() { return this.this$0.number; }
}
"""
    fixed_outer, outer_count = fix_text(outer)
    fixed_orphan, orphan_count = fix_text(orphan)
    assert outer_count == 9 and orphan_count == 1
    assert fix_text(fixed_outer)[0] == fixed_outer
    assert fix_text(fixed_orphan)[0] == fixed_orphan

    jdk = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin"
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        (work / "Outer.java").write_text(fixed_outer)
        (work / "Outer$1.java").write_text(fixed_orphan)
        subprocess.run(
            [str(jdk / "javac"), "-source", "1.4", "-target", "1.4", "Outer.java", "Outer$1.java"],
            cwd=work, check=True, capture_output=True, text=True,
        )
        subprocess.run([str(jdk / "java"), "Outer"], cwd=work, check=True)


if __name__ == "__main__":
    test_remaining_repairs_compile_and_run()
