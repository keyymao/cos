#!/usr/bin/env python3
"""Добавляет расчётные отметки на скриншоты АЧХ ЛР №3, вариант 24/53.

Скрипт не пересобирает Word-документ и не меняет его XML: он извлекает
`word/media/image3.png` и `word/media/image4.png`, рисует отметки и подменяет
только эти два PNG в копии DOCX. Исходный файл в `лабораторные/текущие/`
остаётся без изменений.

Зависимость: Pillow (`python -m pip install pillow`).
"""

from __future__ import annotations

import argparse
import io
import math
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба3"
FINAL_DIR = ROOT / "лабораторные" / "исправленые" / "лаба3"

# Данные варианта 24/53 и результаты раздела 1.8 отчёта.
F_DISPLAY_MAX = 6832.71  # правая граница частотной оси на скриншотах, Гц
F_PASS = 2074.6          # граница ПП ЦФ после билинейного преобразования, Гц
F_STOP = 3173.3          # граница ПЗ ЦФ после билинейного преобразования, Гц
A_MAX_DB = 0.4455
A_MIN_DB = 40.0
H_PASS_MIN = 10 ** (-A_MAX_DB / 20.0)  # 0,950003...
H_STOP_MAX = 10 ** (-A_MIN_DB / 20.0)  # 0,01

