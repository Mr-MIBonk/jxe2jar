#!/usr/bin/env python3
"""J9UTF8 reader check: an empty ROM string must not swallow the next pool record."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from common import ReaderStream, decode_modified_utf8  # noqa: E402
from constpool import _encode_utf8  # noqa: E402


def _rec(text):
    """One J9UTF8: LE u16 length + modified-UTF8 data, padded to 2-byte alignment."""
    data = text.encode()
    return struct.pack("<H", len(data)) + data + (b"\x00" if len(data) % 2 else b"")


def _raw_rec(data):
    return struct.pack("<H", len(data)) + data


def main():
    # Layout lifted from MU1326-lsd.jxe around offset 0x393B18F.
    pool = _rec("") + _rec("isNativeLittleEndian") + _rec("java/lang/OutOfMemoryError")
    stream = ReaderStream.bytes_to_stream(pool)

    stream.set(0)
    assert stream.read_string() == "", "empty string leaked the next pool record"
    stream.set(2)
    assert stream.read_string() == "isNativeLittleEndian"
    stream.set(24)
    assert stream.read_string() == "java/lang/OutOfMemoryError"

    # Odd-length record: the pad byte must not bleed into the string.
    padded = _rec("freePointer") + _rec("isNativeLittleEndian")
    stream = ReaderStream.bytes_to_stream(padded)
    stream.set(0)
    assert stream.read_string() == "freePointer"
    stream.set(14)
    assert stream.read_string() == "isNativeLittleEndian"

    # Actual Yylex.ZZ_CMAP_PACKED: each pair is a run length and a map value.
    # It starts with a control character, contains many NULs, and ends with a
    # large run (U+FF82). Preserve it through ROM reading and classfile output.
    cmap_packed = (
        "\11\0\1\7\1\7\2\0\1\7\22\0\1\7\1\0\1\11\10\0"
        "\1\6\1\31\1\2\1\4\1\12\12\3\1\32\6\0\4\1\1\5"
        "\1\1\24\0\1\27\1\10\1\30\3\0\1\22\1\13\2\1\1\21"
        "\1\14\5\0\1\23\1\0\1\15\3\0\1\16\1\24\1\17\1\20"
        "\5\0\1\25\1\0\1\26\uff82\0"
    )
    cmap_bytes = cmap_packed.encode("utf-8").replace(b"\x00", b"\xc0\x80")
    decoded = ReaderStream.bytes_to_stream(_raw_rec(cmap_bytes)).read_string()
    assert decoded == cmap_packed
    assert _encode_utf8(decoded) == cmap_bytes

    cmap = "".join(value * ord(count)
                   for count, value in zip(decoded[::2], decoded[1::2]))
    assert len(cmap) == 0x10000
    assert cmap[:9] == "\0" * 9
    assert cmap[9] == "\7"
    assert cmap[-1] == "\0"

    # Corrupt byte sequences must not be mistaken for valid ROM strings.
    malformed = (
        b"\x00",           # Raw NUL
        b"\x80",           # Continuation without a lead byte
        b"\xc0A",          # Invalid continuation
        b"\xe2A\xac",     # Invalid continuation in a three-byte sequence
        b"\xe2\x82A",     # Invalid final continuation
        b"\xc0\x81",      # Overlong encoding of U+0001
        b"\xe0\x80\x80",  # Overlong encoding of U+0000
        b"\xc2",           # Truncated sequence
        b"\xf0\x90\x80\x80",  # Four-byte UTF-8 is not modified UTF-8
    )
    for data in malformed:
        try:
            ReaderStream.bytes_to_stream(_raw_rec(data))._read_j9utf8_at(0)
        except UnicodeDecodeError:
            pass
        else:
            raise AssertionError(f"accepted malformed modified UTF-8: {data!r}")

    # Supplementary characters are represented as pairs of surrogate code units.
    assert decode_modified_utf8(b"\xed\xa0\xbd\xed\xb8\x80") == "\ud83d\ude00"

    print("ok")


if __name__ == "__main__":
    main()
