#!/usr/bin/env python3
"""Ícone de protótipo para Android, gerado apenas com biblioteca padrão."""
import struct
import zlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "src/pt/blitztoons/res"

def chunk(tag, data):
    return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xffffffff)

def png(size):
    lines = []
    for y in range(size):
        line = bytearray([0])
        for x in range(size):
            u, v = x / size, y / size
            left = 0.29 <= u <= 0.39 and 0.19 <= v <= 0.81
            bars = 0.32 <= u <= 0.60 and (0.19 <= v <= 0.29 or 0.45 <= v <= 0.55 or 0.71 <= v <= 0.81)
            bowls = 0.56 <= u <= 0.69 and (0.25 <= v <= 0.51 or 0.51 <= v <= 0.75)
            color = (252, 180, 52, 255) if (left or bars or bowls) else (26, 30, 44, 255)
            line.extend(color)
        lines.append(bytes(line))
    raw = zlib.compress(b"".join(lines), 9)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")

for density, size in {"mdpi":48, "hdpi":72, "xhdpi":96, "xxhdpi":144, "xxxhdpi":192}.items():
    folder = BASE / f"mipmap-{density}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ic_launcher.png").write_bytes(png(size))
print("Ícones para cinco densidades gerados")
