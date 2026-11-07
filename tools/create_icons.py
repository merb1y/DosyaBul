"""Harici kütüphane olmadan uygulamanın PNG ve ICO simgelerini üretir.

Tasarım Rofi panelini yansıtır: koyu gövde, mor gradyan çerçeve, üstte mor
arama alanı (büyüteç ve imleç ile) ve altında seçili satırı olan sonuç listesi.
Her boyut analitik anti-alias ile ayrı çizilir; küçük boyutlarda (16-32 px)
satır sayısı ve ayrıntı azaltılarak simge okunaklı kalır.
"""

import math
import struct
import zlib
from pathlib import Path

BODY_TOP = (30, 30, 46)
BODY_BOTTOM = (17, 17, 27)
BORDER_A = (203, 166, 247)  # açık mor
BORDER_B = (116, 93, 232)  # koyu mor
BAR_A = (186, 140, 250)
BAR_B = (120, 90, 235)
SELECTED = (58, 58, 84)
ROW_TEXT = (205, 214, 244)
ROW_DIM = (108, 112, 140)
WHITE = (255, 255, 255)
SHADOW = (5, 5, 14)


def ramp(edge_low, edge_high, value):
    """smoothstep: value <= edge_low iken 0, edge_high iken 1."""
    if edge_high == edge_low:
        return 1.0 if value >= edge_high else 0.0
    t = (value - edge_low) / (edge_high - edge_low)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def over(base, source):
    br, bg, bb, ba = base
    sr, sg, sb, sa = source
    alpha = sa + ba * (1.0 - sa)
    if alpha <= 0.0:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        (sr * sa + br * ba * (1.0 - sa)) / alpha,
        (sg * sa + bg * ba * (1.0 - sa)) / alpha,
        (sb * sa + bb * ba * (1.0 - sa)) / alpha,
        alpha,
    )


def box_distance(x, y, cx, cy, half_w, half_h, radius):
    """Yuvarlatılmış dikdörtgenin işaretli mesafesi (içeride negatif)."""
    qx = abs(x - cx) - (half_w - radius)
    qy = abs(y - cy) - (half_h - radius)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - radius


def fill_box(x, y, left, top, right, bottom, radius, pixel):
    distance = box_distance(x, y, (left + right) / 2, (top + bottom) / 2, (right - left) / 2, (bottom - top) / 2, radius)
    return 1.0 - ramp(-pixel, pixel, distance)


def squircle_distance(x, y, half, radius):
    return box_distance(x, y, 0.5, 0.5, half, half, radius)


def segment_distance(x, y, ax, ay, bx, by):
    length = (bx - ax) ** 2 + (by - ay) ** 2
    projection = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / length))
    return math.hypot(x - ax - projection * (bx - ax), y - ay - projection * (by - ay))


def capsule(x, y, ax, ay, bx, by, width, pixel):
    return 1.0 - ramp(width / 2 - pixel, width / 2 + pixel, segment_distance(x, y, ax, ay, bx, by))


def ring(x, y, cx, cy, mid_radius, width, pixel):
    distance = math.hypot(x - cx, y - cy)
    inner = mid_radius - width / 2
    outer = mid_radius + width / 2
    return ramp(inner - pixel, inner + pixel, distance) * (1.0 - ramp(outer - pixel, outer + pixel, distance))


