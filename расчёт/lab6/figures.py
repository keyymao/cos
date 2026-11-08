#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Графики и структурная схема для ЛР №6 (вариант 12 / зачётка 06)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
from scipy import signal

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets"
OUT.mkdir(exist_ok=True)
d = json.loads((HERE / "variant_data_lab6.json").read_text(encoding="utf-8"))

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "axes.linewidth": 0.9,
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
})
BLUE = "#205493"
RED = "#c0392b"
GREEN = "#27854b"
GRAY = "#666666"

n = np.array([row["n"] for row in d["coefficients"]])
ideal = np.array([row["h_ideal"] for row in d["coefficients"]])
window = np.array([row["w"] for row in d["coefficients"]])
b = np.array([row["b"] for row in d["coefficients"]])
fd, f1, f3, fc = d["Fd"], d["F1"], d["F3"], d["Fc"]
frequencies = np.linspace(0.0, fd / 2.0, 200001)
_, response = signal.freqz(b, worN=2.0 * np.pi * frequencies / fd)
magnitude = np.abs(response)
db = 20.0 * np.log10(np.maximum(magnitude, 1e-8))


def stem_plot(values: np.ndarray, filename: str, title: str, ylabel: str, ylim=None) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    markerline, stemlines, baseline = ax.stem(n, values, basefmt="k-")
    plt.setp(markerline, marker="o", markersize=5.5, markerfacecolor=BLUE, markeredgecolor=BLUE)
    plt.setp(stemlines, color=BLUE, linewidth=1.5)
    plt.setp(baseline, color="black", linewidth=0.8)
    ax.set_xlabel("Отсчёт n")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.set_xticks(n)
    ax.grid(True, linestyle=":", alpha=0.65)
    ax.axhline(0.0, color="black", linewidth=0.8)
    if ylim:
        ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=180)
    plt.close(fig)


def structure() -> None:
    fig, ax = plt.subplots(figsize=(12.2, 5.8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8)
    ax.axis("off")

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
            linewidth=1.2, color="#222222",
        ))

    def delay(x):
        ax.add_patch(Rectangle(
            (x - 0.55, 4.55), 1.1, 0.9, facecolor="#eaf1f8",
            edgecolor=BLUE, linewidth=1.3, zorder=2,
        ))
        ax.text(x, 5.0, r"$z^{-1}$", ha="center", va="center", fontsize=13, zorder=3)

    def tap(x, label):
        ax.plot([x, x], [5.0, 3.25], color="#222222", linewidth=1.2)
        ax.add_patch(Circle((x, 5.0), 0.06, color="#222222", zorder=4))
        ax.add_patch(Rectangle(
            (x - 0.65, 2.45), 1.3, 0.8, facecolor="#eef7ef",
            edgecolor=GREEN, linewidth=1.2,
        ))
        ax.text(x, 2.85, label, ha="center", va="center", fontsize=11)
        arrow(x + 0.65, 2.85, 13.25, 2.85)

    # Цепь задержек: показаны крайние звенья, середина обозначена многоточием.
    arrow(0.25, 5.0, 1.25, 5.0)
    ax.text(0.25, 5.35, "Вход x(k)", fontsize=11)
    ax.plot([1.3, 12.7], [5.0, 5.0], color="#222222", linewidth=1.2, zorder=0)
    for x in [2.3, 4.3, 9.7, 11.7]:
        delay(x)
    ax.text(7.5, 5.0, "···", fontsize=28, ha="center", va="center", backgroundcolor="white")
    ax.text(7.5, 5.65, r"$z^{-3}\ldots z^{-14}$", fontsize=10, ha="center")
    for x, label in zip(
        [1.3, 3.3, 5.3, 10.7, 12.7],
        [r"$b_0$", r"$b_1$", r"$b_2$", r"$b_{15}$", r"$b_{16}$"],
    ):
        tap(x, label)

    # Общий сумматор и выход.
    ax.plot([13.3, 13.3], [2.85, 5.0], color="#222222", linewidth=1.2)
    arrow(13.3, 5.0, 13.58, 5.0)
    ax.add_patch(Circle((14.0, 5.0), 0.42, facecolor="#fff4e8", edgecolor=RED, linewidth=1.3))
    ax.text(14.0, 5.0, "Σ", fontsize=18, ha="center", va="center")
    arrow(14.42, 5.0, 15.45, 5.0)
    ax.text(15.45, 5.35, "Выход y(k)", fontsize=11, ha="right")

    ax.text(8.0, 7.25, "Прямая форма КИХ-фильтра: R = 16, N = 17", fontsize=14,
            fontweight="bold", ha="center")
    ax.text(8.0, 6.45, "16 последовательных линий задержки; 17 усилителей с коэффициентами b₀…b₁₆",
            fontsize=11, ha="center")
    ax.text(8.0, 1.35, "Коэффициенты берутся из таблицы 2 и вводятся со своими знаками",
            fontsize=11, ha="center", color=GRAY)
    ax.text(8.0, 0.75, "y(k) = Σ b(i)·x(k−i), i = 0…16", fontsize=12, ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "fig4_structure.png", dpi=180)
    plt.close(fig)


