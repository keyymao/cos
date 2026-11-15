# -*- coding: utf-8 -*-
"""
fig_architecture.png — структурная схема системы (рис. 1 отчёта КР2).

Горизонтальная цепочка модулей, как в примере «Отчет.pdf».
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "figures" / "fig_architecture.png"

BOXES = [
    ("WAV-файл\n(вход)", "#ececec"),
    ("Модуль анализа\nДПФ, спектр,\nспектрограмма", "#c7d9f5"),
    ("Модуль\nэквалайзера\nполосы НЧ/СЧ/ВЧ,\nK = $10^{G/20}$", "#cfe8cf"),
    ("Модуль подавления\nпомех\nпоиск f₀, режекторный\nБИХ-фильтр (filtfilt)", "#f6d2c0"),
    ("Модуль синтеза\nмасштабирование,\nPCM 16 бит, WAV", "#d9d4ef"),
]
FLOW = "сигнал → спектр и спектрограмма → сигнал с заданными усилениями → сигнал без помехи → WAV"

fig, ax = plt.subplots(figsize=(11.4, 2.5))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.set_title("Структурная схема системы", fontsize=12, fontweight="bold", pad=10)

n = len(BOXES)
bw, by, bh = 0.155, 0.42, 0.38
xs = [0.03 + i * (bw + 0.058) for i in range(n)]
for (text, color), x in zip(BOXES, xs):
    ax.add_patch(FancyBboxPatch((x, by), bw, bh, boxstyle="round,pad=0.012",
                                fc=color, ec="0.25", lw=1.2))
    ax.text(x + bw / 2, by + bh / 2, text, ha="center", va="center", fontsize=9.6)
for x in xs[:-1]:
    ax.add_patch(FancyArrowPatch((x + bw + 0.014, by + bh / 2),
                                 (x + bw + 0.043, by + bh / 2),
                                 arrowstyle="-|>", mutation_scale=16, lw=1.4, color="0.25"))
ax.text(0.5, 0.20, FLOW, ha="center", va="center", fontsize=9.4, color="0.35")

fig.tight_layout()
fig.savefig(OUT, bbox_inches="tight", dpi=150)
plt.close(fig)
print("saved", OUT)
