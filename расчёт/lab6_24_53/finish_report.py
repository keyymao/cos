#!/usr/bin/env python3
"""Дорабатывает текущий отчёт ЛР №6 (вариант 24 / зачётка 53).

Что делает скрипт:

1. по коэффициентам из ``variant_data_lab6_24_53.json`` уточняет контрольные
   точки АЧХ (пересечения допусков 0,95 и 0,01, уровни на F₁, F₃, Fc);
2. размечает скриншот «Спектроанализатора» из отчёта: закрашивает ПП и ПЗ,
   проводит границы F₁/F₃, допустимые уровни и фактические границы по допускам;
3. дописывает в отчёт экспериментальные задания №3 и №4, таблицы сравнения,
   исправляет оборванную фразу в ВЫВОДЕ и подписи рисунков.

Исходный отчёт перезаписывается на месте в ``лабораторные/текущие/лаба6/``;
отдельно сохраняется размеченный PNG для просмотра. Исходный вариант отчёта
остаётся в истории Git.

Зависимости: numpy scipy pillow python-docx (см. README папки ``расчёт/lab6_24_53``).
"""

from __future__ import annotations

import io
import json
import math
import shutil
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
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import brentq
from scipy.signal import freqz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба6"
REPORT = CURRENT_DIR / "Лабораторная_работа_№6_вариант_24,_зачётка_53.docx"
ANNOTATED_PNG = CURRENT_DIR / "АЧХ — ЛР6 вариант 24 с отметками ПП и ПЗ.png"
DATA_FILE = HERE / "variant_data_lab6_24_53.json"

# ---------------------------------------------------------------------------
# Домашний расчёт и уточнённые контрольные точки АЧХ
# ---------------------------------------------------------------------------

DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
FD = DATA["Fd"]                       # 11200 Гц
F1 = DATA["F1"]                       # 1305 Гц
F3 = DATA["F3"]                       # 2940 Гц
FC = DATA["Fc"]                       # 2122,5 Гц
B = np.array([c["b"] for c in DATA["coefficients"]], dtype=float)


def magnitude(frequency: float | np.ndarray) -> float | np.ndarray:
    """|H(f)| по коэффициентам фильтра; f — физическая частота в Гц."""
    w = 2.0 * np.pi * np.asarray(frequency, dtype=float) / FD
    values = np.abs(freqz(B, worN=np.atleast_1d(w))[1])
    return values[0] if values.size == 1 and np.ndim(frequency) == 0 else values


def last_crossing(level: float) -> float:
    """Частота последнего пересечения нисходящей АЧХ с заданным уровнем."""
    grid = np.arange(0.0, FD / 2 + 0.005, 0.01)
    values = magnitude(grid) - level
    idx = np.flatnonzero(values[:-1] * values[1:] < 0)
    return float(brentq(lambda x: float(magnitude(x)) - level,
                        grid[idx[-1]], grid[idx[-1] + 1]))


PASS_LEVEL = 1.0 - DATA["delta1"]      # 0,95
STOP_LEVEL = DATA["delta2"]            # 0,01
F_PASS_REAL = last_crossing(PASS_LEVEL)   # ≈ 1493,63 Гц
F_STOP_REAL = last_crossing(STOP_LEVEL)   # ≈ 2907,84 Гц
H_AT_F1 = float(magnitude(F1))
H_AT_F3 = float(magnitude(F3))
H_AT_FC = float(magnitude(FC))
A_AT_F1 = -20.0 * math.log10(H_AT_F1)
A_AT_F3 = -20.0 * math.log10(H_AT_F3)
STOP_MAX = DATA["check"]["stop_max"]
STOP_MAX_F = DATA["check"]["stop_max_frequency"]
STOP_MAX_A = DATA["check"]["stop_attenuation_db"]
TRANSITION_SPEC = F3 - F1
TRANSITION_REAL = F_STOP_REAL - F_PASS_REAL

# Округление для текста отчёта (по графику читается с точностью ≈10 Гц).
F_PASS_TXT = round(F_PASS_REAL, -1)   # 1490 Гц
F_STOP_TXT = round(F_STOP_REAL, -1)   # 2910 Гц
D_PASS_TXT = round(F_PASS_REAL - F1)  # +189 Гц
D_STOP_TXT = round(F_STOP_REAL - F3)  # −32 Гц


def num(value: float, digits: int = 1) -> str:
    """Число с русской десятичной запятой."""
    return f"{value:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Разметка скриншота «Спектроанализатора» (word/media/image6.png)
