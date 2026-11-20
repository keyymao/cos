#!/usr/bin/env python3
"""Размечает АЧХ ЛР №3 и №4 для варианта 12 / зачётки 06.

Стиль разметки повторяет предоставленные примеры: толстые цветные линии
границ ПП/ПЗ, горизонтальные контрольные уровни, двойная стрелка 40 дБ и
простые подписи без развёрнутых вычислений. Для ЛР №4 дополнительно
вставляется ответ на экспериментальное задание №3.

Исходные DOCX в `лабораторные/текущие/` не изменяются. Исправленные копии
создаются в `лабораторные/исправленые/лаба3/` и `.../лаба4/`.

Зависимость: Pillow (`python3 -m pip install pillow`).
"""

from __future__ import annotations

import argparse
import io
import shutil
import tempfile
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "лабораторные" / "текущие"
CORRECTED = ROOT / "лабораторные" / "исправленые"

# Правая граница частотной оси на всех четырёх скриншотах «Спектр-2».
F_DISPLAY_MAX = 5724.71

# Общие требования варианта 12 / зачётки 06.
F_ANALOG_PASS = 3740.0
F_ANALOG_STOP = 1440.0
A_MAX_DB = 0.4455
A_MIN_DB = 40.0
H_PASS_MIN = 10 ** (-A_MAX_DB / 20.0)  # 0,950003...
H_STOP_MAX = 10 ** (-A_MIN_DB / 20.0)  # 0,01

# ЛР №3: границы ЦФ после обычного билинейного преобразования.
LAB3_F_PASS = 2993.7161618711953
LAB3_F_STOP = 1380.7739127813281
LAB3_A_STOP = 40.07680786291414

# ЛР №4: преобразование с предыскажением.
LAB4_F_PASS = 3740.0
LAB4_F_STOP_40 = 1943.3571413406553
LAB4_A_AT_SPEC = 57.702526343701706
LAB4_H_AT_SPEC = 0.0013027877996048159

