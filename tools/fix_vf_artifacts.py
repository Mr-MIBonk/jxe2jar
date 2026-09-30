#!/usr/bin/env python3
"""
fix_vf_artifacts.py - Repair non-compilable Vineflower rendering artifacts.

Repairs Vineflower rendering artifacts including invalid placeholder types,
keyword-derived variable names, and captured variables in anonymous classes.
The latter are reconstructed from the synthetic constructor arguments and
fields: Java source needs final local captures rather than constructor
arguments on an interface.

Usage:
  python3 tools/fix_vf_artifacts.py <dir>            # dry-run (report only)
  python3 tools/fix_vf_artifacts.py <dir> --apply     # rewrite files in place
"""

import argparse
import os
import re
import sys

TOKEN = "<unrepresentable>"

# Vineflower's `jad` renamer derives a variable name by lower-casing its type, which
# collides with a reserved word when the type lower-cases to one (`Void`->void,
# `Else`->else, `Final`->final, `If`->if, ...), producing an illegal identifier like
# `accept(Void void)` or `ElseIterator(..., Else else)`. Suffix the identifier with `_` in
# its declaration. The lookahead `[=;,)]` keeps this to declaration/parameter positions
# (so a real modifier keyword like `final int` is never touched).
_JAVA_KEYWORDS = (
    "abstract|assert|boolean|break|byte|case|catch|char|class|const|continue|default|do|"
    "double|else|enum|extends|final|finally|float|for|goto|if|implements|import|instanceof|"
    "int|interface|long|native|new|package|private|protected|public|return|short|static|"
    "strictfp|super|switch|synchronized|this|throw|throws|transient|try|void|volatile|while|"
    "true|false|null"
)
KEYWORD_PARAM = re.compile(
    r"\b([A-Z][A-Za-z0-9_$]*)\s+(" + _JAVA_KEYWORDS + r")\b(?=\s*[=;,)])"
)

# Vineflower sometimes emits a cast as a self-duplicated intersection type,
# `(Map & Map)x`, which is a valid but pointless intersection of a type with itself.
# Collapse `(X & X)` -> `(X)` (backref keeps it to identical types; a real `(A & B)`
# intersection cast is left untouched). This also drops the Java-8-only intersection
# syntax that some downstream parsers reject.
DUP_INTERSECTION = re.compile(r"\(\s*([A-Za-z_$][\w$.]*)\s*&\s*\1\s*\)")

# Generics are stripped, so a raw `List.toArray(new T[n])` is typed `Object[]` and fails to
# assign to a `T[]`. The runtime result IS a `T[]`, so an explicit `(T[])` cast is always
# correct (redundant, not wrong, when the collection was actually generic). Only the
# assignment/return forms with a simple dotted receiver are matched; an existing cast makes
# the receiver group start with `(`, so it is skipped (no double cast).
TOARRAY_CAST = re.compile(
    r"(?<![=!<>+\-*/&|^%~])(=|\breturn)(\s+)([A-Za-z_][\w.$]*)\.toArray\(\s*new\s+([\w.$]+)\["
)

# The converted J9 anonymous constructor can retain synthetic capture arguments.
# Vineflower sometimes prints those arguments on an interface constructor, then
# emits an initializer that refers to its invented constructor-parameter names.
# Keep the captured values in final locals and bind the synthetic fields to them.
ANON_CAPTURE = re.compile(
    r"new (ListItemFactory|IPowerEvent|NavLocationCallback|NotifySDSCommand|AbstractParkingFocusPropertyDecorator|TimerListener|(?:NaviMyAudiSaveToAdbCommand\.)?IAdbImportListener|NotifyNaviServiceListenerCommand|TransitionCallback|ITelServiceListener|Runnable|SimpleButtonListener)\(([^()]*)\)\s*\{"
)
CAPTURE_FIELD = re.compile(r"^\s*private final ([\w.$]+) ([\w$]+);\s*$")
CAPTURE_ASSIGN = re.compile(r"^(\s*this\.([\w$]+)\s*=\s*)([\w$]+)(;\s*)$")
CLASS_DOLLAR_CALL = re.compile(r'(?<![\w.$])(?:[A-Za-z_$][\w$]*\.)?class\$\(\s*"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)"\s*\)')
BROKEN_CLASS_DOLLAR_LITERAL = re.compile(
    r'(?P<owner>[A-Za-z_$][\w$]*)\.class\$[\w$]+\s*=\s*(?P=owner)\.(?P<literal>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\.class)'
)


