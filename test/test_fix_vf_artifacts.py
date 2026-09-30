"""Vineflower's anonymous capture repair must retain captured values."""

import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from fix_vf_artifacts import fix_text  # noqa: E402


def test_anonymous_captures_compile_and_run():
    outer = """interface ListItemFactory { int value(); }
interface IPowerEvent { int value(); }
interface NavLocationCallback { int value(); }
interface TimerListener { int value(); }
interface IAdbImportListener { int value(); }
class Helper { int twice(int value) { return value * 2; } }
abstract class AbstractParkingFocusPropertyDecorator {
    AbstractParkingFocusPropertyDecorator(int value) { this.value = value; }
    final int value;
    abstract int result();
}
abstract class NavCommand {
    NavCommand() {}
    NavCommand(String name) {}
    abstract int value();
}
abstract class NotifySDSCommand {
    NotifySDSCommand(String listener, String name) {}
    abstract int value();
}
abstract class NotifyNaviServiceListenerCommand {
    NotifyNaviServiceListenerCommand(String listener) {}
    abstract int value();
}
public class Outer {
    final int base = 10;
    int result;
    class Named {
        final Outer this$0 = Outer.this;
        NavLocationCallback callback() {
            return new NavLocationCallback(this) {
                private final Outer.Named this$1;
                {
                    this.this$1 = fakeNamed;
                }
                public int value() { return this.this$1.this$0.base; }
            };
        }
        NavCommand nav(int i) {
            return new NavCommand(this, "named", i) {
                private final int val$index;
                private final Outer.Named this$1;
                {
                    this.this$1 = fakeNamed;
                    this.val$index = j;
                }
                int value() { return this.this$1.this$0.base + this.val$index; }
            };
        }
    }
    Class literal() { return class$("java.lang.String"); }
    Class qualifiedLiteral() { return Outer.class$("java.lang.Integer"); }
    static int invoke(int value, ListItemFactory factory) { return value + factory.value(); }
    int list(final Helper helper, int i) {
        ListItemFactory item = new ListItemFactory(helper, i) {
            private final Helper val$factory;
            private final int val$terminalID;
            {
                this.val$factory = helper1;
                this.val$terminalID = j;
            }
            public int value() { return this.val$factory.twice(this.val$terminalID); }
        };
        return item.value();
    }
    IPowerEvent event() {
        return new IPowerEvent(this) {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            public int value() { return this.this$0.base; }
        };
    }
    int multiline(Helper helper, int i) {
        return invoke(
            i,
            new ListItemFactory(helper, i) {
                private final Helper val$factory;
                private final int val$terminalID;
                {
                    this.val$factory = helper1;
                    this.val$terminalID = j;
                }
                public int value() { return this.val$factory.twice(this.val$terminalID); }
            }
        );
    }
    TimerListener timer() {
        return new TimerListener(this) {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            public int value() { return this.this$0.base; }
        };
    }
    IAdbImportListener adb() {
        return new IAdbImportListener(this) {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            public int value() { return this.this$0.base; }
        };
    }
    NotifyNaviServiceListenerCommand notifyService() {
        return new NotifyNaviServiceListenerCommand(this, "listener") {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            int value() { return this.this$0.base; }
        };
    }
    AbstractParkingFocusPropertyDecorator decorator(int config) {
        return new AbstractParkingFocusPropertyDecorator(this, config) {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            int result() { return this.this$0.base + this.value; }
        };
    }
    NavCommand nav(int i) {
        return new NavCommand(this, "with,comma", i) {
            private final int val$index;
            private final Outer this$0;
            {
                this.this$0 = outer1;
                this.val$index = j;
            }
            int value() { return this.this$0.base + this.val$index; }
        };
    }
    static NavCommand staticNav(int i) {
        return new NavCommand("static", i) {
            private final int val$index;
            {
                this.val$index = j;
            }
            int value() { return this.val$index; }
        };
    }
    NavLocationCallback callback(Helper helper) {
        return new NavLocationCallback(this, helper) {
            private final Helper val$helper;
            private final Outer this$0;
            {
                this.this$0 = outer1;
                this.val$helper = helper1;
            }
            public int value() { return this.val$helper.twice(this.this$0.base); }
        };
    }
    NotifySDSCommand notifyCommand() {
        return new NotifySDSCommand(this, "listener", "name") {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            int value() { return this.this$0.base; }
        };
    }
    int nested(int i) {
        NavCommand outerCommand = new NavCommand(this, "outer", i) {
            private final int val$index;
            private final Outer this$0;
            {
                this.this$0 = outer1;
                this.val$index = j;
            }
            int value() {
                NavCommand innerCommand = new NavCommand(this, "inner") {
                    private final Object this$1;
                    {
                        this.this$1 = outer$11;
                    }
                    int value() { return this.this$1.val$index + this.this$1.this$0.base; }
                };
                return innerCommand.value();
            }
        };
        return outerCommand.value();
    }
    int nestedRunnable(final int i) {
        NavCommand command = new NavCommand(this) {
            private final Outer this$0;
            {
                this.this$0 = outer1;
            }
            int value() {
                Runnable task = new Runnable(this, i) {
                    private final int val$index;
                    private final Object this$1;
                    {
                        this.this$1 = fakeOuter;
                        this.val$index = j;
                    }
                    public void run() { this.this$1.this$0.result = this.val$index; }
                };
                task.run();
                return this.this$0.result;
            }
        };
        return command.value();
    }
    public static void main(String[] args) {
        Outer outer = new Outer();
        if (outer.new Named().callback().value() != 10 || outer.new Named().nav(7).value() != 17
                || outer.literal() != String.class || outer.qualifiedLiteral() != Integer.class
                || outer.list(new Helper(), 7) != 14
                || outer.multiline(new Helper(), 7) != 21
                || outer.timer().value() != 10 || outer.adb().value() != 10
                || outer.notifyService().value() != 10
                || outer.event().value() != 10
                || outer.decorator(3).result() != 13 || outer.nav(7).value() != 17
                || Outer.staticNav(7).value() != 7
                || outer.callback(new Helper()).value() != 20
                || outer.notifyCommand().value() != 10
                || outer.nested(7) != 17
                || outer.nestedRunnable(7) != 7
                || new Orphan$1(outer).value() != 10)
            throw new AssertionError("captured value changed");
    }
}
"""
    orphan = """class Orphan$1 implements IPowerEvent {
    Orphan$1(Outer outer) { this.this$0 = outer; }
    public int value() { return this.this$0.base; }
}
"""
    fixed_outer, count_outer = fix_text(outer)
    fixed_orphan, count_orphan = fix_text(orphan)
    assert count_outer == 19
    assert count_orphan == 1
    navigation, alias_count = fix_text("class R { Navigation navigation; R(Navigation navigation) { this.navigation = navigationx; } }")
    assert alias_count == 1 and "this.navigation = navigation;" in navigation
    assert fix_text(fixed_outer)[0] == fixed_outer
    assert fix_text(fixed_orphan)[0] == fixed_orphan
    repaired, repair_count = fix_text("class X { Class class$java$lang$String; void f() { X.class$java$lang$String = X.java.lang.String.class; } }")
    assert repair_count == 1 and "= java.lang.String.class" in repaired

    jdk = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin"
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        (work / "Outer.java").write_text(fixed_outer)
        (work / "Orphan$1.java").write_text(fixed_orphan)
        subprocess.run([str(jdk / "javac"), "-source", "1.4", "-target", "1.4",
                        "Outer.java", "Orphan$1.java"], cwd=work, check=True)
        subprocess.run([str(jdk / "java"), "Outer"], cwd=work, check=True)


if __name__ == "__main__":
    test_anonymous_captures_compile_and_run()
