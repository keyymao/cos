#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрольная работа №1 по ЦОС, вариант 10.
Рекурсивное звено 2-го порядка: ПФ, разностное уравнение, структурная схема,
импульсная характеристика, карта нулей и полюсов, АЧХ и ФЧХ.

Исходные данные (вариант 10):
    b0 = 1, b1 = -0.7234, b2 = -0.4231, a1 = 0.7234, a2 = 0.9234

Запуск:  python3 kr1_variant10.py
Результат:  печать расчёта в консоль + рисунки figures/fig*.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.dpi": 150})

# ================= Исходные данные, вариант 10 =================
b0, b1, b2 = 1.0, -0.7234, -0.4231
a1, a2 = 0.7234, 0.9234
b = np.array([b0, b1, b2])
a = np.array([1.0, a1, a2])


def f(x, d=4):
    return f"{x:.{d}f}"


# ================= Задания 4/9: полюсы и нули =================
poles = np.roots(a)          # знаменатель: z^2 + a1*z + a2 = 0
zeros = np.roots(b)          # числитель:  b0*z^2 + b1*z + b2 = 0
p = poles[0]
r = float(np.abs(p))         # радиус полюсов r = sqrt(a2)
phi = float(np.angle(p))     # угол полюса phi_p, рад
sin_phi = float(np.sin(phi))

print("Полюсы: p1,2 =", f(p.real, 4), "± j", f(p.imag, 4),
      "| r =", f(r, 4), "| phi_p =", f(phi, 4), "рад =", f(phi / np.pi, 4), "pi | sin(phi_p) =", f(sin_phi, 4))
print("Нули:   z1 =", f(zeros[0].real, 4), ", z2 =", f(zeros[1].real, 4),
      "(действительные)")

# ================= Задание 4: ИХ по аналитической формуле =================
def h_formula(n):
    """ИХ небазового рекурсивного звена 2-го порядка (нулевые начальные условия)."""
    v = b0 * r**n * np.sin((n + 1) * phi) / sin_phi
    if n >= 1:
        v += b1 * r**(n - 1) * np.sin(n * phi) / sin_phi
    if n >= 2:
        v += b2 * r**(n - 2) * np.sin((n - 1) * phi) / sin_phi
    return v


# ================= Задание 6: ИХ по разностному уравнению =================
def h_de(nmax):
    """y(n) = b0 x(n) + b1 x(n-1) + b2 x(n-2) - a1 y(n-1) - a2 y(n-2), x(n)=delta(n)."""
    h = np.zeros(nmax + 1)
    for n in range(nmax + 1):
        y = b0 * (1.0 if n == 0 else 0.0)
        if n >= 1: y += b1 * (1.0 if n == 1 else 0.0)
        if n >= 2: y += b2 * (1.0 if n == 2 else 0.0)
        if n >= 1: y -= a1 * h[n - 1]
        if n >= 2: y -= a2 * h[n - 2]
        h[n] = y
    return h


NMAX = 40
h_f = np.array([h_formula(n) for n in range(NMAX + 1)])
h_r = h_de(NMAX)

print("\nЗадания 5/6/7 — 5 отсчётов ИХ:")
print(f"{'n':>2} {'h(n) по формуле':>16} {'h(n) по РУ':>12} {'разность':>10}")
for n in range(5):
    print(f"{n:>2} {h_f[n]:>16.6f} {h_r[n]:>12.6f} {h_f[n]-h_r[n]:>10.1e}")

# ================= Задания 10/12/13: АЧХ и ФЧХ =================
def Hjw(w):
    """Частотная характеристика H(e^{jw}) при z = e^{jw}, w = omega*T."""
    z = np.exp(1j * w)
    return (b0 + b1 / z + b2 / z**2) / (1 + a1 / z + a2 / z**2)


w = np.linspace(0, np.pi, 2001)
H = Hjw(w)
A = np.abs(H)
PH = np.angle(H)

pts = [("0", 0.0), ("pi/4", np.pi / 4), ("pi/2", np.pi / 2), ("phi_p", phi), ("pi", np.pi)]
print("\nЗадание 12 — экспресс-анализ АЧХ и ФЧХ в пяти точках:")
print(f"{'w̄':>7} {'w̄, рад':>9} {'A(w̄)':>9} {'φ(w̄), рад':>11}")
for name, wv in pts:
    Hv = Hjw(wv)
    print(f"{name:>7} {wv:>9.4f} {abs(Hv):>9.4f} {np.angle(Hv):>11.4f}")
print("A(0)  = |(1+b1+b2)/(1+a1+a2)| =", f(abs((1 + b1 + b2) / (1 + a1 + a2)), 4))
print("A(pi) = |(1-b1+b2)/(1-a1+a2)| =", f(abs((1 - b1 + b2) / (1 - a1 + a2)), 4))
print("max A(ω̄) =", f(A.max(), 4), "при ω̄ =", f(w[np.argmax(A)], 4), "(полюсный угол φ_p =", f(phi, 4), ")")

# ================= Рисунок 1: структурная схема (задание 3) =================
fig, ax = plt.subplots(figsize=(11.5, 5.6))
ax.set_xlim(-0.6, 12.6); ax.set_ylim(-0.9, 6.1); ax.axis("off")


def box(x, y, text, w=1.05, h=0.55):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.06",
                                fc="white", ec="black", lw=1.4))
    ax.text(x, y, text, ha="center", va="center", fontsize=11)


def arr(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=15, lw=1.4, color="black"))


def line(x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color="black", lw=1.4)


box(0.2, 4, "x(n)", 1.0, 0.6)
line(0.72, 4, 7.2, 4)
box(3.0, 4, "z$^{-1}$"); box(5.0, 4, "z$^{-1}$")
for nx in (1.2, 4.0, 6.0):
    ax.plot(nx, 4, "ko", ms=4)
