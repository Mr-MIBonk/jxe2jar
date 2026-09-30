#!/usr/bin/env python3
"""ROM field flags must survive conversion into the classfile field table."""

import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jxe import J9ROMField  # noqa: E402
from jxe2jar import create_class  # noqa: E402


def test_synthetic_field_flags():
    romclass = SimpleNamespace(
        class_name="cases/SyntheticFieldFlags",
        superclass_name="java/lang/Object",
        access_flags=0x0001,
        interfaces=[],
        constant_pool=[],
        methods=[],
        fields=[
            J9ROMField("val$captured", "I", 0x1012),
            J9ROMField("ordinary", "I", 0x0012),
        ],
    )
    javap = ROOT / "jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home/bin/javap"
    with tempfile.TemporaryDirectory() as directory:
        jar = pathlib.Path(directory) / "flags.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            create_class(romclass, archive)
        output = subprocess.check_output(
            [str(javap), "-classpath", str(jar), "-p", "-v", "cases.SyntheticFieldFlags"],
            text=True,
        )
        synthetic = re.search(r"private final int val\$captured;\s*descriptor: I\s*flags: ([^\n]+)", output)
        ordinary = re.search(r"private final int ordinary;\s*descriptor: I\s*flags: ([^\n]+)", output)
        assert synthetic and "ACC_SYNTHETIC" in synthetic.group(1)
        assert ordinary and "ACC_SYNTHETIC" not in ordinary.group(1)


if __name__ == "__main__":
    test_synthetic_field_flags()
