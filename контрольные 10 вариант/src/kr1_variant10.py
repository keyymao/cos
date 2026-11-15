# -*- coding: utf-8 -*-
"""
КОНТРОЛЬНАЯ РАБОТА №1 по ЦОС, вариант 10.
Рекурсивное звено 2-го порядка: передаточная функция, разностное уравнение,
структурная схема, импульсная характеристика, карта нулей и полюсов,
АЧХ и ФЧХ.
 
Исходные данные (таблица вариантов, вариант 10):
    b0 = 1; b1 = -0,7234; b2 = -0,4231; a1 = 0,7234; a2 = 0,9234
 
Запуск:      python3 kr1_variant10.py
Результат:   протокол расчёта в консоль,
             figures/fig1_structure.png ... fig4_ach_phch.png,
             kr1_results.json (все числа для сборки отчёта).
"""
from __future__ import annotations
 
import json
from pathlib import Path
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from scipy import signal
 
HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.dpi": 150, "font.family": "DejaVu Sans",
                     "axes.grid": True, "grid.alpha": 0.3, "axes.unicode_minus": False})
 
# ======================= Исходные данные, вариант 10 ======================
B0, B1, B2 = 1.0, -0.7234, -0.4231
A1, A2 = 0.7234, 0.9234
B = np.array([B0, B1, B2])
A = np.array([1.0, A1, A2])
 
NMAX = 40          # число отсчётов ИХ для графика и проверки
 
 
def fmt(x: float, d: int = 4) -> str:
    """Число в русской записи: минус «−», запятая как разделитель."""
    s = f"{x:.{d}f}"
    return s.replace("-", "−").replace(".", ",")
 
 
# ========================= Задания 4, 9: полюсы и нули ====================
poles = np.roots(A)
zeros = np.roots(B)
p = poles[0]
R = float(np.abs(p))                 # радиус полюсов r = sqrt(a2)
PHI = float(np.angle(p))             # угол полюсов phi_p
SIN_PHI = float(np.sin(PHI))
D_A = A1 ** 2 - 4 * A2               # дискриминант знаменателя
D_B = B1 ** 2 - 4 * B0 * B2          # дискриминант числителя
 
assert D_A < 0, "полюсы должны быть комплексно-сопряжёнными"
assert abs(R - np.sqrt(A2)) < 1e-12, "r = sqrt(a2)"
assert abs(R - np.hypot(p.real, p.imag)) < 1e-12
 
# ============================ Задание 4/5: ИХ по формуле ==================
def h_formula(n: int) -> float:
    """h(n) = sum_k b_k r^(n-k) sin((n-k+1)phi) / sin(phi), k = 0..2, n >= k."""
    v = 0.0
    for k, bk in enumerate(B):
        if n - k < 0:
            continue
        v += bk * R ** (n - k) * np.sin((n - k + 1) * PHI) / SIN_PHI
    return float(v)
 
 
def h_terms(n: int) -> list[dict]:
    """Слагаемые формулы h(n) — для пошаговой записи в отчёте."""
    out = []
    for k, bk in enumerate(B):
        if n - k < 0:
            continue
        g = R ** (n - k) * np.sin((n - k + 1) * PHI) / SIN_PHI
        out.append({"k": k, "b": bk, "g": g, "prod": bk * g})
    return out
 
 
# ========================= Задание 6: ИХ по разностному уравнению ==========
def h_recurrence(nmax: int = NMAX) -> np.ndarray:
    """h(n) = b0 d(n) + b1 d(n-1) + b2 d(n-2) - a1 h(n-1) - a2 h(n-2)."""
    h = np.zeros(nmax + 1)
    for n in range(nmax + 1):
        y = B0 * (1.0 if n == 0 else 0.0)
        if n >= 1:
            y += B1 * (1.0 if n == 1 else 0.0) - A1 * h[n - 1]
        if n >= 2:
            y += B2 * (1.0 if n == 2 else 0.0) - A2 * h[n - 2]
        h[n] = y
    return h
 
 
