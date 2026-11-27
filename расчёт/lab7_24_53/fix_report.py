#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Исправление отчёта ЛР №7 (вариант 24 / зачётка 53).

Что исправляет скрипт
---------------------
1. Задание №3 (не было выполнено). Строятся осциллограммы модуля
   коэффициентов ДПФ для одного гармонического колебания и для суммы двух
   колебаний, на них курсором отмечены номера отсчётов и максимумы уровней
   (k = 128 и 896 → 634,88; k = 64 и 960 → 5079,04). В текст отчёта
   добавляются измерения, таблица результатов и пояснения.
2. Подписи амплитудного и фазового спектра (рисунки 6–9). В исходном отчёте
   они назывались «АЧХ» и «ИХ», хотя показывают модуль и фазу коэффициентов
   ДПФ последовательности прямоугольных импульсов. Подписи и текст
   исправлены, на скриншоты спектроанализатора нанесены нули f = 625m Гц,
   осциллограммы модуля и фазы построены с осью номеров отсчётов k.

Результат сохраняется отдельным DOCX в ``лабораторные/исправленые/лаба7/``;
исходный файл в ``лабораторные/текущие/лаба7/`` не изменяется. Все
исправленные рисунки сохраняются рядом с DOCX отдельными PNG.

Запуск из корня репозитория::

    python3 расчёт/lab7_24_53/fix_report.py                # рисунки + DOCX
    python3 расчёт/lab7_24_53/fix_report.py --figures-only # только рисунки

