"""
📄 Export builders — PDF (โพยรายที่นั่ง) · CSV (ตารางรวม) · ZIP (ภาพกริดทุกฉาก)

ทั้งหมดเป็น **pure functions**: รับแถวข้อมูลธรรมดา (dict) และคืน `bytes`
⇒ service/worker ทำหน้าที่แค่ query + เขียนไฟล์ · เทสต์ได้โดยไม่ต้องมี DB/Redis

PDF ใช้ Pillow วาดเป็นภาพ A4 (150 DPI) แล้วรวมเป็น PDF แทน reportlab เพราะ:
- ข้อความไทยต้องผ่าน text shaping (Raqm) — reportlab ไม่ทำ GPOS ให้สระ/วรรณยุกต์ซ้อนถูกตำแหน่ง
- Pillow binary wheel มี Raqm ฝังมาแล้ว (`PIL.features.check("raqm")`)
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.grid import StandGeometry, extract_plate, normalize_blocked, seat_labels

# ── palette / colors ────────────────────────────────────────────────

WHITE = (255, 255, 255)
INK = (31, 35, 40)
MUTED = (95, 99, 104)
LINE = (231, 231, 234)
CANVAS = (247, 247, 248)
EMPTY_CELL = (226, 232, 240)

# A4 ที่ 150 DPI — Pillow PDF plugin ใช้ `resolution` แปลง px → pt
PAGE_W, PAGE_H = 1240, 1754
DPI = 150
MARGIN = 44
GAP = 22


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return value


def _rgb(hex_color: str | None, fallback=WHITE) -> tuple[int, int, int]:
    raw = (hex_color or "").lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _color_map(palettes: list[dict]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for palette in palettes:
        for color in palette.get("colors") or []:
            out[int(color["id"])] = color
    return out


def _geometry(stand: dict) -> StandGeometry:
    return StandGeometry(
        rows=int(stand["rows"]), cols=int(stand["cols"]),
        sub_rows=int(stand["sub_rows"]), sub_cols=int(stand["sub_cols"]),
        row_direction=stand.get("row_direction", "bottom_to_top"),
        col_direction=stand.get("col_direction", "left_to_right"),
    )


def _plate(grid: list, g: StandGeometry, r: int, c: int):
    if len(grid) != g.grid_width * g.grid_height:
        return None
    return extract_plate(grid, g, r, c)


def _distinct(plate) -> list[int]:
    if not plate:
        return []
    seen: list[int] = []
    for row in plate:
        for cell in row:
            if cell is not None and int(cell) not in seen:
                seen.append(int(cell))
    return seen


# ── seat records ────────────────────────────────────────────────────

def seat_records(event: dict, stands: list[dict], palettes: list[dict],
                 stunts: list[dict], rosters: list[dict]) -> list[dict]:
    """แตกทุกที่นั่งของทุก stand เป็นแถวเดียวต่อที่นั่ง พร้อมเพลทของทุกฉาก.

    `stand.blocked_seats` (ช่องบันได/ทางเดิน) ถูกข้าม — ไม่มีนักเรียนนั่งตรงนั้น
    """
    colors = _color_map(palettes)
    roster_index = {
        (int(r["stand_id"]), int(r["row_index"]), int(r["col_index"])): r
        for r in rosters
    }
    stunts_by_stand: dict[int, list[dict]] = {}
    for stunt in stunts:
        stunts_by_stand.setdefault(int(stunt["stand_id"]), []).append(stunt)

    records: list[dict] = []
    for stand in stands:
        g = _geometry(stand)
        blocked = set(normalize_blocked(_as_list(stand.get("blocked_seats"))))
        for r in range(g.rows):
            for c in range(g.cols):
                if (r, c) in blocked:
                    continue
                row_label, seat_label = seat_labels(
                    r, c, g,
                    stand.get("row_label_style", "alpha"), stand.get("col_label_style", "numeric"),
                    stand.get("row_label_prefix", ""), stand.get("col_label_prefix", ""),
                )
                student = roster_index.get((int(stand["id"]), r, c))
                cues = []
                for stunt in stunts_by_stand.get(int(stand["id"]), []):
                    grid = _as_list(stunt.get("grid_data"))
                    cues.append({
                        "stunt_id": stunt["id"],
                        "code": stunt["code"],
                        "title": stunt["title"],
                        "notes": stunt.get("notes"),
                        "side": stunt.get("side", "A"),
                        "plate": _plate(grid, g, r, c),
                    })
                records.append({
                    "event_name": event["name"],
                    "event_date": event.get("event_date"),
                    "stand_id": int(stand["id"]),
                    "stand_name": stand["name"],
                    "row_index": r,
                    "col_index": c,
                    "sub_rows": g.sub_rows,
                    "sub_cols": g.sub_cols,
                    "row_label": row_label,
                    "seat_label": seat_label,
                    "student_code": (student or {}).get("student_code"),
                    "student_name": (student or {}).get("student_name"),
                    "access_code": (student or {}).get("access_code"),
                    "cues": cues,
                })
    return records


# ── CSV ─────────────────────────────────────────────────────────────

CSV_HEADER = [
    "stand", "row", "seat", "row_index", "col_index",
    "student_code", "student_name", "access_code",
    "stunt_code", "stunt_title", "side", "sub_grid_codes", "notes",
]


def _plate_codes(plate, colors: dict[int, dict]) -> str:
    if not plate:
        return ""
    out = []
    for row in plate:
        for cell in row:
            if cell is None:
                out.append("-")
            else:
                color = colors.get(int(cell))
                out.append(color["code"] if color else str(cell))
    return " ".join(out)


def _distinct_codes(plate, colors: dict[int, dict]) -> str:
    codes = []
    for cid in _distinct(plate):
        color = colors.get(cid)
        if color:
            codes.append(f"{color['code']} {color['name_th']}")
    return " · ".join(codes)


def build_csv(records: list[dict], palettes: list[dict]) -> bytes:
    colors = _color_map(palettes)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for rec in records:
        base = [
            rec["stand_name"], rec["row_label"], rec["seat_label"],
            # index เป็น 0-based (ตรงกับ DB/API) — label ด้านบนเป็น 1-based ตามป้ายแสตน
            rec["row_index"], rec["col_index"],
            rec["student_code"] or "", rec["student_name"] or "", rec.get("access_code") or "",
        ]
        for cue in rec["cues"]:
            writer.writerow(base + [
                cue["code"], cue["title"], cue["side"],
                _plate_codes(cue["plate"], colors), cue.get("notes") or "",
            ])
        if not rec["cues"]:
            writer.writerow(base + ["", "", "", "", ""])
    # BOM — ให้ Excel เปิดภาษาไทย/UTF-8 ถูกต้องโดยไม่ต้อง import wizard
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ── fonts ───────────────────────────────────────────────────────────

_FONT_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansThai.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
_font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _font(size: int):
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            try:
                font = ImageFont.truetype(str(candidate), size=size)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> str:
    """ตัดข้อความ (ใส่ …) ให้พอดีความกว้าง — ข้อความไทยตัดกลาง clustered mark ได้บ้าง แต่พอดีกว่า overflow."""
    text = text or ""
    if max_width <= 0 or draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textlength(text[:mid] + ellipsis, font=font) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ellipsis) if lo else ellipsis


# ── PDF ─────────────────────────────────────────────────────────────

def _draw_mini_grid(draw, plate, colors, x: int, y: int, cell: int, label: str | None = None):
    if not plate:
        return 0, 0
    rows, cols = len(plate), len(plate[0]) if plate else 0
    if label:
        draw.text((x, y), label, font=_font(11), fill=MUTED)
        y += 14
    cell_font = _font(max(7, min(11, cell - 3)))
    for r in range(rows):
        for c in range(cols):
            value = plate[r][c]
            color = colors.get(int(value)) if value is not None else None
            fill = _rgb(color["hex"]) if color else EMPTY_CELL
            x0, y0 = x + c * cell, y + r * cell
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=fill, outline=WHITE)
            if color and cell >= 13:
                text_color = _rgb(color.get("text_color"), INK)
                code = str(color["code"])[:2]
                draw.text((x0 + cell / 2, y0 + cell / 2), code,
                          font=cell_font, fill=text_color, anchor="mm")
    return cols * cell, rows * cell + (14 if label else 0)


def _draw_cue(draw, cue: dict, colors: dict[int, dict], x: int, y: int, w: int, h: int) -> None:
    # รหัสฉาก + ชื่อ
    draw.text((x, y), f"{cue['code']}", font=_font(15), fill=INK)
    code_w = draw.textlength(f"{cue['code']} ", font=_font(15))
    title = _fit_text(draw, cue["title"], _font(14), w - code_w)
    draw.text((x + code_w, y + 1), title, font=_font(14), fill=MUTED)

    gy = y + 24
    cell = max(8, min(13, int((h - 30) / 5)))
    used_w = 0
    if cue["plate"]:
        gw, _ = _draw_mini_grid(draw, cue["plate"], colors, x, gy, cell, cue["side"])
        used_w = gw

    # รายชื่อสีที่ต้องใช้ (ไม่เกิน 4 สี)
    codes = _distinct_codes(cue["plate"], colors) or "—"
    more = _distinct(cue["plate"])
    if len(more) > 4:
        shown = " · ".join(
            f"{colors[c]['code']} {colors[c]['name_th']}" for c in more[:4] if c in colors
        )
        codes = f"{shown} +{len(more) - 4}"
    draw.text((x + used_w + 16, gy + 6),
              _fit_text(draw, codes, _font(11), max(20, w - used_w - 16)),
              font=_font(11), fill=MUTED)


def _draw_card(draw, box, rec: dict, colors: dict[int, dict]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=20, fill=WHITE, outline=LINE, width=2)

    # หัวการ์ด
    draw.text((x0 + 24, y0 + 18), rec["seat_label"], font=_font(40), fill=INK)
    seat_w = draw.textlength(rec["seat_label"], font=_font(40))
    draw.text((x0 + 30 + seat_w, y0 + 32), f"แถว {rec['row_label']}",
              font=_font(15), fill=MUTED)

    student = rec["student_name"] or "—"
    if rec["student_code"]:
        student = f"{student} · {rec['student_code']}"
    draw.text((x0 + 24, y0 + 70), _fit_text(draw, student, _font(14), x1 - x0 - 48),
              font=_font(14), fill=INK)

    # รหัสล็อกอิน (พิมพ์แจกนักเรียน) — มุมบนขวาของการ์ด
    if rec.get("access_code"):
        label = "รหัสล็อกอิน"
        lw = draw.textlength(label, font=_font(12))
        draw.text((x1 - 24 - lw, y0 + 22), label, font=_font(12), fill=MUTED)
        acw = draw.textlength(rec["access_code"], font=_font(26))
        draw.text((x1 - 24 - acw, y0 + 38), rec["access_code"], font=_font(26), fill=INK)

    draw.line([x0 + 24, y0 + 98, x1 - 24, y0 + 98], fill=LINE, width=2)

    cues = rec["cues"]
    if not cues:
        draw.text((x0 + 24, y0 + 120), "ยังไม่มีฉากที่เผยแพร่", font=_font(14), fill=MUTED)
        return

    inner_x, inner_y = x0 + 24, y0 + 112
    inner_w, inner_h = (x1 - x0) - 48, (y1 - y0) - 136
    columns = 2 if len(cues) > 3 else 1
    per_col = (len(cues) + columns - 1) // columns
    col_w = (inner_w - (columns - 1) * 20) / columns
    item_h = min(112, inner_h / max(per_col, 1))

    for idx, cue in enumerate(cues):
        col = idx // per_col
        row = idx % per_col
        _draw_cue(draw, cue, colors, int(inner_x + col * (col_w + 20)),
                  int(inner_y + row * item_h), int(col_w), int(item_h - 6))


def build_pdf(event: dict, records: list[dict], palettes: list[dict]) -> bytes:
    colors = _color_map(palettes)
    cards_per_page = 4
    pages: list[Image.Image] = []

    # แบ่งที่นั่งตาม stand เพื่อขึ้นหัวการ์ดถูกแสตน
    groups: dict[int, list[dict]] = {}
    for rec in records:
        groups.setdefault(rec["stand_id"], []).append(rec)
    ordered = [rec for group in groups.values() for rec in group]

    if not ordered:
        ordered = []  # ยังไม่มีที่นั่ง — สร้างหน้าปกเปล่า

    card_w = (PAGE_W - MARGIN * 2 - GAP) / 2
    card_h = (PAGE_H - MARGIN * 2 - GAP) / 2

    total_pages = max(1, (len(ordered) + cards_per_page - 1) // cards_per_page)
    for page_no in range(total_pages):
        page = Image.new("RGB", (PAGE_W, PAGE_H), CANVAS)
        draw = ImageDraw.Draw(page)
        title = f"โพยรายที่นั่ง · {event['name']}"
        draw.text((MARGIN, 16), _fit_text(draw, title, _font(18), PAGE_W - MARGIN * 2 - 120),
                  font=_font(18), fill=INK)
        draw.text((PAGE_W - MARGIN - 90, 18), f"หน้า {page_no + 1}/{total_pages}",
                  font=_font(12), fill=MUTED)

        chunk = ordered[page_no * cards_per_page:(page_no + 1) * cards_per_page]
        if not chunk:
            draw.text((PAGE_W / 2, PAGE_H / 2), "ยังไม่มีที่นั่ง/รายชื่อให้ export",
                      font=_font(22), fill=MUTED, anchor="mm")
        for i, rec in enumerate(chunk):
            col, row = i % 2, i // 2
            x0 = MARGIN + col * (card_w + GAP)
            y0 = MARGIN + row * (card_h + GAP)
            _draw_card(draw, (x0, y0, x0 + card_w, y0 + card_h), rec, colors)

        # legend สีล่างหน้า (เฉพาะสีที่ใช้จริงในหน้านี้)
        used: list[int] = []
        for rec in chunk:
            for cue in rec["cues"]:
                for cid in _distinct(cue["plate"]):
                    if cid not in used:
                        used.append(cid)
        if used:
            lx, ly = MARGIN, PAGE_H - MARGIN + 6
            for cid in used[:14]:
                color = colors.get(cid)
                if not color:
                    continue
                draw.rectangle([lx, ly + 4, lx + 14, ly + 18], fill=_rgb(color["hex"]), outline=LINE)
                label = f"{color['code']} {color['name_th']}"
                draw.text((lx + 20, ly), _fit_text(draw, label, _font(11), 150), font=_font(11), fill=MUTED)
                lx += 20 + min(150, draw.textlength(label, font=_font(11))) + 26

        pages.append(page)

    out = io.BytesIO()
    pages[0].save(
        out, format="PDF", save_all=True, append_images=pages[1:],
        resolution=DPI, quality=88,
    )
    return out.getvalue()


# ── ZIP ─────────────────────────────────────────────────────────────

def _safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zก-๙._-]+", "-", text or "").strip("-")
    return cleaned or "stunt"


def _render_grid_png(stunt: dict, g: StandGeometry, colors: dict[int, dict], scale: int) -> bytes:
    width, height = g.grid_width, g.grid_height
    img = Image.new("RGB", (width * scale, height * scale), EMPTY_CELL)
    draw = ImageDraw.Draw(img)
    grid = _as_list(stunt.get("grid_data"))
    if len(grid) == width * height:
        for r in range(height):
            for c in range(width):
                value = grid[r * width + c]
                if value is None:
                    continue
                color = colors.get(int(value))
                if not color:
                    continue
                x0, y0 = c * scale, r * scale
                draw.rectangle([x0, y0, x0 + scale - 1, y0 + scale - 1], fill=_rgb(color["hex"]))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def build_zip(event: dict, stands: list[dict], palettes: list[dict],
              stunts: list[dict], records: list[dict]) -> bytes:
    colors = _color_map(palettes)
    geom_by_stand = {int(s["id"]): _geometry(s) for s in stands}
    buf = io.BytesIO()

    manifest = {
        "event": {"slug": event.get("slug"), "name": event["name"],
                  "event_date": str(event.get("event_date") or "")},
        "generated": str(date.today()),
        "files": [],
        "colors": [
            {"id": cid, "code": c["code"], "name_th": c["name_th"], "hex": c["hex"]}
            for cid, c in sorted(colors.items())
        ],
    }

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, stunt in enumerate(stunts, start=1):
            g = geom_by_stand.get(int(stunt["stand_id"]))
            if not g:
                continue
            scale = max(2, min(12, 1800 // max(1, g.grid_width)))
            code = _safe_filename(stunt["code"])

            side = str(stunt.get("side", "A")).lower()
            name = f"stunts/{index:02d}-{code}-{side}.png"
            zf.writestr(name, _render_grid_png(stunt, g, colors, scale))
            manifest["files"].append({
                "file": name, "code": stunt["code"], "title": stunt["title"],
                "side": side, "order_index": stunt.get("order_index", 0),
            })

        zf.writestr("seats.csv", build_csv(records, palettes))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        zf.writestr("README.txt", (
            f"Pixel Stand — {event['name']}\n"
            f"สร้างเมื่อ {date.today().isoformat()}\n\n"
            "stunts/*.png = ภาพกริดเต็มของแต่ละฉาก (ตามด้าน A/B)\n"
            "seats.csv   = ตารางรวมรายที่นั่ง (ด้าน, รหัสสีทุกช่อง, รหัสล็อกอิน)\n"
            "manifest.json = ลำดับฉาก + รายการสี\n"
        ).encode("utf-8"))

    return buf.getvalue()