def ach_linear() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 8.0))
    ax = axes[0]
    ax.plot(frequencies, magnitude, color=BLUE, linewidth=1.7)
    ax.fill_between(frequencies, 0.95, 1.05, where=frequencies >= f1, color="#dff0e4", alpha=0.8)
    ax.axhline(1.0, color=GRAY, linestyle="--", linewidth=0.9)
    ax.axvline(f3, color=RED, linestyle="--", linewidth=1.1)
    ax.axvline(fc, color=GRAY, linestyle=":", linewidth=1.1)
    ax.axvline(f1, color=GREEN, linestyle="--", linewidth=1.1)
    ax.set_xlim(0, fd / 2)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("|H(f)|")
    ax.set_title("а) АЧХ во всей основной полосе частот", fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.text(f3 + 70, 0.14, "F₃ = 1005 Гц", color=RED, fontsize=10)
    ax.text(fc + 70, 0.57, "Fc = 1762,5 Гц", color=GRAY, fontsize=10)
    ax.text(f1 + 70, 0.82, "F₁ = 2520 Гц", color=GREEN, fontsize=10)

    ax = axes[1]
    ax.plot(frequencies, magnitude, color=BLUE, linewidth=1.8)
    ax.axhline(0.01, color=RED, linestyle="--", linewidth=1.0, label="δ₂ = 0,01")
    ax.axhline(0.95, color=GREEN, linestyle="--", linewidth=1.0)
    ax.axhline(1.05, color=GREEN, linestyle="--", linewidth=1.0, label="Допуск в ПП: 1 ± 0,05")
    ax.axvline(f3, color=RED, linestyle="--", linewidth=1.1)
    ax.axvline(fc, color=GRAY, linestyle=":", linewidth=1.1)
    ax.axvline(f1, color=GREEN, linestyle="--", linewidth=1.1)
    ax.scatter(
        [f3, fc, f1],
        [d["points"][1]["magnitude"], d["points"][2]["magnitude"], d["points"][3]["magnitude"]],
        color=[RED, GRAY, GREEN], s=32, zorder=4,
    )
    ax.set_xlim(700, 2850)
    ax.set_ylim(0, 1.12)
    ax.set_xlabel("Частота f, Гц")
    ax.set_ylabel("|H(f)|")
    ax.set_title("б) Переходная полоса и заданные границы", fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout(h_pad=2.0)
    fig.savefig(OUT / "fig5_ach_linear.png", dpi=180)
    plt.close(fig)


def ach_db() -> None:
    fig, ax = plt.subplots(figsize=(9.4, 4.9))
    ax.plot(frequencies, db, color=BLUE, linewidth=1.7)
    ax.axhline(-40.0, color=RED, linestyle="--", linewidth=1.1, label="−40 дБ")
    ax.axvline(f3, color=RED, linestyle="--", linewidth=1.1)
    ax.axvline(f1, color=GREEN, linestyle="--", linewidth=1.1)
    ax.scatter(
        [f3, f1],
        [-d["points"][1]["attenuation_db"], -d["points"][3]["attenuation_db"]],
        color=[RED, GREEN], s=38, zorder=4,
    )
    ax.annotate(
        "F₃: −40,292 дБ", xy=(f3, -d["points"][1]["attenuation_db"]),
        xytext=(1320, -57), arrowprops={"arrowstyle": "->", "color": RED},
        color=RED, fontsize=10, bbox={"boxstyle": "round", "fc": "#fdecea", "ec": RED},
    )
    ax.annotate(
        "F₁: −0,084 дБ", xy=(f1, -d["points"][3]["attenuation_db"]),
        xytext=(2940, -22), arrowprops={"arrowstyle": "->", "color": GREEN},
        color=GREEN, fontsize=10, bbox={"boxstyle": "round", "fc": "#eaf6ee", "ec": GREEN},
    )
    ax.set_xlim(0, fd / 2)
    ax.set_ylim(-80, 5)
    ax.set_xlabel("Частота f, Гц")
    ax.set_ylabel("20 lg |H(f)|, дБ")
    ax.set_title("АЧХ синтезированного ФВЧ в логарифмическом масштабе", fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.65)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig6_ach_db.png", dpi=180)
    plt.close(fig)


def causal_impulse() -> None:
    values = np.array(d["impulse_response"])
    k = np.arange(len(values))
    fig, ax = plt.subplots(figsize=(9.4, 4.7))
    markerline, stemlines, baseline = ax.stem(k, values, basefmt="k-")
    plt.setp(markerline, marker="o", markersize=5, markerfacecolor=BLUE, markeredgecolor=BLUE)
    plt.setp(stemlines, color=BLUE, linewidth=1.4)
    plt.setp(baseline, color="black", linewidth=0.8)
    ax.axvline(8, color=RED, linestyle="--", linewidth=1.0, label="Центр симметрии: k = 8")
    ax.set_xlabel("Дискретное время k")
    ax.set_ylabel("y(k)")
    ax.set_title("Реакция каузального фильтра на единичный импульс", fontweight="bold")
    ax.set_xticks(k)
    ax.grid(True, linestyle=":", alpha=0.65)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "fig7_causal_ih.png", dpi=180)
    plt.close(fig)


def main() -> None:
    stem_plot(ideal, "fig1_ideal_ih.png", "ИХ идеального ФВЧ (17 отсчётов)", "hᵤ(n)")
    stem_plot(window, "fig2_kaiser_window.png", "Оконная последовательность Кайзера", "w(n)", (-0.03, 1.08))
    stem_plot(b, "fig3_real_ih.png", "ИХ реального ФВЧ после применения окна", "h(n)")
    structure()
    ach_linear()
    ach_db()
    causal_impulse()
    for path in sorted(OUT.glob("*.png")):
        print("saved:", path)


if __name__ == "__main__":
    main()
