"""🧭 Coordinate Convention — หัวใจของระบบแปรอักษร (กันภาพกลับด้าน).

เทสต์พิสูจน์:
- 33×9 × 5×5 = 165×45 = 7,425 พิกเซล
- ทั้ง 4 ทิศทาง (row×col direction) แปลงพิกัดถูก + round-trip ไม่เพี้ยน
- ป้ายแถว A–I / ที่นั่ง 1–33 (1-based) + 0-based ภายใน
- blocked seats + extract_plate + validate_grid + crop/pad
"""
import pytest

from core.exceptions import ValidationError
from core.grid import (
    StandGeometry, cell_to_seat, crop_or_pad_grid, extract_plate, is_blocked,
    seat_base, seat_cells, seat_labels, validate_blocked_seats, validate_grid,
)

G = StandGeometry(rows=9, cols=33, sub_rows=5, sub_cols=5)  # 165×45


def test_dimensions():
    assert G.grid_width == 165
    assert G.grid_height == 45
    assert G.total_cells == 7425


def test_seat_0_0_default_directions():
    # default bottom_to_top + left_to_right: seat (0,0) อยู่ล่างซ้ายของ viewer
    # → base_r = (9-1-0)*5 = 40, base_c = 0
    assert seat_base(0, 0, G) == (40, 0)
    assert seat_base(8, 32, G) == (0, 160)  # มุมบนขวา


@pytest.mark.parametrize("row_dir,col_dir,exp_00,exp_88", [
    ("bottom_to_top", "left_to_right", (40, 0), (0, 160)),
    ("bottom_to_top", "right_to_left", (40, 160), (0, 0)),
    ("top_to_bottom", "left_to_right", (0, 0), (40, 160)),
    ("top_to_bottom", "right_to_left", (0, 160), (40, 0)),
])
def test_four_directions(row_dir, col_dir, exp_00, exp_88):
    g = StandGeometry(rows=9, cols=33, sub_rows=5, sub_cols=5,
                      row_direction=row_dir, col_direction=col_dir)
    assert seat_base(0, 0, g) == exp_00
    assert seat_base(8, 32, g) == exp_88


@pytest.mark.parametrize("row_dir,col_dir", [
    ("bottom_to_top", "left_to_right"),
    ("bottom_to_top", "right_to_left"),
    ("top_to_bottom", "left_to_right"),
    ("top_to_bottom", "right_to_left"),
])
def test_round_trip_no_mirror(row_dir, col_dir):
    g = StandGeometry(rows=9, cols=33, sub_rows=5, sub_cols=5,
                      row_direction=row_dir, col_direction=col_dir)
    for seat_row in (0, 4, 8):
        for seat_col in (0, 16, 32):
            for gr, gc in seat_cells(seat_row, seat_col, g):
                assert cell_to_seat(gr, gc, g) == (seat_row, seat_col, gr % 5, gc % 5)


def test_plate_extraction_contains_marker_only_once():
    g = StandGeometry(rows=9, cols=33, sub_rows=5, sub_cols=5,
                      row_direction="bottom_to_top", col_direction="left_to_right")
    grid = [None] * (165 * 45)
    # วาง marker ที่ช่อง (4, 4) ของที่นั่ง (0,0) → base (40,0) → index (40+4)*165 + 4
    grid[(40 + 4) * 165 + 4] = 777
    plate = extract_plate(grid, g, 0, 0)
    assert plate[4][4] == 777
    # marker ไม่อยู่ในเพลทข้างเคียง (ที่นั่ง (0,1))
    assert extract_plate(grid, g, 0, 1)[4][4] is None


def test_plate_size_1x1():
    g = StandGeometry(rows=2, cols=2, sub_rows=1, sub_cols=1, row_direction="top_to_bottom")
    grid = [1, 2, 3, 4]  # 2x2
    assert extract_plate(grid, g, 0, 0) == [[1]]
    assert extract_plate(grid, g, 1, 0) == [[3]]


def test_labels():
    g = StandGeometry(rows=9, cols=33)
    assert seat_labels(0, 0, g, "alpha", "numeric") == ("A", "1")
    assert seat_labels(8, 32, g, "alpha", "numeric") == ("I", "33")
    assert seat_labels(26, 0, g, "alpha", "numeric")[0] == "AA"  # เกิน Z
    assert seat_labels(0, 0, g, "numeric", "numeric") == ("1", "1")
    assert seat_labels(0, 0, StandGeometry(rows=1, cols=1), "alpha", "numeric",
                       row_prefix="แถว", col_prefix="นั่ง") == ("แถวA", "นั่ง1")


def test_blocked_seats():
    g = StandGeometry(rows=9, cols=33)
    validate_blocked_seats([{"row": 0, "col": 0}], g)
    with pytest.raises(ValidationError):
        validate_blocked_seats([{"row": 99, "col": 0}], g)
    assert is_blocked(0, 0, [{"row": 0, "col": 0}])
    assert not is_blocked(1, 0, [{"row": 0, "col": 0}])


def test_validate_grid():
    g = StandGeometry(rows=9, cols=33)
    validate_grid([None] * 7425, 165, 45, [1, 2, 3], 200000)
    with pytest.raises(ValidationError):
        validate_grid([None] * 7424, 165, 45, [1], 200000)  # ยาวผิด
    with pytest.raises(ValidationError):
        validate_grid([999] * 7425, 165, 45, [1], 200000)  # สีไม่อยู่ใน palette
    with pytest.raises(ValidationError):
        validate_grid([], 165, 45, [], 200000)  # ต้องเป็น list ยาวถูก


def test_crop_or_pad():
    # 165×45 → 100×30 (crop ขวา/ล่าง) แล้วกลับ → top-left ไม่เสียหาย
    src = list(range(165 * 45))
    cropped = crop_or_pad_grid(src, 165, 45, 100, 30)
    assert len(cropped) == 100 * 30
    # top-left region ตรง
    assert cropped[0] == src[0]
    assert cropped[29 * 100 + 99] == src[29 * 165 + 99]
    # pad กลับเป็นใหญ่ขึ้น
    padded = crop_or_pad_grid(cropped, 100, 30, 165, 45)
    assert len(padded) == 165 * 45
    assert padded[29 * 165 + 99] == cropped[29 * 100 + 99]
    # ส่วนที่ pad เป็น None
    assert padded[30 * 165 + 0] is None
