"""
🧭 Coordinate Convention — แหล่งความจริงเดียวของการแปลงพิกัดแสตน ↔ พิกเซล

นี่คือหัวใจของระบบแปรอักษร (design report §6 + docs/rules/testing.md):
- แสตนจริง = `cols` คอลัมน์ × `rows` แถว (default 33×9 = 297 ที่นั่ง)
- แต่ละคนถือเพลท `sub_rows × sub_cols` (default 5×5 = 25 พิกเซล)
- กริดรวม = `grid_width × grid_height` = (cols*sub_cols) × (rows*sub_rows) = 165×45 = 7,425
- `grid_data` เก็บแบบ **row-major flat array** ใน Audience View: `r=0` = แถว A (แถวล่างสุด
  เมื่อมองจากสนาม ถ้า row_direction=bottom_to_top) · `c=0` = ที่นั่ง 1 (ซ้ายสุด ถ้า left_to_right)
- พิกัดภายในเป็น **0-based** เสมอ · ป้าย (label) เป็น 1-based · API public รับ 1-based แล้วแปลง

ทิศทาง (กันภาพกลับด้าน — §1): `row_direction`/`col_direction` กำหนดว่าแถว/ที่นั่งของจริง
ถูกวาดที่มุมไหนของกริด viewer ⇒ เทสต์ต้องพิสูจน์ว่าไม่มีการสลับซ้ายขวา/บนล่างโดยไม่ตั้งใจ
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.exceptions import ValidationError

# ── geometry ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StandGeometry:
    rows: int
    cols: int
    sub_rows: int = 5
    sub_cols: int = 5
    row_direction: str = "bottom_to_top"
    col_direction: str = "left_to_right"

    @property
    def grid_width(self) -> int:
        return self.cols * self.sub_cols

    @property
    def grid_height(self) -> int:
        return self.rows * self.sub_rows

    @property
    def total_cells(self) -> int:
        return self.grid_width * self.grid_height


def validate_geometry(g: StandGeometry, max_total_cells: int) -> None:
    """ตรวจช่วงค่า + เพดานจำนวนช่อง — ใช้ก่อน insert/update stand และก่อน validate grid."""
    if not (0 < g.rows and 0 < g.cols):
        raise ValidationError("rows/cols ต้องมากกว่า 0")
    if not (1 <= g.sub_rows <= 16 and 1 <= g.sub_cols <= 16):
        raise ValidationError("sub_rows/sub_cols ต้องอยู่ระหว่าง 1–16")
    if g.row_direction not in ("bottom_to_top", "top_to_bottom"):
        raise ValidationError("row_direction ไม่ถูกต้อง")
    if g.col_direction not in ("left_to_right", "right_to_left"):
        raise ValidationError("col_direction ไม่ถูกต้อง")
    if g.total_cells > max_total_cells:
        raise ValidationError(
            f"กริดรวม {g.total_cells} ช่อง เกินเพดาน {max_total_cells} (MAX_TOTAL_CELLS)"
        )


# ── แปลงพิกัดที่นั่ง → พิกเซล ────────────────────────────────────────

def seat_base(seat_row: int, seat_col: int, g: StandGeometry) -> Tuple[int, int]:
    """มุมบนซ้าย (grid_r, grid_c) ของเพลทของที่นั่งนั้น ในกริด viewer (0-based)."""
    if not (0 <= seat_row < g.rows and 0 <= seat_col < g.cols):
        raise ValidationError("พิกัดที่นั่งอยู่นอกแสตน")
    if g.row_direction == "bottom_to_top":
        base_r = (g.rows - 1 - seat_row) * g.sub_rows
    else:
        base_r = seat_row * g.sub_rows
    if g.col_direction == "left_to_right":
        base_c = seat_col * g.sub_cols
    else:
        base_c = (g.cols - 1 - seat_col) * g.sub_cols
    return base_r, base_c


def seat_cells(seat_row: int, seat_col: int, g: StandGeometry) -> List[Tuple[int, int]]:
    """พิกัด (grid_r, grid_c) ทั้งหมดในเพลทของที่นั่ง (เรียง row-major)."""
    base_r, base_c = seat_base(seat_row, seat_col, g)
    cells = []
    for sr in range(g.sub_rows):
        for sc in range(g.sub_cols):
            cells.append((base_r + sr, base_c + sc))
    return cells


def cell_to_seat(grid_r: int, grid_c: int, g: StandGeometry) -> Tuple[int, int, int, int]:
    """แปลงพิกัด pixel กลับเป็น (seat_row, seat_col, sub_r, sub_c) — 0-based."""
    if not (0 <= grid_r < g.grid_height and 0 <= grid_c < g.grid_width):
        raise ValidationError("พิกัด pixel อยู่นอกกริด")
    if g.row_direction == "bottom_to_top":
        seat_row = g.rows - 1 - (grid_r // g.sub_rows)
    else:
        seat_row = grid_r // g.sub_rows
    if g.col_direction == "left_to_right":
        seat_col = grid_c // g.sub_cols
    else:
        seat_col = g.cols - 1 - (grid_c // g.sub_cols)
    sub_r = grid_r % g.sub_rows
    sub_c = grid_c % g.sub_cols
    return seat_row, seat_col, sub_r, sub_c


def extract_plate(
    grid_data: List[Optional[int]], g: StandGeometry, seat_row: int, seat_col: int
) -> List[List[Optional[int]]]:
    """ดึงเพลท 2 มิติ (sub_rows × sub_cols) ของที่นั่งนั้นจาก flat grid_data."""
    if len(grid_data) != g.grid_width * g.grid_height:
        raise ValidationError("ความยาว grid_data ไม่ตรงกับขนาดกริด")
    plate = []
    for sr in range(g.sub_rows):
        row = []
        for sc in range(g.sub_cols):
            gr, gc = (seat_base(seat_row, seat_col, g)[0] + sr, seat_base(seat_row, seat_col, g)[1] + sc)
            row.append(grid_data[gr * g.grid_width + gc])
        plate.append(row)
    return plate


# ── ป้าย (label) — 1-based ──────────────────────────────────────────

def _alpha(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA, ..."""
    s = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        s = chr(ord('A') + rem) + s
    return s


