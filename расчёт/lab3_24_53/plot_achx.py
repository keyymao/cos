#!/usr/bin/env python3
"""Строит понятные расчётные АЧХ ЛР №3 для варианта 24/53.

Используются коэффициенты из таблицы 3 загруженного отчёта. На графиках
отмечаются искажённые граничные частоты цифрового фильтра из раздела 1.8,
а также допустимые уровни в полосах пропускания и задержания.

Зависимости: numpy, matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

ROOT = Path(__file__).resolve().parents[2]
FINAL_DIR = ROOT / "лабораторные" / "исправленые" / "лаба3"

FD = 14800.0
F_PASS = 2074.6
F_STOP = 3173.3
A_MAX_DB = 0.4455
A_MIN_DB = 40.0
H_PASS_MIN = 10 ** (-A_MAX_DB / 20.0)
H_STOP_MAX = 10 ** (-A_MIN_DB / 20.0)
K = 0.0004522
SECTIONS = (
    (-1.1831, 0.8840),
    (-1.2959, 0.6914),
    (-1.4619, 0.5718),
)

BLUE = "#005cb8"
RED = "#c62828"
GREEN = "#2e7d32"
ORANGE = "#ef6c00"


def frequency_response(frequency: np.ndarray | float) -> np.ndarray:
    """Вычисляет H(e^jω) по трём биквадратным звеньям таблицы 3."""
    frequency = np.asarray(frequency, dtype=float)
    z_inv = np.exp(-2j * np.pi * frequency / FD)
    response = K * np.ones_like(z_inv, dtype=complex)
    for a1, a2 in SECTIONS:
        response *= (1 + z_inv) ** 2 / (1 + a1 * z_inv + a2 * z_inv**2)
    return response


def annotate_bands(ax: plt.Axes) -> None:
    ax.axvspan(0, F_PASS, color=BLUE, alpha=0.055, label="полоса пропускания")
    ax.axvspan(F_PASS, F_STOP, color=ORANGE, alpha=0.055, label="переходная полоса")
    ax.axvspan(F_STOP, FD / 2, color=RED, alpha=0.045, label="полоса задержания")
    ax.axvline(F_PASS, color=BLUE, linestyle="--", linewidth=1.8)
    ax.axvline(F_STOP, color=RED, linestyle="--", linewidth=1.8)


def plot_logarithmic(frequency: np.ndarray, magnitude: np.ndarray, output: Path) -> None:
    db = 20 * np.log10(np.maximum(magnitude, 1e-8))
    h1 = float(np.abs(frequency_response(F_PASS)))
    h3 = float(np.abs(frequency_response(F_STOP)))
    db1 = 20 * np.log10(h1)
    db3 = 20 * np.log10(h3)

    fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
    annotate_bands(ax)
    ax.plot(frequency, db, color="#263238", linewidth=2.2, label="расчётная АЧХ")
    ax.hlines(-A_MAX_DB, 0, F_PASS, colors=BLUE, linestyles=":", linewidth=2)
    ax.hlines(-A_MIN_DB, F_STOP, FD / 2, colors=RED, linestyles=":", linewidth=2)
    ax.scatter([F_PASS, F_STOP], [db1, db3], color=[BLUE, RED], s=65, zorder=5)

    ax.annotate(
        f"f₁ = {F_PASS:.1f} Гц\n|H| = {h1:.4f}; {db1:.3f} дБ",
        xy=(F_PASS, db1),
        xytext=(F_PASS + 380, -12),
        arrowprops={"arrowstyle": "->", "color": BLUE, "lw": 1.8},
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": BLUE},
        color=BLUE,
        fontsize=10,
    )
    ax.annotate(
        f"f₃ = {F_STOP:.1f} Гц\n|H| = {h3:.4f}; {db3:.2f} дБ",
        xy=(F_STOP, db3),
        xytext=(F_STOP + 550, -58),
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.8},
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": RED},
        color=RED,
        fontsize=10,
    )

    ax.text(
        90,
        -A_MAX_DB - 3.2,
        f"−aₘₐₓ = −{A_MAX_DB:.4f} дБ",
        color=BLUE,
        fontsize=10,
    )
    ax.text(
        F_STOP + 100,
        -A_MIN_DB + 2.2,
        f"−aₘᵢₙ = −{A_MIN_DB:.0f} дБ",
        color=RED,
        fontsize=10,
    )
    ax.set(
        title="АЧХ ФНЧ Чебышёва — логарифмический масштаб (вариант 24/53)",
        xlabel="Частота, Гц",
        ylabel="20 lg |H|, дБ",
        xlim=(0, FD / 2),
        ylim=(-100, 3),
    )
    ax.grid(True, which="both", alpha=0.28)
    ax.legend(loc="lower left", ncols=2, fontsize=9)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_linear(frequency: np.ndarray, magnitude: np.ndarray, output: Path) -> None:
    h1 = float(np.abs(frequency_response(F_PASS)))
    h3 = float(np.abs(frequency_response(F_STOP)))

    fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
    annotate_bands(ax)
    ax.plot(frequency, magnitude, color="#263238", linewidth=2.2, label="расчётная АЧХ")

    # Допуски: 0,95...1 в ПП и не более 0,01 в ПЗ.
    ax.fill_between([0, F_PASS], H_PASS_MIN, 1.0, color=BLUE, alpha=0.14)
    ax.hlines(H_PASS_MIN, 0, F_PASS, colors=BLUE, linestyles=":", linewidth=2.2)
    ax.hlines(1.0, 0, F_PASS, colors=BLUE, linestyles=":", linewidth=1.4)
    ax.fill_between([F_STOP, FD / 2], 0, H_STOP_MAX, color=RED, alpha=0.14)
    ax.hlines(H_STOP_MAX, F_STOP, FD / 2, colors=RED, linestyles=":", linewidth=2.2)
    ax.scatter([F_PASS, F_STOP], [h1, h3], color=[BLUE, RED], s=65, zorder=5)

    ax.annotate(
        f"ПП: 0,95 ≤ |H| ≤ 1\naₘₐₓ = {A_MAX_DB:.4f} дБ",
        xy=(F_PASS * 0.58, H_PASS_MIN),
        xytext=(300, 0.70),
        arrowprops={"arrowstyle": "->", "color": BLUE, "lw": 1.8},
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": BLUE},
        color=BLUE,
        fontsize=10,
    )
    ax.annotate(
        f"ПЗ: |H| ≤ 0,01\naₘᵢₙ = {A_MIN_DB:.0f} дБ",
        xy=(F_STOP + 400, H_STOP_MAX),
        xytext=(3300, 0.22),
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.8},
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": RED},
        color=RED,
        fontsize=10,
    )

    ax.set(
        title="АЧХ ФНЧ Чебышёва — линейный масштаб (вариант 24/53)",
        xlabel="Частота, Гц",
        ylabel="|H|",
        xlim=(0, FD / 2),
        ylim=(-0.025, 1.07),
    )
    ax.grid(True, alpha=0.28)
    ax.legend(loc="lower left", ncols=2, fontsize=9)

    # Увеличение ПЗ делает уровень 0,01 заметным, хотя на общей шкале он у нуля.
    inset = inset_axes(ax, width="38%", height="34%", loc="upper right", borderpad=1.5)
    stop = frequency >= F_STOP
    inset.plot(frequency[stop], magnitude[stop], color="#263238", linewidth=1.5)
    inset.axhline(H_STOP_MAX, color=RED, linestyle=":", linewidth=1.8)
    inset.axvline(F_STOP, color=RED, linestyle="--", linewidth=1.2)
    inset.fill_between([F_STOP, FD / 2], 0, H_STOP_MAX, color=RED, alpha=0.12)
    inset.set_xlim(F_STOP, FD / 2)
    inset.set_ylim(0, 0.015)
    inset.set_title("Увеличение полосы задержания", fontsize=9)
    inset.set_xlabel("Гц", fontsize=8)
    inset.set_ylabel("|H|", fontsize=8)
    inset.tick_params(labelsize=8)
    inset.grid(True, alpha=0.25)

    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FINAL_DIR, help="папка результатов")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frequency = np.linspace(0.0, FD / 2, 8193)
    magnitude = np.abs(frequency_response(frequency))
    log_path = args.output_dir / "АЧХ логарифмическая — расчётный график.png"
    linear_path = args.output_dir / "АЧХ линейная — расчётный график.png"
    plot_logarithmic(frequency, magnitude, log_path)
    plot_linear(frequency, magnitude, linear_path)

    h1 = float(np.abs(frequency_response(F_PASS)))
    h3 = float(np.abs(frequency_response(F_STOP)))
    print(f"f1={F_PASS:.1f} Гц: |H|={h1:.7f}, a={-20*np.log10(h1):.4f} дБ")
    print(f"f3={F_STOP:.1f} Гц: |H|={h3:.7f}, a={-20*np.log10(h3):.4f} дБ")
    print(f"Сохранено: {log_path}")
    print(f"Сохранено: {linear_path}")


if __name__ == "__main__":
    main()
