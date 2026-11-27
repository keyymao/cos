#!/usr/bin/env python3
"""Дорабатывает отчёт ЛР №6 (вариант 12 / зачётка 06).

Скрипт создаёт отдельную исправленную копию, не изменяя загруженный DOCX:

1. отмечает ПЗ, ПП и переходную полосу на АЧХ, снятой при Fд = 10600 Гц;
2. определяет по рисунку граничные частоты на уровнях 0,01, 0,5 и 0,95;
3. заново добавляет лабораторные задания №3 и №4 под полученные значения;
4. уточняет подписи экспериментальных ИХ и АЧХ и дополняет вывод.

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
SOURCE_REPORT = CURRENT_DIR / "Копировать Лабораторная_работа_№6_вариант_12.docx"
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


# Контрольные пересечения расчётной АЧХ по коэффициентам таблицы 2.
F_STOP_CALC = crossing(STOP_LEVEL, 900.0, 1150.0)       # 1007,12 Гц
F_CUTOFF_CALC = crossing(0.5, 1600.0, 1900.0)           # 1762,19 Гц
F_PASS_CALC = crossing(PASS_LEVEL, 2200.0, 2500.0)      # 2360,48 Гц
GROUP_DELAY_MS = float(DATA["group_delay"]) / FD * 1000.0
SUM_B = float(np.sum(B))
ALT_SUM_B = float(np.sum(B * (-1.0) ** np.arange(B.size)))

# Значения, снятые непосредственно с нового рисунка при Fд = 10600 Гц.
# Синий курсор установлен на границе ПП и показывает 2,409 кГц; уровни
# 0,01 и 0,5 отсчитаны относительно установившегося уровня в ПП.
F_STOP_GRAPH = 990.0
F_CUTOFF_GRAPH = 1740.0
F_PASS_GRAPH = 2409.0
TRANSITION_SPEC = F1 - F3
TRANSITION_GRAPH = F_PASS_GRAPH - F_STOP_GRAPH


def num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Привязка нового рисунка АЧХ к частотной оси
# ---------------------------------------------------------------------------

# Курсор на рисунке показывает 2,409 кГц при x = 1560. Частотная шкала уже
# соответствует Fд = 10600 Гц, поэтому дополнительный пересчёт не требуется.
GRAPH_CURSOR_HZ = 2409.0
GRAPH_CURSOR_X = 1560
GRAPH_X_RIGHT = 2061
GRAPH_Y_BOTTOM = 1454
GRAPH_Y_UNITY = 411.0       # установившийся уровень |H| ≈ 1 в ПП
PX_PER_DB = 9.76            # 10 дБ ≈ 97,6 пикселя

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
GRAY = (75, 85, 95, 255)
WHITE = (255, 255, 255, 242)


def fx(frequency: float) -> int:
    """Переводит частоту в координату x по курсору на рисунке 8."""
    return round(frequency / GRAPH_CURSOR_HZ * GRAPH_CURSOR_X)


def dy(attenuation_db: float) -> int:
    return round(GRAPH_Y_UNITY + attenuation_db * PX_PER_DB)


X_F3_SPEC = fx(F3)
X_F1_SPEC = fx(F1)
X_STOP_GRAPH = fx(F_STOP_GRAPH)
X_CUTOFF_GRAPH = fx(F_CUTOFF_GRAPH)
X_PASS_GRAPH = fx(F_PASS_GRAPH)
Y_095 = dy(-20.0 * math.log10(PASS_LEVEL))
Y_050 = dy(-20.0 * math.log10(0.5))
Y_40 = dy(40.0)


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
        width=max(4, radius // 2),
    )


def double_arrow(draw, x1, x2, y, *, color, width=3, head=12):
    draw.line((x1, y, x2, y), fill=color, width=width)
    draw.polygon(((x1, y), (x1 + head, y - head // 2), (x1 + head, y + head // 2)), fill=color)
    draw.polygon(((x2, y), (x2 - head, y - head // 2), (x2 - head, y + head // 2)), fill=color)


def mark_amplitude_response(source: bytes) -> tuple[bytes, bytes]:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    if image.size != (2062, 1455):
        raise RuntimeError(f"Неожиданный размер рисунка АЧХ: {image.size}")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Полосы показаны короткими линиями в свободной верхней части рисунка.
    band_y = 165
    draw.line((0, band_y, X_F3_SPEC, band_y), fill=RED, width=9)
    double_arrow(draw, X_F3_SPEC, X_F1_SPEC, band_y, color=GRAY, width=5, head=17)
    draw.line((X_F1_SPEC, band_y, GRAPH_X_RIGHT, band_y), fill=BLUE, width=9)

    # Сплошные линии — значения, снятые с рисунка; пунктиры — F₁ и Fc по расчёту.
    draw.line((X_STOP_GRAPH, 205, X_STOP_GRAPH, GRAPH_Y_BOTTOM), fill=RED, width=8)
    draw.line((X_PASS_GRAPH, 205, X_PASS_GRAPH, GRAPH_Y_BOTTOM), fill=BLUE, width=8)
    dashed_line(
        draw,
        (X_F1_SPEC, 205, X_F1_SPEC, GRAPH_Y_BOTTOM),
        fill=BLUE,
        width=5,
        dash=23,
        gap=14,
    )
    dashed_line(
        draw,
        (X_CUTOFF_GRAPH, 205, X_CUTOFF_GRAPH, GRAPH_Y_BOTTOM),
        fill=GRAY,
        width=5,
        dash=20,
        gap=14,
    )

    draw.line((0, Y_40, X_STOP_GRAPH, Y_40), fill=RED, width=7)
    draw.line((X_PASS_GRAPH, Y_095, GRAPH_X_RIGHT, Y_095), fill=BLUE, width=7)

    marker(draw, X_STOP_GRAPH, Y_40, RED, radius=11)
    marker(draw, X_CUTOFF_GRAPH, Y_050, GRAY, radius=11)
    marker(draw, X_PASS_GRAPH, Y_095, BLUE, radius=11)

    f_band = font(31, bold=True)
    f_value = font(29, bold=True)

    plain_label(
        draw,
        (X_F3_SPEC // 2, 110),
        "ПЗ  0…1005 Гц",
        color=RED,
        text_font=f_band,
        anchor="mm",
        align="center",
        stroke=5,
    )
    plain_label(
        draw,
        ((X_F3_SPEC + X_F1_SPEC) // 2, 110),
        "переходная  1005…2520 Гц",
        color=GRAY,
        text_font=font(27, bold=True),
        anchor="mm",
        align="center",
        stroke=5,
    )
    plain_label(
        draw,
        ((X_F1_SPEC + GRAPH_X_RIGHT) // 2, 110),
        "ПП  f ≥ 2520 Гц",
        color=BLUE,
        text_font=f_band,
        anchor="mm",
        align="center",
        stroke=5,
    )

    plain_label(
        draw,
        (410, 715),
        "f₃ ≈ 0,99 кГц\n|H| = 0,01",
        color=RED,
        text_font=f_value,
        anchor="mm",
        align="center",
        stroke=5,
    )
    plain_label(
        draw,
        (X_CUTOFF_GRAPH, 350),
        "Fc ≈ 1,74 кГц",
        color=GRAY,
        text_font=f_value,
        anchor="mm",
        align="center",
        stroke=5,
    )
    plain_label(
        draw,
        (1780, 310),
        "f₁ ≈ 2,409 кГц   |H| = 0,95",
        color=BLUE,
        text_font=f_value,
        anchor="mm",
        align="center",
        stroke=5,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    png = io.BytesIO()
    jpeg = io.BytesIO()
    result.save(png, format="PNG", optimize=True)
    result.save(jpeg, format="JPEG", quality=95, subsampling=0)
    return png.getvalue(), jpeg.getvalue()


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
            if p.runs:
                p.runs[-1].text = p.runs[-1].text.rstrip()
            p.add_run(
                " По рисунку 8 получены f₃ ≈ 0,99 кГц, Fc ≈ 1,74 кГц и "
                "f₁ ≈ 2,409 кГц. На рисунке 7 видны 17 симметричных отсчётов "
                "с максимумом b(8) = 0,66745283, что соответствует расчёту."
            )

    keep_figure_with_caption(doc, "Рисунок 6")
    keep_figure_with_caption(doc, "Рисунок 7", collapse_spacer=True)
    keep_figure_with_caption(doc, "Рисунок 8")


def build_report(annotated_jpeg: bytes) -> None:
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
        "По рисунку 8 определяем границы полос по заданным уровням. Для ПЗ берём "
        "|H| = 0,01, что соответствует ослаблению 40 дБ относительно уровня в ПП. "
        "Для ПП используется уровень |H| = 0,95. Частотная ось построена при "
        "Fд = 10600 Гц, поэтому значения считываются с рисунка без пересчёта.",
    )
    add_text(
        doc,
        anchor,
        "– граница полосы задержания по уровню |H| = 0,01: "
        "f₃ ≈ 0,99 кГц (990 Гц);",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        "– граница полосы пропускания по уровню |H| = 0,95: "
        "f₁ ≈ 2,409 кГц;",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        "– частота среза по уровню |H| = 0,5: Fc ≈ 1,74 кГц.",
        bullet=True,
    )
    add_text(
        doc,
        anchor,
        f"В домашнем расчёте получены F₃ = {F3:.0f} Гц, F₁ = {F1:.0f} Гц и "
        f"Fc = {num(FC, 1)} Гц. По рисунку граница ПЗ ниже расчётной на "
        f"{abs(F_STOP_GRAPH - F3):.0f} Гц (1,5 %), граница ПП — на "
        f"{abs(F_PASS_GRAPH - F1):.0f} Гц (4,4 %), а частота среза — на "
        f"{num(abs(F_CUTOFF_GRAPH - FC), 1)} Гц (1,3 %). Ширина переходной полосы "
        f"составляет примерно {TRANSITION_GRAPH:.0f} Гц вместо {TRANSITION_SPEC:.0f} Гц, "
        f"то есть она уже на {TRANSITION_SPEC - TRANSITION_GRAPH:.0f} Гц. "
        "Расхождение небольшое и связано с точностью снятия значений по рисунку.",
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
        "На рисунке 7 виден один основной положительный отсчёт и симметричные "
        "отрицательные лепестки по обе стороны от него. ИХ заканчивается после "
        "семнадцатого отсчёта, поэтому фильтр является КИХ-фильтром порядка R = 16.",
    )
    add_text(
        doc,
        anchor,
        "По расчёту центральный коэффициент b(8) = 0,66745283, соседние коэффициенты "
        "b(7) = b(9) = −0,26921926, b(6) = b(10) = −0,12635967, а крайние "
        "b(0) = b(16) = −0,00515576. На рисунке положение максимума, знаки лепестков "
        "и симметрия совпадают с этими значениями. Точные амплитуды не снимаются, "
        "так как вертикальная шкала не подписана.",
    )
    add_text(
        doc,
        anchor,
        f"Симметрия b(i) = b(16 − i) обеспечивает линейную ФЧХ и задержку "
        f"8 отсчётов ({num(GROUP_DELAY_MS, 3)} мс). Значения "
        f"Σb(i) = {num(SUM_B, 7)} ≈ 0 и |Σb(i)(−1)ⁱ| = "
        f"{num(abs(ALT_SUM_B), 7)} ≈ 1 подтверждают подавление постоянной "
        "составляющей и пропускание высоких частот. Характер ИХ на рисунке 7 "
        "соответствует домашнему расчёту.",
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
            if "word/media/image6.jpeg" not in names:
                raise RuntimeError("В сохранённом DOCX не найдена часть image6.jpeg")
            for item in zin.infolist():
                data = annotated_jpeg if item.filename == "word/media/image6.jpeg" else zin.read(item.filename)
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


def validate_output(annotated_png: bytes, annotated_jpeg: bytes) -> None:
    doc = Document(str(OUTPUT_REPORT))
    texts = [p.text for p in doc.paragraphs]
    full_text = "\n".join(texts).lower()
    assert sum(t.startswith("3. Определение граничных частот") for t in texts) == 1
    assert sum(t.startswith("4. Анализ характера ИХ") for t in texts) == 1
    assert any("с отмеченными ПП и ПЗ" in t for t in texts)
    assert "2,409 кГц" in "\n".join(texts)
    assert "скриншот" not in full_text
    assert "48 кГц" not in full_text
    # Новых таблиц нет: остаются только две исходные расчётные таблицы.
    assert len(doc.tables) == 2

    conclusion = next(p for p in doc.paragraphs if p.text.strip() == "ВЫВОД")
    assert conclusion.paragraph_format.keep_with_next is True
    for caption_prefix in ("Рисунок 6", "Рисунок 7", "Рисунок 8"):
        caption = next(p for p in doc.paragraphs if p.text.strip().startswith(caption_prefix))
        image_paragraph = caption._p.getprevious()
        assert image_paragraph is not None and image_paragraph.xpath(".//w:drawing")
        assert image_paragraph.xpath("./w:pPr/w:keepNext")

    assert ANNOTATED_PNG.read_bytes() == annotated_png
    with ZipFile(OUTPUT_REPORT, "r") as package:
        assert package.testzip() is None
        assert package.read("word/media/image6.jpeg") == annotated_jpeg


def main() -> None:
    if not SOURCE_REPORT.exists():
        raise FileNotFoundError(SOURCE_REPORT)
    source_digest = sha256(SOURCE_REPORT.read_bytes()).digest()
    with ZipFile(SOURCE_REPORT, "r") as docx:
        source_jpeg = docx.read("word/media/image6.jpeg")
    annotated_png, annotated_jpeg = mark_amplitude_response(source_jpeg)
    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    ANNOTATED_PNG.write_bytes(annotated_png)
    build_report(annotated_jpeg)
    validate_output(annotated_png, annotated_jpeg)
    assert sha256(SOURCE_REPORT.read_bytes()).digest() == source_digest

    print(f"Исходный отчёт сохранён без изменений: {SOURCE_REPORT}")
    print(f"Исправленный отчёт: {OUTPUT_REPORT}")
    print(f"Размеченная АЧХ: {ANNOTATED_PNG}")
    print(
        f"По рисунку: f₃ ≈ {F_STOP_GRAPH:.0f} Гц; "
        f"f₁ ≈ {F_PASS_GRAPH:.0f} Гц; Fc ≈ {F_CUTOFF_GRAPH:.0f} Гц"
    )
    print(
        f"По расчёту: f₃ = {F_STOP_CALC:.2f} Гц; "
        f"f₁ = {F_PASS_CALC:.2f} Гц; Fc = {F_CUTOFF_CALC:.2f} Гц"
    )


if __name__ == "__main__":
    main()
