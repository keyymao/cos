#!/usr/bin/env python3
"""Дорабатывает ЛР №6 для варианта 12 / зачётки 06.

Скрипт не изменяет исходный DOCX и исходный снимок. Он:

1. определяет по присланной логарифмической АЧХ границы ПЗ, ПП и частоту среза;
2. отмечает на снимке заданные полосы и найденные пересечения;
3. заменяет рисунок 8 в отдельной копии отчёта;
4. заново оформляет лабораторные задания №3 и №4 и уточняет вывод.

Зависимости: numpy, scipy, pillow, python-docx.
"""

from __future__ import annotations

import io
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, Twips
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import median_filter
from scipy.optimize import brentq
from scipy.signal import freqz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба6"
CORRECTED_DIR = ROOT / "лабораторные" / "исправленые" / "лаба6"
SOURCE_REPORT = CURRENT_DIR / "Копировать Лабораторная_работа_№6_вариант_12.docx"
SOURCE_ACH = CURRENT_DIR / "АЧХ — ЛР6 вариант 12 — исходный снимок.png"
OUTPUT_REPORT = (
    CORRECTED_DIR
    / "Лабораторная работа №6 (вариант 12, зачётка 06) — исправленная.docx"
)
ANNOTATED_PNG = CORRECTED_DIR / "АЧХ — ЛР6 вариант 12 с отметками ПП и ПЗ.png"
DATA_FILE = HERE / "variant_data_lab6.json"

# ---------------------------------------------------------------------------
# Исходные данные варианта и расчётная АЧХ
# ---------------------------------------------------------------------------

DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
FD = float(DATA["Fd"])                    # 10600 Гц
F1 = float(DATA["F1"])                    # 2520 Гц — заданная граница ПП
F3 = float(DATA["F3"])                    # 1005 Гц — заданная граница ПЗ
FC = float(DATA["Fc"])                    # 1762,5 Гц
B = np.array([item["b"] for item in DATA["coefficients"]], dtype=float)
PASS_LEVEL = 1.0 - float(DATA["delta1"])  # 0,95
STOP_LEVEL = float(DATA["delta2"])        # 0,01


def magnitude(frequency: float | np.ndarray) -> float | np.ndarray:
    """Возвращает |H(f)| по округлённым коэффициентам таблицы 2."""
    w = 2.0 * np.pi * np.asarray(frequency, dtype=float) / FD
    values = np.abs(freqz(B, worN=np.atleast_1d(w))[1])
    return values[0] if values.size == 1 and np.ndim(frequency) == 0 else values


def crossing(level: float, left: float, right: float) -> float:
    return float(brentq(lambda value: float(magnitude(value)) - level, left, right))


# Пересечения расчётной характеристики, используемые для сравнения в задании №3.
F_STOP_CALC = crossing(STOP_LEVEL, 900.0, 1150.0)
F_CUTOFF_CALC = crossing(0.5, 1600.0, 1900.0)
F_PASS_CALC = crossing(PASS_LEVEL, 2200.0, 2500.0)
GROUP_DELAY_MS = float(DATA["group_delay"]) / FD * 1000.0
SUM_B = float(np.sum(B))
ALT_SUM_B = float(np.sum(B * (-1.0) ** np.arange(B.size)))

# ---------------------------------------------------------------------------
# Калибровка присланного снимка АЧХ
# ---------------------------------------------------------------------------

# На снимке частотная шкала линейная. Три подписи интерфейса:
# x = 4    -> 0,00 Гц;
# x = 950  -> 2448,14 Гц (красный курсор);
# x = 1895 -> 4893,70 Гц (правая граница видимого диапазона).
GRAPH_SIZE = (1919, 899)
GRAPH_X_ZERO = 4
GRAPH_X_CURSOR = 950
GRAPH_CURSOR_HZ = 2448.14
GRAPH_X_RIGHT = 1895
GRAPH_RIGHT_HZ = 4893.70
GRAPH_Y_BOTTOM = 884