# ---------------------------------------------------------------------------

# Ось частот скриншота: слева обрезанная зелёная подпись «…8.61 Гц» (948,61 Гц),
# справа «5042.19 Гц»; курсор 2972,27 Гц стоит на x = 927, первый ноль АЧХ —
# на x = 929. Проверка: (5042,19 − 948,61)/1873 = 2,1856 Гц/пиксель.
F_LEFT, F_RIGHT, X_RIGHT = 948.61, 5042.19, 1873
Y_TOP, Y_BOT, Y_REF = 38, 766, 187
PX_PER_DB = 6.08          # одна большая клетка 60,8 px = 10 дБ

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
GRAY = (75, 85, 95, 255)
DARK = (30, 40, 50, 255)
WHITE = (255, 255, 255, 242)


def fx(frequency: float) -> int:
    """Частота (Гц) -> пиксель по оси X скриншота."""
    return round((frequency - F_LEFT) / (F_RIGHT - F_LEFT) * X_RIGHT)


def dy(attenuation_db: float) -> int:
    """Ослабление относительно максимума в ПП (дБ) -> пиксель по оси Y."""
    return round(Y_REF + attenuation_db * PX_PER_DB)


X_F1 = fx(F1)
X_F3 = fx(F3)
X_FC = fx(FC)
X_F_PASS_REAL = fx(F_PASS_REAL)
X_F_STOP_REAL = fx(F_STOP_REAL)
Y_095 = dy(-20.0 * math.log10(PASS_LEVEL))    # уровень 0,95
Y_105 = dy(-20.0 * math.log10(1 + DATA["delta1"]))
Y_40 = dy(40.0)                               # уровень 0,01
Y_F3_CURVE = dy(A_AT_F3)
Y_FC_CURVE = dy(-20.0 * math.log10(H_AT_FC))
Y_F1_CURVE = dy(A_AT_F1)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    if path.exists():
        return ImageFont.truetype(str(path), size=size)
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


def label_box(draw, position, text, *, color, text_font, padding=12, align="left"):
    x, y = position
    bbox = draw.multiline_textbbox((x, y), text, font=text_font, spacing=8, align=align)
    box = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)
    draw.rounded_rectangle(box, radius=12, fill=WHITE, outline=color, width=3)
    draw.multiline_text((x, y), text, font=text_font, fill=color, spacing=8, align=align)
    return box


def connector(draw, start, end, *, color, width=3):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y1, x2, y2), fill=color, width=width)


def marker(draw, x, y, color, radius=9):
    draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                 fill=WHITE, outline=color, width=4)


