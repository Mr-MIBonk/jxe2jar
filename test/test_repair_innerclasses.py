#!/usr/bin/env python3
"""Recover both capturing and static anonymous-class ownership."""

from pathlib import Path
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
JAVAC = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin/javac"
JAVA = JAVAC.with_name("java")
ASM = ROOT / "tools/uninline/lib/asm-9.7.jar"


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


def test_flattened_nested_anonymous_owner():
    # Some firmware compilers call an anonymous class inside Owner$1 Owner$2,
    # rather than Owner$1$1. The this$1 field plus NEW in Owner$1 identifies
    # its actual lexical owner.
    generator = r'''
import java.io.FileOutputStream;
import org.objectweb.asm.*;

public class GenerateNested implements Opcodes {
    static void write(String name, String captured, String constructed) throws Exception {
        ClassWriter out = new ClassWriter(0);
        out.visit(V1_4, 0, name, null, "java/lang/Object", null);
        out.visitInnerClass("Owner$1", null, null, 0);
        out.visitInnerClass("Owner$2", null, null, 0);
        if (captured != null) {
            String field = captured.equals("Owner") ? "this$0" : "this$1";
            out.visitField(ACC_FINAL, field, "L" + captured + ";", null, null).visitEnd();
        }
        String descriptor = captured == null ? "()V" : "(L" + captured + ";)V";
        MethodVisitor init = out.visitMethod(0, "<init>", descriptor, null, null);
        init.visitCode();
        init.visitVarInsn(ALOAD, 0);
        init.visitMethodInsn(INVOKESPECIAL, "java/lang/Object", "<init>", "()V", false);
        if (captured != null) {
            init.visitVarInsn(ALOAD, 0);
            init.visitVarInsn(ALOAD, 1);
            init.visitFieldInsn(PUTFIELD, name, captured.equals("Owner") ? "this$0" : "this$1",
                                "L" + captured + ";");
        }
        init.visitInsn(RETURN);
        init.visitMaxs(2, captured == null ? 1 : 2);
        init.visitEnd();
        if (constructed != null) {
            MethodVisitor make = out.visitMethod(0, "make", "()V", null, null);
            make.visitCode();
            make.visitTypeInsn(NEW, constructed);
            make.visitInsn(DUP);
            make.visitVarInsn(ALOAD, 0);
            make.visitMethodInsn(INVOKESPECIAL, constructed, "<init>", "(L" + name + ";)V", false);
            make.visitInsn(POP);
            make.visitInsn(RETURN);
            make.visitMaxs(3, 1);
            make.visitEnd();
        }
        out.visitEnd();
        FileOutputStream file = new FileOutputStream(name + ".class");
        file.write(out.toByteArray());
        file.close();
    }
    public static void main(String[] args) throws Exception {
        write("Owner", null, "Owner$1");
        write("Owner$1", "Owner", "Owner$2");
        write("Owner$2", "Owner$1", null);
    }
}
'''
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        source = work / "GenerateNested.java"
        source.write_text(generator)
        subprocess.run([str(JAVAC), "-cp", str(ASM), str(source)], cwd=work,
                       check=True, capture_output=True, text=True)
        subprocess.run([str(JAVA), "-cp", str(work) + ":" + str(ASM), "GenerateNested"],
                       cwd=work, check=True, capture_output=True, text=True)
        original = work / "input.jar"
        repaired = work / "output.jar"
        with zipfile.ZipFile(original, "w") as archive:
            for path in work.glob("Owner*.class"):
                archive.write(path, path.name)
        result = subprocess.run(["bash", str(ROOT / "tools/innerclasses/repair.sh"),
                                 str(original), str(repaired)], check=True,
                                capture_output=True, text=True)
        assert "Owner$1 -> Owner" in result.stdout
        assert "Owner$2 -> Owner$1" in result.stdout
        again = work / "again.jar"
        repeated = subprocess.run(["bash", str(ROOT / "tools/innerclasses/repair.sh"),
                                   str(repaired), str(again)], check=True,
                                  capture_output=True, text=True)
        assert "restored anonymous classes: 0" in repeated.stdout


if __name__ == "__main__":
    test_repair_innerclasses()
    test_flattened_nested_anonymous_owner()