def seat_labels(seat_row: int, seat_col: int, g: StandGeometry,
                row_style: str = "alpha", col_style: str = "numeric",
                row_prefix: str = "", col_prefix: str = "") -> Tuple[str, str]:
    """ป้ายแถว/ที่นั่งแบบ 1-based — 'alpha' = A..Z,AA.. · 'numeric' = 1,2,3..."""
    if row_style == "alpha":
        row_label = row_prefix + _alpha(seat_row)
    else:
        row_label = row_prefix + str(seat_row + 1)
    if col_style == "alpha":
        col_label = col_prefix + _alpha(seat_col)
    else:
        col_label = col_prefix + str(seat_col + 1)
    return row_label, col_label


# ── blocked seats ───────────────────────────────────────────────────

def normalize_blocked(blocked) -> List[Tuple[int, int]]:
    """รับ list ของ {'row':r,'col':c} หรือ {'r':r,'c':c} → เซต (row, col) 0-based."""
    out = set()
    for item in blocked or []:
        r = item.get("row", item.get("r"))
        c = item.get("col", item.get("c"))
        if r is None or c is None:
            raise ValidationError("blocked_seats แต่ละรายการต้องมี row/col")
        out.add((int(r), int(c)))
    return sorted(out)


def validate_blocked_seats(blocked, g: StandGeometry) -> None:
    for r, c in normalize_blocked(blocked):
        if not (0 <= r < g.rows and 0 <= c < g.cols):
            raise ValidationError(f"blocked seat อยู่นอกแสตน: ({r},{c})")


def is_blocked(seat_row: int, seat_col: int, blocked) -> bool:
    return (seat_row, seat_col) in normalize_blocked(blocked)


# ── grid validation + resize ────────────────────────────────────────

def validate_grid(grid_data, grid_width: int, grid_height: int,
                  allowed_color_ids, max_total_cells: int) -> None:
    """ตรวจว่า flat grid ยาวถูกต้อง และทุกค่าอยู่ใน palette (หรือ null)."""
    if not isinstance(grid_data, list):
        raise ValidationError("grid_data ต้องเป็น array")
    if grid_width * grid_height > max_total_cells:
        raise ValidationError("กริดเกินเพดาน MAX_TOTAL_CELLS")
    if len(grid_data) != grid_width * grid_height:
        raise ValidationError(
            f"grid_data ยาว {len(grid_data)} แต่ควรเป็น {grid_width * grid_height}"
        )
    allowed = set(allowed_color_ids or [])
    for v in grid_data:
        if v is not None and int(v) not in allowed:
            raise ValidationError(f"grid_data มีสี {v} ที่ไม่อยู่ใน palette")


def crop_or_pad_grid(grid_data: list, old_w: int, old_h: int, new_w: int, new_h: int) -> list:
    """ปรับขนาด flat grid แบบ audience top-left anchor: crop ขวา/ล่าง, pad ด้วย null."""
    out = []
    for r in range(new_h):
        for c in range(new_w):
            if r < old_h and c < old_w:
                out.append(grid_data[r * old_w + c])
            else:
                out.append(None)
    return out
