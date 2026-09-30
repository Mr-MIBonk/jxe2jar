#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
INPUT=${1:?usage: repair.sh INPUT.jar OUTPUT.jar}
OUTPUT=${2:?usage: repair.sh INPUT.jar OUTPUT.jar}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
javac -cp "$ROOT/tools/uninline/lib/asm-9.7.jar" -d "$WORK" "$ROOT/tools/innerclasses/RepairInnerClasses.java"
java -cp "$WORK:$ROOT/tools/uninline/lib/asm-9.7.jar" RepairInnerClasses "$INPUT" "$OUTPUT"
