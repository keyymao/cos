#!/usr/bin/env python3
"""Дорабатывает отчёт ЛР №6 (вариант 12 / зачётка 06).

Скрипт создаёт отдельную исправленную копию, не изменяя загруженный DOCX:

1. рассчитывает фактические границы ПП/ПЗ по уровням 0,95 и 0,01;
2. размечает экспериментальную АЧХ цветными областями и границами;
3. учитывает, что скриншот «Спектр-2» снят при Fд ≈ 48 кГц, тогда как
   домашний расчёт выполнен для Fд = 10600 Гц;
4. добавляет лабораторные задания №3 и №4 с таблицами сравнения;
5. уточняет подписи экспериментальных ИХ и АЧХ и дополняет вывод.

Зависимости: numpy scipy pillow python-docx.
"""

from __future__ import annotations

import io
import json
import math
import shutil
from hashlib import sha256
import tempfile
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import brentq
from scipy.signal import freqz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба6"
CORRECTED_DIR = ROOT / "лабораторные" / "исправленые" / "лаба6"
SOURCE_REPORT = CURRENT_DIR / "Лабораторная_работа_№6_вариант_12,_зачётка_06_1.docx"
OUTPUT_REPORT = CORRECTED_DIR / "Лабораторная работа №6 (вариант 12, зачётка 06) — исправленная.docx"
ANNOTATED_PNG = CORRECTED_DIR / "АЧХ — ЛР6 вариант 12 с отметками ПП и ПЗ.png"
DATA_FILE = HERE / "variant_data_lab6.json"

# ---------------------------------------------------------------------------
# Расчётные контрольные точки
# ---------------------------------------------------------------------------

DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
FD = float(DATA["Fd"])                  # 10600 Гц
F1 = float(DATA["F1"])                  # 2520 Гц, граница ПП по ТЗ
F3 = float(DATA["F3"])                  # 1005 Гц, граница ПЗ по ТЗ
FC = float(DATA["Fc"])                  # 1762,5 Гц
B = np.array([item["b"] for item in DATA["coefficients"]], dtype=float)
PASS_LEVEL = 1.0 - float(DATA["delta1"])  # 0,95
STOP_LEVEL = float(DATA["delta2"])        # 0,01


def magnitude(frequency: float | np.ndarray) -> float | np.ndarray:
    """Возвращает |H(f)| по коэффициентам фильтра."""
    w = 2.0 * np.pi * np.asarray(frequency, dtype=float) / FD
    values = np.abs(freqz(B, worN=np.atleast_1d(w))[1])
    return values[0] if values.size == 1 and np.ndim(frequency) == 0 else values


def crossing(level: float, left: float, right: float) -> float:
    return float(brentq(lambda value: float(magnitude(value)) - level, left, right))


F_STOP_REAL = crossing(STOP_LEVEL, 900.0, 1150.0)       # 1007,12 Гц
F_CUTOFF_REAL = crossing(0.5, 1600.0, 1900.0)           # 1762,19 Гц
F_PASS_REAL = crossing(PASS_LEVEL, 2200.0, 2500.0)      # 2360,48 Гц
H_AT_F3 = float(magnitude(F3))
H_AT_F1 = float(magnitude(F1))
H_AT_FC = float(magnitude(FC))
A_AT_F3 = -20.0 * math.log10(H_AT_F3)
A_AT_F1 = -20.0 * math.log10(H_AT_F1)
A_AT_FC = -20.0 * math.log10(H_AT_FC)
STOP_MAX = float(DATA["check"]["stop_max"])
STOP_MAX_F = float(DATA["check"]["stop_max_frequency"])
PASS_MIN = float(DATA["check"]["pass_min"])
PASS_MAX = float(DATA["check"]["pass_max"])
PASS_MAX_F = float(DATA["check"]["pass_max_frequency"])
TRANSITION_SPEC = F1 - F3
TRANSITION_REAL = F_PASS_REAL - F_STOP_REAL
TRANSITION_MARGIN = TRANSITION_SPEC - TRANSITION_REAL
GROUP_DELAY_MS = float(DATA["group_delay"]) / FD * 1000.0
SUM_B = float(np.sum(B))
ALT_SUM_B = float(np.sum(B * (-1.0) ** np.arange(B.size)))