def color_at(x, y, size):
    pixel = 0.62 / size
    small = size <= 32
    out = (0.0, 0.0, 0.0, 0.0)

    # Yumuşak gölge (yalnızca büyük boyutlarda)
    if size >= 48:
        shade = 1.0 - ramp(-pixel * 6.0, pixel * 10.0, box_distance(x, y, 0.5, 0.53, 0.45, 0.45, 0.17))
        if shade > 0:
            out = over(out, (SHADOW[0], SHADOW[1], SHADOW[2], shade * 0.30))

    outer = 1.0 - ramp(-pixel, pixel, squircle_distance(x, y, 0.46, 0.17))
    if outer <= 0:
        return out

    # Mor gradyan çerçeve + koyu gövde
    border = mix(BORDER_A, BORDER_B, ramp(0.0, 1.6, x + y - 0.2))
    out = over(out, (border[0], border[1], border[2], outer))
    border_w = 0.05 if small else 0.036
    inner_half = 0.46 - border_w
    inner = 1.0 - ramp(-pixel, pixel, squircle_distance(x, y, inner_half, 0.17 - border_w * 0.6))
    body = mix(BODY_TOP, BODY_BOTTOM, ramp(0.0, 1.0, y))
    out = over(out, (body[0], body[1], body[2], inner))
    if inner <= 0:
        return out

    # Arama alanı
    bar_left, bar_right = 0.17, 0.83
    if small:
        bar_top, bar_bottom = 0.19, 0.43
    else:
        bar_top, bar_bottom = 0.18, 0.37
    bar_radius = (bar_bottom - bar_top) * 0.28
    bar = fill_box(x, y, bar_left, bar_top, bar_right, bar_bottom, bar_radius, pixel)
    if bar > 0:
        fill = mix(BAR_A, BAR_B, ramp(bar_left, bar_right, x))
        out = over(out, (fill[0], fill[1], fill[2], bar))

        # Büyüteç
        mid_y = (bar_top + bar_bottom) / 2
        lens_r = (bar_bottom - bar_top) * 0.20
        stroke = (bar_bottom - bar_top) * (0.115 if small else 0.095)
        lx = bar_left + (bar_bottom - bar_top) * 0.52
        ly = mid_y - lens_r * 0.15
        glyph = ring(x, y, lx, ly, lens_r, stroke, pixel)
        hx, hy = lx + lens_r * 0.72, ly + lens_r * 0.72
        glyph = max(glyph, capsule(x, y, hx, hy, hx + lens_r * 0.62, hy + lens_r * 0.62, stroke * 1.05, pixel))
        if glyph > 0:
            out = over(out, (WHITE[0], WHITE[1], WHITE[2], glyph * bar))

        if not small:
            # Yazı imleci ve yazılmış metin
            text_x = lx + lens_r * 2.5
            text = capsule(x, y, text_x, mid_y, text_x + 0.20, mid_y, 0.026, pixel)
            cursor = capsule(x, y, text_x + 0.245, mid_y - 0.036, text_x + 0.245, mid_y + 0.036, 0.020, pixel)
            mark = max(text, cursor)
            if mark > 0:
                out = over(out, (WHITE[0], WHITE[1], WHITE[2], mark * bar * 0.92))

    # Sonuç satırları
    if small:
        rows = [(0.50, 0.66, True), (0.72, 0.84, False)] if size > 16 else [(0.52, 0.80, True)]
    else:
        rows = [(0.45, 0.58, True), (0.63, 0.76, False), (0.81, 0.89, False)]
    for index, (top, bottom, selected) in enumerate(rows):
        if small:
            left, right = 0.17, 0.83
        else:
            left, right = 0.17, 0.83
        height = bottom - top
        if selected:
            row = fill_box(x, y, left, top, right, bottom, height * 0.30, pixel)
            if row > 0:
                out = over(out, (SELECTED[0], SELECTED[1], SELECTED[2], row))
                # Seçili satırın sol vurgu çubuğu
                if not small:
                    accent = capsule(x, y, left + 0.012, top + height * 0.22, left + 0.012, bottom - height * 0.22, 0.016, pixel)
                    out = over(out, (BAR_A[0], BAR_A[1], BAR_A[2], accent * row))
        mid = (top + bottom) / 2
        icon_size = height * (0.62 if not small else 0.64)
        icon_left = left + (0.045 if not small else 0.05)
        icon = fill_box(x, y, icon_left, mid - icon_size / 2, icon_left + icon_size, mid + icon_size / 2, icon_size * 0.28, pixel)
        color = BAR_A if selected else ROW_DIM
        if icon > 0:
            out = over(out, (color[0], color[1], color[2], icon * (1.0 if selected else 0.85)))
        text_left = icon_left + icon_size + 0.04
        widths = (0.36, 0.26, 0.30)
        text_right = text_left + widths[index % 3] * (0.85 if small else 1.0)
        text_color = ROW_TEXT if selected else ROW_DIM
        text_w = height * (0.26 if not small else 0.30)
        text = capsule(x, y, text_left, mid, text_right, mid, text_w, pixel)
        if text > 0:
            out = over(out, (text_color[0], text_color[1], text_color[2], text * (0.95 if selected else 0.8)))

    return out


def chunk(name, data):
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)


def png(size):
    # 2x2 süper örnekleme: pürüzsüz kenarlar
    offsets = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for ox, oy in offsets:
                r, g, b, a = color_at((x + ox) / size, (y + oy) / size, size)
                acc[0] += r * a
                acc[1] += g * a
                acc[2] += b * a
                acc[3] += a
            alpha = acc[3] / 4
            if alpha > 0:
                r, g, b = (acc[i] / acc[3] for i in range(3))
            else:
                r = g = b = 0.0
            raw.extend((max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b))), max(0, min(255, round(alpha * 255)))))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main():
    assets = Path(__file__).resolve().parent.parent / "assets"
    assets.mkdir(exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = [(size, png(size)) for size in sizes]
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, image in images:
        dimension = 0 if size == 256 else size
        directory.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    (assets / "icon.ico").write_bytes(bytes(directory) + b"".join(image for _, image in images))
    (assets / "icon.png").write_bytes(dict(images)[128])
    (assets / "icon_preview.png").write_bytes(dict(images)[256])
    print("Uygulama simgeleri hazır.")


if __name__ == "__main__":
    main()