BLUE = (0, 92, 184, 255)
RED = (198, 40, 40, 255)
DARK = (30, 40, 50, 255)
WHITE = (255, 255, 255, 235)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Возвращает шрифт с кириллицей, а при его отсутствии — системный."""
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
    """Рисует горизонтальный или вертикальный пунктир."""
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
    padding: int = 12,
) -> tuple[int, int, int, int]:
    """Рисует читаемую подпись на полупрозрачной белой подложке."""
    x, y = position
    bbox = draw.multiline_textbbox((x, y), text, font=text_font, spacing=5)
    box = (
        bbox[0] - padding,
        bbox[1] - padding,
        bbox[2] + padding,
        bbox[3] + padding,
    )
    draw.rounded_rectangle(box, radius=10, fill=WHITE, outline=color, width=3)
    draw.multiline_text((x, y), text, font=text_font, fill=color, spacing=5)
    return box


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: tuple[int, int, int, int],
    width: int = 4,
) -> None:
    """Рисует линию со стрелкой к конечной точке."""
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 15
    spread = math.pi / 7
    p1 = (x2 - length * math.cos(angle - spread), y2 - length * math.sin(angle - spread))
    p2 = (x2 - length * math.cos(angle + spread), y2 - length * math.sin(angle + spread))
    draw.polygon((end, p1, p2), fill=color)


def is_green(pixel: tuple[int, ...]) -> bool:
    """Определяет зелёные пиксели заливки/границы графика «Спектр-2»."""
    r, g, b = pixel[:3]
    return g > r + 20 and r > b + 20 and g > 120


def green_bounds(image: Image.Image, x: int, radius: int = 2) -> tuple[int, int] | None:
    """Возвращает верхний и нижний зелёный пиксель около заданной абсциссы."""
    rgb = image.convert("RGB")
    ys: list[int] = []
    for xx in range(max(0, x - radius), min(rgb.width, x + radius + 1)):
        for y in range(0, rgb.height - 30):
            if is_green(rgb.getpixel((xx, y))):
                ys.append(y)
    return (min(ys), max(ys)) if ys else None


def frequency_x(frequency: float, width: int) -> int:
    """Переводит частоту в пиксель по шкале скриншота."""
    return round(frequency / F_DISPLAY_MAX * (width - 1))


def mark_logarithmic(source: bytes) -> bytes:
    """Отмечает две граничные частоты на логарифмической АЧХ."""
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x_pass = frequency_x(F_PASS, image.width)
    x_stop = frequency_x(F_STOP, image.width)
    baseline = green_bounds(image, 20)[1] if green_bounds(image, 20) else image.height - 50

    # Вертикальные линии доходят только до рабочей области графика, не до панели управления.
    dashed_line(draw, (x_pass, 35, x_pass, baseline), fill=BLUE, width=5)
    dashed_line(draw, (x_stop, 35, x_stop, baseline), fill=RED, width=5)

    for x, color in ((x_pass, BLUE), (x_stop, RED)):
        bounds = green_bounds(image, x)
        if bounds:
            y_curve = bounds[0]
            draw.ellipse((x - 10, y_curve - 10, x + 10, y_curve + 10), fill=WHITE, outline=color, width=5)

    fnt = font(28, bold=True)
    box1 = label_box(
        draw,
        (235, 125),
        "f₁ = 2074,6 Гц\nграница полосы пропускания",
        color=BLUE,
        text_font=fnt,
    )
    box2 = label_box(
        draw,
        (955, 300),
        "f₃ = 3173,3 Гц\nграница полосы задержания",
        color=RED,
        text_font=fnt,
    )
    arrow(draw, (box1[2], (box1[1] + box1[3]) // 2), (x_pass, 200), color=BLUE)
    arrow(draw, (box2[0], (box2[1] + box2[3]) // 2), (x_stop, 390), color=RED)

    note_font = font(23)
    label_box(
        draw,
        (1190, 55),
        "Границы ЦФ после\nбилинейного преобразования",
        color=DARK,
        text_font=note_font,
        padding=10,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


def mark_linear(source: bytes) -> bytes:
    """Отмечает допустимые уровни в ПП и ПЗ на линейной АЧХ."""
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x_pass = frequency_x(F_PASS, image.width)
    x_stop = frequency_x(F_STOP, image.width)

    # Нуль — нижняя граница зелёной заливки. Уровень |H|=1 оценивается по
    # верхним точкам пульсаций в первой части полосы пропускания.
    sample_bounds = [
        green_bounds(image, x)
        for x in range(20, max(21, int(x_pass * 0.90)), 5)
    ]
    sample_bounds = [bounds for bounds in sample_bounds if bounds]
    if not sample_bounds:
        raise RuntimeError("Не удалось распознать зелёную АЧХ на линейном скриншоте")
    baseline = max(bounds[1] for bounds in sample_bounds)
    tops = sorted(bounds[0] for bounds in sample_bounds)
    unity_y = tops[max(0, len(tops) // 20)]  # устойчивый 5-й процентиль
    amplitude_pixels = baseline - unity_y
    pass_min_y = round(baseline - H_PASS_MIN * amplitude_pixels)
    stop_max_y = round(baseline - H_STOP_MAX * amplitude_pixels)

    # Допустимая полоса пульсаций 0,95...1 в ПП.
    draw.rectangle((0, unity_y, x_pass, pass_min_y), fill=(0, 92, 184, 45))
    dashed_line(draw, (0, unity_y, x_pass, unity_y), fill=BLUE, width=4)
    dashed_line(draw, (0, pass_min_y, x_pass, pass_min_y), fill=BLUE, width=5)

    # В ПЗ модуль должен быть не выше 0,01.
    draw.rectangle((x_stop, stop_max_y, image.width - 1, baseline), fill=(198, 40, 40, 35))
    dashed_line(draw, (x_stop, stop_max_y, image.width - 1, stop_max_y), fill=RED, width=5)

    # Границы полос облегчают чтение, но сделаны тоньше уровней.
    dashed_line(draw, (x_pass, 45, x_pass, baseline), fill=(0, 92, 184, 150), width=3)
    dashed_line(draw, (x_stop, 45, x_stop, baseline), fill=(198, 40, 40, 150), width=3)

    fnt = font(27, bold=True)
    pass_box = label_box(
        draw,
        (45, 365),
        "0,95 ≤ |H| ≤ 1\naₘₐₓ = 0,4455 дБ (ПП)",
        color=BLUE,
        text_font=fnt,
    )
    stop_box = label_box(
        draw,
        (1090, 760),
        "|H| ≤ 0,01\naₘᵢₙ = 40 дБ (ПЗ)",
        color=RED,
        text_font=fnt,
    )
    arrow(draw, (pass_box[2], (pass_box[1] + pass_box[3]) // 2), (x_pass - 35, pass_min_y), color=BLUE)
    arrow(draw, (stop_box[0], (stop_box[1] + stop_box[3]) // 2), (x_stop + 35, stop_max_y), color=RED)

    note_font = font(22)
    label_box(
        draw,
        (1120, 50),
        "Уровни нормированы относительно\nмаксимума АЧХ в полосе пропускания",
        color=DARK,
        text_font=note_font,
        padding=10,
    )

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


def select_source() -> Path:
    candidates = sorted(CURRENT_DIR.glob("*вариант_24*.docx"))
    if len(candidates) != 1:
        names = "\n".join(f"  - {p.name}" for p in candidates) or "  (файлы не найдены)"
        raise RuntimeError(f"Ожидался один DOCX варианта 24/53:\n{names}")
    return candidates[0]


def rebuild_docx(source: Path, destination: Path, replacements: dict[str, bytes]) -> None:
    """Копирует DOCX, заменяя только указанные ZIP-элементы."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, dir=destination.parent) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with ZipFile(source, "r") as zin, ZipFile(tmp_path, "w", compression=ZIP_DEFLATED) as zout:
            names = set(zin.namelist())
            missing = set(replacements) - names
            if missing:
                raise RuntimeError(f"В DOCX не найдены изображения: {sorted(missing)}")
            for item in zin.infolist():
                data = replacements.get(item.filename, zin.read(item.filename))
                zout.writestr(item, data)
        with ZipFile(tmp_path, "r") as check:
            bad = check.testzip()
            if bad:
                raise RuntimeError(f"Повреждён элемент DOCX: {bad}")
        shutil.move(tmp_path, destination)
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
        log_png = mark_logarithmic(docx.read("word/media/image3.png"))
        linear_png = mark_linear(docx.read("word/media/image4.png"))

    log_path = output_dir / "АЧХ логарифмическая — скриншот с отметками.png"
    linear_path = output_dir / "АЧХ линейная — скриншот с отметками.png"
    report_path = output_dir / "Лабораторная работа №3 (вариант 24, зачётка 53) — АЧХ с отметками.docx"
    log_path.write_bytes(log_png)
    linear_path.write_bytes(linear_png)
    rebuild_docx(
        source,
        report_path,
        {
            "word/media/image3.png": log_png,
            "word/media/image4.png": linear_png,
        },
    )

    print(f"Источник: {source}")
    print(f"Логарифмическая АЧХ: {log_path}")
    print(f"Линейная АЧХ: {linear_path}")
    print(f"Исправленный DOCX: {report_path}")


if __name__ == "__main__":
    main()
