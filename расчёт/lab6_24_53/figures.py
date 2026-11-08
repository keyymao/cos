#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Графики домашнего расчёта ЛР №6 (вариант 24 / зачётка 53).

Строятся три рисунка по п. 1.1 методических указаний: ИХ «идеального» фильтра,
оконная функция Кайзера и ИХ реального спроектированного фильтра.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "assets"
OUT.mkdir(exist_ok=True)
d = json.loads((HERE / "variant_data_lab6_24_53.json").read_text(encoding="utf-8"))

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 11,
    "axes.linewidth": 0.9,
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
})
BLUE = "#205493"

n = np.array([row["n"] for row in d["coefficients"]])
ideal = np.array([row["h_ideal"] for row in d["coefficients"]])
window = np.array([row["w"] for row in d["coefficients"]])
b = np.array([row["b"] for row in d["coefficients"]])


def stem_plot(values: np.ndarray, filename: str, title: str, ylabel: str, ylim=None) -> None:
    fig, ax = plt.subplots(figsize=(9.6, 4.0))
    markerline, stemlines, baseline = ax.stem(n, values, basefmt="k-")
    plt.setp(markerline, marker="o", markersize=5.5, markerfacecolor=BLUE, markeredgecolor=BLUE)
    plt.setp(stemlines, color=BLUE, linewidth=1.5)
    plt.setp(baseline, color="black", linewidth=0.8)
    ax.set_xlabel("Отсчёт n")
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
        ax.title.set_fontsize(12)
    ax.set_xticks(n)
    ax.grid(True, linestyle=":", alpha=0.65)
    ax.axhline(0.0, color="black", linewidth=0.8)
    if ylim:
        ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=200)
    plt.close(fig)


def main() -> None:
    stem_plot(ideal, "fig1_ideal_ih.png", "ИХ идеального фильтра", "hᵤ(n)")
    stem_plot(window, "fig2_kaiser_window.png", "Оконная функция", "w(n)", (-0.03, 1.08))
    stem_plot(b, "fig3_real_ih.png", "ИХ проектируемого фильтра", "h(n)")
    for path in sorted(OUT.glob("*.png")):
        print("saved:", path)


if __name__ == "__main__":
    main()