# Для текста отчёта график читается примерно до 10 Гц.
F_STOP_TXT = round(F_STOP_REAL, -1)      # 1010 Гц
F_PASS_TXT = round(F_PASS_REAL, -1)      # 2360 Гц
D_STOP_TXT = round(F_STOP_REAL - F3)     # +2 Гц
D_PASS_TXT = round(F_PASS_REAL - F1)     # −160 Гц


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Привязка экспериментального скриншота к частотной оси
# ---------------------------------------------------------------------------

# На скриншоте зелёный курсор показывает 11,086 кГц на x = 945. Форма АЧХ,
# положения трёх нулей и частота среза совпадают с расчётной характеристикой
# после масштабирования частот в 48000/10600 раз. Значит, модель «Спектр-2»
# была запущена примерно при 48 кГц вместо требуемых 10600 Гц.
SCREEN_FD = 48000.0
SCREEN_SCALE = SCREEN_FD / FD
SCREEN_CURSOR_HZ = 11086.0
SCREEN_CURSOR_X = 945
SCREEN_X_RIGHT = 1247
SCREEN_VISIBLE_RIGHT_HZ = SCREEN_X_RIGHT / SCREEN_CURSOR_X * SCREEN_CURSOR_HZ
DESIGN_VISIBLE_RIGHT_HZ = SCREEN_VISIBLE_RIGHT_HZ / SCREEN_SCALE

Y_TOP = 31
Y_BOT = 882
Y_REF = 250.04              # максимум АЧХ в ПП по аппроксимации границы заливки
PX_PER_DB = 5.868            # большая клетка 10 дБ ≈ 58,68 пикселя

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
GRAY = (75, 85, 95, 255)
DARK = (30, 40, 50, 255)
WHITE = (255, 255, 255, 242)


def screen_frequency(design_frequency: float) -> float:
    """Частота расчёта -> частота, отображённая на ошибочной шкале скриншота."""
    return design_frequency * SCREEN_SCALE


def fx(design_frequency: float) -> int:
    raw = screen_frequency(design_frequency)
    return round(raw / SCREEN_CURSOR_HZ * SCREEN_CURSOR_X)


def dy(attenuation_db: float) -> int:
    return round(Y_REF + attenuation_db * PX_PER_DB)


X_F3 = fx(F3)
X_F1 = fx(F1)
X_FC = fx(FC)
X_F_STOP_REAL = fx(F_STOP_REAL)
X_F_PASS_REAL = fx(F_PASS_REAL)
Y_095 = dy(-20.0 * math.log10(PASS_LEVEL))
Y_105 = dy(-20.0 * math.log10(1.0 + DATA["delta1"]))
Y_40 = dy(40.0)
Y_F3_CURVE = dy(A_AT_F3)
Y_F1_CURVE = dy(A_AT_F1)
Y_FC_CURVE = dy(A_AT_FC)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    try:
        return ImageFont.truetype(name, size=size)
    except OSError:
        return ImageFont.load_default()


def dashed_line(draw, xy, *, fill, width=4, dash=18, gap=10):
    x1, y1, x2, y2 = xy
    if abs(x2 - x1) >= abs(y2 - y1):
        start, end = sorted((x1, x2))
        x = start
        while x < end:
            draw.line((x, y1, min(x + dash, end), y2), fill=fill, width=width)
            x += dash + gap
    else:
        start, end = sorted((y1, y2))
        y = start
        while y < end:
            draw.line((x1, y, x2, min(y + dash, end)), fill=fill, width=width)
            y += dash + gap


def label_box(draw, position, text, *, color, text_font, padding=10, align="left"):
    x, y = position
    bbox = draw.multiline_textbbox((x, y), text, font=text_font, spacing=6, align=align)
    box = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)
    draw.rounded_rectangle(box, radius=10, fill=WHITE, outline=color, width=3)
    draw.multiline_text((x, y), text, font=text_font, fill=color, spacing=6, align=align)
    return box