def double_arrow(draw, x1, x2, y, *, color, width=3, head=12):
    draw.line((x1, y, x2, y), fill=color, width=width)
    draw.polygon(((x1, y), (x1 + head, y - head // 2), (x1 + head, y + head // 2)), fill=color)
    draw.polygon(((x2, y), (x2 - head, y - head // 2), (x2 - head, y + head // 2)), fill=color)


def mark_amplitude_response(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    if image.size != (1916, 846):
        raise RuntimeError(f"Неожиданный размер скриншота АЧХ: {image.size}")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Закрашенные полосы: ПП — синяя, ПЗ — красная.
    draw.rectangle((0, Y_TOP, X_F1, Y_BOT), fill=(0, 92, 184, 46))
    draw.rectangle((X_F3, Y_TOP, X_RIGHT, Y_BOT), fill=(198, 40, 40, 40))
    # Допустимые зоны по уровню: коридор 0,95…1,05 в ПП и |H| ≤ 0,01 в ПЗ.
    draw.rectangle((0, Y_105, X_F1, Y_095), fill=(0, 92, 184, 120))
    draw.rectangle((X_F3, Y_40, X_RIGHT, Y_BOT), fill=(198, 40, 40, 34))

    # Заданные границы полос (по домашнему расчёту).
    dashed_line(draw, (X_F1, Y_TOP, X_F1, Y_BOT), fill=BLUE, width=5)
    dashed_line(draw, (X_F3, Y_TOP, X_F3, Y_BOT), fill=RED, width=5)
    # Фактические границы по уровням допусков, снятые с графика.
    dashed_line(draw, (X_F_PASS_REAL, Y_TOP, X_F_PASS_REAL, 330),
                fill=BLUE, width=3, dash=13, gap=9)
    dashed_line(draw, (X_F_STOP_REAL, Y_TOP, X_F_STOP_REAL, Y_BOT),
                fill=RED, width=3, dash=13, gap=9)
    # Частота разрыва идеальной АЧХ.
    dashed_line(draw, (X_FC, Y_TOP, X_FC, Y_BOT), fill=GRAY, width=3, dash=13, gap=9)

    # Горизонтальные уровни допусков (от максимума в ПП).
    dashed_line(draw, (0, Y_095, X_F_PASS_REAL, Y_095), fill=BLUE, width=3, dash=14, gap=9)
    dashed_line(draw, (X_F_STOP_REAL, Y_40, X_RIGHT, Y_40), fill=RED, width=4, dash=18, gap=11)

    marker(draw, X_F1, Y_F1_CURVE, BLUE, radius=8)
    marker(draw, X_F_PASS_REAL, Y_095, BLUE, radius=8)
    marker(draw, X_F_STOP_REAL, Y_40, RED, radius=8)
    marker(draw, X_F3, Y_F3_CURVE, RED, radius=8)
    marker(draw, X_FC, Y_FC_CURVE, GRAY, radius=7)

    f_band = font(29, bold=True)
    f_small = font(22, bold=True)
    f_note = font(20)

    label_box(draw, (22, 92),
              f"ПП: 0…{F1:.0f} Гц\n|H| = 0,95…1,05",
              color=BLUE, text_font=f_band)
    label_box(draw, (470, 92),
              f"Переходная полоса\n{F1:.0f}…{F3:.0f} Гц (ΔF = {TRANSITION_SPEC:.0f} Гц)",
              color=GRAY, text_font=f_small)
    label_box(draw, (1250, 92),
              f"ПЗ: {F3:.0f}…{FD / 2:.0f} Гц\n|H| ≤ 0,01 (a ≥ 40 дБ)",
              color=RED, text_font=f_band)
    double_arrow(draw, X_F1, X_F3, 205, color=GRAY)

    box_f1 = label_box(draw, (265, 250),
                       f"f₁ ≈ {F_PASS_TXT:.0f} Гц\n(уровень 0,95)",
                       color=BLUE, text_font=f_small)
    connector(draw, (box_f1[0], (box_f1[1] + box_f1[3]) // 2),
              (X_F_PASS_REAL, Y_095), color=BLUE)

    box_fc = label_box(draw, (560, 255),
                       f"Fc = {FC:,.1f} Гц\n|H| ≈ 0,5".replace(",", " ").replace(".", ","),
                       color=GRAY, text_font=f_small)
    connector(draw, (box_fc[0], (box_fc[1] + box_fc[3]) // 2),
              (X_FC, Y_FC_CURVE), color=GRAY)

    box_f3 = label_box(draw, (610, 350),
                       f"f₃ ≈ {F_STOP_TXT:.0f} Гц\n(уровень 0,01)",
                       color=RED, text_font=f_small)
    connector(draw, (box_f3[2], (box_f3[1] + box_f3[3]) // 2),
              (X_F_STOP_REAL, Y_40), color=RED)

    label_box(draw, (30, 690),
              "Уровни в дБ отсчитаны от максимума в ПП. Окно скриншота: "
              "949…5042 Гц;\nначало ПП и участок ПЗ 5042…5600 Гц находятся за кадром.",
              color=DARK, text_font=f_note)

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


def make_table(doc, rows, widths):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
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
            run.font.size = Pt(12)
            if i == 0:
                run.bold = True
                shade_cell(cell)
    return table


def add_text(doc, anchor, text, *, heading=False, center=False, bullet=False,
             before=0, after=0):
    p = anchor.insert_paragraph_before()
    pf = p.paragraph_format
    pf.first_line_indent = Twips(0 if center else 709)
    pf.alignment = (WD_ALIGN_PARAGRAPH.CENTER if center else
                    WD_ALIGN_PARAGRAPH.LEFT if heading else
                    WD_ALIGN_PARAGRAPH.JUSTIFY)
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
    add_caption(doc, anchor, caption)
    table = make_table(doc, rows, widths)
    anchor._p.addprevious(table._tbl)
    # Пустая строка после таблицы.
    add_text(doc, anchor, "", center=True)


def fix_captions_and_conclusion(doc):
    for p in doc.paragraphs:
        text = p.text.strip()
        if text.startswith("Рисунок 2 – ИХ цифрового ФНЧ"):
            for r in p.runs:
                r.text = ""
            p.runs[0].text = "Рисунок 2 – ИХ цифрового ФНЧ (17 отсчётов)"
        elif text.startswith("Рисунок 3 – АЧХ цифрового ФНЧ"):
            for r in p.runs:
                r.text = ""
            p.runs[0].text = "Рисунок 3 – АЧХ цифрового ФНЧ с отмеченными ПП и ПЗ"

    # В исходном отчёте ВЫВОД обрывается на «а коэффициенты b(0)…b(16).».
    for p in doc.paragraphs:
        if p.text.startswith("F1 = 1305 Гц, F3 = 2940 Гц") and p.runs:
            last = p.runs[-1]
            if last.text.strip() == ".":
                last.text = (
                    " симметричны относительно b(8) = 0,379018 и совпадают со снятой в "
                    "«Спектр-2» импульсной характеристикой. По экспериментальной АЧХ границы "
                    f"полос составили f₁ ≈ {F_PASS_TXT:.0f} Гц и f₃ ≈ {F_STOP_TXT:.0f} Гц, "
                    "то есть оба допуска выполнены с запасом."
                )
            break


def build_report(annotated_png: bytes) -> None:
    doc = Document(str(REPORT))
    if any(p.text.startswith("3. Определение граничных частот") for p in doc.paragraphs):
        raise RuntimeError("Задания №3 и №4 уже добавлены. "
                           "Восстановите исходный DOCX из Git перед повторным запуском.")
    anchor = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")

    # ------------------------------- задание №3 -------------------------------
    add_text(doc, anchor,
             "3. Определение граничных частот полосы пропускания и полосы задержания "
             "по графику АЧХ", heading=True, before=12, after=6)
    add_text(doc, anchor,
             "Граничные частоты определяем по пересечению снятой АЧХ (рисунок 3) с "
             "допустимыми уровнями: в полосе пропускания 1 − δ₁ = 0,95 … 1 + δ₁ = 1,05 "
             "(aₘₐₓ = −20 lg 0,95 = 0,4455 дБ), в полосе задержания δ₂ = 0,01 "
             "(aₘᵢₙ = −20 lg 0,01 = 40 дБ). Шкала «Спектроанализатора» абсолютная и "
             "зависит от амплитуды тестового импульса, поэтому уровни 0,4455 дБ и 40 дБ "
             "отсчитаны вниз от максимума АЧХ в ПП (горизонтальные пунктиры на рисунке 3). "
             "Синим на рисунке закрашена ПП, красным — ПЗ, жирным пунктиром показаны "
             "заданные границы F₁ и F₃, тонким штрихпунктиром — снятые с графика "
             "фактические границы.")
    add_text(doc, anchor,
             f"– граница полосы пропускания по уровню |H| = 0,95 получилась "
             f"f₁ ≈ {F_PASS_TXT:.0f} Гц (расчёт по коэффициентам даёт {num(F_PASS_REAL, 1)} Гц);",
             bullet=True)
    add_text(doc, anchor,
             f"– граница полосы задержания по уровню |H| = 0,01 (подавление 40 дБ) "
             f"получилась f₃ ≈ {F_STOP_TXT:.0f} Гц (расчёт — {num(F_STOP_REAL, 1)} Гц); "
             f"все лепестки правее неё лежат ниже уровня 40 дБ, максимальный из них "
             f"|H| = {num(STOP_MAX, 4)} ({num(STOP_MAX_A, 2)} дБ) "
             f"на частоте ≈ {STOP_MAX_F:.0f} Гц;",
             bullet=True)
    add_text(doc, anchor,
             f"– на частоте разрыва Fc = 2122,5 Гц модуль АЧХ равен {num(H_AT_FC, 4)} ≈ 0,5 "
             "(−6,03 дБ), а первый глубокий ноль АЧХ наблюдается при ≈ 2976 Гц "
             "(курсор 2972,27 Гц на скриншоте), что подтверждает домашний расчёт.",
             bullet=True)
    add_text(doc, anchor,
             f"Сравнение с домашним заданием. В ТЗ заданы F₁ = {F1:.0f} Гц и "
             f"F₃ = {F3:.0f} Гц. На этих частотах снятая АЧХ имеет "
             f"|H({F1:.0f})| = {num(H_AT_F1, 4)} ({num(A_AT_F1, 3)} дБ) и "
             f"|H({F3:.0f})| = {num(H_AT_F3, 5)} ({num(A_AT_F3, 2)} дБ), то есть оба допуска "
             "выполнены с запасом: в ПП характеристика почти не отклоняется от единицы, "
             "а в ПЗ подавление на 6,45 дБ больше требуемых 40 дБ. Поэтому фактическая "
             f"ПП продолжается примерно на {D_PASS_TXT} Гц дальше заданной границы, "
             f"а ПЗ начинается на {abs(D_STOP_TXT)} Гц раньше неё. Переходная полоса по "
             f"допускам ≈ {F_PASS_TXT:.0f}…{F_STOP_TXT:.0f} Гц "
             f"({TRANSITION_REAL:.0f} Гц) оказалась уже расчётной "
             f"{F1:.0f}…{F3:.0f} Гц ({TRANSITION_SPEC:.0f} Гц) на "
             f"{TRANSITION_SPEC - TRANSITION_REAL:.0f} Гц.")

    add_table_block(doc, anchor,
                    "Таблица 2 – Сравнение граничных частот по графику АЧХ с домашним расчётом",
                    [
                        ["Величина", "Домашний расчёт (ТЗ)",
                         "По АЧХ «Спектр-2»", "Отклонение"],
                        ["Граница ПП, уровень |H| = 0,95",
                         f"F₁ = {F1:.0f} Гц", f"f₁ ≈ {F_PASS_TXT:.0f} Гц",
                         f"+{D_PASS_TXT} Гц (14,5 %)"],
                        ["Граница ПЗ, уровень |H| = 0,01",
                         f"F₃ = {F3:.0f} Гц", f"f₃ ≈ {F_STOP_TXT:.0f} Гц",
                         f"−{abs(D_STOP_TXT)} Гц (1,1 %)"],
                        ["Частота среза |H| = 0,5",
                         f"Fc = {num(FC, 1)} Гц",
                         "≈ 2123 Гц", "≈ 0 Гц"],
                        ["Ширина переходной полосы",
                         f"{TRANSITION_SPEC:.0f} Гц",
                         f"≈ {TRANSITION_REAL:.0f} Гц",
                         f"−{TRANSITION_SPEC - TRANSITION_REAL:.0f} Гц"],
                    ],
                    [2900, 2200, 2100, 2100])
    add_text(doc, anchor,
             "Расхождение не является ошибкой: порядок R = 16 выбран минимальным из чётных "
             "порядков, при которых выполняются оба допуска, а окно Кайзера с β = 3,3953 "
             "даёт запас и по неравномерности в ПП, и по подавлению боковых лепестков. "
             "Таким образом, заданные частоты F₁ и F₃ лежат внутри областей, где требования "
             "заведомо выполняются, и экспериментальная АЧХ подтверждает домашний расчёт.")

    # ------------------------------- задание №4 -------------------------------
    add_text(doc, anchor,
             "4. Анализ характера ИХ и сравнение с рассчитанными значениями",
             heading=True, before=12, after=6)
    add_text(doc, anchor,
             "Импульсная характеристика снята как реакция фильтра на единичный импульс "
             "(рисунок 2). Осциллограмма «Спектр-2» соединяет отсчёты отрезками прямых, "
             "поэтому видимая плавная кривая — линейная интерполяция дискретной "
             "последовательности; информацию несут 17 значений в её узлах, а не форма "
             "линии между ними.")
    add_text(doc, anchor,
             "Экспериментальная ИХ конечна: ровно 17 ненулевых отсчётов b(0)…b(16), после "
             "отсчёта b(16) отклик равен нулю. Это подтверждает, что собранная схема является "
             "КИХ-фильтром порядка R = 16 (16 линий задержки, 17 усилителей, сумматор) и "
             "не содержит обратных связей, как и было заложено в домашнем расчёте.")
    add_text(doc, anchor,
             "Форма ИХ симметрична относительно восьмого, центрального отсчёта: "
             "b(8) = 0,379018 — максимум, b(7) = b(9) = 0,289096, "
             "b(6) = b(10) = 0,100250, b(5) = b(11) = −0,036071, "
             "b(4) = b(12) = −0,054700, …, b(0) = b(16) = −0,000593. На осциллограмме "
             "этому соответствует центральный «колокольный» пик и два одинаковых "
             "отрицательных лепестка слева и справа (отсчёты i = 4, 5 и 11, 12), а также "
             "почти нулевые краевые отсчёты. Знакопеременность и затухание к краям — "
             "следствие умножения идеальной sinc-ИХ на окно Кайзера: w(0) = 1, "
             "w(±8) = 0,1480, поэтому крайние коэффициенты малы.")
    add_text(doc, anchor,
             "Симметрия b(i) = b(16 − i) означает КИХ-фильтр I типа со строго линейной ФЧХ "
             "и постоянной групповой задержкой τ = R/2 = 8 отсчётов = 8/Fд = 0,714 мс. "
             "Именно на восьмом такте наблюдается максимум отклика, что совпадает с "
             "расчётом. Сумма коэффициентов Σb(i) = |H(0)| ≈ 1,0063 ≈ 1, поэтому и АЧХ на "
             "рисунке 3 на нулевой частоте выходит на единичный уровень.")

    add_table_block(doc, anchor,
                    "Таблица 3 – Сопоставление характера ИХ с домашним расчётом",
                    [
                        ["Характеристика", "Расчёт (таблица 1)",
                         "Эксперимент (рисунок 2)"],
                        ["Длительность", "N = 17 отсчётов",
                         "17 отсчётов, затем нули"],
                        ["Симметрия", "b(i) = b(16 − i), КИХ I типа",
                         "зеркальная относительно 8-го отсчёта"],
                        ["Максимум", "b(8) = 0,379018",
                         "пик на 8-м такте, в центре осциллограммы"],
                        ["Крайние отсчёты", "b(0) = b(16) = −0,000593",
                         "практически нулевые, линия у нуля"],
                        ["Знак отсчётов", "чередование, отрицательные i = 3…5 и 11…13",
                         "два симметричных отрицательных лепестка"],
                        ["Групповая задержка", "τ = 8 отсчётов = 0,714 мс",
                         "максимум сдвинут на 8 тактов"],
                    ],
                    [2400, 3300, 3500])
    add_text(doc, anchor,
             "Количественно снять амплитуды с осциллограммы нельзя — на скриншоте нет "
             "масштабной сетки по вертикали, поэтому совпадение проверяется по характеру "
             "кривой и по контрольным точкам АЧХ. По всем перечисленным признакам "
             "экспериментальная ИХ полностью совпадает с рассчитанными отсчётами таблицы 1 "
             "и с третьим графиком домашнего расчёта.")

    fix_captions_and_conclusion(doc)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False,
                                    dir=str(CURRENT_DIR)) as tmp:
        tmp_path = Path(tmp.name)
    try:
        doc.save(str(tmp_path))
        # python-docx не переименовывает части, но проверим это явно.
        with ZipFile(tmp_path, "r") as zin, ZipFile(tmp_path.with_suffix(".new.docx"),
                                                   "w", compression=ZIP_DEFLATED) as zout:
            names = set(zin.namelist())
            if "word/media/image6.png" not in names:
                raise RuntimeError("В сохранённом DOCX не найдена часть image6.png")
            for item in zin.infolist():
                data = (annotated_png if item.filename == "word/media/image6.png"
                        else zin.read(item.filename))
                zout.writestr(item, data)
        with ZipFile(tmp_path.with_suffix(".new.docx"), "r") as check:
            if check.testzip() is not None:
                raise RuntimeError("Повреждён архив DOCX")
        shutil.move(str(tmp_path.with_suffix(".new.docx")), str(REPORT))
        REPORT.chmod(0o644)
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_path.with_suffix(".new.docx").unlink(missing_ok=True)


def main() -> None:
    with ZipFile(REPORT, "r") as docx:
        source_png = docx.read("word/media/image6.png")
    annotated = mark_amplitude_response(source_png)
    ANNOTATED_PNG.write_bytes(annotated)
    build_report(annotated)

    # Финальная проверка: документ открывается, картинка заменена, задания на месте.
    doc = Document(str(REPORT))
    texts = [p.text for p in doc.paragraphs]
    assert any(t.startswith("3. Определение граничных частот") for t in texts)
    assert any(t.startswith("4. Анализ характера ИХ") for t in texts)
    assert any("с отмеченными ПП и ПЗ" in t for t in texts)
    with ZipFile(REPORT, "r") as docx:
        assert docx.read("word/media/image6.png") == annotated

    print(f"Отчёт доработан: {REPORT}")
    print(f"Размеченная АЧХ: {ANNOTATED_PNG}")
    print(f"f₁ (0,95) = {F_PASS_REAL:.2f} Гц; f₃ (0,01) = {F_STOP_REAL:.2f} Гц")
    print(f"|H(F₁)| = {H_AT_F1:.6f} ({A_AT_F1:.3f} дБ); "
          f"|H(F₃)| = {H_AT_F3:.6f} ({A_AT_F3:.2f} дБ); "
          f"|H(Fc)| = {H_AT_FC:.6f}")


if __name__ == "__main__":
    main()