def _capture_statement_line(lines, index):
    """Place capture locals before the whole statement, including multiline calls."""
    for j in range(index - 1, -1, -1):
        if lines[j].rstrip().endswith((";", "{", "}")):
            return j + 1
    return 0


def fix_anonymous_captures(text):
    lines = text.splitlines(keepends=True)
    before = {}
    fixed = 0
    for i, line in enumerate(lines):
        match = ANON_CAPTURE.search(line)
        if not match:
            continue
        kind, raw_args = match.groups()
        args = [arg.strip() for arg in raw_args.split(",")]
        if not args or not args[0]:
            continue
        if kind in ("AbstractParkingFocusPropertyDecorator", "NotifySDSCommand", "NotifyNaviServiceListenerCommand"):
            if args[0] != "this":
                continue
            real_args, captured_args = args[1:], []
        elif kind == "IPowerEvent":
            if args != ["this"]:
                continue
            real_args, captured_args = [], []
        else:
            real_args = []
            captured_args = args[1:] if args[0] == "this" else args
        if any(not re.fullmatch(r"[A-Za-z_$][\w$]*", arg) for arg in captured_args):
            continue

        fields = {}
        j = i + 1
        while j < len(lines):
            if not lines[j].strip():
                j += 1
                continue
            field = CAPTURE_FIELD.match(lines[j])
            if not field:
                break
            fields[field.group(2)] = field.group(1)
            j += 1
        if j >= len(lines) or lines[j].strip() != "{":
            continue
        j += 1
        assignments = {}
        while j < len(lines) and lines[j].strip() != "}":
            if lines[j].strip():
                assignment = CAPTURE_ASSIGN.match(lines[j])
                if not assignment:
                    break
                assignments[assignment.group(2)] = (j, assignment)
            j += 1
        if j >= len(lines) or lines[j].strip() != "}" or set(assignments) != set(fields):
            continue
        value_fields = [name for name in fields if name.startswith("val$")]
        if len(value_fields) != len(captured_args):
            continue
        outer_fields = [name for name in fields if re.fullmatch(r"this\$\d+", name)]
        if len(outer_fields) > 1 or (outer_fields and args[0] != "this"):
            continue
        if any(name not in outer_fields and not name.startswith("val$") for name in fields):
            continue
        if any(fields[name] == "Object" for name in outer_fields):
            continue

        lines[i] = line[:match.start()] + f"new {kind}({', '.join(real_args)}) {{" + line[match.end():]
        start = _capture_statement_line(lines, i)
        indent = re.match(r"\s*", lines[start]).group()
        aliases = []
        for name, arg in zip(value_fields, captured_args):
            alias = f"__vf_capture_{fixed}_{name[4:].replace('$', '_')}"
            aliases.append(f"{indent}final {fields[name]} {alias} = {arg};\n")
            k, assignment = assignments[name]
            lines[k] = assignment.group(1) + alias + assignment.group(4)
        if aliases:
            before.setdefault(start, []).extend(aliases)
        for name in outer_fields:
            k, assignment = assignments[name]
            lines[k] = assignment.group(1) + fields[name] + ".this" + assignment.group(4)
        fixed += 1
    return "".join("".join(before.get(i, [])) + line for i, line in enumerate(lines)), fixed


