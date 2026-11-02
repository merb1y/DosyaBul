"""Harici kütüphane olmadan uygulamanın PNG ve ICO simgelerini üretir."""

import math
import struct
import zlib
from pathlib import Path


def segment_distance(x, y, ax, ay, bx, by):
    projection = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax)**2 + (by - ay)**2)))
    return math.hypot(x - ax - projection * (bx - ax), y - ay - projection * (by - ay))


def color_at(x, y):
    corner_x = max(0.20, min(0.80, x))
    corner_y = max(0.20, min(0.80, y))
    if math.hypot(x - corner_x, y - corner_y) > 0.18:
        return (0, 0, 0, 0)
    radius = math.hypot(x - 0.43, y - 0.42)
    if abs(radius - 0.225) < 0.032 or segment_distance(x, y, 0.59, 0.59, 0.79, 0.79) < 0.04:
        return (255, 255, 255, 255)
    if segment_distance(x, y, 0.33, 0.38, 0.53, 0.38) < 0.017 or segment_distance(x, y, 0.33, 0.46, 0.47, 0.46) < 0.017:
        return (158, 227, 255, 255)
    return (36, 107, 253, 255)


def chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)


def png(size):
    raw = bytearray()
    samples = 4
    for y in range(size):
        raw.append(0)
        for x in range(size):
            values = [0, 0, 0, 0]
            for sy in range(samples):
                for sx in range(samples):
                    color = color_at((x + (sx + 0.5) / samples) / size, (y + (sy + 0.5) / samples) / size)
                    for channel in range(4):
                        values[channel] += color[channel]
            raw.extend(round(value / samples**2) for value in values)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main():
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    sizes = (16, 32, 48, 64, 128, 256)
    images = [(size, png(size)) for size in sizes]
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, image in images:
        dimension = 0 if size == 256 else size
        directory.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    (assets / "icon.ico").write_bytes(bytes(directory) + b"".join(image for _, image in images))
    (assets / "icon.png").write_bytes(dict(images)[128])
    print("Uygulama simgeleri hazır.")


if __name__ == "__main__":
    main()
