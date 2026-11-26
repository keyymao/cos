#!/usr/bin/env python3
"""Дорабатывает отчёт ЛР №6 (вариант 12 / зачётка 06).

Скрипт создаёт отдельную исправленную копию, не изменяя загруженный DOCX:

1. рассчитывает фактические границы ПП/ПЗ по уровням 0,95 и 0,01;
2. аккуратно размечает экспериментальную АЧХ линиями без перекрытия кривой;
3. учитывает, что скриншот «Спектр-2» снят при Fд ≈ 48 кГц, тогда как
   домашний расчёт выполнен для Fд = 10600 Гц;
4. добавляет лабораторные задания №3 и №4 в компактном текстовом виде;
5. уточняет подписи экспериментальных ИХ и АЧХ и дополняет вывод.

Зависимости: numpy scipy pillow python-docx.
"""

from __future__ import annotations

import io
import json
import math
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
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
TRANSITION_SPEC = F1 - F3
TRANSITION_REAL = F_PASS_REAL - F_STOP_REAL
TRANSITION_MARGIN = TRANSITION_SPEC - TRANSITION_REAL
GROUP_DELAY_MS = float(DATA["group_delay"]) / FD * 1000.0
SUM_B = float(np.sum(B))
ALT_SUM_B = float(np.sum(B * (-1.0) ** np.arange(B.size)))

# Для текста отчёта график читается примерно до 10 Гц.
F_STOP_TXT = round(F_STOP_REAL, -1)      # 1010 Гц
F_PASS_TXT = round(F_PASS_REAL, -1)      # 2360 Гц
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

Y_BOT = 882
Y_REF = 250.04              # максимум АЧХ в ПП по аппроксимации границы заливки
PX_PER_DB = 5.868            # большая клетка 10 дБ ≈ 58,68 пикселя

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
GRAY = (75, 85, 95, 255)
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
Y_40 = dy(40.0)
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