box(1.2, 5.4, "b$_0$ = 1")
box(4.0, 5.4, "b$_1$ = −0,7234")
box(6.0, 5.4, "b$_2$ = −0,4231")
for nx in (1.2, 4.0, 6.0):
    arr(nx, 4.28, nx, 5.12)
    line(nx + 0.53, 5.4, 9.4, 5.4)
line(9.4, 5.4, 9.4, 3.62)
arr(9.4, 3.75, 9.28, 3.5)

ax.add_patch(Circle((9.4, 3.1), 0.42, fc="white", ec="black", lw=1.5))
ax.text(9.4, 3.1, "Σ", ha="center", va="center", fontsize=13)
ax.text(9.02, 3.55, "+", fontsize=13, ha="center")
ax.text(9.02, 2.62, "−", fontsize=13, ha="center")
arr(9.82, 3.1, 10.6, 3.1)
ax.text(10.2, 3.32, "y(n)", ha="center", fontsize=11)
box(11.3, 3.1, "y(n)", 1.0, 0.6)

line(11.3, 2.78, 11.3, 1.6)
line(11.3, 1.6, 5.2, 1.6)
box(8.7, 1.6, "z$^{-1}$"); box(6.7, 1.6, "z$^{-1}$")
arr(10.75, 1.6, 9.25, 1.6)
arr(8.15, 1.6, 7.25, 1.6)
arr(6.15, 1.6, 5.4, 1.6)
for nx in (7.7, 5.7):
    ax.plot(nx, 1.6, "ko", ms=4)
box(7.7, 0.2, "−a$_1$ = −0,7234", 1.7, 0.6)
box(5.7, 0.2, "−a$_2$ = −0,9234", 1.7, 0.6)
for nx in (7.7, 5.7):
    arr(nx, 1.32, nx, 0.52)
    line(nx + 0.85, 0.2, 9.4, 0.2)
line(9.4, 0.2, 9.4, 2.68)
arr(9.4, 2.55, 9.42, 2.72)

ax.set_title("Задание 3. Структурная схема рекурсивного звена 2-го порядка (вариант 10)", fontsize=12)
fig.tight_layout()
fig.savefig(OUT / "fig1_structure.png", bbox_inches="tight")
plt.close(fig)

# ================= Рисунок 2: ИХ (задание 8) =================
fig, ax = plt.subplots(figsize=(9, 4.5))
n = np.arange(NMAX + 1)
ax.stem(n, h_f, basefmt=" ")
ax.plot(n, h_f, "k--", lw=0.8, alpha=0.5)
ax.set_xlabel("n"); ax.set_ylabel("h(n)")
ax.set_title("Задание 8. Импульсная характеристика рекурсивного звена 2-го порядка (вариант 10)")
ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "fig2_h.png", bbox_inches="tight"); plt.close(fig)

# ================= Рисунок 3: карта нулей и полюсов (задание 9) =================
fig, ax = plt.subplots(figsize=(6.5, 6.5))
ang = np.linspace(0, 2 * np.pi, 400)
ax.plot(np.cos(ang), np.sin(ang), "k--", lw=1, label="единичная окружность")
ax.axhline(0, color="gray", lw=0.7); ax.axvline(0, color="gray", lw=0.7)
ax.scatter(zeros.real, zeros.imag, marker="o", s=90, facecolors="none", edgecolors="blue", lw=2, label="нули")
ax.scatter(poles.real, poles.imag, marker="x", s=110, c="red", lw=2, label="полюсы")
for z in zeros:
    ax.annotate(f"{z.real:.4f}", (z.real, z.imag), textcoords="offset points",
                xytext=(8, -14), fontsize=9, color="blue")
for z in poles:
    ax.annotate(f"{z.real:.4f}{z.imag:+.4f}j", (z.real, z.imag), textcoords="offset points",
                xytext=(8, 6), fontsize=9, color="red")
ax.set_xlim(-1.4, 1.4); ax.set_ylim(-1.4, 1.4); ax.set_aspect("equal")
ax.set_xlabel("Re z"); ax.set_ylabel("Im z")
ax.set_title("Задание 9. Карта нулей и полюсов (вариант 10)")
ax.grid(alpha=0.3); ax.legend(loc="upper right")
fig.tight_layout(); fig.savefig(OUT / "fig3_zplane.png", bbox_inches="tight"); plt.close(fig)

# ================= Рисунок 4: АЧХ и ФЧХ (задание 13) =================
fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
axes[0].plot(w, A, lw=1.8)
for name, wv in pts:
    axes[0].plot(wv, abs(Hjw(wv)), "ro", ms=6)
    axes[0].annotate(f"{abs(Hjw(wv)):.2f}", (wv, abs(Hjw(wv))), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=9)
axes[0].set_ylabel("A(ω̄)")
axes[0].set_title("Задание 13. АЧХ и ФЧХ рекурсивного звена 2-го порядка (вариант 10)")
axes[0].grid(alpha=0.3)
axes[1].plot(w, PH, lw=1.8)
for name, wv in pts:
    axes[1].plot(wv, np.angle(Hjw(wv)), "ro", ms=6)
axes[1].set_ylabel("φ(ω̄), рад")
axes[1].set_xlabel("нормированная частота ω̄ = ωT, рад")
axes[1].set_xticks([0, np.pi / 4, np.pi / 2, phi, np.pi], ["0", "π/4", "π/2", "φp", "π"])
axes[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "fig4_ach_phch.png", bbox_inches="tight"); plt.close(fig)

print("\nРисунки сохранены в", OUT)
print("h[0..9]:", [f(h_formula(n), 4) for n in range(10)])