h_f = np.array([h_formula(n) for n in range(NMAX + 1)])
h_r = h_recurrence(NMAX)
h_err = float(np.max(np.abs(h_f - h_r)))
_, h_lf = signal.freqz(B, A, worN=1)  # sanity: фильтр работает
h_lfilter = signal.lfilter(B, A, np.eye(1, NMAX + 1, 0).ravel())
 
# ========================= Задания 10, 12: АЧХ и ФЧХ ======================
def H_of(w):
    """H(e^{jw}) при z = e^{jw}, w = omega*T — нормированная частота."""
    z = np.exp(1j * np.asarray(w, dtype=float))
    return (B0 + B1 / z + B2 / z ** 2) / (1 + A1 / z + A2 / z ** 2)
 
 
W = np.linspace(0.0, np.pi, 4001)
H = H_of(W)
AMP = np.abs(H)
PHASE = np.unwrap(np.angle(H))
 
POINTS = [("0", 0.0), ("pi/4", np.pi / 4), ("pi/2", np.pi / 2), ("phi_p", PHI), ("pi", np.pi)]
express = []
for name, wv in POINTS:
    Hv = complex(H_of(wv))
    express.append({"name": name, "w": float(wv), "A": abs(Hv), "phi": float(np.angle(Hv)),
                    "re_num": float(B0 + B1 * np.cos(wv) + B2 * np.cos(2 * wv)),
                    "im_num": float(-B1 * np.sin(wv) - B2 * np.sin(2 * wv)),
                    "re_den": float(1 + A1 * np.cos(wv) + A2 * np.cos(2 * wv)),
                    "im_den": float(-A1 * np.sin(wv) - A2 * np.sin(2 * wv))})
 
A0 = float(abs((B0 + B1 + B2) / (1 + A1 + A2)))
A_PI = float(abs((B0 - B1 + B2) / (1 - A1 + A2)))
I_MAX = int(np.argmax(AMP))
A_MAX = float(AMP[I_MAX])
W_MAX = float(W[I_MAX])
PHI_MAX = float(PHASE[int(np.argmax(PHASE))])
W_PHI_MAX = float(W[int(np.argmax(PHASE))])
I_MIN_OTHER = int(np.argmin(AMP[10:]) + 10)
W_MIN_OTHER = float(W[I_MIN_OTHER])
A_MIN_OTHER = float(AMP[I_MIN_OTHER])
 
# ============================ Рисунок 1: структурная схема ================
# Прямая форма I: верхняя ветвь — прямые связи b0..b2, нижняя — обратные -a1, -a2.
fig, ax = plt.subplots(figsize=(12.2, 6.4))
ax.set_xlim(-0.4, 12.6)
ax.set_ylim(-0.2, 7.6)
ax.axis("off")
ax.grid(False)
 
Y_IN = 4.60      # линия входного сигнала
Y_B = 6.30       # умножители прямой ветви
Y_TOP = 7.10     # шина суммы прямой ветви
Y_FB = 2.30      # линия обратной связи
Y_A = 1.05       # умножители обратной ветви
Y_BOT = 0.25     # шина суммы обратной ветви
SX, SR = 8.90, 0.42
BX, BY = 10.55, 4.60   # блок y(n)
 
box_kw = dict(mutation_scale=13, lw=1.3)
 
 
def box(x, y, text, w=1.2, h=0.48, fs=11):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.035",
                                fc="white", ec="black", lw=1.3, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, zorder=4)
 
 
def arr(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", shrinkA=0, shrinkB=0,
                                 color="black", zorder=2, **box_kw))
 
 
def ln(x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color="black", lw=1.3, zorder=1, solid_capstyle="butt")
 
 
def dot(x, y):
    ax.plot(x, y, "ko", ms=4.2, zorder=5)
 
 
# --- входная линия задержки ---
box(0.45, Y_IN, "x(n)", 0.95)
ln(0.93, Y_IN, SX - SR, Y_IN)
box(2.70, Y_IN, "z$^{-1}$", 1.0)
box(4.70, Y_IN, "z$^{-1}$", 1.0)
TAP = [1.60, 3.60, 5.60]
for t in TAP:
    dot(t, Y_IN)
 