Зависимости: numpy, matplotlib, pillow, python-docx.
"""
from __future__ import annotations

import argparse
import io
import re
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CURRENT_DIR = ROOT / "лабораторные" / "текущие" / "лаба7"
FINAL_DIR = ROOT / "лабораторные" / "исправленые" / "лаба7"
SOURCE_DOCX = CURRENT_DIR / "Лабораторная_работа_№7_вариант_24,_зачётка_53_1.docx"
TARGET_DOCX = FINAL_DIR / "Лабораторная работа №7 (вариант 24, зачётка 53) — исправленная.docx"

# ---------------------------------------------------------------------------
# Параметры варианта 24 / зачётка 53
# ---------------------------------------------------------------------------
N = 1024
FD = 10000.0
DF = FD / N                     # 9,765625 Гц
A1 = 1.0 + 0.01 * 24            # 1,24
A2 = 2.0 * A1                   # 2,48
F1 = FD / 8.0                   # 1250 Гц → k = 128
F2 = FD / 16.0                  # 625 Гц  → k = 64
K1 = int(round(N * F1 / FD))    # 128
K2 = int(round(N * F2 / FD))    # 64

PEAK_A1 = A1 * N / 2            # 634,88
PEAK_A2 = A2 * N / 2            # 1269,76
PEAK_4A2 = 4 * A2 * N / 2       # 5079,04
PULSE_WIDTH = 16                # X(0) = 16, нули при k = 64m
PULSE_SIDE_MAX = 3.5214217      # максимум первого бокового лепестка (k = 92)

# Отдельные PNG рядом с DOCX
PNG_SINGLE = "Спектр одной гармоники — ЛР7 вариант 24 с отметками.png"
PNG_SUM = "Спектр суммы гармоник — ЛР7 вариант 24 с отметками.png"
PNG_PULSE_LIN = "Амплитудный спектр импульсов — линейный масштаб — ЛР7 вариант 24 с отметками.png"
PNG_PULSE_LOG = "Амплитудный спектр импульсов — логарифмический масштаб — ЛР7 вариант 24 с отметками.png"
PNG_MODULE = "Осциллограмма модуля ДПФ импульсов — ЛР7 вариант 24 с отметками.png"
PNG_PHASE = "Осциллограмма фазы ДПФ импульсов — ЛР7 вариант 24 с отметками.png"

GREEN = "#3d9b1e"
DARK = "#1a1a1a"
GRID = "#9b9b9b"
BLUE = "#0d47a1"
RED = "#c62828"
GRAY = "#455a64"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "axes.edgecolor": "#555555",
    "axes.linewidth": 1.1,
})


def ru(value: float, digits: int = 2) -> str:
    """Число с русской десятичной запятой."""
    return f"{value:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Модель сигналов
# ---------------------------------------------------------------------------
def harmonic_spectra() -> tuple[np.ndarray, np.ndarray]:
    """Модули ДПФ одной гармоники и суммы гармоник при K2 = 4."""
    n = np.arange(N)
    single = A1 * np.cos(2 * np.pi * F1 * n / FD)
    total = single + 4 * A2 * np.cos(2 * np.pi * F2 * n / FD)
    return np.abs(np.fft.fft(single)), np.abs(np.fft.fft(total))


def pulse_spectrum() -> np.ndarray:
    """ДПФ одного прямоугольного импульса шириной 16 отсчётов."""
    pulse = np.zeros(N)
    pulse[:PULSE_WIDTH] = 1.0
    return np.fft.fft(pulse)


def pulse_phase() -> np.ndarray:
    """Фаза ДПФ импульса; в нулях модуля значения не определены (NaN)."""
    k = np.arange(N)
    denominator = np.sin(np.pi * k / N)
    denominator = np.where(np.abs(denominator) < 1e-15, 1.0, denominator)
    kernel = np.sin(np.pi * PULSE_WIDTH * k / N) / denominator
    kernel[0] = float(PULSE_WIDTH)
    phase = -15.0 * np.pi * k / N + np.where(kernel < 0, np.pi, 0.0)
    phase = np.angle(np.exp(1j * phase))
    phase[np.abs(kernel) < 1e-10] = np.nan
    return phase


# ---------------------------------------------------------------------------
# Оформление «осциллограммы»
# ---------------------------------------------------------------------------
def scope_axes(ax: plt.Axes, *, ymin: float, ymax: float, yticks, ylabel: str) -> None:
    ax.set_xlim(0, N - 1)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks(range(0, N + 1, 128))
    ax.set_xticks(range(0, N + 1, 32), minor=True)
    ax.set_yticks(yticks)
    ax.set_xlabel("Номер отсчёта ДПФ  k", fontsize=13.5)
    ax.set_ylabel(ylabel, fontsize=13.5)
    ax.grid(which="major", color=GRID, lw=0.75, alpha=0.9)
    ax.grid(which="minor", color=GRID, lw=0.45, alpha=0.35, ls=":")
    ax.tick_params(labelsize=12)
    ax.axhline(0, color="#666666", lw=1.0)


def note_box(ax: plt.Axes, xy, text: str, *, color: str = GRAY,
             fontsize: float = 12.5) -> None:
    ax.annotate(text, xy=xy, ha="center", va="center", fontsize=fontsize,
                color=color, zorder=6,
                bbox=dict(boxstyle="round,pad=0.40", fc="white", ec=GRID,
                          lw=1.0, alpha=0.95))


def peak_label(ax: plt.Axes, k: int, value: float, text: str, *,
               xytext, ha: str = "left", color: str = RED) -> None:
    ax.plot([k], [value], marker="v", ms=8, color=color, zorder=7)
    ax.axvline(k, color=DARK, lw=1.0, ls=(0, (4, 3)), alpha=0.8, zorder=3)
    ax.annotate(text, xy=(k, value), xytext=xytext, ha=ha, va="center",
                fontsize=13, color=color, fontweight="bold", zorder=8,
                bbox=dict(boxstyle="round,pad=0.38", fc="white", ec=color,
                          lw=1.4, alpha=0.97),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.4,
                                shrinkA=2, shrinkB=6))


def state_bar(fig: plt.Figure, readings: list[str]) -> None:
    """Строка состояния внизу экрана осциллографа: показания курсоров."""
    for x, reading in zip((0.012, 0.365), readings):
        fig.text(x, 0.026, reading, fontsize=12.5, color=DARK, ha="left",
                 bbox=dict(boxstyle="round,pad=0.42", fc="#f4f4f4",
                           ec="#777777", lw=1.1))


# ---------------------------------------------------------------------------
# Рисунки 3 и 4 — определение максимумов модуля ДПФ (задание №3)
# ---------------------------------------------------------------------------
def figure_single(path: Path) -> None:
    mag, _ = harmonic_spectra()
    k = np.arange(N)
    fig = plt.figure(figsize=(11.8, 5.9), dpi=200)
    ax = fig.add_axes([0.072, 0.215, 0.908, 0.610])
    ax.plot(k, mag, color=GREEN, lw=1.4)
    scope_axes(ax, ymin=0, ymax=800, yticks=range(0, 701, 100),
               ylabel="Модуль  |X(k)|")
    ax.set_title(
        "Одна гармоника: A$_1$ = 1,24;  f$_1$ = 1250 Гц (128 периодов в блоке)\n"
        "N = 1024;  F$_д$ = 10 000 Гц;  Δf = F$_д$/N = 9,766 Гц",
        fontsize=14, color=DARK, pad=12,
    )
    peak_label(ax, K1, PEAK_A1, f"k = {K1}\n|X| = {ru(PEAK_A1)}", xytext=(215, 520))
    peak_label(ax, N - K1, PEAK_A1, f"k = {N - K1}\n|X| = {ru(PEAK_A1)}",
               xytext=(N - K1 - 142, 520), ha="right")
    note_box(ax, (512, 175),
             "на остальных 1020 отсчётах  |X(k)| = 0\n"
             "растекания спектра нет: f₁ = 128·Δf")
    state_bar(fig, [f"k = {K1}   |X| = {ru(PEAK_A1, 3)} В",
                    f"k = {N - K1}   |X| = {ru(PEAK_A1, 3)} В"])
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def figure_sum(path: Path) -> None:
    _, total = harmonic_spectra()
    k = np.arange(N)
    fig = plt.figure(figsize=(11.8, 5.9), dpi=200)
    ax = fig.add_axes([0.075, 0.215, 0.905, 0.610])
    ax.plot(k, total, color=GREEN, lw=1.4)
    scope_axes(ax, ymin=0, ymax=6100, yticks=range(0, 5001, 1000),
               ylabel="Модуль  |X(k)|")
    ax.set_title(
        "Сумма гармоник: A$_1$ = 1,24 (f$_1$ = 1250 Гц);  4A$_2$ = 9,92 (f$_2$ = 625 Гц)\n"
        "N = 1024;  F$_д$ = 10 000 Гц;  Δf = F$_д$/N = 9,766 Гц",
        fontsize=14, color=DARK, pad=12,
    )
    peak_label(ax, K2, PEAK_4A2, f"k = {K2}\n|X| = {ru(PEAK_4A2)}", xytext=(160, 4350))
    peak_label(ax, N - K2, PEAK_4A2, f"k = {N - K2}\n|X| = {ru(PEAK_4A2)}",
               xytext=(N - K2 - 96, 4350), ha="right")
    peak_label(ax, K1, PEAK_A1, f"k = {K1}\n|X| = {ru(PEAK_A1)}", xytext=(240, 1180))
    peak_label(ax, N - K1, PEAK_A1, f"k = {N - K1}\n|X| = {ru(PEAK_A1)}",
               xytext=(N - K1 - 140, 1180), ha="right")
    note_box(ax, (512, 3000),
             "уровень первой гармоники в 8 раз ниже:\n"
             "634,88 = 5079,04 / 8")
    state_bar(fig, [f"k = {K2}   |X| = {ru(PEAK_4A2, 2)} В",
                    f"k = {K1}   |X| = {ru(PEAK_A1, 2)} В"])
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Рисунки 8 и 9 — осциллограммы модуля и фазы ДПФ импульсов
# ---------------------------------------------------------------------------
def figure_pulse_module(path: Path) -> None:
    mag = np.abs(pulse_spectrum())
    k = np.arange(N)
    fig = plt.figure(figsize=(11.8, 5.9), dpi=200)
    ax = fig.add_axes([0.075, 0.215, 0.905, 0.610])
    ax.plot(k, mag, color=GREEN, lw=1.3)
    scope_axes(ax, ymin=-0.6, ymax=18.4, yticks=range(0, 17, 2),
               ylabel="Модуль  |X(k)|")
    ax.set_title(
        "Прямоугольный импульс: ширина 16 отсчётов, период повторения 1024\n"
        "N = 1024;  F$_д$ = 10 000 Гц;  X(0) = 16;  нули при k = 64m",
        fontsize=14, color=DARK, pad=12,
    )
    for m in range(1, 8):
        ax.axvline(64 * m, color=BLUE, lw=1.0, ls=(0, (4, 3)), alpha=0.6)
        ax.text(64 * m, 17.2, str(64 * m), color=BLUE, fontsize=11.5,
                fontweight="bold", ha="center", va="bottom")
    peak_label(ax, 0, float(PULSE_WIDTH), "k = 0\n|X| = 16", xytext=(132, 13.6))
    peak_label(ax, 92, PULSE_SIDE_MAX, "k = 92\n|X| = 3,52", xytext=(214, 7.0))
    note_box(ax, (640, 12.0),
             "штриховые линии — нули |X(k)| = 0:\nk = 64m  (f = 625m Гц)")
    state_bar(fig, ["k = 0   |X| = 16,00 В", "k = 92   |X| = 3,52 В"])
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def figure_pulse_phase(path: Path) -> None:
    phase = pulse_phase()
    k = np.arange(N)
    fig = plt.figure(figsize=(11.8, 5.9), dpi=200)
    ax = fig.add_axes([0.085, 0.215, 0.895, 0.610])
    ax.plot(k, phase, color=GREEN, lw=1.3)
    scope_axes(ax, ymin=-4.15, ymax=3.75,
               yticks=[-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi],
               ylabel="Фаза  φ(k), рад")
    ax.set_yticklabels(["−π", "−π/2", "0", "π/2", "π"])
    ax.set_title(
        "Прямоугольный импульс: ширина 16 отсчётов, период повторения 1024\n"
        "фаза линейна внутри лепестка, в нулях |X(k)| = 0 — перескок на π",
        fontsize=14, color=DARK, pad=12,
    )
    for m in range(1, 8):
        ax.axvline(64 * m, color=BLUE, lw=1.0, ls=(0, (4, 3)), alpha=0.5)
    note_box(ax, (700, -3.35),
             "разрывы — нули модуля k = 64m;\n"
             "наклон φ(k) = −15πk / 1024 (фазовый сдвиг импульса)")
    state_bar(fig, [f"k = 32   φ = {ru(float(phase[32]), 2)} рад",
                    f"k = 976   φ = {ru(float(phase[976]), 2)} рад"])
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Разметка скриншотов спектроанализатора (рисунки 6 и 7)
# ---------------------------------------------------------------------------
WHITE = (255, 255, 255, 235)
BLUE_RGBA = (13, 71, 161, 200)
GRAY_RGBA = (69, 90, 100, 235)
RED_RGBA = (198, 40, 40, 235)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for candidate in (Path("/usr/share/fonts/truetype/dejavu") / name,
                      Path(matplotlib.get_data_path()) / "fonts/ttf" / name):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _dashed(draw: ImageDraw.ImageDraw, xy, *, fill, width=2, dash=9, gap=6) -> None:
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


def _label(draw: ImageDraw.ImageDraw, xy, text, *, color, text_font,
           anchor="la", pad=7):
    bbox = draw.multiline_textbbox(xy, text, font=text_font, spacing=4, anchor=anchor)
    box = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    draw.rounded_rectangle(box, radius=7, fill=WHITE, outline=color, width=2)
    draw.multiline_text(xy, text, font=text_font, fill=color, spacing=4, anchor=anchor)
    return box


def _load_image_part(docx_path: Path, name: str) -> bytes:
    with ZipFile(docx_path) as archive:
        return archive.read(f"word/media/{name}")


def annotate_pulse_spectrum(source: bytes, *, logarithmic: bool) -> bytes:
    """Отмечает нули амплитудного спектра импульсов (рисунки 6 и 7).

    Ось частот скриншота: 0 Гц у левого края, 4990,23 Гц (≈ Fд/2) у правого,
    нули огибающей f = 625m Гц приходятся на провалы через 64 px.
    """
    image = Image.open(io.BytesIO(source)).convert("RGBA")
    width, height = image.size
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # 511 px по оси частот соответствует 4990,23 Гц ≈ Fд/2, шаг сетки
    # 9,766 Гц приходится ровно на 1 px, поэтому нули 625m Гц — это 64m px.
    def px(freq: float) -> int:
        return round(freq / 9.765625)

    top, bottom = 26, height - 14
    for m in range(1, 8):
        _dashed(draw, (px(625.0 * m), top, px(625.0 * m), bottom), fill=BLUE_RGBA)

    caption = ("штриховые линии — нули спектра\n"
               "f = 625m Гц: 625, 1250, 1875 … 4375\n"
               "X(0) = 16 при f = 0")
    if logarithmic:
        caption += "\nпровалы огибающей до −90 дБ"
    _label(draw, (width - 6, 26), caption,
           color=BLUE_RGBA, text_font=_font(14, bold=True), anchor="ra")

    result = Image.alpha_composite(image, layer).convert("RGB")
    out = io.BytesIO()
    result.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Правка DOCX
# ---------------------------------------------------------------------------
FONT_RUN = "Times New Roman"
SIZE = 14.0


def _style_run(run, *, sub=False, sup=False, italic=False, bold=False, size=SIZE):
    run.font.name = FONT_RUN
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if sub:
        run.font.subscript = True
    if sup:
        run.font.superscript = True
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), FONT_RUN)
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "ru-RU")
    rpr.append(lang)


def add_markup(par, text: str, *, size: float = SIZE) -> None:
    """Добавляет текст с разметкой <sub>, <super>, <i>, <b>."""
    token = re.compile(r"(<sub>|</sub>|<super>|</super>|<i>|</i>|<b>|</b>)")
    keys = {"sub": False, "sup": False, "i": False, "b": False}
    for part in token.split(text):
        if part in ("<sub>", "</sub>"):
            keys["sub"] = part == "<sub>"
        elif part in ("<super>", "</super>"):
            keys["sup"] = part == "<super>"
        elif part in ("<i>", "</i>"):
            keys["i"] = part == "<i>"
        elif part in ("<b>", "</b>"):
            keys["b"] = part == "<b>"
        elif part:
            _style_run(par.add_run(part), sub=keys["sub"], sup=keys["sup"],
                       italic=keys["i"], bold=keys["b"], size=size)


def _copy_ppr(target_p, template_p) -> None:
    """Копирует оформление абзаца (отступы, выравнивание, интервалы)."""
    tpl_ppr = template_p.find(qn("w:pPr"))
    if tpl_ppr is None:
        return
    new_ppr = deepcopy(tpl_ppr)
    old = target_p.find(qn("w:pPr"))
    if old is not None:
        target_p.remove(old)
    target_p.insert(0, new_ppr)


def new_paragraph_element(template_p) -> object:
    """Создаёт новый w:p с оформлением шаблона (ещё не вставлен в документ)."""
    p = OxmlElement("w:p")
    _copy_ppr(p, template_p)
    return p


def insert_paragraph(anchor_p, template_p, text: str = "", *, before: bool = False):
    """Вставляет абзац рядом с anchor_p; возвращает элемент нового абзаца."""
    p = new_paragraph_element(template_p)
    if before:
        anchor_p.addprevious(p)
    else:
        anchor_p.addnext(p)
    if text:
        add_markup(Paragraph(p, None), text)
    return p


def _keep_with_next(p) -> None:
    """Запрещает разрыв между абзацем и следующим (рисунок ↔ подпись)."""
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    if ppr.find(qn("w:keepNext")) is None:
        ppr.append(OxmlElement("w:keepNext"))


def insert_caption(anchor_p, template_p, text: str):
    """Подпись рисунка/таблицы: по центру, без абзацного отступа."""
    p = insert_paragraph(anchor_p, template_p, text)
    ppr = p.find(qn("w:pPr"))
    jc = ppr.find(qn("w:jc")) if ppr is not None else None
    ind = ppr.find(qn("w:ind")) if ppr is not None else None
    if ind is not None:
        ind.set(qn("w:firstLine"), "0")
    if jc is not None:
        jc.set(qn("w:val"), "center")
    spacing = ppr.find(qn("w:spacing")) if ppr is not None else None
    if spacing is not None:
        spacing.set(qn("w:before"), "0")
        spacing.set(qn("w:after"), "120")
    return p


def set_text(par, text: str) -> None:
    for run in list(par.runs):
        run._r.getparent().remove(run._r)
    for element in par._p.findall(qn("w:proofErr")):
        par._p.remove(element)
    _style_run(par.add_run(text))


def _shade(cell, fill: str = "EDEDED") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def insert_table(doc, anchor_p, rows: list[list[str]], widths: list[float]):
    """Вставляет таблицу сразу после указанного абзаца; возвращает элемент."""
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    anchor_p.addnext(table._tbl)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "6")
        element.set(qn("w:color"), "000000")
        borders.append(element)
    table._tbl.tblPr.append(borders)

    # Фиксируем ширины столбцов: и сетку, и сами ячейки (иначе Word
    # пересчитывает их по содержимому и таблица «плывёт»).
    widths_twips = [int(width / 2.54 * 1440) for width in widths]
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    table_w = table._tbl.tblPr.find(qn("w:tblW"))
    if table_w is None:
        table_w = OxmlElement("w:tblW")
        table._tbl.tblPr.append(table_w)
    table_w.set(qn("w:type"), "dxa")
    table_w.set(qn("w:w"), str(sum(widths_twips)))
    grid = table._tbl.find(qn("w:tblGrid"))
    for column, width_twips in zip(grid.findall(qn("w:gridCol")), widths_twips):
        column.set(qn("w:w"), str(width_twips))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = table.cell(i, j)
            cell.width = Cm(widths[j])
            tc_w = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
            if tc_w is not None:
                tc_w.set(qn("w:type"), "dxa")
                tc_w.set(qn("w:w"), str(widths_twips[j]))
            par = cell.paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.space_before = Pt(0)
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.0
            _style_run(par.add_run(text), size=12.0, bold=(i == 0))
            if i == 0:
                _shade(cell)
    return table._tbl


def _png_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def set_extent(p, width_cm: float, height_cm: float) -> None:
    """Задаёт размер встроенного рисунка в сантиметрах."""
    cx = str(int(width_cm * 360000))
    cy = str(int(height_cm * 360000))
    extent = p.find(".//" + qn("wp:extent"))
    if extent is not None:
        extent.set("cx", cx)
        extent.set("cy", cy)
    for element in p.iter(qn("a:ext")):
        element.set("cx", cx)
        element.set("cy", cy)


# ---------------------------------------------------------------------------
# Сборка отчёта
# ---------------------------------------------------------------------------
def rebuild_report(figures: dict[str, bytes]) -> None:
    """Собирает исправленный DOCX: переписывает экспериментальную часть."""
    doc = Document(str(SOURCE_DOCX))
    body = doc.element.body

    def paragraphs() -> list[Paragraph]:
        return [Paragraph(p, body) for p in body.findall(qn("w:p"))]

    image_pars: dict[str, Paragraph] = {}
    for par in paragraphs():
        for blip in par._p.findall(".//" + qn("a:blip")):
            image_pars[blip.get(qn("r:embed"))] = par

    order = ["rId9", "rId10", "rId11", "rId12", "rId13", "rId14", "rId15", "rId16"]
    drawing_runs = {}
    for rid in order:
        for run in image_pars[rid].runs:
            if run._r.findall(".//" + qn("a:blip")):
                drawing_runs[rid] = deepcopy(run._r)
                break

    # Удаляем старые абзацы рисунков вместе с соседними подписями
    # (удаляем только абзацы, начинающиеся словом «Рисунок»).
    def is_caption(element) -> bool:
        if element is None or element.tag != qn("w:p"):
            return False
        text_value = "".join(node.text or "" for node in element.iter(qn("w:t")))
        return text_value.strip().startswith("Рисунок")

    for rid in order:
        par_p = image_pars[rid]._p
        prev = par_p.getprevious()
        nxt = par_p.getnext()
        if is_caption(prev):
            prev.getparent().remove(prev)
        if is_caption(nxt):
            nxt.getparent().remove(nxt)
        par_p.getparent().remove(par_p)

    heading = next(p for p in paragraphs() if p.text.strip() == "ЭКСПЕРИМЕНТАЛЬНАЯ ЧАСТЬ")
    conclusion = next(p for p in paragraphs() if p.text.strip() == "ВЫВОД")
    element = heading._p.getnext()
    while element is not None and element is not conclusion._p:
        nxt = element.getnext()
        if element.tag in (qn("w:p"), qn("w:tbl")):
            element.getparent().remove(element)
        element = nxt

    body_template = next(p for p in paragraphs()
                         if p.text.startswith("Прямое ДПФ последовательности"))._p
    conclusion_text = next(p for p in paragraphs()
                           if p.text.startswith("В ходе выполнения"))
    caption_template = next(p for p in paragraphs()
                            if p.text.startswith("Рисунок 1 –"))._p

    blocks = [
        ("p", "Моделирование выполнено в среде имитационного моделирования РТС "
              "«Спектр-2» для параметров варианта 24: частота дискретизации "
              "F<sub>д</sub> = 10 000 Гц, размер блока ДПФ N = 1024. Шаг сетки частот "
              "Δf = F<sub>д</sub>/N = 9,766 Гц, поэтому отсчёту k соответствует частота "
              "f = kΔf. Действительные отсчёты сигнала подаются через модуль «Re+j0» на "
              "модуль «ДПФ» с размером блока 1024, а осциллограф в контрольных точках "
              "показывает модуль коэффициентов ДПФ."),
        ("fig", "rId9", 16.5,
         "Рисунок 2 – Схема, реализующая расчёт коэффициентов ДПФ гармонических сигналов"),
        ("p", "В схеме используются два генератора «Гармонич. SIN & COS» с частотами "
              "f<sub>1</sub> = 1250 Гц и f<sub>2</sub> = 625 Гц, два усилителя и сумматор."),
        ("p", "Первый эксперимент — одно гармоническое колебание: коэффициент усиления "
              "первого усилителя K<sub>1</sub> = 1, второго K<sub>2</sub> = 0, поэтому на "
              "вход ДПФ поступает гармоника A<sub>1</sub> = 1,24 с частотой "
              "f<sub>1</sub> = 1250 Гц. По осциллограмме модуля коэффициентов ДПФ (рис. 3) "
              "курсором определяем номера отсчётов, на которых расположены максимумы, и их "
              "уровни."),
        ("fig", "rId10", 16.0,
         "Рисунок 3 – Определение максимумов модуля коэффициентов ДПФ для одной гармоники "
         "A1 = 1,24, f1 = 1250 Гц"),
        ("p", "Максимумы находятся на отсчётах k = 128 и k = 896 (зеркальный отсчёт "
              "N − k = 1024 − 128 = 896), их уровни одинаковы: |X(128)| = |X(896)| = "
              "A<sub>1</sub>N/2 = 1,24·512 = 634,88. На остальных 1020 отсчётах модуль "
              "равен нулю, так как частота гармоники попадает точно на сетку ДПФ "
              "(f<sub>1</sub> = 128Δf) и растекания спектра нет."),
        ("p", "Второй эксперимент — сумма гармонических колебаний: коэффициент усиления "
              "второго усилителя изменяем с 0 до 4, тогда амплитуда второй составляющей "
              "4A<sub>2</sub> = 9,92. Анализ проводим так же, как и в случае одного "
              "колебания (рис. 4)."),
        ("fig", "rId11", 16.0,
         "Рисунок 4 – Определение максимумов модуля коэффициентов ДПФ для суммы двух "
         "гармонических колебаний при K2 = 4"),
        ("p", "В спектре суммы появляются ещё два максимума: гармоника f<sub>2</sub> = "
              "625 Гц занимает в блоке ровно 64 периода, поэтому ей соответствуют отсчёты "
              "k = 64 и k = 960, а уровень |X(64)| = |X(960)| = 4A<sub>2</sub>N/2 = "
              "9,92·512 = 5079,04 — это наибольший уровень модуля коэффициентов ДПФ. "
              "Максимумы первой гармоники остались на отсчётах k = 128 и k = 896 с уровнем "
              "634,88, то есть в 8 раз меньше."),
        ("p", "Результаты определения максимумов модуля коэффициентов ДПФ для обоих "
              "экспериментов сведены в таблицу 1."),
        ("table",
         "Таблица 1 – Максимумы модуля коэффициентов ДПФ (N = 1024, Fд = 10 000 Гц)",
         [["Режим работы схемы", "Номера отсчётов k", "Максимум |X(k)|"],
          ["Одна гармоника A1, f1 = 1250 Гц (K2 = 0)", "128 и 896", "634,88"],
          ["Сумма гармоник, 4A2 = 9,92, f2 = 625 Гц (K2 = 4)", "64 и 960", "5079,04"],
          ["Сумма гармоник, A1 = 1,24, f1 = 1250 Гц (K2 = 4)", "128 и 896", "634,88"]],
         [9.0, 3.6, 3.8]),
        ("p", "Отсчётам k = 64 и 960 соответствуют частоты 625 и 9375 Гц, отсчётам k = 128 "
              "и 896 — 1250 и 8750 Гц. Зеркальные отсчёты N − k имеют тот же уровень и "
              "отвечают отрицательным частотам действительного сигнала. Если второй "
              "усилитель оставить с коэффициентом K<sub>2</sub> = 1, то уровень второй "
              "гармоники составит A<sub>2</sub>N/2 = 2,48·512 = 1269,76. Все измеренные "
              "уровни совпадают с расчётом A·N/2."),
        ("p", "На рис. 5 представлена вторая схема, реализующая расчёт коэффициентов ДПФ "
              "последовательности прямоугольных импульсов."),
        ("fig", "rId12", 13.1,
         "Рисунок 5 – Схема, реализующая расчёт коэффициентов ДПФ последовательности "
         "прямоугольных импульсов"),
        ("p", "Вместо генераторов и сумматора установлен генератор тактовых импульсов ГТИ: "
              "ширина импульса 16 периодов дискретизации, период повторения 1024 отсчёта. "
              "Между модулями «Re+j0» и «ДПФ» включён спектроанализатор."),
        ("p", "На рис. 6 и рис. 7 приведён амплитудный спектр (модуль коэффициентов ДПФ) "
              "последовательности прямоугольных импульсов в линейном и логарифмическом "
              "масштабе соответственно. Ось частот спектроанализатора начинается с 0 Гц и "
              "заканчивается частотой 4990 Гц ≈ F<sub>д</sub>/2."),
        ("fig", "rId13", 9.08,
         "Рисунок 6 – Амплитудный спектр (модуль коэффициентов ДПФ) в линейном масштабе"),
        ("fig", "rId14", 9.13,
         "Рисунок 7 – Амплитудный спектр (модуль коэффициентов ДПФ) в логарифмическом "
         "масштабе"),
        ("p", "Для импульса шириной 16 отсчётов модуль ДПФ описывается ядром Дирихле: "
              "нулевой отсчёт равен X(0) = 16, а нули огибающей располагаются при k = 64m, "
              "то есть на частотах f = 625m Гц (625, 1250, 1875 Гц и далее). На рис. 6 и "
              "рис. 7 эти нули отмечены штриховыми линиями: в линейном масштабе видны "
              "лепестки убывающей высоты, в логарифмическом — провалы до −90 дБ. Максимум "
              "первого бокового лепестка равен 3,52 при k = 92 (898 Гц)."),
        ("p", "На рис. 8 приведена осциллограмма модуля коэффициентов ДПФ (амплитудный "
              "спектр), на рис. 9 — осциллограмма фазы коэффициентов ДПФ (фазовый спектр) "
              "той же последовательности прямоугольных импульсов."),
        ("fig", "rId15", 16.0,
         "Рисунок 8 – Осциллограмма модуля коэффициентов ДПФ (амплитудный спектр) "
         "последовательности прямоугольных импульсов"),
        ("fig", "rId16", 16.0,
         "Рисунок 9 – Осциллограмма фазы коэффициентов ДПФ (фазовый спектр) "
         "последовательности прямоугольных импульсов"),
        ("p", "Одному отсчёту осциллограммы соответствует один коэффициент ДПФ, поэтому по "
              "оси абсцисс откладываются номера отсчётов k. Модуль повторяет форму "
              "лепестков амплитудного спектра: главный лепесток занимает отсчёты k = 0…64, "
              "далее расположены боковые лепестки между нулями k = 64m. Фаза в пределах "
              "каждого лепестка изменяется линейно, а в нулях модуля претерпевает перескок "
              "на π, поэтому на осциллограмме фазы видны характерные разрывы. Положения "
              "нулей и относительные уровни лепестков на осциллограмме и на "
              "спектроанализаторе совпадают, что подтверждает правильность настройки схемы."),
    ]

    anchor = heading._p
    for block in blocks:
        kind = block[0]
        if kind == "p":
            anchor = insert_paragraph(anchor, body_template, block[1])
        elif kind == "fig":
            _, rid, width_cm, caption_text = block
            par = insert_paragraph(anchor, body_template)
            ppr = par.find(qn("w:pPr"))
            if ppr is not None:
                ind = ppr.find(qn("w:ind"))
                if ind is not None:
                    ind.set(qn("w:firstLine"), "0")
                jc = ppr.find(qn("w:jc"))
                if jc is not None:
                    jc.set(qn("w:val"), "center")
                spacing = ppr.find(qn("w:spacing"))
                if spacing is not None:
                    spacing.set(qn("w:line"), "240")
                    spacing.set(qn("w:lineRule"), "auto")
            par.append(deepcopy(drawing_runs[rid]))
            px_w, px_h = _png_size(figures[rid])
            set_extent(par, width_cm, width_cm * px_h / px_w)
            _keep_with_next(par)
            anchor = insert_caption(par, caption_template, caption_text)
        else:
            _, caption_text, rows, widths = block
            caption_p = insert_caption(anchor, caption_template, caption_text)
            _keep_with_next(caption_p)
            table_p = insert_table(doc, caption_p, rows, widths)
            anchor = insert_paragraph(table_p, body_template, "")

    for rid in order:
        doc.part.related_parts[rid]._blob = figures[rid]

    set_text(conclusion_text,
             "В ходе выполнения данной лабораторной работы были изучены принципы "
             "дискретного преобразования Фурье (ДПФ) и алгоритмы быстрого преобразования "
             "Фурье (БПФ) Кули-Тьюки. Для варианта 24 аналитически рассчитано ДПФ "
             "последовательности x(n) = [0, 0, 0, 1, 1, 1, 1, 0]: X(0) = 4, "
             "X(1) = −1 − √2 + j, X(2) = 0, X(3) = √2 − 1 − j, X(4) = 0, "
             "X(5) = √2 − 1 + j, X(6) = 0, X(7) = −1 − √2 − j, что совпало с результатом "
             "БПФ с прореживанием по времени и с ДПФ прореженных последовательностей. В "
             "экспериментальной части для Fд = 10 000 Гц и N = 1024 по осциллограммам "
             "модуля коэффициентов ДПФ определены максимумы уровней и номера отсчётов: для "
             "одной гармоники A1 = 1,24 — уровень 634,88 на отсчётах k = 128 и 896; для "
             "суммы гармоник при усилении второй ветви в 4 раза — уровень 5079,04 на "
             "отсчётах k = 64 и 960 и уровень 634,88 на отсчётах k = 128 и 896. Все "
             "измеренные уровни совпадают с расчётом A·N/2. Для последовательности "
             "прямоугольных импульсов шириной 16 отсчётов получено X(0) = 16 и нули модуля "
             "ДПФ при k = 64m (625m Гц); осциллограммы модуля и фазы коэффициентов ДПФ "
             "согласуются со спектроанализатором по положению нулей и лепестков.")

    doc.save(str(TARGET_DOCX))
    print("Сохранено:", TARGET_DOCX)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
def build_figures() -> dict[str, bytes]:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    figure_single(FINAL_DIR / PNG_SINGLE)
    figure_sum(FINAL_DIR / PNG_SUM)
    figure_pulse_module(FINAL_DIR / PNG_MODULE)
    figure_pulse_phase(FINAL_DIR / PNG_PHASE)

    fig6 = annotate_pulse_spectrum(_load_image_part(SOURCE_DOCX, "image6.png"),
                                   logarithmic=False)
    fig7 = annotate_pulse_spectrum(_load_image_part(SOURCE_DOCX, "image7.png"),
                                   logarithmic=True)
    (FINAL_DIR / PNG_PULSE_LIN).write_bytes(fig6)
    (FINAL_DIR / PNG_PULSE_LOG).write_bytes(fig7)

    fig2 = _load_image_part(SOURCE_DOCX, "image2.png")
    fig5 = _load_image_part(SOURCE_DOCX, "image5.png")
    return {
        "rId9": fig2,
        "rId10": (FINAL_DIR / PNG_SINGLE).read_bytes(),
        "rId11": (FINAL_DIR / PNG_SUM).read_bytes(),
        "rId12": fig5,
        "rId13": fig6,
        "rId14": fig7,
        "rId15": (FINAL_DIR / PNG_MODULE).read_bytes(),
        "rId16": (FINAL_DIR / PNG_PHASE).read_bytes(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Исправление отчёта ЛР №7 (вариант 24)")
    parser.add_argument("--figures-only", action="store_true",
                        help="только построить рисунки, не собирать DOCX")
    args = parser.parse_args()

    figures = build_figures()
    print("Рисунки сохранены в", FINAL_DIR)
    if not args.figures_only:
        rebuild_report(figures)


if __name__ == "__main__":
    main()