def plain_label(
    draw,
    position,
    text,
    *,
    color,
    text_font,
    anchor="la",
    align="left",
    spacing=4,
    stroke=3,
):
    """Подпись без рамки с тонким белым ореолом, как в предыдущей работе."""
    draw.multiline_text(
        position,
        text,
        font=text_font,
        fill=color,
        anchor=anchor,
        align=align,
        spacing=spacing,
        stroke_width=stroke,
        stroke_fill=WHITE,
    )


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

    # Полосы показаны только короткими цветными линиями в свободной верхней части:
    # так разметка остаётся заметной, но не закрывает исходную кривую.
    band_y = 100
    draw.line((0, band_y, X_F3, band_y), fill=RED, width=6)
    double_arrow(draw, X_F3, X_F1, band_y, color=GRAY, width=3, head=11)
    draw.line((X_F1, band_y, SCREEN_X_RIGHT, band_y), fill=BLUE, width=6)

    # Сплошные линии — фактические границы по уровням, пунктир — F₁ по ТЗ и Fc.
    draw.line((X_F_STOP_REAL, 120, X_F_STOP_REAL, Y_BOT), fill=RED, width=5)
    draw.line((X_F_PASS_REAL, 120, X_F_PASS_REAL, Y_BOT), fill=BLUE, width=5)
    dashed_line(draw, (X_F1, 120, X_F1, Y_BOT), fill=BLUE, width=3, dash=14, gap=9)
    dashed_line(draw, (X_FC, 120, X_FC, Y_BOT), fill=GRAY, width=3, dash=12, gap=9)

    # Контрольные уровни относительно максимума АЧХ в ПП.
    draw.line((0, Y_40, X_F_STOP_REAL, Y_40), fill=RED, width=4)
    draw.line((X_F_PASS_REAL, Y_095, SCREEN_X_RIGHT, Y_095), fill=BLUE, width=4)

    marker(draw, X_F_STOP_REAL, Y_40, RED, radius=7)
    marker(draw, X_FC, Y_FC_CURVE, GRAY, radius=7)
    marker(draw, X_F_PASS_REAL, Y_095, BLUE, radius=7)

    f_band = font(19, bold=True)
    f_value = font(18, bold=True)

    plain_label(
        draw,
        ((X_F3 + 0) // 2, 67),
        "ПЗ  0…1005 Гц",
        color=RED,
        text_font=f_band,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        ((X_F3 + X_F1) // 2, 67),
        "переходная  1005…2520 Гц",
        color=GRAY,
        text_font=font(17, bold=True),
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        ((X_F1 + SCREEN_X_RIGHT) // 2, 67),
        "ПП  f ≥ 2520 Гц",
        color=BLUE,
        text_font=f_band,
        anchor="mm",
        align="center",
    )

    # Только три короткие подписи у контрольных точек — без рамок и выносок.
    plain_label(
        draw,
        (255, 430),
        "f₃ ≈ 1007 Гц\n|H| = 0,01",
        color=RED,
        text_font=f_value,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (X_FC, 205),
        "Fc = 1762,5 Гц",
        color=GRAY,
        text_font=f_value,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (1065, 185),
        "f₁ ≈ 2360 Гц   |H| = 0,95",
        color=BLUE,
        text_font=f_value,
        anchor="mm",
        align="center",
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Правка DOCX
# ---------------------------------------------------------------------------


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
    anchor.paragraph_format.keep_with_next = True

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
        "пропускания |H| = 1 − δ₁ = 0,95. Короткие линии сверху показывают ПЗ "
        "(красная), переходную полосу (серая) и ПП (синяя). Сплошные красная и синяя "
        "вертикали с маркерами соответствуют фактическим границам, синий пунктир — "
        "заданной F₁, серый пунктир — частоте среза Fc.",
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
        "На рисунке 7 показаны 17 отсчётов b(0)…b(16); соединяющая их линия является "
        "только интерполяцией. После b(16) отклик равен нулю, что соответствует "
        "КИХ-фильтру порядка R = 16 с 16 линиями задержки и без обратных связей.",
    )
    add_text(
        doc,
        anchor,
        "ИХ зеркально симметрична: центральный максимум b(8) = 0,66745283, соседние "
        "отсчёты b(7) = b(9) = −0,26921926, края b(0) = b(16) = −0,00515576. "
        f"Симметрия b(i) = b(16 − i) даёт линейную ФЧХ и задержку 8 отсчётов, или "
        f"{num(GROUP_DELAY_MS, 3)} мс; максимум на восьмом такте совпадает с расчётом.",
    )
    add_text(
        doc,
        anchor,
        f"Сумма коэффициентов Σb(i) = {num(SUM_B, 7)} ≈ 0 подтверждает подавление "
        f"постоянной составляющей, а |Σb(i)(−1)ⁱ| = {num(abs(ALT_SUM_B), 7)} ≈ 1 — "
        "пропускание высоких частот. Вертикальная шкала осциллограммы не подписана, "
        "поэтому точные амплитуды с неё не снимаются; однако длительность, положение "
        "максимума, симметрия и знаки лепестков совпадают с коэффициентами таблицы 2. "
        "Экспериментальная ИХ подтверждает домашний расчёт.",
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
    # Новых таблиц нет: остаются только две исходные расчётные таблицы.
    assert len(doc.tables) == 2

    conclusion = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")
    assert conclusion.paragraph_format.keep_with_next is True
    for caption_prefix in ("Рисунок 6", "Рисунок 7", "Рисунок 8"):
        caption = next(p for p in doc.paragraphs if p.text.strip().startswith(caption_prefix))
        image_paragraph = caption._p.getprevious()
        assert image_paragraph is not None and image_paragraph.xpath(".//w:drawing")
        assert image_paragraph.xpath("./w:pPr/w:keepNext")

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
