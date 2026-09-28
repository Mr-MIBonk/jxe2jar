import struct
from io import BytesIO, IOBase


class ReadError(Exception):
    """A read requested more data than the stream contains."""


class BitArray:
    def __init__(self, bytes=None):
        if bytes is not None:
            self.bytes = bytes
        else:
            self.bytes = b""

    @property
    def length(self):
        return len(self.bytes) * 8

class BitStream:
    def __init__(self, obj=None):
        if isinstance(obj, IOBase):
            self.stream = BytesIO(obj.read())
        elif isinstance(obj, bytes):
            self.stream = BytesIO(obj)
        elif isinstance(obj, BitArray):
            self.stream = BytesIO(obj.bytes)
        else:
            self.stream = BytesIO()

    def _append(self, obj):
        if isinstance(obj, BitArray):
            pos = self.stream.tell()
            self.stream.seek(0, 2)
            self.stream.write(obj.bytes)
            self.stream.seek(pos)
        else:
            raise TypeError("Can only append BitArray")

    def append(self, obj):
        self._append(obj)
        self.stream.seek(0, 2)

    @property
    def bytepos(self):
        return self.stream.tell()

    @bytepos.setter
    def bytepos(self, pos):
        if pos < 0 or pos > len(self.stream.getbuffer()):
            raise ValueError("Cannot seek past the end of the data")
        self.stream.seek(pos)

    def _read_exact(self, size):
        available = len(self.stream.getbuffer()) - self.stream.tell()
        if size < 0:
            raise ValueError("Negative read length")
        if size > available:
            raise ReadError(
                f"Needed a length of at least {size * 8} bits, "
                f"but only {available * 8} bits were available"
            )
        return self.stream.read(size)

    def read(self, fmt):
        if fmt.startswith("bytes:"):
            length = int(fmt.split(":")[1])
            return self._read_exact(length)

        sizes = {"8": 1, "16": 2, "32": 4}
        parts = fmt.split(":")
        type_endian = parts[0]
        bits = parts[1]

        size = sizes[bits]
        data = self._read_exact(size)

        if type_endian == "uintle":
            struct_fmt = "<" + {1: "B", 2: "H", 4: "I"}[size]
        elif type_endian == "intle":
            struct_fmt = "<" + {1: "b", 2: "h", 4: "i"}[size]
        elif type_endian == "uintbe":
            struct_fmt = ">" + {1: "B", 2: "H", 4: "I"}[size]
        elif type_endian == "intbe":
            struct_fmt = ">" + {1: "b", 2: "h", 4: "i"}[size]
        else:
            raise ValueError(f"Unknown format {fmt}")

        return struct.unpack(struct_fmt, data)[0]

    @property
    def bytes(self):
        return self.stream.getvalue()

    @property
    def length(self):
        pos = self.stream.tell()
        self.stream.seek(0, 2)
        size = self.stream.tell()
        self.stream.seek(pos)
        return size * 8

    def tofile(self, f):
        f.write(self.stream.getvalue())

def pack(fmt, value):
    sizes = {"8": 1, "16": 2, "32": 4}
    parts = fmt.split(":")
    type_endian = parts[0]
    bits = parts[1]

    size = sizes[bits]

    if type_endian == "uintle":
        struct_fmt = "<" + {1: "B", 2: "H", 4: "I"}[size]
    elif type_endian == "intle":
        struct_fmt = "<" + {1: "b", 2: "h", 4: "i"}[size]
    elif type_endian == "uintbe":
        struct_fmt = ">" + {1: "B", 2: "H", 4: "I"}[size]
    elif type_endian == "intbe":
        struct_fmt = ">" + {1: "b", 2: "h", 4: "i"}[size]
    else:
        raise ValueError(f"Unknown format {fmt}")

    return BitArray(bytes=struct.pack(struct_fmt, value))