# Горизонтальные линии с подписями −50, −60, …, −140 дБ.
DB_GRID_Y = np.array([19, 107, 196, 284, 373, 461, 549, 638, 726, 815], dtype=float)
DB_GRID_ATTENUATION = np.arange(50.0, 150.0, 10.0)
PX_PER_DB, DB_GRID_INTERCEPT = np.polyfit(DB_GRID_ATTENUATION, DB_GRID_Y, 1)

RED = (198, 40, 40, 255)
BLUE = (0, 92, 184, 255)
GRAY = (75, 85, 95, 255)
WHITE = (255, 255, 255, 242)


def fx(frequency: float) -> int:
    """Переводит частоту в координату x по видимой шкале снимка."""
    return round(
        GRAPH_X_ZERO
        + frequency / GRAPH_RIGHT_HZ * (GRAPH_X_RIGHT - GRAPH_X_ZERO)
    )


def xf(x: float) -> float:
    """Переводит координату x снимка в герцы."""
    return (
        (x - GRAPH_X_ZERO)
        / (GRAPH_X_RIGHT - GRAPH_X_ZERO)
        * GRAPH_RIGHT_HZ
    )


@dataclass(frozen=True)
class GraphMeasurements:
    curve_y: np.ndarray
    plateau_y: float
    stop_y: float
    cutoff_y: float
    pass_y: float
    f_stop: float
    f_cutoff: float
    f_pass: float
    cursor_ratio: float


def _first_descending_crossing(curve_y: np.ndarray, target_y: float) -> float:
    """Находит x первого пересечения монотонного участка АЧХ с уровнем."""
    left = fx(900.0)
    right = fx(2700.0)
    matches = np.flatnonzero(curve_y[left : right + 1] <= target_y)
    if not matches.size:
        raise RuntimeError(f"На снимке не найдено пересечение с y={target_y:.2f}")
    x_right = left + int(matches[0])
    x_left = x_right - 1
    y_left = float(curve_y[x_left])
    y_right = float(curve_y[x_right])
    if y_left == y_right:
        return float(x_right)
    return x_left + (y_left - target_y) / (y_left - y_right)


def analyse_graph(image: Image.Image) -> GraphMeasurements:
    """Снимает три контрольные частоты непосредственно с пикселей АЧХ."""
    if image.size != GRAPH_SIZE:
        raise RuntimeError(
            f"Неожиданный размер присланной АЧХ: {image.size}; ожидался {GRAPH_SIZE}"
        )

    array = np.asarray(image.convert("RGB"))
    # Верхняя граница жёлтой заливки совпадает с линией АЧХ. Серые линии сетки
    # дают пропуски, поэтому они интерполируются, затем применяется медианный
    # фильтр шириной 5 пикселей.
    yellow = (
        (array[:, :, 0] >= 145)
        & (array[:, :, 1] >= 145)
        & (array[:, :, 2] < 30)
        & (np.abs(array[:, :, 0].astype(int) - array[:, :, 1].astype(int)) <= 5)
    )
    curve = np.full(image.width, np.nan, dtype=float)
    for x in range(GRAPH_X_ZERO, GRAPH_X_RIGHT + 1):
        ys = np.flatnonzero(yellow[:, x] & (np.arange(image.height) > 180))
        if ys.size:
            curve[x] = float(ys[0])

    x_values = np.arange(image.width)
    valid = np.isfinite(curve) & (x_values >= GRAPH_X_ZERO) & (x_values <= GRAPH_X_RIGHT)
    if int(valid.sum()) < 1800:
        raise RuntimeError("Не удалось надёжно выделить линию АЧХ на снимке")
    curve = np.interp(x_values, x_values[valid], curve[valid])
    curve = median_filter(curve, size=5, mode="nearest")

    plateau = float(np.median(curve[fx(3000.0) : fx(4500.0)]))
    stop_y = plateau + (-20.0 * math.log10(STOP_LEVEL)) * PX_PER_DB
    cutoff_y = plateau + (-20.0 * math.log10(0.5)) * PX_PER_DB
    pass_y = plateau + (-20.0 * math.log10(PASS_LEVEL)) * PX_PER_DB

    x_stop = _first_descending_crossing(curve, stop_y)
    x_cutoff = _first_descending_crossing(curve, cutoff_y)
    x_pass = _first_descending_crossing(curve, pass_y)

    cursor_drop_db = max(0.0, (float(curve[GRAPH_X_CURSOR]) - plateau) / PX_PER_DB)
    cursor_ratio = 10.0 ** (-cursor_drop_db / 20.0)
    result = GraphMeasurements(
        curve_y=curve,
        plateau_y=plateau,
        stop_y=stop_y,
        cutoff_y=cutoff_y,
        pass_y=pass_y,
        f_stop=xf(x_stop),
        f_cutoff=xf(x_cutoff),
        f_pass=xf(x_pass),
        cursor_ratio=cursor_ratio,
    )

    # Защита от случайной подмены исходного снимка или неверной калибровки.
    assert 995.0 <= result.f_stop <= 1020.0
    assert 1740.0 <= result.f_cutoff <= 1780.0
    assert 2340.0 <= result.f_pass <= 2400.0
    assert abs(xf(GRAPH_X_CURSOR) - GRAPH_CURSOR_HZ) < 0.01
    return result