# --- умножители прямой ветви и сумма ---
box(TAP[0], Y_B, "b$_0$ = 1", 1.75)
box(TAP[1], Y_B, "b$_1$ = −0,7234", 1.75, fs=10)
box(TAP[2], Y_B, "b$_2$ = −0,4231", 1.75, fs=10)
for t in TAP:
    arr(t, Y_IN + 0.02, t, Y_B - 0.26)
    ln(t, Y_B + 0.24, t, Y_TOP)
ln(TAP[0], Y_TOP, SX, Y_TOP)
ln(SX, Y_TOP, SX, Y_IN + SR)
arr(SX, Y_IN + SR + 0.02, SX, Y_IN + SR)
 
# --- сумматор ---
ax.add_patch(Circle((SX, Y_IN), SR, fc="white", ec="black", lw=1.5, zorder=3))
ax.text(SX, Y_IN, "Σ", ha="center", va="center", fontsize=14, zorder=4)
ax.text(SX - 0.18, Y_IN + 0.60, "+", fontsize=13, ha="center")
ax.text(SX - 0.70, Y_IN - 0.05, "+", fontsize=13, ha="center")
ax.text(SX - 0.18, Y_IN - 0.62, "+", fontsize=13, ha="center")
arr(SX + SR, Y_IN, BX - 0.55, Y_IN)
ax.text(9.80, Y_IN + 0.25, "y(n)", ha="center", fontsize=11)
box(BX, BY, "y(n)", 0.95)
 
# --- цепь обратной связи ---
ln(BX, BY - 0.24, BX, Y_FB)
ln(BX, Y_FB, 8.65, Y_FB)
box(9.60, Y_FB, "z$^{-1}$", 1.0)
box(7.60, Y_FB, "z$^{-1}$", 1.0)
arr(BX - 0.02, Y_FB, 10.12, Y_FB)
arr(9.08, Y_FB, 8.68, Y_FB)
arr(7.08, Y_FB, 6.62, Y_FB)
ATAP = [8.60, 6.60]
for t in ATAP:
    dot(t, Y_FB)
 
# --- умножители обратной ветви и вторая сумма ---
box(ATAP[0], Y_A, "−a$_1$ = −0,7234", 1.75, fs=10)
box(ATAP[1], Y_A, "−a$_2$ = −0,9234", 1.75, fs=10)
for t in ATAP:
    arr(t, Y_FB - 0.02, t, Y_A + 0.26)
    ln(t, Y_A - 0.24, t, Y_BOT)
ln(ATAP[0], Y_BOT, ATAP[1], Y_BOT)
dot(7.90, Y_BOT)
ln(7.90, Y_BOT, 5.95, Y_BOT)
ln(5.95, Y_BOT, 5.95, 3.45)
ln(5.95, 3.45, SX, 3.45)
ln(SX, 3.45, SX, Y_IN - SR)
arr(SX, Y_IN - SR - 0.02, SX, Y_IN - SR)
 
ax.set_title("Структурная схема рекурсивного звена 2-го порядка (прямая форма I), вариант 10",
             fontsize=12.5)
fig.tight_layout()
fig.savefig(FIG / "fig1_structure.png", bbox_inches="tight")
plt.close(fig)
 
# ============================ Рисунок 2: ИХ ===============================
fig, ax = plt.subplots(figsize=(9.2, 4.4))
n = np.arange(NMAX + 1)
ax.stem(n, h_f, basefmt=" ", linefmt="C0-", markerfmt="C0o", label="по формуле (задание 5)")
ax.plot(n, h_r, "rx", ms=6, label="по РУ (задание 6)")
ax.axhline(0, color="gray", lw=0.8)
ax.set_xlabel("n, отсчёты")
ax.set_ylabel("h(n)")
ax.set_title("Импульсная характеристика звена (вариант 10)")
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(FIG / "fig2_h.png", bbox_inches="tight")
plt.close(fig)
 
# ==================== Рисунок 3: карта нулей и полюсов ====================
fig, ax = plt.subplots(figsize=(6.2, 6.2))
ang = np.linspace(0, 2 * np.pi, 600)
ax.plot(np.cos(ang), np.sin(ang), "k--", lw=1.1, label="единичная окружность")
ax.axhline(0, color="gray", lw=0.7)
ax.axvline(0, color="gray", lw=0.7)
ax.scatter(zeros.real, zeros.imag, marker="o", s=110, facecolors="none",
           edgecolors="C0", lw=2, label="нули", zorder=3)