PASS = (0, 94, 184, 255)       # синяя ПП
STOP = (204, 38, 48, 255)      # красная ПЗ
SPEC = (145, 91, 0, 255)       # охра: заданная аналоговая граница
DARK = (30, 36, 42, 255)
WHITE = (255, 255, 255, 255)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    """Возвращает шрифт с кириллицей и математическими индексами."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    try:
        return ImageFont.truetype(name, size=size)
    except OSError:
        return ImageFont.load_default()


def is_green(pixel: tuple[int, ...]) -> bool:
    r, g, b = pixel[:3]
    return g > r + 18 and r > b + 18 and g > 120


def green_bounds(image: Image.Image, x: int, radius: int = 2) -> tuple[int, int] | None:
    """Возвращает верхний и нижний зелёный пиксель около абсциссы x."""
    rgb = image.convert("RGB")
    ys: list[int] = []
    for xx in range(max(0, x - radius), min(rgb.width, x + radius + 1)):
        for y in range(0, rgb.height - 8):
            if is_green(rgb.getpixel((xx, y))):
                ys.append(y)
    return (min(ys), max(ys)) if ys else None


def plot_reference(image: Image.Image) -> tuple[int, int]:
    """Определяет единичный уровень ФВЧ и нулевую линию зелёной заливки."""
    bounds = [green_bounds(image, x) for x in range(20, image.width - 20, 12)]
    bounds = [item for item in bounds if item]
    if not bounds:
        raise RuntimeError("Не удалось распознать зелёную АЧХ")
    baseline = max(item[1] for item in bounds)
    high_frequency = [
        green_bounds(image, x)
        for x in range(round(image.width * 0.72), round(image.width * 0.96), 5)
    ]
    tops = sorted(item[0] for item in high_frequency if item)
    if not tops:
        raise RuntimeError("Не удалось распознать уровень в полосе пропускания")
    unity_y = tops[max(0, len(tops) // 20)]
    return unity_y, baseline


def frequency_x(frequency: float, width: int) -> int:
    return round(frequency / F_DISPLAY_MAX * (width - 1))


def curve_y(image: Image.Image, frequency: float) -> int:
    x = frequency_x(frequency, image.width)
    bounds = green_bounds(image, x)
    if not bounds:
        raise RuntimeError(f"Не удалось найти АЧХ около {frequency:.2f} Гц")
    return bounds[0]


def dashed_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int],
    width: int = 4,
    dash: int = 18,
    gap: int = 11,
) -> None:
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
    position: tuple[int, int],
    text: str,
    *,
    color: tuple[int, int, int, int],
    text_font: ImageFont.ImageFont,
    anchor: str = "la",
    align: str = "left",
    spacing: int = 5,
    stroke: int = 4,
) -> None:
    """Рисует подпись без рамки, с белым ореолом для читаемости."""
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


def marker(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    *,
    radius: int = 8,
) -> None:
    width = 4 if radius >= 7 else 3
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=WHITE,
        outline=color,
        width=width,
    )


def double_arrow(
    draw: ImageDraw.ImageDraw,
    x: int,
    y1: int,
    y2: int,
    *,
    color: tuple[int, int, int, int] = DARK,
    width: int = 5,
) -> None:
    """Рисует вертикальную двустороннюю стрелку между двумя уровнями."""
    top, bottom = sorted((y1, y2))
    draw.line((x, top + 12, x, bottom - 12), fill=color, width=width)
    draw.polygon(((x, top), (x - 10, top + 19), (x + 10, top + 19)), fill=color)
    draw.polygon(((x, bottom), (x - 10, bottom - 19), (x + 10, bottom - 19)), fill=color)


def leader(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: tuple[int, int, int, int],
    width: int = 3,
) -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y1, x2, y2), fill=color, width=width)


def finish(image: Image.Image, layer: Image.Image) -> bytes:
    result = Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


def annotate_lab3_log(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _, baseline = plot_reference(image)

    x_stop = frequency_x(LAB3_F_STOP, image.width)
    x_pass = frequency_x(LAB3_F_PASS, image.width)
    y_stop = curve_y(image, LAB3_F_STOP)
    y_pass = curve_y(image, LAB3_F_PASS)

    # Стиль примера: толстые вертикали границ и горизонтальные уровни.
    draw.line((x_stop, 45, x_stop, baseline), fill=STOP, width=6)
    draw.line((x_pass, 45, x_pass, baseline), fill=PASS, width=6)
    draw.line((35, y_stop, x_pass + 120, y_stop), fill=STOP, width=5)
    draw.line((x_stop - 80, y_pass, image.width - 65, y_pass), fill=PASS, width=5)

    arrow_x = round((x_stop + x_pass) / 2)
    double_arrow(draw, arrow_x, y_pass, y_stop)
    marker(draw, x_stop, y_stop, STOP)
    marker(draw, x_pass, y_pass, PASS)

    label_font = font(28, bold=True)
    plain_label(
        draw,
        (arrow_x + 28, round((y_pass + y_stop) / 2)),
        "a = 40 дБ",
        color=DARK,
        text_font=label_font,
        anchor="lm",
    )
    plain_label(
        draw,
        (330, 790),
        "f₃ = 1380,8 Гц (ПЗ)\na ≈ 40,08 дБ",
        color=STOP,
        text_font=label_font,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (1260, 790),
        "f₁ = 2993,7 Гц (ПП)\na = 0,4455 дБ",
        color=PASS,
        text_font=label_font,
        anchor="mm",
        align="center",
    )
    return finish(image, layer)


def annotate_lab3_linear(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    unity_y, baseline = plot_reference(image)
    amplitude = baseline - unity_y

    x_stop = frequency_x(LAB3_F_STOP, image.width)
    x_pass = frequency_x(LAB3_F_PASS, image.width)
    y_stop = round(baseline - H_STOP_MAX * amplitude)
    y_pass = round(baseline - H_PASS_MIN * amplitude)

    draw.line((x_stop, 45, x_stop, baseline), fill=STOP, width=6)
    draw.line((x_pass, 45, x_pass, baseline), fill=PASS, width=6)
    draw.line((35, y_stop, x_pass + 120, y_stop), fill=STOP, width=5)
    draw.line((x_stop - 80, y_pass, image.width - 65, y_pass), fill=PASS, width=5)
    marker(draw, x_stop, y_stop, STOP, radius=6)
    marker(draw, x_pass, y_pass, PASS)

    label_font = font(27, bold=True)
    plain_label(
        draw,
        (250, 760),
        "f₃ = 1380,8 Гц (ПЗ)",
        color=STOP,
        text_font=label_font,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (1240, 730),
        "f₁ = 2993,7 Гц (ПП)",
        color=PASS,
        text_font=label_font,
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (380, y_stop - 30),
        "|H| = 0,01;  a ≈ 40,08 дБ",
        color=STOP,
        text_font=font(24, bold=True),
        anchor="ms",
        align="center",
    )
    plain_label(
        draw,
        (1450, y_pass - 25),
        "|H| ≈ 0,95;  a = 0,4455 дБ",
        color=PASS,
        text_font=font(24, bold=True),
        anchor="ms",
        align="center",
    )
    return finish(image, layer)


def annotate_lab4_log(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    _, baseline = plot_reference(image)

    x_spec = frequency_x(F_ANALOG_STOP, image.width)
    x_stop = frequency_x(LAB4_F_STOP_40, image.width)
    x_pass = frequency_x(LAB4_F_PASS, image.width)
    y_spec = curve_y(image, F_ANALOG_STOP)
    y_stop = curve_y(image, LAB4_F_STOP_40)
    y_pass = curve_y(image, LAB4_F_PASS)

    # Сплошные линии показывают фактические границы по уровням; пунктир — F₃ по ТЗ.
    dashed_line(draw, (x_spec, 42, x_spec, baseline), fill=SPEC, width=4)
    draw.line((x_stop, 42, x_stop, baseline), fill=STOP, width=6)
    draw.line((x_pass, 42, x_pass, baseline), fill=PASS, width=6)
    draw.line((35, y_stop, x_pass + 120, y_stop), fill=STOP, width=5)
    draw.line((x_stop - 70, y_pass, image.width - 60, y_pass), fill=PASS, width=5)

    arrow_x = round((x_stop + x_pass) / 2) - 90
    double_arrow(draw, arrow_x, y_pass, y_stop)
    marker(draw, x_spec, y_spec, SPEC)
    marker(draw, x_stop, y_stop, STOP)
    marker(draw, x_pass, y_pass, PASS)

    plain_label(
        draw,
        (arrow_x + 28, round((y_pass + y_stop) / 2)),
        "a = 40 дБ",
        color=DARK,
        text_font=font(27, bold=True),
        anchor="lm",
    )
    plain_label(
        draw,
        (260, 690),
        "F₃ по ТЗ = 1440 Гц\na ≈ 57,70 дБ",
        color=SPEC,
        text_font=font(25, bold=True),
        anchor="mm",
        align="center",
    )
    leader(draw, (390, 650), (x_spec, y_spec), color=SPEC)
    plain_label(
        draw,
        (760, 750),
        "f₃ ≈ 1943 Гц (ПЗ)\na = 40 дБ",
        color=STOP,
        text_font=font(26, bold=True),
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (1420, 750),
        "f₁ = F₁ по ТЗ = 3740 Гц (ПП)\na = 0,4455 дБ",
        color=PASS,
        text_font=font(25, bold=True),
        anchor="mm",
        align="center",
    )
    return finish(image, layer)


def annotate_lab4_linear(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    unity_y, baseline = plot_reference(image)
    amplitude = baseline - unity_y

    x_spec = frequency_x(F_ANALOG_STOP, image.width)
    x_stop = frequency_x(LAB4_F_STOP_40, image.width)
    x_pass = frequency_x(LAB4_F_PASS, image.width)
    y_spec = round(baseline - LAB4_H_AT_SPEC * amplitude)
    y_stop = round(baseline - H_STOP_MAX * amplitude)
    y_pass = round(baseline - H_PASS_MIN * amplitude)

    dashed_line(draw, (x_spec, 42, x_spec, baseline), fill=SPEC, width=4)
    draw.line((x_stop, 42, x_stop, baseline), fill=STOP, width=6)
    draw.line((x_pass, 42, x_pass, baseline), fill=PASS, width=6)
    draw.line((35, y_stop, x_pass + 120, y_stop), fill=STOP, width=5)
    draw.line((x_stop - 70, y_pass, image.width - 60, y_pass), fill=PASS, width=5)
    marker(draw, x_spec, y_spec, SPEC, radius=5)
    marker(draw, x_stop, y_stop, STOP, radius=6)
    marker(draw, x_pass, y_pass, PASS)

    plain_label(
        draw,
        (245, 685),
        "F₃ по ТЗ = 1440 Гц\na ≈ 57,70 дБ",
        color=SPEC,
        text_font=font(24, bold=True),
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (745, 755),
        "f₃ ≈ 1943 Гц (ПЗ)\n|H| = 0,01;  a = 40 дБ",
        color=STOP,
        text_font=font(24, bold=True),
        anchor="mm",
        align="center",
    )
    plain_label(
        draw,
        (1450, 690),
        "f₁ = F₁ по ТЗ = 3740 Гц (ПП)\n|H| ≈ 0,95;  a = 0,4455 дБ",
        color=PASS,
        text_font=font(24, bold=True),
        anchor="mm",
        align="center",
    )
    return finish(image, layer)


def run_xml(text: str, *, bold: bool = False) -> str:
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        f"{bold_xml}<w:sz w:val=\"28\"/><w:szCs w:val=\"28\"/><w:lang w:val=\"ru-RU\"/>"
        f"</w:rPr><w:t>{escape(text)}</w:t></w:r>"
    )


def paragraph_xml(text: str, *, heading: bool = False, bullet: bool = False) -> str:
    if heading:
        ppr = (
            "<w:pPr><w:keepNext/><w:jc w:val=\"center\"/>"
            '<w:spacing w:before="240" w:after="160" w:line="360" w:lineRule="auto"/>'
            "</w:pPr>"
        )
        return f"<w:p>{ppr}{run_xml(text, bold=True)}</w:p>"
    indent = '<w:ind w:left="709" w:hanging="360"/>' if bullet else '<w:ind w:firstLine="709"/>'
    ppr = (
        f"<w:pPr><w:jc w:val=\"both\"/>{indent}"
        '<w:spacing w:after="0" w:line="360" w:lineRule="auto"/>'
        "</w:pPr>"
    )
    return f"<w:p>{ppr}{run_xml(text)}</w:p>"


def paragraph_start(document_xml: bytes, text_pos: int) -> int:
    """Находит открывающий тег абзаца, не путая его с `<w:pPr>`."""
    position = max(
        document_xml.rfind(b"<w:p ", 0, text_pos),
        document_xml.rfind(b"<w:p>", 0, text_pos),
    )
    if position < 0:
        raise RuntimeError("Не найдено начало требуемого абзаца")
    return position


def add_lab4_assignment(document_xml: bytes) -> bytes:
    """Исправляет порядок масштабов и добавляет экспериментальное задание №3."""
    old_intro = (
        "На рис. 2 и рис. 3 представлены графики АЧХ в линейном и "
        "логарифмическом масштабе соответственно."
    ).encode("utf-8")
    new_intro = (
        "На рис. 2 и рис. 3 представлены графики АЧХ в логарифмическом и "
        "линейном масштабе соответственно."
    ).encode("utf-8")
    if old_intro in document_xml:
        document_xml = document_xml.replace(old_intro, new_intro, 1)

    heading = "3. Определение граничных частот по графику АЧХ"
    if heading.encode("utf-8") in document_xml:
        return document_xml

    marker_text = "ОТВЕТЫ НА КОНТРОЛЬНЫЕ ВОПРОСЫ".encode("utf-8")
    text_pos = document_xml.find(marker_text)
    if text_pos < 0:
        raise RuntimeError("В document.xml не найден раздел контрольных вопросов")
    insert_pos = paragraph_start(document_xml, text_pos)

    paragraphs = [
        paragraph_xml(heading, heading=True),
        paragraph_xml(
            "Граничные частоты определяем по пересечению нормированной АЧХ с контрольными уровнями: "
            "aₘₐₓ = 0,4455 дБ (|H| ≈ 0,95) для полосы пропускания и aₘᵢₙ = 40 дБ "
            "(|H| = 0,01) для полосы задержания."
        ),
        paragraph_xml(
            "– граница полосы пропускания цифрового фильтра составляет f₁ ≈ 3740 Гц;",
            bullet=True,
        ),
        paragraph_xml(
            "– граница полосы задержания по уровню 40 дБ составляет f₃ ≈ 1943 Гц.",
            bullet=True,
        ),
        paragraph_xml("Сравнение с частотами аналогового фильтра по техническому заданию", heading=True),
        paragraph_xml(
            "Граница полосы пропускания совпала с заданной частотой F₁ = 3740 Гц. "
            "Это подтверждает правильность внесённого предыскажения; в ЛР №3 без предыскажения "
            "граница составляла около 2993,7 Гц."
        ),
        paragraph_xml(
            "Для полосы задержания в техническом задании указано F₃ = 1440 Гц, тогда как уровень "
            "40 дБ достигается при f₃ ≈ 1943 Гц. Для ФВЧ это означает, что фактическая полоса "
            "задержания продолжается до более высокой частоты, поэтому заданная граница 1440 Гц "
            "полностью лежит внутри полосы задержания."
        ),
        paragraph_xml(
            "На частоте 1440 Гц ослабление составляет около 57,70 дБ и превышает требуемые "
            "40 дБ на 17,70 дБ. Разность частот равна примерно 503 Гц, то есть 35,0 % "
            "относительно F₃ по техническому заданию."
        ),
        paragraph_xml(
            "Следовательно, предыскажение точно сохранило границу полосы пропускания, а требование "
            "к полосе задержания выполняется с запасом."
        ),
    ]
    fragment = "".join(paragraphs).encode("utf-8")
    return document_xml[:insert_pos] + fragment + document_xml[insert_pos:]


def validate_lab4_xml(document_xml: bytes) -> None:
    root = ET.fromstring(document_xml)
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = list(root.iter(f"{w}p"))
    for paragraph in paragraphs:
        if any(node is not paragraph and node.tag == f"{w}p" for node in paragraph.iter()):
            raise RuntimeError("Некорректный document.xml: один абзац вложен в другой")
    texts = ["".join(node.text or "" for node in p.iter(f"{w}t")) for p in paragraphs]
    heading = "3. Определение граничных частот по графику АЧХ"
    controls = "ОТВЕТЫ НА КОНТРОЛЬНЫЕ ВОПРОСЫ"
    if texts.count(heading) != 1 or texts.count(controls) != 1:
        raise RuntimeError("Раздел задания №3 или контрольных вопросов встречается неверное число раз")
    if texts.index(heading) >= texts.index(controls):
        raise RuntimeError("Задание №3 должно находиться перед контрольными вопросами")
    expected_intro = (
        "На рис. 2 и рис. 3 представлены графики АЧХ в логарифмическом и "
        "линейном масштабе соответственно."
    )
    if texts.count(expected_intro) != 1:
        raise RuntimeError("Не исправлена последовательность масштабов рисунков 2 и 3")


def select_source(lab: str) -> Path:
    candidates = sorted((CURRENT / lab).glob("*вариант_12*.docx"))
    if len(candidates) != 1:
        names = "\n".join(f"  - {p.name}" for p in candidates) or "  (файлы не найдены)"
        raise RuntimeError(f"Ожидался один текущий DOCX варианта 12 в {lab}:\n{names}")
    return candidates[0]


def rebuild_docx(source: Path, destination: Path, replacements: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=destination.parent) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with ZipFile(source, "r") as zin, ZipFile(tmp_path, "w", compression=ZIP_DEFLATED) as zout:
            names = set(zin.namelist())
            missing = set(replacements) - names
            if missing:
                raise RuntimeError(f"В DOCX не найдены элементы: {sorted(missing)}")
            for item in zin.infolist():
                data = replacements.get(item.filename, zin.read(item.filename))
                zout.writestr(item, data)
        with ZipFile(tmp_path, "r") as check:
            bad = check.testzip()
            if bad:
                raise RuntimeError(f"Повреждён элемент DOCX: {bad}")
        shutil.move(tmp_path, destination)
        destination.chmod(0o644)
    finally:
        tmp_path.unlink(missing_ok=True)


def process_lab3(source: Path, output_dir: Path) -> list[Path]:
    with ZipFile(source, "r") as docx:
        log_png = annotate_lab3_log(docx.read("word/media/image3.png"))
        linear_png = annotate_lab3_linear(docx.read("word/media/image4.png"))
    log_path = output_dir / "АЧХ логарифмическая — ЛР3 вариант 12 с отметками.png"
    linear_path = output_dir / "АЧХ линейная — ЛР3 вариант 12 с отметками.png"
    report_path = output_dir / "Лабораторная работа №3 (вариант 12, зачётка 06) — АЧХ с отметками.docx"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(log_png)
    linear_path.write_bytes(linear_png)
    rebuild_docx(
        source,
        report_path,
        {"word/media/image3.png": log_png, "word/media/image4.png": linear_png},
    )
    return [report_path, log_path, linear_path]


def process_lab4(source: Path, output_dir: Path) -> list[Path]:
    with ZipFile(source, "r") as docx:
        log_png = annotate_lab4_log(docx.read("word/media/image2.png"))
        linear_png = annotate_lab4_linear(docx.read("word/media/image3.png"))
        document_xml = add_lab4_assignment(docx.read("word/document.xml"))
        validate_lab4_xml(document_xml)
    log_path = output_dir / "АЧХ логарифмическая — ЛР4 вариант 12 с отметками.png"
    linear_path = output_dir / "АЧХ линейная — ЛР4 вариант 12 с отметками.png"
    report_path = output_dir / "Лабораторная работа №4 (вариант 12, зачётка 06) — исправленная.docx"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(log_png)
    linear_path.write_bytes(linear_png)
    rebuild_docx(
        source,
        report_path,
        {
            "word/media/image2.png": log_png,
            "word/media/image3.png": linear_png,
            "word/document.xml": document_xml,
        },
    )
    return [report_path, log_path, linear_path]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab3-source", type=Path, default=None)
    parser.add_argument("--lab4-source", type=Path, default=None)
    args = parser.parse_args()

    lab3_source = args.lab3_source or select_source("лаба3")
    lab4_source = args.lab4_source or select_source("лаба4")
    outputs = []
    outputs.extend(process_lab3(lab3_source, CORRECTED / "лаба3"))
    outputs.extend(process_lab4(lab4_source, CORRECTED / "лаба4"))

    print(f"Источник ЛР №3: {lab3_source}")
    print(f"Источник ЛР №4: {lab4_source}")
    for output in outputs:
        print(f"Создано: {output}")


if __name__ == "__main__":
    main()
