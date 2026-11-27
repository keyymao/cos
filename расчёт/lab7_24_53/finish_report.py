#!/usr/bin/env python3
"""Исправляет ЛР №7 для варианта 24 / зачётки 53.

Скрипт не изменяет исходный отчёт из папки ``старые``. Он:

1. выполняет лабораторное задание 3 по методическим указаниям;
2. строит и отмечает максимумы модуля ДПФ одной гармоники и их суммы;
3. вставляет два расчётных графика вместо соответствующих заглушек;
4. исправляет подписи амплитудного и фазового спектров;
5. сохраняет итоговый DOCX и оба графика в папку ``исправленые``.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REPORT = (
    ROOT
    / "лабораторные"
    / "старые"
    / "лаба7"
    / "Лабораторная работа №7 (вариант 24, зачётка 53).docx"
)
OUTPUT_DIR = ROOT / "лабораторные" / "исправленые" / "лаба7"
OUTPUT_REPORT = OUTPUT_DIR / "Лабораторная работа №7 (вариант 24, зачётка 53) — исправленная.docx"
SINGLE_FIGURE = OUTPUT_DIR / "Амплитудный спектр одной гармоники — ЛР7 вариант 24 с отметками.png"
SUM_FIGURE = OUTPUT_DIR / "Амплитудный спектр суммы гармоник — ЛР7 вариант 24 с отметками.png"

N = 1024
FD = 10000.0
A1 = 1.24
A2 = 2.48
F1 = 1250.0
F2 = 625.0
K1 = round(F1 * N / FD)
K2 = round(F2 * N / FD)
MIRROR_K1 = N - K1
MIRROR_K2 = N - K2
PEAK_1 = A1 * N / 2.0
PEAK_2_GAIN4 = 4.0 * A2 * N / 2.0

FONT = "Times New Roman"
BLUE = "#22577A"
CYAN = "#238B8E"
RED = "#C44536"
DARK = "#263238"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "savefig.dpi": 240,
    }
)


def ru(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def calculate_spectra() -> tuple[np.ndarray, np.ndarray]:
    """Возвращает модули ДПФ для режимов K2=0 и K2=4."""
    n = np.arange(N)
    one_harmonic = A1 * np.cos(2.0 * np.pi * F1 * n / FD)
    harmonic_sum = one_harmonic + 4.0 * A2 * np.cos(2.0 * np.pi * F2 * n / FD)
    single_magnitude = np.abs(np.fft.fft(one_harmonic))
    sum_magnitude = np.abs(np.fft.fft(harmonic_sum))

    assert np.isclose(single_magnitude[K1], PEAK_1, atol=1e-8)
    assert np.isclose(single_magnitude[MIRROR_K1], PEAK_1, atol=1e-8)
    assert np.isclose(sum_magnitude[K2], PEAK_2_GAIN4, atol=1e-8)
    assert np.isclose(sum_magnitude[MIRROR_K2], PEAK_2_GAIN4, atol=1e-8)
    assert np.isclose(sum_magnitude[K1], PEAK_1, atol=1e-8)
    assert np.isclose(sum_magnitude[MIRROR_K1], PEAK_1, atol=1e-8)
    return single_magnitude, sum_magnitude


def make_single_figure(magnitude: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(11.8, 4.8))
    bins = [K1, MIRROR_K1]
    levels = [magnitude[K1], magnitude[MIRROR_K1]]
    ax.vlines(bins, 0, levels, color=BLUE, linewidth=2.0)
    ax.scatter(bins, levels, s=45, color=RED, zorder=3)
    ax.axhline(0, color=DARK, linewidth=0.8)
    ax.set_xlim(0, N - 1)
    ax.set_ylim(0, PEAK_1 * 1.22)
    ax.set_xticks([0, 128, 256, 512, 768, 896, 1023])
    ax.set_xlabel("Номер частотного отсчёта k")
    ax.set_ylabel("|X(k)|")
    ax.set_title("Задание 3. Модуль коэффициентов ДПФ одной гармоники")
    ax.annotate(
        f"k = {K1}\nf = {F1:.0f} Гц\n|X| = {ru(PEAK_1)}",
        (K1, PEAK_1),
        xytext=(220, PEAK_1 * 1.08),
        arrowprops={"arrowstyle": "->", "color": RED},
        color=RED,
        ha="left",
        va="center",
    )
    ax.annotate(
        f"k = {MIRROR_K1}\nзеркальный отсчёт\n|X| = {ru(PEAK_1)}",
        (MIRROR_K1, PEAK_1),
        xytext=(790, PEAK_1 * 1.08),
        arrowprops={"arrowstyle": "->", "color": RED},
        color=RED,
        ha="right",
        va="center",
    )
    ax.text(
        512,
        PEAK_1 * 0.48,
        "Максимумы: k = 128 и k = 896\nmax |X(k)| = 634,88",
        ha="center",
        va="center",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#B0BEC5"},
    )
    fig.tight_layout()
    fig.savefig(SINGLE_FIGURE, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def marked_zoom(ax, magnitude: np.ndarray, center: int, level: float, frequency: float, mirror: int, color: str) -> None:
    x = np.arange(center - 12, center + 13)
    markerline, stemlines, baseline = ax.stem(x, magnitude[x], basefmt=" ")
    plt.setp(markerline, marker="o", markersize=3.5, color=color)
    plt.setp(stemlines, linewidth=1.0, color=color)
    plt.setp(baseline, visible=False)
    ax.scatter([center], [level], s=42, color=RED, zorder=4)
    ax.set_xlim(center - 12, center + 12)
    ax.set_ylim(0, level * 1.14)
    ax.set_xlabel("k")
    ax.set_ylabel("|X(k)|")
    ax.set_title(f"f = {frequency:.0f} Гц: k = {center} и {mirror}")
    ax.annotate(
        f"|X| = {ru(level)}",
        (center, level),
        xytext=(center + 3, level * 0.90),
        arrowprops={"arrowstyle": "->", "color": RED},
        color=RED,
    )


def make_sum_figure(magnitude: np.ndarray) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.8), gridspec_kw={"width_ratios": [1.55, 1, 1]})

    main = axes[0]
    bins_f2 = [K2, MIRROR_K2]
    bins_f1 = [K1, MIRROR_K1]
    main.vlines(bins_f2, 0, [PEAK_2_GAIN4] * 2, color=RED, linewidth=2.0, label="f₂ = 625 Гц")
    main.vlines(bins_f1, 0, [PEAK_1] * 2, color=BLUE, linewidth=2.0, label="f₁ = 1250 Гц")
    main.scatter(bins_f2, [PEAK_2_GAIN4] * 2, color=RED, s=38, zorder=3)
    main.scatter(bins_f1, [PEAK_1] * 2, color=BLUE, s=38, zorder=3)
    main.set_xlim(0, N - 1)
    main.set_ylim(0, PEAK_2_GAIN4 * 1.10)
    main.set_xticks([0, 64, 128, 512, 896, 960, 1023])
    main.set_xlabel("Номер отсчёта k")
    main.set_ylabel("|X(k)|")
    main.set_title("Весь блок ДПФ")
    main.legend(loc="upper center", fontsize=9)
    main.text(
        512,
        PEAK_2_GAIN4 * 0.61,
        "max |XΣ(k)| = 5079,04\nпри k = 64 и 960",
        ha="center",
        va="center",
        color=RED,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#B0BEC5"},
    )

    marked_zoom(axes[1], magnitude, K2, PEAK_2_GAIN4, F2, MIRROR_K2, RED)
    marked_zoom(axes[2], magnitude, K1, PEAK_1, F1, MIRROR_K1, BLUE)
    fig.suptitle("Задание 3. Модуль коэффициентов ДПФ суммы гармоник (K₁ = 1, K₂ = 4)", fontsize=12.5)
    fig.tight_layout()
    fig.savefig(SUM_FIGURE, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def set_run_font(run, *, size: int = 14, bold: bool = False) -> None:
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), FONT)


def clear_paragraph(paragraph: Paragraph) -> None:
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)


def replace_text(
    paragraph: Paragraph,
    text: str,
    *,
    size: int = 14,
    bold: bool = False,
    alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
    first_line_indent: float = 1.25,
) -> None:
    clear_paragraph(paragraph)
    paragraph.alignment = alignment
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Cm(first_line_indent)
    fmt.line_spacing = 1.5 if size >= 14 else 1.0
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold)


def find_paragraph(doc: Document, prefix: str) -> Paragraph:
    try:
        return next(p for p in doc.paragraphs if p.text.strip().startswith(prefix))
    except StopIteration as exc:
        raise RuntimeError(f"В отчёте не найден абзац: {prefix}") from exc


def replace_placeholder_before_caption(doc: Document, caption_prefix: str, image_path: Path) -> Paragraph:
    caption = find_paragraph(doc, caption_prefix)
    node = caption._p.getprevious()
    empty_nodes = []
    placeholder = None
    while node is not None and node.tag == qn("w:p"):
        paragraph = Paragraph(node, caption._parent)
        text = paragraph.text.strip()
        if text.startswith("[место для скриншота"):
            placeholder = paragraph
            break
        if text or node.xpath(".//w:drawing"):
            break
        empty_nodes.append(node)
        node = node.getprevious()
    if placeholder is None:
        raise RuntimeError(f"Перед подписью {caption_prefix} не найдена заглушка")

    for empty in empty_nodes:
        empty.getparent().remove(empty)

    clear_paragraph(placeholder)
    placeholder.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = placeholder.paragraph_format
    fmt.first_line_indent = Cm(0)
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(2)
    fmt.keep_with_next = True
    run = placeholder.add_run()
    run.add_picture(str(image_path), width=Cm(15.6))
    caption.paragraph_format.keep_together = True
    return placeholder


def insert_body_before(anchor: Paragraph, text: str) -> Paragraph:
    paragraph = anchor.insert_paragraph_before()
    replace_text(paragraph, text)
    return paragraph


def revise_report() -> None:
    source_digest = sha256(SOURCE_REPORT.read_bytes()).digest()
    doc = Document(str(SOURCE_REPORT))
    if any(p.text.strip().startswith("3. Определение максимумов") for p in doc.paragraphs):
        raise RuntimeError("Исходный отчёт уже содержит исправленное задание 3")

    figure3 = replace_placeholder_before_caption(doc, "Рисунок 3", SINGLE_FIGURE)
    replace_placeholder_before_caption(doc, "Рисунок 4", SUM_FIGURE)

    heading = find_paragraph(doc, "На рис. 3 измеряем")
    replace_text(
        heading,
        "3. Определение максимумов уровней модуля коэффициентов ДПФ и номеров отсчётов",
        bold=True,
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
        first_line_indent=0,
    )
    heading.paragraph_format.space_before = Pt(10)
    heading.paragraph_format.space_after = Pt(4)
    heading.paragraph_format.keep_with_next = True
    insert_body_before(
        figure3,
        "Согласно заданию 3 методических указаний сначала рассматриваем одну гармонику при K₁ = 1 и K₂ = 0, затем сумму двух гармоник при K₁ = 1 и K₂ = 4. Номер спектрального отсчёта определяем по формуле k = fN/Fд. Так как обе частоты кратны частотному разрешению Δf = Fд/N = 9,765625 Гц, растекания спектра нет.",
    )

    replace_text(
        find_paragraph(doc, "Рисунок 3"),
        "Рисунок 3 – Максимумы модуля коэффициентов ДПФ одной гармоники",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "Гармоника 1250 Гц укладывается"),
        "Для гармоники f₁ = 1250 Гц получаем k₁ = 1250·1024/10000 = 128. Второй максимум находится на зеркальном отсчёте N − k₁ = 896. Уровень каждого максимума равен A₁N/2 = 1,24·1024/2 = 634,88. Следовательно, максимальный уровень |X₁(k)| равен 634,88 при k = 128 и k = 896.",
    )
    replace_text(
        find_paragraph(doc, "Далее изменяем значение коэффициента"),
        "Затем устанавливаем коэффициент усиления второй ветви K₂ = 4. На вход ДПФ поступает сумма гармоник с частотами 1250 и 625 Гц. Амплитуда второй составляющей становится 4A₂ = 9,92.",
    )
    replace_text(
        find_paragraph(doc, "Рисунок 4"),
        "Рисунок 4 – Максимумы модуля коэффициентов ДПФ суммы двух гармоник",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "При усилении 4 амплитуда второй"),
        "Для второй гармоники k₂ = 625·1024/10000 = 64, зеркальный отсчёт равен 960. Уровень этих спектральных линий составляет 4A₂N/2 = 4·2,48·1024/2 = 5079,04. Линии первой гармоники остаются на отсчётах 128 и 896 с уровнем 634,88. Поэтому максимальный уровень |XΣ(k)| для суммы двух гармоник равен 5079,04 при k = 64 и k = 960; дополнительные максимумы уровня 634,88 находятся при k = 128 и k = 896.",
    )

    replace_text(
        find_paragraph(doc, "На рис. 2 представлена схема"),
        "На рисунке 2 представлена схема, реализующая расчёт коэффициентов ДПФ гармонических сигналов в среде имитационного моделирования РТС «Спектр-2» для варианта 24. Частота дискретизации установлена равной 10000 Гц, размер блока ДПФ — 1024 отсчёта.",
    )
    replace_text(
        find_paragraph(doc, "В схеме используются два генератора"),
        "В схеме используются два генератора «Гармонич. SIN & COS» с частотами 1250 Гц и 625 Гц, два усилителя и сумматор. В первом эксперименте коэффициент усиления первого усилителя равен 1, второго — 0, поэтому на ДПФ подаётся одна гармоника с амплитудой A₁ = 1,24.",
    )

    replace_text(
        find_paragraph(doc, "На рис. 5 представлена вторая схема"),
        "На рисунке 5 представлена вторая схема, реализующая расчёт коэффициентов ДПФ последовательности прямоугольных импульсов.",
    )
    replace_text(
        find_paragraph(doc, "На рис. 6 и рис. 7"),
        "На рисунках 6 и 7 показан модуль коэффициентов ДПФ последовательности прямоугольных импульсов в линейном и логарифмическом масштабе соответственно.",
    )
    replace_text(
        find_paragraph(doc, "Рисунок 6"),
        "Рисунок 6 – Модуль коэффициентов ДПФ прямоугольных импульсов в линейном масштабе",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "Рисунок 7"),
        "Рисунок 7 – Модуль коэффициентов ДПФ прямоугольных импульсов в логарифмическом масштабе",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "На рис. 8 представлен"),
        "На рисунке 8 показан амплитудный спектр сигнала, а на рисунке 9 — фазовый спектр сигнала.",
    )
    replace_text(
        find_paragraph(doc, "Рисунок 8"),
        "Рисунок 8 – Амплитудный спектр сигнала",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "Рисунок 9"),
        "Рисунок 9 – Фазовый спектр сигнала",
        size=13,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=0,
    )
    replace_text(
        find_paragraph(doc, "Осциллограммы снимаются с выхода"),
        "Амплитудный спектр определяется модулем |X(k)|, а фазовый спектр — аргументом φ(k) = arg X(k). В пределах каждого лепестка фаза изменяется практически линейно; в точках, где модуль коэффициента равен нулю, значение фазы не определено.",
    )

    conclusion = find_paragraph(doc, "В ходе выполнения данной лабораторной работы")
    addition = (
        " Лабораторное задание 3 выполнено: для одной гармоники максимальный уровень модуля ДПФ равен 634,88 при k = 128 и 896; для суммы гармоник при K₂ = 4 общий максимум равен 5079,04 при k = 64 и 960, а линии первой гармоники имеют уровень 634,88 при k = 128 и 896. Подписи амплитудного и фазового спектров приведены в соответствие с их физическим смыслом."
    )
    run = conclusion.add_run(addition)
    set_run_font(run)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_REPORT))
    assert sha256(SOURCE_REPORT.read_bytes()).digest() == source_digest


def validate_output() -> None:
    doc = Document(str(OUTPUT_REPORT))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert text.count("3. Определение максимумов уровней модуля") == 1
    assert "максимальный уровень |X₁(k)| равен 634,88 при k = 128 и k = 896" in text
    assert "максимальный уровень |XΣ(k)| для суммы двух гармоник равен 5079,04" in text
    assert "Рисунок 8 – Амплитудный спектр сигнала" in text
    assert "Рисунок 9 – Фазовый спектр сигнала" in text
    assert "Рисунок 8 – ИХ по амплитуде" not in text
    assert "Рисунок 9 – ИХ по фазе" not in text
    assert len(doc.tables) == 0

    for caption_prefix in ("Рисунок 1", "Рисунок 3", "Рисунок 4"):
        caption = find_paragraph(doc, caption_prefix)
        image_paragraph = caption._p.getprevious()
        assert image_paragraph is not None and image_paragraph.xpath(".//w:drawing")

    with ZipFile(OUTPUT_REPORT, "r") as package:
        assert package.testzip() is None
        media = [package.read(name) for name in package.namelist() if name.startswith("word/media/")]
        assert SINGLE_FIGURE.read_bytes() in media
        assert SUM_FIGURE.read_bytes() in media


def main() -> None:
    if not SOURCE_REPORT.exists():
        raise FileNotFoundError(SOURCE_REPORT)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    single_magnitude, sum_magnitude = calculate_spectra()
    make_single_figure(single_magnitude)
    make_sum_figure(sum_magnitude)
    revise_report()
    validate_output()

    print(f"Исходный отчёт сохранён без изменений: {SOURCE_REPORT}")
    print(f"Исправленный отчёт: {OUTPUT_REPORT}")
    print(f"График одной гармоники: {SINGLE_FIGURE}")
    print(f"График суммы гармоник: {SUM_FIGURE}")
    print(f"Одна гармоника: max |X(k)| = {PEAK_1:.2f}, k = {K1}, {MIRROR_K1}")
    print(f"Сумма: max |XΣ(k)| = {PEAK_2_GAIN4:.2f}, k = {K2}, {MIRROR_K2}")


if __name__ == "__main__":
    main()
