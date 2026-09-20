import struct
from io import BytesIO, IOBase

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

    @property
    def bytepos(self):
        return self.stream.tell()

    @bytepos.setter
    def bytepos(self, pos):
        self.stream.seek(pos)

    def read(self, fmt):
        if fmt.startswith("bytes:"):
            length = int(fmt.split(":")[1])
            return self.stream.read(length)

        sizes = {"8": 1, "16": 2, "32": 4}
        parts = fmt.split(":")
        type_endian = parts[0]
        bits = parts[1]

        size = sizes[bits]
        data = self.stream.read(size)
        if len(data) < size:
            raise EOFError

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
