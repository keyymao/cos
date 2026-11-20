#!/usr/bin/env python3
"""Дорабатывает загруженный отчёт ЛР №4 (вариант 24/53).

Скрипт:
1. извлекает скриншоты логарифмической и линейной АЧХ из DOCX;
2. отмечает граничные частоты и допустимые уровни;
3. добавляет перед выводом ответ на экспериментальное задание №3;
4. сохраняет новую копию в `лабораторные/исправленые/лаба4/`.

Исходный DOCX в `лабораторные/текущие/лаба4/` не изменяется.
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
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба4"
FINAL_DIR = ROOT / "лабораторные" / "исправленые" / "лаба4"

# Ось частот на приложенных скриншотах «Спектр-2».
F_DISPLAY_MAX = 6832.71

# Техническое задание и результат расчёта/снятия АЧХ.
F_PASS = 2220.0          # уровень a_max = 0,4455 дБ
F_STOP = 3261.19         # уровень a_min = 40 дБ
F_STOP_SPEC = 3760.0     # заданная граница ПЗ аналогового фильтра
A_MAX_DB = 0.4455
A_MIN_DB = 40.0
A_AT_STOP_SPEC_DB = 53.35
H_PASS_MIN = 10 ** (-A_MAX_DB / 20.0)  # 0,950003...
H_STOP_MAX = 10 ** (-A_MIN_DB / 20.0)  # 0,01

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
GRAY = (75, 85, 95, 235)
DARK = (30, 40, 50, 255)
WHITE = (255, 255, 255, 238)


def font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
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


def dashed_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float, float, float],
    *,
    fill: tuple[int, int, int, int],
    width: int = 5,
    dash: int = 18,
    gap: int = 10,
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


def label_box(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    color: tuple[int, int, int, int],
    text_font: ImageFont.ImageFont,
    padding: int = 11,
) -> tuple[int, int, int, int]:
    x, y = position
    bbox = draw.multiline_textbbox((x, y), text, font=text_font, spacing=5)
    box = (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding)
    draw.rounded_rectangle(box, radius=10, fill=WHITE, outline=color, width=3)
    draw.multiline_text((x, y), text, font=text_font, fill=color, spacing=5)
    return box


def connector(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: tuple[int, int, int, int],
    width: int = 4,
) -> None:
    """Соединяет подпись с точкой без стрелки: конец всегда точно в маркере."""
    x1, y1 = start
    x2, y2 = end
    elbow = (x2, y1)
    draw.line((x1, y1, elbow[0], elbow[1], x2, y2), fill=color, width=width)


def is_green(pixel: tuple[int, ...]) -> bool:
    r, g, b = pixel[:3]
    return g > r + 20 and r > b + 20 and g > 120


def green_bounds(image: Image.Image, x: int, radius: int = 2) -> tuple[int, int] | None:
    rgb = image.convert("RGB")
    ys: list[int] = []
    for xx in range(max(0, x - radius), min(rgb.width, x + radius + 1)):
        for y in range(0, rgb.height - 5):
            if is_green(rgb.getpixel((xx, y))):
                ys.append(y)
    return (min(ys), max(ys)) if ys else None


def frequency_x(frequency: float, width: int) -> int:
    return round(frequency / F_DISPLAY_MAX * (width - 1))


def marker(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
    *,
    radius: int = 10,
) -> None:
    width = 4 if radius < 10 else 5
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        fill=WHITE,
        outline=color,
        width=width,
    )


def passband_reference(image: Image.Image, x_pass: int) -> tuple[int, int]:
    """Возвращает y единичного уровня и нижнюю границу зелёной заливки."""
    samples = [green_bounds(image, x) for x in range(20, max(25, int(x_pass * 0.9)), 5)]
    samples = [bounds for bounds in samples if bounds]
    if not samples:
        raise RuntimeError("Не удалось распознать зелёную АЧХ")
    tops = sorted(bounds[0] for bounds in samples)
    unity_y = tops[max(0, len(tops) // 20)]  # устойчивый 5-й процентиль
    baseline = max(bounds[1] for bounds in samples)
    return unity_y, baseline


def mark_logarithmic(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    x_pass = frequency_x(F_PASS, image.width)
    x_stop = frequency_x(F_STOP, image.width)
    x_spec = frequency_x(F_STOP_SPEC, image.width)
    unity_y, baseline = passband_reference(image, x_pass)

    pass_bounds = green_bounds(image, x_pass)
    stop_bounds = green_bounds(image, x_stop)
    spec_bounds = green_bounds(image, x_spec)
    y_pass = pass_bounds[0] if pass_bounds else unity_y + 4
    # На скриншоте одна малая клетка соответствует 5 дБ (около 44 px).
    y_stop_level = round(unity_y + A_MIN_DB * 8.8)
    y_stop_curve = stop_bounds[0] if stop_bounds else y_stop_level
    y_spec_curve = spec_bounds[0] if spec_bounds else min(baseline, y_stop_level + 115)

    # Уровни подавления относительно максимума в ПП.
    dashed_line(draw, (0, y_pass, x_pass, y_pass), fill=BLUE, width=4)
    dashed_line(draw, (x_stop, y_stop_level, image.width - 1, y_stop_level), fill=RED, width=4)

    # Границы цифрового фильтра и заданная частота аналогового прототипа.
    dashed_line(draw, (x_pass, 30, x_pass, baseline), fill=BLUE, width=5)
    dashed_line(draw, (x_stop, 30, x_stop, baseline), fill=RED, width=5)
    dashed_line(draw, (x_spec, 30, x_spec, baseline), fill=GRAY, width=3, dash=12, gap=9)
    marker(draw, x_pass, y_pass, BLUE)
    marker(draw, x_stop, y_stop_curve, RED)
    marker(draw, x_spec, y_spec_curve, GRAY)

    fnt = font(27, bold=True)
    pass_box = label_box(
        draw,
        (105, 155),
        "f₁ ≈ 2220 Гц\naₘₐₓ = 0,4455 дБ",
        color=BLUE,
        text_font=fnt,
    )
    stop_box = label_box(
        draw,
        (965, 300),
        "f₃ ≈ 3261 Гц\naₘᵢₙ = 40 дБ",
        color=RED,
        text_font=fnt,
    )
    # Соединители заканчиваются ровно в центрах круглых маркеров.
    connector(draw, (pass_box[2], (pass_box[1] + pass_box[3]) // 2), (x_pass, y_pass), color=BLUE)
    connector(draw, (stop_box[0], (stop_box[1] + stop_box[3]) // 2), (x_stop, y_stop_curve), color=RED)

    spec_font = font(22, bold=True)
    spec_box = label_box(
        draw,
        (1235, 540),
        "F₃ по ТЗ = 3760 Гц\na(3760) ≈ 53,35 дБ",
        color=GRAY,
        text_font=spec_font,
        padding=9,
    )
    connector(draw, (spec_box[0], (spec_box[1] + spec_box[3]) // 2), (x_spec, y_spec_curve), color=GRAY, width=3)

    note_font = font(21)
    label_box(
        draw,
        (1280, 55),
        "Подавление отсчитывается\nот максимума в ПП",
        color=DARK,
        text_font=note_font,
        padding=9,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


def mark_linear(source: bytes) -> bytes:
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    x_pass = frequency_x(F_PASS, image.width)
    x_stop = frequency_x(F_STOP, image.width)
    x_spec = frequency_x(F_STOP_SPEC, image.width)
    unity_y, baseline = passband_reference(image, x_pass)
    amplitude_pixels = baseline - unity_y
    pass_min_y = round(baseline - H_PASS_MIN * amplitude_pixels)
    stop_max_y = round(baseline - H_STOP_MAX * amplitude_pixels)

    # Допустимые области 0,95...1 и 0...0,01.
    draw.rectangle((0, unity_y, x_pass, pass_min_y), fill=(0, 92, 184, 48))
    dashed_line(draw, (0, unity_y, x_pass, unity_y), fill=BLUE, width=4)
    dashed_line(draw, (0, pass_min_y, x_pass, pass_min_y), fill=BLUE, width=5)
    draw.rectangle((x_stop, stop_max_y, image.width - 1, baseline), fill=(198, 40, 40, 38))
    dashed_line(draw, (x_stop, stop_max_y, image.width - 1, stop_max_y), fill=RED, width=5)

    dashed_line(draw, (x_pass, 30, x_pass, baseline), fill=BLUE, width=4)
    dashed_line(draw, (x_stop, 30, x_stop, baseline), fill=RED, width=4)
    dashed_line(draw, (x_spec, 30, x_spec, baseline), fill=GRAY, width=3, dash=12, gap=9)
    marker(draw, x_pass, pass_min_y, BLUE)
    marker(draw, x_stop, stop_max_y, RED, radius=6)
    # При F₃ по ТЗ модуль равен 0,00215, поэтому маркер почти совпадает с осью |H| = 0.
    y_spec_curve = round(baseline - 0.0021515 * amplitude_pixels)
    marker(draw, x_spec, y_spec_curve, GRAY, radius=6)

    fnt = font(26, bold=True)
    pass_box = label_box(
        draw,
        (35, 540),
        "0,95 ≤ |H| ≤ 1\nf₁ ≈ 2220 Гц",
        color=BLUE,
        text_font=fnt,
    )
    stop_box = label_box(
        draw,
        (970, 680),
        "|H| ≤ 0,01\nf₃ ≈ 3261 Гц",
        color=RED,
        text_font=fnt,
    )
    connector(draw, (pass_box[2], (pass_box[1] + pass_box[3]) // 2), (x_pass, pass_min_y), color=BLUE)
    connector(draw, (stop_box[0], (stop_box[1] + stop_box[3]) // 2), (x_stop, stop_max_y), color=RED)

    spec_font = font(21, bold=True)
    spec_box = label_box(
        draw,
        (1260, 775),
        "F₃ по ТЗ = 3760 Гц\na(3760) ≈ 53,35 дБ",
        color=GRAY,
        text_font=spec_font,
        padding=9,
    )
    connector(
        draw,
        (spec_box[0], (spec_box[1] + spec_box[3]) // 2),
        (x_spec, y_spec_curve),
        color=GRAY,
        width=3,
    )
    note_font = font(21)
    label_box(
        draw,
        (1220, 35),
        "Уровни нормированы\nотносительно max |H| в ПП",
        color=DARK,
        text_font=note_font,
        padding=9,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


def run_xml(text: str, *, bold: bool = False) -> str:
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        f"{bold_xml}<w:sz w:val=\"28\"/><w:szCs w:val=\"28\"/>"
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


def validate_document_xml(document_xml: bytes) -> None:
    """Проверяет синтаксис XML и запрещённую для OOXML вложенность абзацев."""
    root = ET.fromstring(document_xml)
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = list(root.iter(f"{w}p"))
    for paragraph in paragraphs:
        if any(node is not paragraph and node.tag == f"{w}p" for node in paragraph.iter()):
            raise RuntimeError("Некорректный document.xml: один абзац вложен в другой")
    texts = ["".join(node.text or "" for node in p.iter(f"{w}t")) for p in paragraphs]
    assignment = [i for i, text in enumerate(texts) if text == "3. Определение граничных частот по графику АЧХ"]
    conclusion = [i for i, text in enumerate(texts) if "ВЫВОД" in text]
    if len(assignment) != 1 or len(conclusion) != 1 or assignment[0] >= conclusion[0]:
        raise RuntimeError("Раздел задания №3 должен встречаться один раз перед разделом «ВЫВОД»")


def add_assignment_three(document_xml: bytes) -> bytes:
    """Вставляет ответ на задание №3 непосредственно перед разделом «ВЫВОД»."""
    if "3. Определение граничных частот по графику АЧХ".encode("utf-8") in document_xml:
        return document_xml
    marker_text = "ВЫВОД".encode("utf-8")
    text_pos = document_xml.find(marker_text)
    if text_pos < 0:
        raise RuntimeError("В document.xml не найден раздел «ВЫВОД»")
    # Ищем именно открывающий тег абзаца, а не расположенный внутри него <w:pPr>.
    # У абзацев Word бывают как атрибуты (`<w:p ...>`), так и пустой набор атрибутов.
    paragraph_pos = max(
        document_xml.rfind(b"<w:p ", 0, text_pos),
        document_xml.rfind(b"<w:p>", 0, text_pos),
    )
    if paragraph_pos < 0:
        raise RuntimeError("Не найдено начало абзаца перед разделом «ВЫВОД»")

    paragraphs = [
        paragraph_xml("3. Определение граничных частот по графику АЧХ", heading=True),
        paragraph_xml(
            "Граничные частоты определяем по пересечению нормированной АЧХ с допустимыми уровнями: "
            "|H| = 0,95 (aₘₐₓ = 0,4455 дБ) для полосы пропускания и |H| = 0,01 "
            "(aₘᵢₙ = 40 дБ) для полосы задержания."
        ),
        paragraph_xml(
            "– по графику граница полосы пропускания цифрового фильтра составляет f₁ ≈ 2220 Гц;",
            bullet=True,
        ),
        paragraph_xml(
            "– граница полосы задержания по уровню 40 дБ составляет f₃ ≈ 3261 Гц.",
            bullet=True,
        ),
        paragraph_xml("Сравнение с частотами аналогового фильтра, заданными в техническом задании", heading=True),
        paragraph_xml(
            "Граница полосы пропускания совпала с заданной частотой F₁ = 2220 Гц: расхождение практически "
            "равно нулю. Это показывает, что предыскажение частоты F₁ внесено правильно."
        ),
        paragraph_xml(
            "Для полосы задержания в техническом задании указано F₃ = 3760 Гц, тогда как уровень 40 дБ "
            "достигается уже при f₃ ≈ 3261 Гц. Разность составляет примерно 499 Гц (13,3 % относительно F₃)."
        ),
        paragraph_xml(
            "На заданной частоте 3760 Гц расчётное ослабление равно 53,35 дБ, то есть превышает требуемые "
            "40 дБ на 13,35 дБ. Следовательно, требование к полосе задержания выполняется с запасом."
        ),
        paragraph_xml(
            "Таким образом, преобразование с предыскажением точно сохранило границу полосы пропускания, "
            "а полоса задержания цифрового фильтра начинается раньше заданной границы, не нарушая технического задания."
        ),
    ]
    fragment = "".join(paragraphs).encode("utf-8")
    return document_xml[:paragraph_pos] + fragment + document_xml[paragraph_pos:]


def select_source() -> Path:
    candidates = sorted(CURRENT_DIR.glob("*вариант_24*.docx"))
    if len(candidates) != 1:
        names = "\n".join(f"  - {p.name}" for p in candidates) or "  (файлы не найдены)"
        raise RuntimeError(f"Ожидался один DOCX варианта 24/53:\n{names}")
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None, help="исходный DOCX варианта 24/53")
    parser.add_argument("--output-dir", type=Path, default=FINAL_DIR, help="папка результатов")
    args = parser.parse_args()

    source = args.source or select_source()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(source, "r") as docx:
        log_png = mark_logarithmic(docx.read("word/media/image2.png"))
        linear_png = mark_linear(docx.read("word/media/image3.png"))
        document_xml = add_assignment_three(docx.read("word/document.xml"))
        validate_document_xml(document_xml)

    log_path = output_dir / "АЧХ логарифмическая — ЛР4 вариант 24 с отметками.png"
    linear_path = output_dir / "АЧХ линейная — ЛР4 вариант 24 с отметками.png"
    report_path = output_dir / "Лабораторная работа №4 (вариант 24, зачётка 53) — исправленная.docx"
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

    print(f"Источник: {source}")
    print(f"Логарифмическая АЧХ: {log_path}")
    print(f"Линейная АЧХ: {linear_path}")
    print(f"Исправленный DOCX: {report_path}")


if __name__ == "__main__":
    main()