def fix_dangling_outer_field(text):
    if not re.search(r"this\.this\$0\s*=", text) or re.search(r"\bthis\$0\s*;", text):
        return text, 0
    match = re.search(r"(class\s+[\w$]+\$\d+[^\{]*\{)\s*(?:\r?\n)(\s*[\w$]+\$\d+\(([\w.$]+)\s+[\w$]+\)\s*\{)", text)
    if not match:
        return text, 0
    indent = re.match(r"\s*", match.group(2)).group()
    insert = f"\n{indent}private final {match.group(3)} this$0;\n"
    return text[:match.start(2)] + insert + text[match.start(2):], 1


def _constructor_arguments(text, opening):
    """Split a Java argument list, retaining calls and commas inside strings."""
    depth = {"(": 1, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    start = opening + 1
    parts = []
    quote = None
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char in depth:
            depth[char] += 1
        elif char in pairs:
            depth[pairs[char]] -= 1
            if char == ")" and depth["("] == 0:
                parts.append(text[start:i].strip())
                return parts, i
        elif char == "," and depth["("] == 1 and depth["["] == 0 and depth["{"] == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    return [], -1


def _statement_line(text, position):
    line = text.rfind("\n", 0, position) + 1
    for _ in range(6):
        prefix = text[line:position]
        if re.search(r"\breturn\b|\bthrow\b|=|\.add\(|\.setErrorCommand\(", prefix):
            return line
        if line == 0:
            break
        previous = text.rfind("\n", 0, line - 1) + 1
        if previous == line:
            break
        line = previous
    return None


def fix_nav_command_captures(text):
    """Undo synthetic outer/captured arguments on anonymous NavCommand classes."""
    edits = []
    fixed = 0
    for match in re.finditer(r"new NavCommand\(", text):
        args, end = _constructor_arguments(text, match.end() - 1)
        if end < 0 or not args:
            continue
        pos = end + 1
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            continue
        pos += 1
        fields = []
        while True:
            field = re.match(r"\s*private final ([\w.$\[\]]+) ([\w$]+);", text[pos:])
            if not field:
                break
            fields.append((field.group(2), field.group(1)))
            pos += field.end()
        value_fields = [(name, typ) for name, typ in fields if name.startswith("val$")]
        outer_fields = [(name, typ) for name, typ in fields if re.fullmatch(r"this\$\d+", name)]
        if len(outer_fields) > 1 or len(value_fields) + len(outer_fields) != len(fields):
            continue
        if outer_fields and args[0] != "this":
            continue
        if outer_fields and outer_fields[0][1] == "Object":
            continue
        tail = args[1:] if outer_fields else args
        if len(tail) == len(value_fields):
            real_args, captured = [], tail
        elif len(tail) == len(value_fields) + 1:
            real_args, captured = tail[:1], tail[1:]
        else:
            continue
        pos = _skip_whitespace(text, pos)
        if pos >= len(text) or text[pos] != "{":
            continue
        pos += 1
        assignments = {}
        while True:
            pos = _skip_whitespace(text, pos)
            assignment = re.match(r"this\.([\w$]+)\s*=\s*([^;]+);", text[pos:])
            if not assignment:
                break
            assignments[assignment.group(1)] = (
                pos + assignment.start(2), pos + assignment.end(2)
            )
            pos += assignment.end()
        pos = _skip_whitespace(text, pos)
        if pos >= len(text) or text[pos] != "}" or set(assignments) != {name for name, _ in fields}:
            continue
        if any(text[start:end].startswith("__vf_") for start, end in assignments.values()):
            continue
        statement = _statement_line(text, match.start()) if captured else None
        if captured and statement is None:
            continue
        edits.append((match.start(), end + 1, "new NavCommand(" + ", ".join(real_args) + ")"))
        if outer_fields:
            name, typ = outer_fields[0]
            edits.append((*assignments[name], typ + ".this"))
        if captured:
            indent = re.match(r"[ \t]*", text[statement:]).group()
            aliases = []
            for name, typ in value_fields:
                arg = captured[len(aliases)]
                alias = f"__vf_nav_capture_{fixed}_{name[4:].replace('$', '_')}"
                aliases.append(f"{indent}final {typ} {alias} = {arg};\n")
                edits.append((*assignments[name], alias))
            edits.append((statement, statement, "".join(aliases)))
        fixed += 1
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, fixed


def _skip_whitespace(text, position):
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _matching_brace(text, opening):
    depth = 0
    quote = None
    escaped = False
    comment = None
    i = opening
    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if comment == "line":
            if char == "\n":
                comment = None
        elif comment == "block":
            if char == "*" and next_char == "/":
                comment = None
                i += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and next_char == "/":
            comment = "line"
            i += 1
        elif char == "/" and next_char == "*":
            comment = "block"
            i += 1
        elif char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def fix_nested_nav_command_captures(text):
    """Replace an unnamed enclosing anonymous instance with its final fields."""
    edits = []
    fixed = 0
    for match in re.finditer(r"new NavCommand\(", text):
        args, end = _constructor_arguments(text, match.end() - 1)
        if end < 0 or not args or args[0] != "this" or len(args) > 2:
            continue
        opening = _skip_whitespace(text, end + 1)
        if opening >= len(text) or text[opening] != "{":
            continue
        header = re.match(
            r"\s*private final Object this\$1;\s*\{\s*this\.this\$1\s*=\s*[\w$]+;\s*\}",
            text[opening + 1:]
        )
        if not header:
            continue
        header_end = opening + 1 + header.end()
        closing = _matching_brace(text, opening)
        if closing < 0:
            continue
        body = text[header_end:closing]
        references = list(re.finditer(r"this\s*\.\s*this\$1\s*\.\s*([\w$]+)", body))
        if len(references) != len(re.findall(r"this\s*\.\s*this\$1", body)):
            continue
        used = {reference.group(1) for reference in references}

        outer_fields = None
        for outer in reversed(list(re.finditer(r"new NavCommand\(", text[:match.start()]))):
            _, outer_end = _constructor_arguments(text, outer.end() - 1)
            if outer_end < 0:
                continue
            outer_open = _skip_whitespace(text, outer_end + 1)
            if outer_open >= len(text) or text[outer_open] != "{" or _matching_brace(text, outer_open) < match.start():
                continue
            pos = outer_open + 1
            fields = {}
            while True:
                field = re.match(r"\s*private final ([\w.$\[\]]+) ([\w$]+);", text[pos:])
                if not field:
                    break
                fields[field.group(2)] = field.group(1)
                pos += field.end()
            if used <= fields.keys():
                outer_fields = fields
                break
        if outer_fields is None:
            continue
        statement = _statement_line(text, match.start()) if used else None
        if used and statement is None:
            continue
        edits.append((match.start(), end + 1, "new NavCommand(" + ", ".join(args[1:]) + ")"))
        edits.append((opening + 1, header_end, "\n"))
        if used:
            indent = re.match(r"[ \t]*", text[statement:]).group()
            aliases = []
            for field in sorted(used):
                alias = f"__vf_nested_capture_{fixed}_{field.replace('$', '_')}"
                aliases.append(f"{indent}final {outer_fields[field]} {alias} = this.{field};\n")
                for reference in references:
                    if reference.group(1) == field:
                        start = header_end + reference.start()
                        end_ref = header_end + reference.end()
                        edits.append((start, end_ref, alias))
            edits.append((statement, statement, "".join(aliases)))
        fixed += 1
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, fixed


def fix_nested_object_captures(text):
    """Repair an anonymous class whose synthetic enclosing field became Object."""
    edits = []
    fixed = 0
    for match in re.finditer(r"new (NavCommand|Runnable|NavLocationCallback|NotifyNaviServiceListenerCommand)\(", text):
        kind = match.group(1)
        args, end = _constructor_arguments(text, match.end() - 1)
        if end < 0 or not args or args[0] != "this":
            continue
        opening = _skip_whitespace(text, end + 1)
        if opening >= len(text) or text[opening] != "{":
            continue
        closing = _matching_brace(text, opening)
        if closing < 0:
            continue
        pos = opening + 1
        fields = {}
        field_spans = {}
        while True:
            field = re.match(r"\s*private final ([\w.$\[\]]+) ([\w$]+);", text[pos:])
            if not field:
                break
            fields[field.group(2)] = field.group(1)
            field_spans[field.group(2)] = (pos, pos + field.end())
            pos += field.end()
        outer_names = [name for name, typ in fields.items() if re.fullmatch(r"this\$[1-9]\d*", name) and typ == "Object"]
        if len(outer_names) != 1 or any(name not in outer_names and not name.startswith("val$") for name in fields):
            continue
        outer_name = outer_names[0]
        value_fields = [name for name in fields if name.startswith("val$")]
        pos = _skip_whitespace(text, pos)
        if pos >= len(text) or text[pos] != "{":
            continue
        pos += 1
        assignments = {}
        assignment_spans = {}
        while True:
            start = pos
            pos = _skip_whitespace(text, pos)
            assignment = re.match(r"this\.([\w$]+)\s*=\s*([^;]+);", text[pos:])
            if not assignment:
                break
            assignments[assignment.group(1)] = (pos + assignment.start(2), pos + assignment.end(2))
            assignment_spans[assignment.group(1)] = (start, pos + assignment.end())
            pos += assignment.end()
        pos = _skip_whitespace(text, pos)
        if pos >= len(text) or text[pos] != "}" or set(assignments) != set(fields):
            continue
        tail = args[1:]
        if kind in ("Runnable", "NavLocationCallback"):
            if len(tail) != len(value_fields):
                continue
            real_args, captured = [], tail
        elif kind == "NotifyNaviServiceListenerCommand":
            if len(tail) != len(value_fields) + 1:
                continue
            real_args, captured = tail[:1], tail[1:]
        elif len(tail) == len(value_fields) + 1:
            real_args, captured = tail[:1], tail[1:]
        elif len(tail) == len(value_fields):
            real_args, captured = [], tail
        else:
            continue
        if any(text[start:end].startswith("__vf_nested_object_") for start, end in assignments.values()):
            continue

        body = text[pos + 1:closing]
        reference_rx = re.compile(r"this\s*\.\s*" + re.escape(outer_name) + r"\s*\.\s*([\w$]+)")
        refs = list(reference_rx.finditer(body))
        if len(refs) != len(re.findall(r"this\s*\.\s*" + re.escape(outer_name), body)):
            continue
        used = {ref.group(1) for ref in refs}
        enclosing_fields = {}
        if used:
            for candidate in reversed(list(re.finditer(r"new [A-Za-z_$][\w.$]*\(", text[:match.start()]))):
                _, outer_end = _constructor_arguments(text, candidate.end() - 1)
                outer_open = _skip_whitespace(text, outer_end + 1) if outer_end >= 0 else -1
                if outer_open < 0 or outer_open >= len(text) or text[outer_open] != "{":
                    continue
                if _matching_brace(text, outer_open) < match.start():
                    continue
                field_pos = outer_open + 1
                found = {}
                while True:
                    field = re.match(r"\s*private final ([\w.$\[\]]+) ([\w$]+);", text[field_pos:])
                    if not field:
                        break
                    found[field.group(2)] = field.group(1)
                    field_pos += field.end()
                if used <= found.keys():
                    enclosing_fields = found
                    break
            if not enclosing_fields:
                continue

        line = text.count("\n", 0, match.start())
        lines = text.splitlines(keepends=True)
        statement = sum(map(len, lines[:_capture_statement_line(lines, line)]))
        indent = re.match(r"[ \t]*", text[statement:]).group()
        aliases = []
        for name, arg in zip(value_fields, captured):
            alias = f"__vf_nested_object_{fixed}_{name[4:].replace('$', '_')}"
            aliases.append(f"{indent}final {fields[name]} {alias} = {arg};\n")
            edits.append((*assignments[name], alias))
        for ref in refs:
            field = ref.group(1)
            if field == "this$0":
                replacement = enclosing_fields[field] + ".this"
            else:
                replacement = f"__vf_nested_object_{fixed}_outer_{field.replace('$', '_')}"
                if not any(alias.endswith(f" {replacement} = this.{field};\n") for alias in aliases):
                    aliases.append(f"{indent}final {enclosing_fields[field]} {replacement} = this.{field};\n")
            edits.append((pos + 1 + ref.start(), pos + 1 + ref.end(), replacement))
        if aliases:
            edits.append((statement, statement, "".join(aliases)))
        edits.append((match.start(), end + 1, "new " + kind + "(" + ", ".join(real_args) + ")"))
        edits.append((*field_spans[outer_name], ""))
        edits.append((*assignment_spans[outer_name], ""))
        fixed += 1
    for start, end, replacement in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, fixed


def fix_navigation_param_alias(text):
    # Two RRD constructors are rendered with a nonexistent `navigationx` even
    # though their parameter is named `navigation` in the same declaration.
    if "Navigation navigation" not in text or "Navigation navigationx" in text:
        return text, 0
    return re.subn(r"(this\.navigation\s*=\s*)navigationx;", r"\1navigation;", text)


def fix_class_dollar_literals(text):
    # VF can retain an old compiler's class$(String) call but omit its
    # synthetic helper. The encoded class name is already a Java literal.
    if re.search(r"\bClass\s+class\$\s*\(", text):
        return text, 0
    text, repaired = BROKEN_CLASS_DOLLAR_LITERAL.subn(
        lambda match: match.group(0).replace(match.group("owner") + "." + match.group("literal"), match.group("literal")), text
    )
    text, converted = CLASS_DOLLAR_CALL.subn(
        lambda match: match.group(1).replace("$", ".") + ".class", text
    )
    return text, repaired + converted


def fix_text(text):
    n = text.count(TOKEN)
    text = text.replace(TOKEN, "Object")
    text, k = KEYWORD_PARAM.subn(lambda m: f"{m.group(1)} {m.group(2)}_", text)
    text, d = DUP_INTERSECTION.subn(r"(\1)", text)
    text, a = TOARRAY_CAST.subn(r"\1\2(\4[]) \3.toArray(new \4[", text)
    text, captures = fix_anonymous_captures(text)
    text, outer = fix_dangling_outer_field(text)
    text, nav = fix_nav_command_captures(text)
    text, nested_nav = fix_nested_nav_command_captures(text)
    text, nested_object = fix_nested_object_captures(text)
    text, nav_param = fix_navigation_param_alias(text)
    text, class_literals = fix_class_dollar_literals(text)
    return text, n + k + d + a + captures + outer + nav + nested_nav + nested_object + nav_param + class_literals


def main():
    ap = argparse.ArgumentParser(description="Fix Vineflower rendering artifacts.")
    ap.add_argument("dir")
    ap.add_argument("--apply", action="store_true", help="rewrite files in place")
    args = ap.parse_args()

    changed = hits = 0
    for dp, _, files in os.walk(args.dir):
        for name in files:
            if not name.endswith(".java"):
                continue
            path = os.path.join(dp, name)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            new, n = fix_text(text)
            if new == text:
                continue
            hits += n
            changed += 1
            if args.apply:
                open(path, "w", encoding="utf-8").write(new)

    action = "fixed" if args.apply else "would fix"
    print(f"{action} {hits} artifact(s) in {changed} file(s)")
    if not args.apply:
        print("dry-run - pass --apply to rewrite files")


if __name__ == "__main__":
    main()