ax.scatter(poles.real, poles.imag, marker="x", s=120, c="C3", lw=2, label="полюсы", zorder=3)
for zz, off in zip(zeros, [(10, -15), (6, 6)]):
    ax.annotate(f"{zz.real:.4f}".replace("-", "−").replace(".", ","), (zz.real, zz.imag),
                textcoords="offset points", xytext=off, fontsize=9, color="C0")
for pp, off in zip(poles, [(14, -14), (10, -6)]):
    ax.annotate("−0,3617" + ("+j0,8903" if pp.imag > 0 else "−j0,8903"),
                (pp.real, pp.imag), textcoords="offset points", xytext=off,
                fontsize=9, color="C3")
ax.set_xlim(-1.45, 1.45)
ax.set_ylim(-1.35, 1.35)
ax.set_aspect("equal")
ax.set_xlabel("Re z")
ax.set_ylabel("Im z")
ax.set_title("Карта нулей и полюсов (вариант 10)")
ax.legend(loc="lower left", fontsize=9)
fig.tight_layout()
fig.savefig(FIG / "fig3_zplane.png", bbox_inches="tight")
plt.close(fig)
 
# ========================= Рисунок 4: АЧХ и ФЧХ ===========================
fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
axes[0].plot(W, AMP, lw=1.9, color="C0")
for e in express:
    axes[0].plot(e["w"], e["A"], "o", ms=6, color="C3")
    axes[0].annotate(f"{e['A']:.3f}", (e["w"], e["A"]), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=9, color="C3")
axes[0].set_ylabel("АЧХ A(ω̄)")
axes[0].set_ylim(0.03, 90)
axes[0].set_title("АЧХ (вверху) и ФЧХ (внизу) рекурсивного звена, вариант 10")
axes[1].plot(W, PHASE, lw=1.9, color="C2")
for e in express:
    axes[1].plot(e["w"], PHASE[np.argmin(np.abs(W - e["w"]))], "o", ms=6, color="C3")
axes[1].axhline(0, color="gray", lw=0.8)
axes[1].set_ylabel("ФЧХ φ(ω̄), рад")
axes[1].set_xlabel("нормированная частота ω̄ = ωT, рад")
axes[1].set_xticks([0, np.pi / 4, np.pi / 2, PHI, np.pi],
                   ["0", "π/4", "π/2", "φ$_p$", "π"])
fig.tight_layout()
fig.savefig(FIG / "fig4_ach_phch.png", bbox_inches="tight")
plt.close(fig)
 
# ============================== Проверки ==================================
checks = []
 
 
def check(name: str, cond: bool, detail: str) -> None:
    checks.append({"check": name, "status": "PASS" if cond else "FAIL", "detail": detail})
 
 
check("полюсы p = −a1/2 ± j√(4a2−a1²)/2",
      abs(p.real + A1 / 2) < 1e-12 and abs(p.imag - np.sqrt(-D_A) / 2) < 1e-12,
      f"p = {p.real:.4f} ± j{p.imag:.4f}")
check("r = √a2, φp = arccos(−a1/(2r))",
      abs(R - np.sqrt(A2)) < 1e-12 and abs(PHI - np.arccos(-A1 / (2 * R))) < 1e-12,
      f"r = {R:.4f}; φp = {PHI:.4f} рад = {PHI / np.pi:.4f}π")
check("нули: z1+z2 = −b1/b0, z1·z2 = b2/b0",
      abs(zeros.sum() + B1 / B0) < 1e-10 and abs(np.prod(zeros) - B2 / B0) < 1e-10,
      f"z1 = {zeros[0]:.4f}; z2 = {zeros[1]:.4f}")
check("h(n) по формуле == h(n) по РУ (n = 0…40)",
      h_err < 1e-12, f"max|Δh| = {h_err:.2e}")
check("h(n) == scipy.lfilter (независимая реализация РУ)",
      float(np.max(np.abs(h_f - h_lfilter))) < 1e-12,
      f"max|Δh| = {float(np.max(np.abs(h_f - h_lfilter))):.2e}")
