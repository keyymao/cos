#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расчётные иллюстрации ЛР №7 (не скриншоты «Спектр-2»)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
import numpy as np
from scipy.signal import spectrogram

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)
DATA = json.loads((HERE / "variant_data_lab7_24_53.json").read_text(encoding="utf-8"))

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.dpi": 130,
    "savefig.dpi": 240,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "lines.linewidth": 1.3,
})

BLUE = "#22577A"
CYAN = "#38A3A5"
GREEN = "#57CC99"
LIGHT = "#C7F9CC"
ORANGE = "#F4A261"
RED = "#C44536"
DARK = "#263238"


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(ASSETS / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved:", ASSETS / name)


def stem(ax, x, y, color=BLUE, width=1.0):
    markerline, stemlines, baseline = ax.stem(x, y, basefmt=" ")
    plt.setp(markerline, marker="o", markersize=4, color=color)
    plt.setp(stemlines, linewidth=width, color=color)
    plt.setp(baseline, visible=False)


def fft_graph():
    fig, ax = plt.subplots(figsize=(13.2, 8.0))
    ax.set_xlim(-1.65, 9.1)
    ax.set_ylim(-1.35, 8.2)
    ax.axis("off")
    xs = [0.0, 2.15, 4.3, 6.45]
    ys = [7 - i for i in range(8)]
    inputs = DATA["bit_reversed"]
    input_names = [0, 4, 2, 6, 1, 5, 3, 7]
    for i, y in enumerate(ys):
        ax.text(-1.52, y, f"x({input_names[i]}) = {inputs[i]}", ha="left", va="center", fontsize=10)
        ax.plot([xs[0] - 0.15, xs[0]], [y, y], color=DARK, lw=1.0)

    # Соединения бабочек: этап 1 — пары через 1, этап 2 — через 2, этап 3 — через 4.
    # Верхний вход a идёт на оба выхода без изменений. Нижний вход b сначала
    # умножается на W, после чего идёт на верхний выход со знаком + и на нижний со знаком −.
    stage_specs = [
        (0, 1, [(0, 1, "$W_2^0=1$"), (2, 3, "$W_2^0=1$"), (4, 5, "$W_2^0=1$"), (6, 7, "$W_2^0=1$")]),
        (1, 2, [(0, 2, "$W_4^0=1$"), (1, 3, "$W_4^1=-j$"), (4, 6, "$W_4^0=1$"), (5, 7, "$W_4^1=-j$")]),
        (2, 3, [(0, 4, "$W_8^0$"), (1, 5, "$W_8^1$"), (2, 6, "$W_8^2$"), (3, 7, "$W_8^3$")]),
    ]
    for source_stage, target_stage, butterflies in stage_specs:
        x0, x1 = xs[source_stage], xs[target_stage]
        branch = x0 + 0.43 * (x1 - x0)
        for upper, lower, twiddle in butterflies:
            yu, yl = ys[upper], ys[lower]
            # Две независимые ветви a и W·b; разветвление выполняется после узла умножения.
            ax.plot([x0 + 0.14, branch], [yu, yu], color="#78909C", lw=0.9, zorder=1)
            ax.plot([x0 + 0.14, branch], [yl, yl], color=ORANGE, lw=1.15, zorder=1)
            for start_y, color in [(yu, "#78909C"), (yl, ORANGE)]:
                ax.plot([branch, x1 - 0.14], [start_y, yu], color=color, lw=0.9, zorder=1)
                ax.plot([branch, x1 - 0.14], [start_y, yl], color=color, lw=0.9, zorder=1)
                ax.plot(branch, start_y, marker="o", ms=2.2, color=color, zorder=2)
            ax.text(branch, yl + 0.22, twiddle, ha="center", va="bottom", fontsize=9.2, color=RED,
                    bbox=dict(boxstyle="round,pad=0.10", fc="white", ec="none", alpha=0.92))
            ax.text(x1 - 0.32, yl - 0.13, "−", color=RED, fontsize=13, ha="center", va="center")
            ax.text(x1 - 0.32, yu + 0.12, "+", color=BLUE, fontsize=10, ha="center", va="center")

    stage1_values = [1, 1, 1, 1, 1, 1, 1, 1]
    stage2_values = [2, 0, 2, 0, 2, 0, 2, 0]
    for stage, x in enumerate(xs):
        for i, y in enumerate(ys):
            radius = 0.16 if stage in (1, 2) else 0.105
            circle = Circle((x, y), radius, fc="white", ec=BLUE, lw=1.4, zorder=3)
            ax.add_patch(circle)
            if stage == 1:
                ax.text(x, y, str(stage1_values[i]), ha="center", va="center", fontsize=8.2, zorder=4)
            elif stage == 2:
                ax.text(x, y, str(stage2_values[i]), ha="center", va="center", fontsize=8.2, zorder=4)
        if stage < 3:
            ax.text(x, 7.72, ["Вход с бит-\nреверсией", "Этап 1\nДПФ-2", "Этап 2\nДПФ-4"][stage],
                    ha="center", va="bottom", fontsize=11, fontweight="bold", color=BLUE)
    ax.text(xs[-1], 7.72, "Этап 3\nДПФ-8", ha="center", va="bottom", fontsize=11, fontweight="bold", color=BLUE)

    output_text = [
        "X(0) = 4",
        "X(1) = −2,414 + j",
        "X(2) = 0",
        "X(3) = 0,414 − j",
        "X(4) = 0",
        "X(5) = 0,414 + j",
        "X(6) = 0",
        "X(7) = −2,414 − j",
    ]
    for i, y in enumerate(ys):
        ax.plot([xs[-1], xs[-1] + 0.16], [y, y], color=DARK, lw=1.0)
        ax.text(xs[-1] + 0.24, y, output_text[i], ha="left", va="center", fontsize=9.7)
    ax.text(2.2, -0.85,
            "Каждая «бабочка»: верхний выход = a + W·b, нижний выход = a − W·b.\n"
            "Порядок входов: x(0), x(4), x(2), x(6), x(1), x(5), x(3), x(7).",
            ha="center", va="center", fontsize=10.5, color=DARK,
            bbox=dict(boxstyle="round,pad=0.45", fc="#F4F8FA", ec="#B0BEC5"))
    save(fig, "fig1_fft_graph.png")


def dft8_plot():
    values = np.array([complex(v["re"], v["im"]) for v in DATA["dft"]])
    k = np.arange(8)
    fig, axes = plt.subplots(2, 1, figsize=(9.3, 7.1), sharex=True)
    stem(axes[0], k, np.abs(values))
    axes[0].set_ylabel("|X(k)|")
    axes[0].set_title("ДПФ последовательности x(n) = [0, 0, 0, 1, 1, 1, 1, 0]")
    axes[0].set_ylim(0, 4.7)
    for i in [0, 1, 3, 5, 7]:
        axes[0].annotate(f"{abs(values[i]):.3f}", (i, abs(values[i])), xytext=(0, 7), textcoords="offset points", ha="center")
    stem(axes[1], k, np.angle(values), color=CYAN)
    axes[1].set_ylabel("arg X(k), рад")
    axes[1].set_xlabel("Номер частотного отсчёта k")
    axes[1].set_xticks(k)
    axes[1].set_yticks([-math.pi, -3*math.pi/4, -math.pi/2, -math.pi/4, 0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi])
    axes[1].set_yticklabels(["−π", "−3π/4", "−π/2", "−π/4", "0", "π/4", "π/2", "3π/4", "π"])
    axes[1].axhline(0, color=DARK, lw=0.7)
    fig.tight_layout()
    save(fig, "fig2_dft8.png")


def block(ax, xy, width, height, text, fc="#EDF6F9"):
    rect = Rectangle(xy, width, height, facecolor=fc, edgecolor=BLUE, lw=1.4)
    ax.add_patch(rect)
    ax.text(xy[0] + width/2, xy[1] + height/2, text, ha="center", va="center", fontsize=10)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13, color=DARK, lw=1.2))