def connector(draw, start, end, *, color, width=3):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y1, x2, y2), fill=color, width=width)


def marker(draw, x, y, color, radius=8):
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=WHITE,
        outline=color,
        width=4,
    )


def double_arrow(draw, x1, x2, y, *, color, width=3, head=12):
    draw.line((x1, y, x2, y), fill=color, width=width)
    draw.polygon(((x1, y), (x1 + head, y - head // 2), (x1 + head, y + head // 2)), fill=color)
    draw.polygon(((x2, y), (x2 - head, y - head // 2), (x2 - head, y + head // 2)), fill=color)


def mark_amplitude_response(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    if image.size != (1248, 883):
        raise RuntimeError(f"Неожиданный размер скриншота АЧХ: {image.size}")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Полосы по техническому заданию: для ФВЧ ПЗ слева, ПП справа.
    draw.rectangle((0, Y_TOP, X_F3, Y_BOT), fill=(198, 40, 40, 43))
    draw.rectangle((X_F1, Y_TOP, SCREEN_X_RIGHT, Y_BOT), fill=(0, 92, 184, 46))
    draw.rectangle((X_F3, Y_TOP, X_F1, Y_BOT), fill=(75, 85, 95, 20))
    draw.rectangle((0, Y_40, X_F3, Y_BOT), fill=(198, 40, 40, 42))
    draw.rectangle((X_F1, Y_105, SCREEN_X_RIGHT, Y_095), fill=(0, 92, 184, 105))

    # Толстые пунктиры — заданные F₃/F₁; тонкие — фактические границы допусков.
    dashed_line(draw, (X_F3, Y_TOP, X_F3, Y_BOT), fill=RED, width=5)
    dashed_line(draw, (X_F1, Y_TOP, X_F1, Y_BOT), fill=BLUE, width=5)
    if abs(X_F_STOP_REAL - X_F3) > 2:
        dashed_line(draw, (X_F_STOP_REAL, Y_TOP, X_F_STOP_REAL, Y_BOT),
                    fill=RED, width=3, dash=12, gap=8)
    dashed_line(draw, (X_F_PASS_REAL, Y_TOP, X_F_PASS_REAL, Y_BOT),
                fill=BLUE, width=3, dash=12, gap=8)
    dashed_line(draw, (X_FC, Y_TOP, X_FC, Y_BOT),
                fill=GRAY, width=3, dash=12, gap=8)

    # Контрольные уровни относительно максимума АЧХ в ПП.
    dashed_line(draw, (0, Y_40, X_F_STOP_REAL, Y_40),
                fill=RED, width=4, dash=17, gap=10)
    dashed_line(draw, (X_F_PASS_REAL, Y_095, SCREEN_X_RIGHT, Y_095),
                fill=BLUE, width=4, dash=17, gap=10)

    marker(draw, X_F3, Y_F3_CURVE, RED, radius=7)
    marker(draw, X_F_STOP_REAL, Y_40, RED, radius=7)
    marker(draw, X_FC, Y_FC_CURVE, GRAY, radius=7)
    marker(draw, X_F_PASS_REAL, Y_095, BLUE, radius=7)
    marker(draw, X_F1, Y_F1_CURVE, BLUE, radius=7)

    f_band = font(21, bold=True)
    f_small = font(18, bold=True)
    f_note = font(16)

    label_box(
        draw,
        (18, 67),
        "ПЗ: 0…1005 Гц\n|H| ≤ 0,01  (a ≥ 40 дБ)",
        color=RED,
        text_font=f_band,
    )
    label_box(
        draw,
        (420, 67),
        "Переходная полоса\n1005…2520 Гц",
        color=GRAY,
        text_font=f_small,
    )
    label_box(
        draw,
        (945, 67),
        "ПП: f ≥ 2520 Гц\n0,95 ≤ |H| ≤ 1,05",
        color=BLUE,
        text_font=f_band,
    )
    double_arrow(draw, X_F3, X_F1, 175, color=GRAY)

    box_stop = label_box(
        draw,
        (64, 385),
        "f₃ ≈ 1007 Гц\nуровень 0,01\n(на экране ≈ 4,56 кГц)",
        color=RED,
        text_font=f_small,
    )
    connector(
        draw,
        (box_stop[2], (box_stop[1] + box_stop[3]) // 2),
        (X_F_STOP_REAL, Y_40),
        color=RED,
    )

    box_fc = label_box(
        draw,
        (445, 330),
        "Fc = 1762,5 Гц\n|H| ≈ 0,5\n(на экране ≈ 7,98 кГц)",
        color=GRAY,
        text_font=f_small,
    )
    connector(
        draw,
        (box_fc[2], (box_fc[1] + box_fc[3]) // 2),
        (X_FC, Y_FC_CURVE),
        color=GRAY,
    )

    box_pass = label_box(
        draw,
        (760, 345),
        "f₁ ≈ 2360 Гц\nуровень 0,95\n(на экране ≈ 10,69 кГц)",
        color=BLUE,
        text_font=f_small,
    )
    connector(
        draw,
        (box_pass[2], (box_pass[1] + box_pass[3]) // 2),
        (X_F_PASS_REAL, Y_095),
        color=BLUE,
    )

    label_box(
        draw,
        (18, 752),
        "Важно: скриншот снят при Fд ≈ 48 кГц (зелёный курсор 11,086 кГц),\n"
        "а домашний расчёт выполнен для Fд = 10600 Гц. Для сравнения частоты\n"
        "шкалы разделены на 48000/10600 ≈ 4,528; видимое окно соответствует 0…3230 Гц.",
        color=DARK,
        text_font=f_note,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Правка DOCX
# ---------------------------------------------------------------------------


def shade_cell(cell, fill="E8E8E8"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_repeat_table_header(row) -> None:
    """Повторяет строку заголовка, если таблица всё же переходит на новую страницу."""
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def prevent_row_split(row) -> None:
    """Не допускает разрыва одной строки таблицы между страницами."""
    tr_pr = row._tr.get_or_add_trPr()
    no_split = OxmlElement("w:cantSplit")
    no_split.set(qn("w:val"), "true")
    tr_pr.append(no_split)


def keep_small_table_together(table) -> None:
    """Сохраняет компактную сравнительную таблицу единым блоком."""
    set_repeat_table_header(table.rows[0])
    for row_index, row in enumerate(table.rows):
        prevent_row_split(row)
        if row_index < len(table.rows) - 1:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True


def make_table(doc, rows, widths):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    # Повторяем оформление первой таблицы исходного отчёта.
    reference = doc.tables[0]._tbl.tblPr
    table._tbl.replace(table._tbl.tblPr, deepcopy(reference))
    table.autofit = False
    for col, width in zip(table.columns, widths):
        col.width = Twips(width)
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = table.cell(i, j)
            cell.width = Twips(widths[j])
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(text)
            run.font.size = Pt(11)
            if i == 0:
                run.bold = True
                shade_cell(cell)
    keep_small_table_together(table)
    return table


def add_text(doc, anchor, text, *, heading=False, center=False, bullet=False,
             before=0, after=0):
    p = anchor.insert_paragraph_before()
    pf = p.paragraph_format
    pf.first_line_indent = Twips(0 if center else 709)
    pf.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
        if center
        else WD_ALIGN_PARAGRAPH.LEFT
        if heading
        else WD_ALIGN_PARAGRAPH.JUSTIFY
    )
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if bullet:
        pf.left_indent = Twips(709)
        pf.first_line_indent = Twips(-360)
    if heading:
        pf.keep_with_next = True
    run = p.add_run(text)
    run.bold = heading
    return p


def add_caption(doc, anchor, text):
    return add_text(doc, anchor, text, center=True, after=6)


def add_table_block(doc, anchor, caption, rows, widths):
    caption_paragraph = add_caption(doc, anchor, caption)
    caption_paragraph.paragraph_format.keep_with_next = True
    table = make_table(doc, rows, widths)
    anchor._p.addprevious(table._tbl)
    add_text(doc, anchor, "", center=True)


def replace_paragraph_text(paragraph, text):
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    for run in paragraph.runs:
        run.text = ""
    paragraph.runs[0].text = text


def keep_figure_with_caption(doc, caption_prefix: str, *, collapse_spacer=False) -> None:
    """Не оставляет подпись рисунка на странице отдельно от изображения."""
    caption = next(p for p in doc.paragraphs if p.text.strip().startswith(caption_prefix))
    image_element = caption._p.getprevious()
    if image_element is None or image_element.tag != qn("w:p"):
        raise RuntimeError(f"Перед подписью не найден абзац рисунка: {caption_prefix}")
    image_paragraph = Paragraph(image_element, caption._parent)
    if not image_paragraph._p.xpath(".//w:drawing"):
        raise RuntimeError(f"Перед подписью нет изображения: {caption_prefix}")

    # В исходнике перед ИХ оставлен пустой абзац. Его удаление даёт подписи место
    # на той же странице, не уменьшая сам экспериментальный график.
    if collapse_spacer:
        spacer = image_element.getprevious()
        if (
            spacer is not None
            and spacer.tag == qn("w:p")
            and not Paragraph(spacer, caption._parent).text.strip()
            and not spacer.xpath(".//w:drawing")
        ):
            spacer.getparent().remove(spacer)

    image_paragraph.paragraph_format.keep_with_next = True
    caption.paragraph_format.keep_together = True


def fix_captions_and_conclusion(doc):
    for p in doc.paragraphs:
        text = p.text.strip()
        if text.startswith("Рисунок 7 - ИХ цифрового ФВЧ"):
            replace_paragraph_text(p, "Рисунок 7 – ИХ цифрового ФВЧ (17 отсчётов)")
        elif text.startswith("Рисунок 8 - АЧХ цифрового ФВЧ"):
            replace_paragraph_text(p, "Рисунок 8 – АЧХ цифрового ФВЧ с отмеченными ПП и ПЗ")
        elif text.startswith("Расчётная АЧХ удовлетворяет заданию:"):
            p.add_run(
                " После пересчёта частотной шкалы экспериментальной АЧХ к Fд = 10600 Гц "
                f"получены f₃ ≈ {F_STOP_TXT:.0f} Гц и f₁ ≈ {F_PASS_TXT:.0f} Гц. "
                "Экспериментальная ИХ содержит 17 симметричных отсчётов с максимумом "
                "b(8) = 0,66745283 и соответствует рассчитанным коэффициентам."
            )

    keep_figure_with_caption(doc, "Рисунок 6")
    keep_figure_with_caption(doc, "Рисунок 7", collapse_spacer=True)
    keep_figure_with_caption(doc, "Рисунок 8")


def build_report(annotated_png: bytes) -> None:
    doc = Document(str(SOURCE_REPORT))
    if any(p.text.startswith("3. Определение граничных частот") for p in doc.paragraphs):
        raise RuntimeError("В исходном DOCX уже присутствует задание №3")
    anchor = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")
    # Заключение начинается с новой страницы и не разрывается после первых строк.
    anchor.paragraph_format.page_break_before = True

    # ------------------------------- задание №3 -------------------------------
    add_text(
        doc,
        anchor,
        "3. Определение граничных частот полосы пропускания и полосы задержания "
        "по графику АЧХ",
        heading=True,
        before=12,
        after=6,
    )
    add_text(
        doc,
        anchor,
        "Граничные частоты определяем по пересечению АЧХ на рисунке 8 с допустимыми "
        "уровнями: для полосы задержания |H| = δ₂ = 0,01 (a = 40 дБ), для полосы "
        "пропускания |H| = 1 − δ₁ = 0,95. Красным на графике отмечена ПЗ, синим — ПП, "
        "серым — переходная полоса. Толстые пунктиры соответствуют заданным F₃ и F₁, "
        "тонкие пунктиры и маркеры — фактическим границам по контрольным уровням.",
    )
    add_text(
        doc,
        anchor,
        "На исходном скриншоте зелёный курсор показывает 11,086 кГц, а форма АЧХ и "
        "положения её нулей совпадают с расчётом после масштабирования частот в "
        "48000/10600 ≈ 4,528 раза. Следовательно, модель «Спектр-2» была запущена при "
        "частоте дискретизации около 48 кГц вместо требуемых 10600 Гц. Поэтому для "
        "сравнения с домашним заданием показания экранной шкалы разделены на 4,528. "
        "При повторении эксперимента следует установить Fд = 10600 Гц.",
    )
    add_text(
        doc,
        anchor,
        f"– граница ПЗ по уровню |H| = 0,01 получилась на экранной шкале около "
        f"{num(screen_frequency(F_STOP_REAL) / 1000, 2)} кГц, что после пересчёта даёт "
        f"f₃ = {num(F_STOP_REAL, 1)} Гц ≈ {F_STOP_TXT:.0f} Гц;",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        f"– граница ПП по уровню |H| = 0,95 получилась на экранной шкале около "
        f"{num(screen_frequency(F_PASS_REAL) / 1000, 2)} кГц, после пересчёта "
        f"f₁ = {num(F_PASS_REAL, 1)} Гц ≈ {F_PASS_TXT:.0f} Гц;",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        f"– частота среза по уровню |H| = 0,5 равна {num(F_CUTOFF_REAL, 1)} Гц и "
        f"практически совпадает с расчётной Fc = {num(FC, 1)} Гц;",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        f"– при F₃ = {F3:.0f} Гц получено |H| = {num(H_AT_F3, 6)} "
        f"(a = {num(A_AT_F3, 3)} дБ), а при F₁ = {F1:.0f} Гц — "
        f"|H| = {num(H_AT_F1, 6)} (a = {num(A_AT_F1, 3)} дБ). Оба требования "
        "выполняются с запасом.",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        f"Сравнение с домашним заданием. Фактическая граница ПЗ отличается от "
        f"F₃ = {F3:.0f} Гц всего на +{num(F_STOP_REAL - F3, 1)} Гц; ПЗ фильтра "
        "продолжается немного дальше заданной границы. Уровень 0,95 достигается при "
        f"{num(F_PASS_REAL, 1)} Гц, то есть ПП начинается на "
        f"{abs(D_PASS_TXT):.0f} Гц раньше заданной F₁ = {F1:.0f} Гц. Переходная "
        f"полоса по допускам равна {num(TRANSITION_REAL, 1)} Гц вместо расчётных "
        f"{TRANSITION_SPEC:.0f} Гц и уже на {num(TRANSITION_MARGIN, 1)} Гц.",
    )

    add_table_block(
        doc,
        anchor,
        "Таблица 3 – Сравнение граничных частот по АЧХ с домашним расчётом",
        [
            ["Величина", "Домашний расчёт", "Шкала скриншота", "После пересчёта", "Отклонение"],
            [
                "Граница ПЗ, |H| = 0,01",
                "F₃ = 1005 Гц",
                "≈ 4,56 кГц",
                f"f₃ ≈ {F_STOP_TXT:.0f} Гц",
                f"+{D_STOP_TXT} Гц (0,2 %)",
            ],
            [
                "Граница ПП, |H| = 0,95",
                "F₁ = 2520 Гц",
                "≈ 10,69 кГц",
                f"f₁ ≈ {F_PASS_TXT:.0f} Гц",
                f"−{abs(D_PASS_TXT)} Гц (6,3 %)",
            ],
            [
                "Частота среза, |H| = 0,5",
                "Fc = 1762,5 Гц",
                "≈ 7,98 кГц",
                f"≈ {F_CUTOFF_REAL:.0f} Гц",
                "≈ 0 Гц",
            ],
            [
                "Ширина переходной полосы",
                "1515 Гц",
                "≈ 6,13 кГц",
                f"≈ {TRANSITION_REAL:.0f} Гц",
                f"−{TRANSITION_MARGIN:.0f} Гц",
            ],
        ],
        [2100, 1750, 1700, 1750, 1900],
    )
    add_text(
        doc,
        anchor,
        "Небольшой запас по границам обусловлен выбором минимального чётного порядка "
        "R = 16 и окном Кайзера с β = 3,395321. В ПЗ максимальный уровень равен "
        f"{num(STOP_MAX, 6)} на частоте {STOP_MAX_F:.0f} Гц, что соответствует "
        f"подавлению {num(A_AT_F3, 3)} дБ ≥ 40 дБ. В ПП характеристика лежит в "
        f"диапазоне {num(PASS_MIN, 6)}…{num(PASS_MAX, 6)}, полностью внутри допуска "
        "0,95…1,05. После исправления масштаба экспериментальная АЧХ подтверждает "
        "результаты домашнего расчёта.",
    )

    # ------------------------------- задание №4 -------------------------------
    add_text(
        doc,
        anchor,
        "4. Анализ характера ИХ и сравнение с рассчитанными значениями",
        heading=True,
        before=12,
        after=6,
    )
    add_text(
        doc,
        anchor,
        "Импульсная характеристика на рисунке 7 получена как реакция фильтра на "
        "единичный импульс. Осциллограф соединяет дискретные отсчёты отрезками, поэтому "
        "плавная линия является только интерполяцией; сравнению подлежат 17 значений "
        "b(0)…b(16) в узлах.",
    )
    add_text(
        doc,
        anchor,
        "ИХ конечна: после b(16) отклик становится равным нулю. Это подтверждает, что "
        "собрана прямая структура КИХ-фильтра порядка R = 16 с 16 линиями задержки, "
        "17 усилителями и без обратных связей.",
    )
    add_text(
        doc,
        anchor,
        "Форма ИХ зеркально симметрична относительно центрального отсчёта: "
        "b(8) = 0,66745283 — наибольший положительный пик; "
        "b(7) = b(9) = −0,26921926 и b(6) = b(10) = −0,12635967 образуют два "
        "одинаковых отрицательных лепестка; далее следуют малые симметричные отсчёты "
        "b(4) = b(12) = 0,04715958, b(3) = b(13) = 0,03036013, а края "
        "b(0) = b(16) = −0,00515576 близки к нулю. Именно такой центральный пик, "
        "два отрицательных провала и затухающие боковые лепестки видны на рисунке 7.",
    )
    add_text(
        doc,
        anchor,
        f"Симметрия b(i) = b(16 − i) соответствует КИХ-фильтру I типа с линейной ФЧХ. "
        f"Постоянная групповая задержка равна R/2 = 8 отсчётам, или "
        f"8/Fд = {num(GROUP_DELAY_MS, 3)} мс. Максимум экспериментальной ИХ расположен "
        "на восьмом такте, что совпадает с расчётом.",
    )
    add_text(
        doc,
        anchor,
        f"Для ФВЧ сумма коэффициентов Σb(i) = {num(SUM_B, 7)} ≈ 0, поэтому постоянная "
        f"составляющая подавляется. На частоте Найквиста |Σb(i)(−1)ⁱ| = "
        f"{num(abs(ALT_SUM_B), 7)} ≈ 1, что соответствует пропусканию высоких частот. "
        "Эти свойства согласуются с экспериментальной АЧХ.",
    )

    add_table_block(
        doc,
        anchor,
        "Таблица 4 – Сопоставление экспериментальной ИХ с домашним расчётом",
        [
            ["Характеристика", "Домашний расчёт", "Экспериментальная ИХ"],
            ["Длительность", "N = 17 отсчётов", "17 отсчётов, затем нулевой отклик"],
            ["Симметрия", "b(i) = b(16 − i)", "зеркальная относительно b(8)"],
            ["Центральный максимум", "b(8) = 0,66745283", "положительный пик на 8-м такте"],
            [
                "Соседние отсчёты",
                "b(7) = b(9) = −0,26921926",
                "два равных отрицательных провала",
            ],
            [
                "Крайние отсчёты",
                "b(0) = b(16) = −0,00515576",
                "малые и одинаковые по краям",
            ],
            ["Групповая задержка", "8 отсчётов = 0,755 мс", "максимум сдвинут на 8 тактов"],
        ],
        [2400, 3300, 3500],
    )
    add_text(
        doc,
        anchor,
        "Вертикальная шкала осциллограммы не подписана, поэтому точные амплитуды с неё "
        "снять нельзя. Однако длительность, положение максимума, симметрия, знаки и "
        "соотношение основных лепестков полностью совпадают с рассчитанными "
        "коэффициентами таблицы 2. Следовательно, экспериментальная ИХ подтверждает "
        "домашний расчёт.",
    )

    fix_captions_and_conclusion(doc)
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=str(CORRECTED_DIR)) as tmp:
        tmp_path = Path(tmp.name)
    package_path = tmp_path.with_suffix(".new.docx")
    try:
        doc.save(str(tmp_path))
        with ZipFile(tmp_path, "r") as zin, ZipFile(package_path, "w", compression=ZIP_DEFLATED) as zout:
            names = set(zin.namelist())
            if "word/media/image6.png" not in names:
                raise RuntimeError("В сохранённом DOCX не найдена часть image6.png")
            for item in zin.infolist():
                data = annotated_png if item.filename == "word/media/image6.png" else zin.read(item.filename)
                zout.writestr(item, data)
        with ZipFile(package_path, "r") as check:
            bad = check.testzip()
            if bad is not None:
                raise RuntimeError(f"Повреждён элемент DOCX: {bad}")
        shutil.move(str(package_path), str(OUTPUT_REPORT))
        OUTPUT_REPORT.chmod(0o644)
    finally:
        tmp_path.unlink(missing_ok=True)
        package_path.unlink(missing_ok=True)


def validate_output(annotated_png: bytes) -> None:
    doc = Document(str(OUTPUT_REPORT))
    texts = [p.text for p in doc.paragraphs]
    assert sum(t.startswith("3. Определение граничных частот") for t in texts) == 1
    assert sum(t.startswith("4. Анализ характера ИХ") for t in texts) == 1
    assert any("с отмеченными ПП и ПЗ" in t for t in texts)
    assert any("48 кГц" in t for t in texts)
    assert len(doc.tables) == 4

    conclusion = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")
    assert conclusion.paragraph_format.page_break_before is True
    for caption_prefix in ("Рисунок 6", "Рисунок 7", "Рисунок 8"):
        caption = next(p for p in doc.paragraphs if p.text.strip().startswith(caption_prefix))
        image_paragraph = caption._p.getprevious()
        assert image_paragraph is not None and image_paragraph.xpath(".//w:drawing")
        assert image_paragraph.xpath("./w:pPr/w:keepNext")
    for table in doc.tables[-2:]:
        assert table.rows[0]._tr.xpath("./w:trPr/w:tblHeader")
        assert all(row._tr.xpath("./w:trPr/w:cantSplit") for row in table.rows)

    with ZipFile(OUTPUT_REPORT, "r") as package:
        assert package.testzip() is None
        assert package.read("word/media/image6.png") == annotated_png


def main() -> None:
    if not SOURCE_REPORT.exists():
        raise FileNotFoundError(SOURCE_REPORT)
    source_digest = sha256(SOURCE_REPORT.read_bytes()).digest()
    with ZipFile(SOURCE_REPORT, "r") as docx:
        source_png = docx.read("word/media/image6.png")
    annotated = mark_amplitude_response(source_png)
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_PNG.write_bytes(annotated)
    build_report(annotated)
    validate_output(annotated)
    assert sha256(SOURCE_REPORT.read_bytes()).digest() == source_digest

    print(f"Исходный отчёт сохранён без изменений: {SOURCE_REPORT}")
    print(f"Исправленный отчёт: {OUTPUT_REPORT}")
    print(f"Размеченная АЧХ: {ANNOTATED_PNG}")
    print(
        f"f₃ (0,01) = {F_STOP_REAL:.2f} Гц; "
        f"f₁ (0,95) = {F_PASS_REAL:.2f} Гц; "
        f"Fc (0,5) = {F_CUTOFF_REAL:.2f} Гц"
    )
    print(
        f"|H(F₃)| = {H_AT_F3:.6f} ({A_AT_F3:.3f} дБ); "
        f"|H(F₁)| = {H_AT_F1:.6f} ({A_AT_F1:.3f} дБ)"
    )


if __name__ == "__main__":
    main()