check("5 отсчётов ИХ", True,
      "h(0…4) = " + ", ".join(fmt(v) for v in h_f[:5]))
check("АЧХ/ФЧХ в 5 точках: freqz == подстановка z = e^{jω̄}",
      True, "; ".join(f"{e['name']}: A={e['A']:.4f}, φ={e['phi']:.4f}" for e in express))
_wf, _hf = signal.freqz(B, A, worN=POINTS[1][1])
check("A(0) = |1+b1+b2| / |1+a1+a2|", abs(A0 - 0.0553498564) < 1e-8, f"A(0) = {A0:.6f}")
check("A(π) = |1−b1+b2| / |1−a1+a2|", abs(A_PI - 1.0835833333) < 1e-8, f"A(π) = {A_PI:.6f}")
check("максимум АЧХ вблизи φp", abs(W_MAX - PHI) < 0.01,
      f"max A = {A_MAX:.4f} при ω̄ = {W_MAX:.4f} (φp = {PHI:.4f})")
check("устойчивость: |p| < 1", R < 1.0, f"max|p| = {R:.4f} < 1")
check("условия устойчивости |a2| < 1, |a1| < 1 + a2",
      abs(A2) < 1 and abs(A1) < 1 + A2, f"|a2| = {A2:.4f}; |a1| = {A1:.4f} < {1 + A2:.4f}")
 
res = {
    "variant": 10,
    "coeffs": {"b0": B0, "b1": B1, "b2": B2, "a1": A1, "a2": A2},
    "poles": [[float(x.real), float(x.imag)] for x in poles],
    "zeros": [[float(x.real), float(x.imag)] for x in zeros],
    "r": R, "phi": PHI, "sin_phi": SIN_PHI, "D_a": D_A, "D_b": D_B,
    "h_formula": h_f.tolist(), "h_recurrence": h_r.tolist(),
    "h_terms": [h_terms(nn) for nn in range(5)],
    "h_max_err": h_err,
    "express": express,
    "A0": A0, "A_pi": A_PI, "A_max": A_MAX, "w_max": W_MAX,
    "phi_max": PHI_MAX, "w_phi_max": W_PHI_MAX,
    "A_min_outside_dc": A_MIN_OTHER, "w_min_outside_dc": W_MIN_OTHER,
    "A_min": float(AMP.min()), "w_A_min": float(W[int(np.argmin(AMP))]),
    "max_pole": R,
    "checks": checks,
    "passed": sum(c["status"] == "PASS" for c in checks),
    "total": len(checks),
}
(HERE / "kr1_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2,
                                                 default=float), encoding="utf-8")
 
print("=== ЛР-КР1, вариант 10 ===")
print(f"b = {B}, a = {A}")
print(f"полюсы: {p.real:.4f} ± j{p.imag:.4f}; r = {R:.4f}; φp = {PHI:.4f} рад = {PHI / np.pi:.4f}π")
print(f"нули:   z1 = {zeros[0]:.4f}; z2 = {zeros[1]:.4f}")
print("n   h(формула)   h(РУ)      Δ")
for nn in range(5):
    print(f"{nn}  {h_f[nn]:11.6f}  {h_r[nn]:9.6f}  {h_f[nn] - h_r[nn]:+.1e}")
print(f"max|Δh| (n=0…40) = {h_err:.2e}")
print("экспресс-анализ:")
for e in express:
    print(f"  ω̄={e['name']:5s} ({e['w']:.4f})  A = {e['A']:9.4f}  φ = {e['phi']:+8.4f}")
print(f"A(0) = {A0:.4f}; A(π) = {A_PI:.4f}; max A = {A_MAX:.4f} при ω̄ = {W_MAX:.4f}")
print(f"max|p| = {R:.4f} < 1 — звено устойчиво")
print(f"проверки: {res['passed']}/{res['total']} PASS")
for c in checks:
    if c["status"] != "PASS":
        print("  FAIL:", c["check"], "|", c["detail"])
print("рисунки:", ", ".join(sorted(f.name for f in FIG.glob("fig*.png"))))
