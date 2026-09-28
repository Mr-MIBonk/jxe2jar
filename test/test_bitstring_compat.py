#!/usr/bin/env python3
"""The bundled byte stream must fail on incomplete ROM data like bitstring."""
import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import bitstring  # noqa: E402
from common import ReaderStream, WriterStream  # noqa: E402


def main():
    stream = ReaderStream.bytes_to_stream(b"AB")
    for read in (lambda: stream.read_bytes(4), lambda: stream.read_u32()):
        try:
            read()
        except bitstring.ReadError:
            assert stream.get() == 0, "failed read moved the cursor"
        else:
            raise AssertionError("incomplete input was accepted")

    stream.set(2)
    try:
        stream.set(3)
    except ValueError:
        assert stream.get() == 2, "failed seek moved the cursor"
    else:
        raise AssertionError("seek past the end was accepted")

    bits = bitstring.BitStream()
    bits.append(bitstring.BitArray(bytes=b"AB"))
    assert bits.bytepos == 2
    bits.bytepos = 0
    bits.append(bitstring.BitArray(bytes=b"CD"))
    assert bits.bytepos == 4 and bits.bytes == b"ABCD"

    output = BytesIO()
    writer = WriterStream(output)
    writer.write_u16(0x1234)
    writer.write_raw_bytes(b"CD")
    writer.write()
    assert output.getvalue() == b"\x12\x34CD"

    print("ok")


if __name__ == "__main__":
    main()