def harmonic_scheme():
    fig, ax = plt.subplots(figsize=(12.6, 5.4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")
    block(ax, (0.2, 4.0), 2.4, 1.0, "Гармоника 1\n$A_1\cos(2πf_1t)$")
    block(ax, (0.2, 1.0), 2.4, 1.0, "Гармоника 2\n$A_2\cos(2πf_2t)$")
    block(ax, (3.3, 4.0), 1.55, 1.0, "K₁ = 1", fc=LIGHT)
    block(ax, (3.3, 1.0), 1.55, 1.0, "K₂ = 0 / 1 / 4", fc=LIGHT)
    ax.add_patch(Circle((6.25, 3.0), 0.43, fc="#FFF3E0", ec=ORANGE, lw=1.5))
    ax.text(6.25, 3.0, "Σ", ha="center", va="center", fontsize=18)
    block(ax, (7.35, 2.45), 1.75, 1.1, "Re + j·0\nN = 1024")
    block(ax, (9.85, 2.45), 1.6, 1.1, "ДПФ\n1024", fc="#DCEEFF")
    block(ax, (12.15, 2.45), 1.55, 1.1, "|X(k)|\nмодуль", fc="#E8F5E9")
    arrow(ax, (2.6, 4.5), (3.3, 4.5))
    arrow(ax, (2.6, 1.5), (3.3, 1.5))
    arrow(ax, (4.85, 4.5), (5.95, 3.25))
    arrow(ax, (4.85, 1.5), (5.95, 2.75))
    arrow(ax, (6.68, 3.0), (7.35, 3.0))
    arrow(ax, (9.1, 3.0), (9.85, 3.0))
    arrow(ax, (11.45, 3.0), (12.15, 3.0))
    ax.text(7.0, 5.55, "Схема численного эксперимента с двумя гармониками", ha="center", fontsize=13, fontweight="bold", color=BLUE)
    ax.text(7.0, 0.2,
            "$F_д=10000$ Гц; $f_1=1250$ Гц ($k=128$); $f_2=625$ Гц ($k=64$).\n"
            "K₂=0 — одна гармоника; K₂=1 — сумма $A_1+A_2$; K₂=4 — практический пункт методички.",
            ha="center", va="center", fontsize=10.5)
    save(fig, "fig3_harmonic_scheme.png")


def harmonic_signals():
    n = np.arange(DATA["N"])
    fd = DATA["Fd"]
    single = DATA["A1"] * np.cos(2*np.pi*DATA["f1"]*n/fd)
    sum_variant = single + DATA["A2"] * np.cos(2*np.pi*DATA["f2"]*n/fd)
    sum_gain4 = single + 4*DATA["A2"] * np.cos(2*np.pi*DATA["f2"]*n/fd)
    return single, sum_variant, sum_gain4


def harmonic_spectra():
    single, sum_variant, sum_gain4 = harmonic_signals()
    spectra = [np.abs(np.fft.fft(v)) for v in (single, sum_variant, sum_gain4)]
    k = np.arange(DATA["N"])

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5), gridspec_kw={"width_ratios": [1.45, 1]})
    axes[0].plot(k, spectra[0], color=BLUE, lw=0.65)
    peak1 = DATA["A1"] * DATA["N"] / 2
    axes[0].scatter([128, 896], [peak1, peak1], color=RED, zorder=3)
    axes[0].set_xlim(0, 1023)
    axes[0].set_ylim(-20, peak1 * 1.12)
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("|X(k)|")
    axes[0].set_title("Одна гармоника $A_1\cos(2πf_1t)$: весь блок")
    axes[0].annotate(f"k = 128, f = {DATA['f1']:.0f} Гц\n|X| = {peak1:.2f}", (128, peak1),
                     xytext=(200, peak1 * 0.86),
                     arrowprops=dict(arrowstyle="->", color=RED), color=RED)
    zoom = np.arange(110, 147)
    stem(axes[1], zoom, spectra[0][zoom], width=0.9)
    axes[1].set_title("Увеличение около k = 128")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("|X(k)|")
    axes[1].set_ylim(-5, peak1 * 1.12)
    fig.suptitle("Расчётный спектр одиночной гармоники; зеркальный пик находится при k = 896", fontsize=12.5)
    fig.tight_layout()
    save(fig, "fig4_single_spectrum.png")

    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.5), gridspec_kw={"width_ratios": [1.5, 1, 1]})
    axes[0].plot(k, spectra[1], color=CYAN, lw=0.65, label="$A_1+A_2$ (K₂=1)")
    axes[0].plot(k, spectra[2], color=BLUE, lw=0.65, alpha=0.85, label="$A_1+4A_2$ (K₂=4)")
    axes[0].set_xlim(0, 1023)
    peak_max = DATA["A2"] * 4 * DATA["N"] / 2
    axes[0].set_ylim(-peak_max * 0.03, peak_max * 1.06)
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("|X(k)|")
    axes[0].set_title("Весь частотный блок")
    axes[0].legend(fontsize=8.5, loc="upper center")
    for ax, center, title in [(axes[1], 64, f"Пик f₂ = {DATA['f2']:.0f} Гц"),
                              (axes[2], 128, f"Пик f₁ = {DATA['f1']:.0f} Гц")]:
        zoom = np.arange(center-12, center+13)
        stem(ax, zoom, spectra[1][zoom], color=CYAN, width=0.8)
        stem(ax, zoom, spectra[2][zoom], color=BLUE, width=0.8)
        ax.set_title(title)
        ax.set_xlabel("k")
        ax.set_ylabel("|X(k)|")
        ax.set_ylim(-peak_max * 0.02, peak_max * 1.06 if center == 64 else peak1 * 1.15)
    fig.suptitle("Сумма гармоник: амплитуда пика равна A·N/2; показаны оба режима второй ветви", fontsize=12.5)
    fig.tight_layout()
    save(fig, "fig5_sum_spectrum.png")