# ---------------------------------------------------------------------------
# Разметка АЧХ
# ---------------------------------------------------------------------------


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


def dashed_line(draw: ImageDraw.ImageDraw, xy, *, fill, width=4, dash=16, gap=10):
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


def plain_label(
    draw: ImageDraw.ImageDraw,
    position,
    text,
    *,
    color,
    text_font,
    anchor="mm",
    align="center",
    stroke=4,
):
    draw.multiline_text(
        position,
        text,
        font=text_font,
        fill=color,
        anchor=anchor,
        align=align,
        spacing=4,
        stroke_width=stroke,
        stroke_fill=WHITE,
    )


def marker(draw: ImageDraw.ImageDraw, x: int, y: int, color, radius=9):
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=WHITE,
        outline=color,
        width=4,
    )


def double_arrow(draw: ImageDraw.ImageDraw, x1: int, x2: int, y: int, *, color):
    draw.line((x1, y, x2, y), fill=color, width=6)
    head = 16
    draw.polygon(((x1, y), (x1 + head, y - 8), (x1 + head, y + 8)), fill=color)
    draw.polygon(((x2, y), (x2 - head, y - 8), (x2 - head, y + 8)), fill=color)


def mark_amplitude_response(
    source_image: Image.Image, measurements: GraphMeasurements
) -> bytes:
    image = source_image.convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    x_f3 = fx(F3)
    x_f1 = fx(F1)
    x_stop = fx(measurements.f_stop)
    x_cutoff = fx(measurements.f_cutoff)
    x_pass = fx(measurements.f_pass)

    # Полосы по требованиям варианта. ПП продолжается до Fд/2 = 5300 Гц,
    # но присланный снимок заканчивается на отметке 4893,70 Гц.
    band_y = 50
    draw.line((GRAPH_X_ZERO, band_y, x_f3, band_y), fill=RED, width=9)
    double_arrow(draw, x_f3, x_f1, band_y, color=GRAY)
    draw.line((x_f1, band_y, GRAPH_X_RIGHT, band_y), fill=BLUE, width=9)

    dashed_line(
        draw,
        (x_f3, 70, x_f3, GRAPH_Y_BOTTOM),
        fill=RED,
        width=4,
        dash=20,
        gap=13,
    )
    dashed_line(
        draw,
        (x_f1, 70, x_f1, GRAPH_Y_BOTTOM),
        fill=BLUE,
        width=4,
        dash=20,
        gap=13,
    )

    band_font = font(25, bold=True)
    plain_label(
        draw,
        ((GRAPH_X_ZERO + x_f3) // 2, 31),
        "ПЗ: 0–1005 Гц",
        color=RED,
        text_font=band_font,
    )
    plain_label(
        draw,
        ((x_f3 + x_f1) // 2, 31),
        "переходная: 1005–2520 Гц",
        color=GRAY,
        text_font=font(22, bold=True),
    )
    plain_label(
        draw,
        ((x_f1 + GRAPH_X_RIGHT) // 2, 31),
        "ПП: f ≥ 2520 Гц",
        color=BLUE,
        text_font=band_font,
    )

    # Фактические пересечения, снятые с кривой относительно уровня в ПП.
    marker(draw, x_stop, round(measurements.stop_y), RED)
    marker(draw, x_cutoff, round(measurements.cutoff_y), GRAY)
    marker(draw, x_pass, round(measurements.pass_y), BLUE)

    value_font = font(24, bold=True)
    plain_label(
        draw,
        (210, 530),
        f"f₃ ≈ {measurements.f_stop:.0f} Гц\n−40 дБ от уровня ПП",
        color=RED,
        text_font=value_font,
    )
    draw.line((335, 545, x_stop - 10, round(measurements.stop_y) - 8), fill=RED, width=3)

    plain_label(
        draw,
        (650, 315),
        f"Fc ≈ {measurements.f_cutoff:.0f} Гц",
        color=GRAY,
        text_font=value_font,
    )
    draw.line((675, 295, x_cutoff - 5, round(measurements.cutoff_y) + 10), fill=GRAY, width=3)

    plain_label(
        draw,
        (1120, 145),
        f"f₁ ≈ {measurements.f_pass:.0f} Гц\nуровень 0,95",
        color=BLUE,
        text_font=value_font,
    )
    draw.line((1035, 165, x_pass + 8, round(measurements.pass_y) - 8), fill=BLUE, width=3)

    result = Image.alpha_composite(image, layer).convert("RGB")
    output = io.BytesIO()
    result.save(output, format="PNG", optimize=True)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Правка DOCX
# ---------------------------------------------------------------------------


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace("-", "−").replace(".", ",")


def add_text(
    anchor: Paragraph,
    text: str,
    *,
    heading=False,
    center=False,
    bullet=False,
    no_indent=False,
    before=0,
    after=0,
) -> Paragraph:
    paragraph = anchor.insert_paragraph_before()
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Twips(0 if center or heading or no_indent else 709)
    fmt.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
        if center
        else WD_ALIGN_PARAGRAPH.LEFT
        if heading
        else WD_ALIGN_PARAGRAPH.JUSTIFY
    )
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    if bullet:
        fmt.left_indent = Twips(709)
        fmt.first_line_indent = Twips(-360)
    if heading:
        fmt.keep_with_next = True
    run = paragraph.add_run(text)
    run.bold = heading
    return paragraph


def replace_paragraph_text(paragraph: Paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    for run in paragraph.runs:
        run.text = ""
    paragraph.runs[0].text = text


def replace_figure_8(doc: Document, annotated_png: bytes) -> None:
    caption = next(
        p for p in doc.paragraphs if p.text.strip().startswith("Рисунок 8")
    )
    image_element = caption._p.getprevious()
    if image_element is None or image_element.tag != qn("w:p"):
        raise RuntimeError("Перед подписью рисунка 8 не найден абзац изображения")
    image_paragraph = Paragraph(image_element, caption._parent)
    if not image_paragraph._p.xpath(".//w:drawing"):
        raise RuntimeError("Перед подписью рисунка 8 нет изображения")

    # Удаляем старый широкий график из абзаца и вставляем присланный снимок без
    # искажения пропорций. Ширина остаётся такой же, как в исходном отчёте.
    for child in list(image_paragraph._p):
        if child.tag != qn("w:pPr"):
            image_paragraph._p.remove(child)
    run = image_paragraph.add_run()
    run.add_picture(io.BytesIO(annotated_png), width=Emu(5_940_425))
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.paragraph_format.keep_with_next = True
    caption.paragraph_format.keep_together = True


def keep_figure_with_caption(
    doc: Document, caption_prefix: str, *, collapse_spacer=False
) -> None:
    caption = next(
        p for p in doc.paragraphs if p.text.strip().startswith(caption_prefix)
    )
    image_element = caption._p.getprevious()
    if image_element is None or image_element.tag != qn("w:p"):
        raise RuntimeError(f"Перед подписью не найден рисунок: {caption_prefix}")
    image_paragraph = Paragraph(image_element, caption._parent)
    if not image_paragraph._p.xpath(".//w:drawing"):
        raise RuntimeError(f"Перед подписью нет изображения: {caption_prefix}")

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


def fix_captions_and_conclusion(doc: Document, measurements: GraphMeasurements) -> None:
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("Рисунок 7 - ИХ цифрового ФВЧ"):
            replace_paragraph_text(
                paragraph, "Рисунок 7 – Экспериментальная ИХ цифрового ФВЧ"
            )
        elif text.startswith("Рисунок 8 - АЧХ цифрового ФВЧ"):
            replace_paragraph_text(
                paragraph,
                "Рисунок 8 – Экспериментальная АЧХ ФВЧ с границами ПП и ПЗ",
            )
        elif text.startswith("Расчётная АЧХ удовлетворяет заданию:"):
            replace_paragraph_text(
                paragraph,
                "Расчётная и экспериментальная АЧХ согласуются: по рисунку 8 "
                f"получены f₃ ≈ {measurements.f_stop:.0f} Гц, "
                f"Fc ≈ {measurements.f_cutoff:.0f} Гц и "
                f"f₁ ≈ {measurements.f_pass:.0f} Гц; требования к ПЗ и ПП "
                "выполнены. Экспериментальная ИХ конечна и симметрична "
                "относительно восьмого отсчёта, что соответствует КИХ-фильтру "
                "порядка 16 с групповой задержкой 8 отсчётов.",
            )

    keep_figure_with_caption(doc, "Рисунок 6")
    keep_figure_with_caption(doc, "Рисунок 7", collapse_spacer=True)
    keep_figure_with_caption(doc, "Рисунок 8")


def build_report(annotated_png: bytes, measurements: GraphMeasurements) -> None:
    doc = Document(str(SOURCE_REPORT))
    if any(p.text.startswith("3. Определение границ") for p in doc.paragraphs):
        raise RuntimeError("В исходном DOCX уже присутствует задание №3")

    replace_figure_8(doc, annotated_png)
    anchor = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")
    anchor.paragraph_format.keep_with_next = True

    # ------------------------------- задание №3 -------------------------------
    add_text(
        anchor,
        "3. Определение границ полосы пропускания и полосы задержания по АЧХ",
        heading=True,
        before=12,
        after=6,
    )
    add_text(
        anchor,
        "Для ФВЧ варианта 12 по домашнему заданию полоса задержания должна "
        "занимать 0…1005 Гц, переходная полоса — 1005…2520 Гц, а полоса "
        "пропускания — 2520…5300 Гц. Эти интервалы отмечены на рисунке 8 "
        "красным, серым и синим цветами соответственно.",
    )
    add_text(
        anchor,
        "Логарифмический график имеет общий вертикальный сдвиг: установившийся "
        "уровень в ПП находится примерно на отметке −72 дБ. Поэтому границы "
        "определяются относительно этого уровня: f₃ — при ослаблении 40 дБ "
        "(|H|/HПП = 0,01), f₁ — при снижении на 0,446 дБ "
        "(|H|/HПП = 0,95), а Fc — при снижении на 6,02 дБ "
        "(|H|/HПП = 0,5). Абсолютный сдвиг кривой на найденные частоты не влияет.",
    )
    add_text(
        anchor,
        f"По пересечениям на рисунке 8 получены f₃ ≈ {measurements.f_stop:.0f} Гц, "
        f"Fc ≈ {measurements.f_cutoff:.0f} Гц и f₁ ≈ "
        f"{measurements.f_pass:.0f} Гц. Красный курсор установлен на "
        f"{num(GRAPH_CURSOR_HZ, 2)} Гц; в этой точке относительный уровень "
        f"составляет около {num(measurements.cursor_ratio, 3)}, то есть уже "
        "превышает нижний допуск ПП 0,95.",
    )

    stop_diff = abs(measurements.f_stop - F_STOP_CALC)
    cutoff_diff = abs(measurements.f_cutoff - F_CUTOFF_CALC)
    pass_diff = abs(measurements.f_pass - F_PASS_CALC)
    add_text(
        anchor,
        f"Расчётная АЧХ даёт f₃ = {num(F_STOP_CALC, 2)} Гц, "
        f"Fc = {num(F_CUTOFF_CALC, 2)} Гц и f₁ = {num(F_PASS_CALC, 2)} Гц. "
        f"Расхождение с экспериментальной АЧХ составляет {num(stop_diff, 1)} Гц "
        f"({num(stop_diff / F_STOP_CALC * 100.0, 2)} %) для f₃, "
        f"{num(cutoff_diff, 1)} Гц "
        f"({num(cutoff_diff / F_CUTOFF_CALC * 100.0, 2)} %) для Fc и "
        f"{num(pass_diff, 1)} Гц "
        f"({num(pass_diff / F_PASS_CALC * 100.0, 2)} %) для f₁. "
        f"Экспериментальная граница ПЗ ({measurements.f_stop:.0f} Гц) не ниже "
        f"заданной F₃ = {F3:.0f} Гц, а граница ПП "
        f"({measurements.f_pass:.0f} Гц) ниже заданной F₁ = {F1:.0f} Гц. "
        "Следовательно, на заданных интервалах требования к ПЗ и ПП выполняются.",
    )

    # ------------------------------- задание №4 -------------------------------
    add_text(
        anchor,
        "4. Анализ экспериментальной ИХ и сравнение с расчётом",
        heading=True,
        before=12,
        after=6,
    )
    add_text(
        anchor,
        "На рисунке 7 ИХ имеет конечную длительность и симметрична относительно "
        "центрального, восьмого, отсчёта. Наблюдаются один основной положительный "
        "максимум и симметричные боковые лепестки обоих знаков. Такой характер "
        "соответствует линейно-фазовому КИХ-фильтру верхних частот I типа "
        "порядка R = 16 и длины N = 17.",
    )
    add_text(
        anchor,
        "По домашнему расчёту центральный коэффициент b(8) = 0,66745283; "
        "ближайшая отрицательная пара b(7) = b(9) = −0,26921926, следующая "
        "пара b(6) = b(10) = −0,12635967, положительная пара "
        "b(4) = b(12) = 0,04715958, крайние коэффициенты "
        "b(0) = b(16) = −0,00515576. На рисунке совпадают положение максимума, "
        "симметрия, знаки и относительный порядок величин лепестков. Поскольку "
        "вертикальная шкала экспериментальной ИХ не подписана, точные амплитуды "
        "по рисунку не приписываются, а берутся из расчётной таблицы 2.",
    )
    add_text(
        anchor,
        f"Равенство b(i) = b(16 − i) обеспечивает линейную ФЧХ и групповую "
        f"задержку R/2 = 8 отсчётов, то есть {num(GROUP_DELAY_MS, 3)} мс при "
        f"Fд = {FD:.0f} Гц. Дополнительно Σb(i) = {num(SUM_B, 7)} ≈ 0, а "
        f"|Σb(i)(−1)ⁱ| = {num(abs(ALT_SUM_B), 7)} ≈ 1: постоянная составляющая "
        "подавляется, а область высоких частот пропускается. Таким образом, "
        "характер экспериментальной ИХ соответствует домашнему расчёту.",
    )

    fix_captions_and_conclusion(doc, measurements)
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        suffix=".docx", delete=False, dir=str(CORRECTED_DIR)
    ) as tmp:
        tmp_path = Path(tmp.name)
    package_path = tmp_path.with_suffix(".new.docx")
    try:
        doc.save(str(tmp_path))
        # Повторная упаковка с фиксированным методом сжатия одновременно служит
        # проверкой всех частей DOCX и не меняет содержимое исходного документа.
        with ZipFile(tmp_path, "r") as source, ZipFile(
            package_path, "w", compression=ZIP_DEFLATED
        ) as target:
            for item in source.infolist():
                target.writestr(item, source.read(item.filename))
        with ZipFile(package_path, "r") as check:
            bad = check.testzip()
            if bad is not None:
                raise RuntimeError(f"Повреждён элемент DOCX: {bad}")
        shutil.move(str(package_path), str(OUTPUT_REPORT))
        OUTPUT_REPORT.chmod(0o644)
    finally:
        tmp_path.unlink(missing_ok=True)
        package_path.unlink(missing_ok=True)


def validate_output(annotated_png: bytes, measurements: GraphMeasurements) -> None:
    doc = Document(str(OUTPUT_REPORT))
    texts = [p.text for p in doc.paragraphs]
    all_text = "\n".join(texts)
    assert sum(t.startswith("3. Определение границ") for t in texts) == 1
    assert sum(t.startswith("4. Анализ экспериментальной ИХ") for t in texts) == 1
    assert "Экспериментальная АЧХ ФВЧ с границами ПП и ПЗ" in all_text
    assert f"f₃ ≈ {measurements.f_stop:.0f} Гц" in all_text
    assert f"f₁ ≈ {measurements.f_pass:.0f} Гц" in all_text
    assert "2,409 кГц" not in all_text
    assert "Таблица 3" not in all_text
    # Сравнение в задании №3 оформлено текстом; остаются две исходные таблицы.
    assert len(doc.tables) == 2

    caption = next(p for p in doc.paragraphs if p.text.startswith("Рисунок 8"))
    image_element = caption._p.getprevious()
    image_paragraph = Paragraph(image_element, caption._parent)
    blips = image_paragraph._p.xpath(".//a:blip")
    assert len(blips) == 1
    relationship_id = blips[0].get(qn("r:embed"))
    assert image_paragraph.part.related_parts[relationship_id].blob == annotated_png
    extent = image_paragraph._p.xpath(".//wp:extent")[0]
    width = int(extent.get("cx"))
    height = int(extent.get("cy"))
    assert abs(width / height - GRAPH_SIZE[0] / GRAPH_SIZE[1]) < 0.01

    assert ANNOTATED_PNG.read_bytes() == annotated_png
    with ZipFile(OUTPUT_REPORT, "r") as package:
        assert package.testzip() is None


def main() -> None:
    for required in (SOURCE_REPORT, SOURCE_ACH, DATA_FILE):
        if not required.exists():
            raise FileNotFoundError(required)

    report_digest = sha256(SOURCE_REPORT.read_bytes()).digest()
    ach_digest = sha256(SOURCE_ACH.read_bytes()).digest()
    source_image = Image.open(SOURCE_ACH).convert("RGB")
    measurements = analyse_graph(source_image)
    annotated_png = mark_amplitude_response(source_image, measurements)

    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_PNG.write_bytes(annotated_png)
    build_report(annotated_png, measurements)
    validate_output(annotated_png, measurements)

    assert sha256(SOURCE_REPORT.read_bytes()).digest() == report_digest
    assert sha256(SOURCE_ACH.read_bytes()).digest() == ach_digest

    print(f"Исходный отчёт сохранён без изменений: {SOURCE_REPORT}")
    print(f"Исходный снимок сохранён без изменений: {SOURCE_ACH}")
    print(f"Исправленный отчёт: {OUTPUT_REPORT}")
    print(f"Размеченная АЧХ: {ANNOTATED_PNG}")
    print(
        "По новому снимку: "
        f"f₃ = {measurements.f_stop:.2f} Гц; "
        f"Fc = {measurements.f_cutoff:.2f} Гц; "
        f"f₁ = {measurements.f_pass:.2f} Гц"
    )
    print(
        "По расчётной АЧХ: "
        f"f₃ = {F_STOP_CALC:.2f} Гц; "
        f"Fc = {F_CUTOFF_CALC:.2f} Гц; "
        f"f₁ = {F_PASS_CALC:.2f} Гц"
    )


if __name__ == "__main__":
    main()
