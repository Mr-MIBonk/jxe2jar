#!/usr/bin/env python3
"""A reported clone catch can be removed without changing the try body."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from repair_unreachable_clone_catches import repair


source = """class C {
    Object cloneIt() {
        try {
            if (ok()) {
                return super.clone();
            }
            return null;
        } catch (CloneNotSupportedException exception) {
            return null;
        }
    }
}
"""
result = repair(source, 8)
assert "catch (CloneNotSupportedException" not in result
assert "if (ok())" in result
assert "return super.clone();" in result
assert "try" not in result
print("ok")