def rectangular_data():
    pulse = np.zeros(DATA["N"])
    pulse[:16] = 1.0
    spectrum = np.fft.fft(pulse)
    return pulse, spectrum


def rectangular_plots():
    pulse, spectrum = rectangular_data()
    magnitude = np.abs(spectrum)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.6), gridspec_kw={"width_ratios": [1, 1.55]})
    stem(axes[0], np.arange(80), pulse[:80], width=0.9)
    axes[0].set_title("Один прямоугольный импульс в блоке")
    axes[0].set_xlabel("n")
    axes[0].set_ylabel("x(n)")
    axes[0].set_ylim(-0.08, 1.18)
    axes[0].annotate("ширина = 16", (8, 1), xytext=(32, 0.85), arrowprops=dict(arrowstyle="->", color=RED), color=RED)
    k = np.arange(513)
    axes[1].plot(k, magnitude[:513], color=BLUE, lw=1.0)
    axes[1].set_title("Модуль ДПФ, линейный масштаб")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("|X(k)|")
    axes[1].axvline(64, color=RED, ls="--", lw=1.0, label="первый нуль: k = 64")
    axes[1].axvline(128, color=ORANGE, ls="--", lw=1.0, label="второй нуль: k = 128")
    axes[1].scatter([0, 64, 128], [magnitude[0], magnitude[64], magnitude[128]], color=[BLUE, RED, ORANGE], zorder=3)
    axes[1].legend()
    fig.suptitle(f"Прямоугольный импульс: N = 1024, Fд = {DATA['Fd']:.0f} Гц, "
                 "период повторения = 1024 отсчёта", fontsize=12.5)
    fig.tight_layout()
    save(fig, "fig6_rect_dft.png")

    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    db = 20*np.log10(np.maximum(magnitude[:513], 1e-4))
    ax.plot(k, db, color=BLUE, lw=1.05)
    ax.set_ylim(-82, 27)
    ax.set_xlim(0, 512)
    ax.set_xlabel("k")
    ax.set_ylabel("20 lg |X(k)|, дБ")
    ax.set_title("Спектр прямоугольного импульса в логарифмическом масштабе")
    for z in [64, 128, 192, 256, 320, 384, 448, 512]:
        ax.axvline(z, color=RED, ls=":", lw=0.75, alpha=0.65)
    ax.axhline(0, color=ORANGE, ls="--", lw=0.9)
    ax.annotate("X(0) = 16 → 24,08 дБ", (0, db[0]), xytext=(55, 20), arrowprops=dict(arrowstyle="->", color=RED), color=RED)
    ax.text(265, -62, f"Нули огибающей: k = 64m\n$f = {DATA['Fd']/16:.0f}m$ Гц", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#B0BEC5"))
    fig.tight_layout()
    save(fig, "fig7_rect_db.png")


def pulse_spectrogram():
    fd = DATA["Fd"]
    periods = 8
    pulse_train = np.tile(rectangular_data()[0], periods)
    t = np.arange(len(pulse_train)) / fd
    f, ts, sxx = spectrogram(
        pulse_train, fs=fd, window="hann", nperseg=256, noverlap=224,
        nfft=1024, detrend=False, scaling="spectrum", mode="magnitude",
    )
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 7.2), gridspec_kw={"height_ratios": [1, 2.25]})
    show = t <= 0.55
    axes[0].plot(t[show]*1000, pulse_train[show], color=BLUE, lw=1.0)
    axes[0].set_ylabel("x(t)")
    axes[0].set_xlabel("Время, мс")
    axes[0].set_title("Периодическая последовательность: первые 3,2 периода")
    axes[0].set_ylim(-0.08, 1.18)
    keep = f <= 1000
    mesh = axes[1].pcolormesh(ts, f[keep], 20*np.log10(np.maximum(sxx[keep], 1e-5)), shading="auto", cmap="viridis", vmin=-65, vmax=5)
    axes[1].set_ylabel("Частота, Гц")
    axes[1].set_xlabel("Время, с")
    axes[1].set_title("Спектрограмма: Hann, окно 256 отсчётов, перекрытие 224, ДПФ 1024")
    cbar = fig.colorbar(mesh, ax=axes[1], pad=0.015)
    cbar.set_label("Амплитуда, дБ")
    fig.suptitle(f"Численное моделирование прямоугольных импульсов; Fд = {DATA['Fd']:.0f} Гц", fontsize=12.5)
    fig.tight_layout()
    save(fig, "fig8_spectrogram.png")


def main():
    # В отчёт входит только граф БПФ (рисунок 1); остальные расчётные графики
    # оставлены как вспомогательные и по умолчанию не строятся.
    fft_graph()
    print("Все иллюстрации сохранены в", ASSETS)


if __name__ == "__main__":
    main()
