#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Расчёт ЛР №4, вариант 24 / зачётка 53 (ФНЧ Чебышёва, n = 6).

Метод: билинейное z-преобразование с внесением предыскажений
(преобразование Константинидиса для ФНЧ, формулы (12), (21) методички
LR_TsOS_4_BIKh_K.pdf):

    p = ctg(w1*T/2) * (1 - z^-1) / (1 + z^-1) = C * (1 - q) / (1 + q)

Аналоговый ФНЧ-прототип H(p) берётся готовым из ЛР №3
(Лабораторная работа №3 (вариант 24, зачётка 53).pdf, п. 1.6).

Проверки:
  1. воспроизведение примеров методички (ФВЧ Чебышёва / Баттерворта);
  2. независимый синтез через scipy.signal.cheby1 + scipy.signal.bilinear;
  3. АЧХ, устойчивость, попадание границ ПП/ПЗ.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAB_DIR = ROOT / "лабораторные" / "лаба4"

# ---------------------------------------------------------------- исходные данные
NBR, ZACH = 24, "53"
F_D = 14800.0
F_1 = 2220.0
F_3 = 3760.0
A_MAX, A_MIN = 0.4455, 40.0

# АФП из ЛР №3 (округлённые значения, как записаны в отчёте, п. 1.6)
K0 = 0.09508
PAIRS = [  # (a, b) в p^2 + a p + b
    (0.16050, 1.02917),
    (0.43850, 0.59614),
    (0.59900, 0.16313),
]

# ---------------------------------------------------------------- преобразование
T = 1.0 / F_D
W1 = 2.0 * math.pi * F_1
ARG = math.pi * F_1 / F_D           # w1*T/2
C_EXACT = 1.0 / math.tan(ARG)        # ctg(w1*T/2)
C = round(C_EXACT, 5)                # 1,96261 — как записано в работе
C2 = round(C * C, 5)                 # 3,85184


def sections(Cval, C2val, K0val, pairs):
    """Коэффициенты c0+c1 q+c2 q^2 после подстановки p = C(1-q)/(1+q).

    p^2 + a p + b = [C^2(1-q)^2 + aC(1-q)(1+q) + b(1+q)^2] / (1+q)^2
    c0 = C^2 + aC + b, c1 = 2(b - C^2), c2 = C^2 - aC + b
    """
    out = []
    for a, b in pairs:
        aC = round(a * Cval, 5)
        c0 = round(C2val + aC + b, 5)
        c1 = round(2.0 * (b - C2val), 5)
        c2 = round(C2val - aC + b, 5)
        out.append({"a": a, "b": b, "aC": aC, "c0": c0, "c1": c1, "c2": c2,
                    "a1": c1 / c0, "a2": c2 / c0})
    return out


def hpf_sections(Cval, pairs, K0val):
    """Для проверки примеров методички: p = C(1+q)/(1-q)."""
    C2v = Cval * Cval
    out = []
    for a, b in pairs:
        c0 = C2v + a * Cval + b
        c1 = 2.0 * (C2v - b)
        c2 = C2v - a * Cval + b
        out.append((c0, c1, c2))
    return out, K0val / np.prod([s[0] for s in out])


def resp(a1s, a2s, K, f):
    """|H(f)| и ослабление a(f) = -20 lg |H(f)| по coeff-ам звеньев."""
    z = np.exp(-2j * np.pi * f / F_D)
    H = K + 0j
    for a1, a2 in zip(a1s, a2s):
        H *= (1.0 + z) ** 2 / (1.0 + a1 * z + a2 * z * z)
    mag = abs(H)
    return mag, (-20.0 * math.log10(mag) if mag > 0 else float("inf"))


def main():
    # ---- 1. Проверка формул на примерах из методички -------------------------
    s, k = hpf_sections(1.2941, [(0.87608, 0.37124), (0.36288, 1.0784)], 0.38032)
    ex_ch = {"K": k, "a1": [x[1] / x[0] for x in s], "a2": [x[2] / x[0] for x in s]}
    assert abs(k - 0.0371) < 2e-4, k
    assert abs(ex_ch["a1"][0] - 0.8199) < 2e-4 and abs(ex_ch["a2"][0] - 0.2869) < 2e-4

    s, k = hpf_sections(1.2941, [(2.3314, 1.4564), (1.7067, 1.4564), (0.6247, 1.4564)], 3.0893)
    ex_bw = {"K": k, "a1": [x[1] / x[0] for x in s], "a2": [x[2] / x[0] for x in s]}
    assert abs(k - 0.0239) < 2e-4, k
    assert abs(ex_bw["a1"][0] - 0.0710) < 2e-4 and abs(ex_bw["a2"][2] - 0.5896) < 2e-4

    # ---- 2. Основной расчёт --------------------------------------------------
    secs = sections(C, C2, K0, PAIRS)
    prod_c0 = round(float(np.prod([s["c0"] for s in secs])), 5)
    K = K0 / prod_c0
    # коэффициенты, которые реально пойдут в таблицу отчёта (5 знаков)
    a1 = [round(s["a1"], 5) for s in secs]
    a2 = [round(s["a2"], 5) for s in secs]
    K_report = round(K, 8)

    # ---- 3. Независимая проверка через scipy --------------------------------
    b_an, a_an = signal.cheby1(6, A_MAX, 1.0, analog=True, btype="low", output="ba")
    # bilinear() использует p = 2 fs (1-q)/(1+q)  =>  fs = C/2
    b_dig, a_dig = signal.bilinear(b_an, a_an, fs=C_EXACT / 2.0)
    poles_dig = np.roots(a_dig)
    max_pole = float(np.max(np.abs(poles_dig)))
    K_scipy = float(b_dig[0])
    roots = np.roots(a_dig)
    biquads = []
    used = [False] * len(roots)
    for i, r in enumerate(roots):
        if used[i]:
            continue
        j = min((k for k in range(len(roots)) if not used[k]),
                key=lambda k: abs(roots[k] - np.conj(r)))
        used[i] = used[j] = True
        poly = np.real(np.poly([r, roots[j]]))
        biquads.append((poly[1] / poly[0], poly[2] / poly[0]))
    biquads.sort(key=lambda t: -t[1])
    err = max(max(abs(x - y) for x, y in zip(a1, [t[0] for t in biquads])),
              max(abs(x - y) for x, y in zip(a2, [t[1] for t in biquads])))

    # ---- 4. АЧХ и контрольные точки ----------------------------------------
    fs = np.linspace(0.0, F_1, 20000)
    ripple = max(-20 * math.log10(resp(a1, a2, K_report, float(f))[0]) for f in fs)
    f40 = brentq(lambda f: resp(a1, a2, K_report, f)[1] - A_MIN, 3000.0, F_3)
    omega3 = F_3 / F_1
    f_omega3 = F_D / math.pi * math.atan(omega3 / C_EXACT)
    points = []
    for f in (0.0, 1000.0, F_1, 3000.0, f40, f_omega3, F_3, 5000.0, F_D / 2):
        mag, att = resp(a1, a2, K_report, f)
        points.append({"f": round(f, 2), "H": mag, "a_db": None if att == float("inf") else att})

    # ---- 5. Сравнение с ЛР №3 (без предыскажений) ---------------------------
    lr3_K, lr3_a1, lr3_a2 = 0.0004522, [-1.1831, -1.2959, -1.4619], [0.8840, 0.6914, 0.5718]
    lr3_f1 = F_D / math.pi * math.atan(math.pi * F_1 / F_D)
    lr3_f3 = F_D / math.pi * math.atan(math.pi * F_3 / F_D)

    data = {
        "variant": NBR, "zach": ZACH, "filter": "ФНЧ Чебышёва", "n": 6,
        "F_d": F_D, "F_1": F_1, "F_3": F_3, "a_max": A_MAX, "a_min": A_MIN,
        "T": T, "w1": W1, "arg": ARG, "C_exact": C_EXACT, "C": C, "C2": C2,
        "K0": K0, "pairs": PAIRS, "sections": secs, "prod_c0": prod_c0,
        "K": K, "K_report": K_report, "a1": a1, "a2": a2,
        "check": {
            "max_pole": max_pole, "K_scipy": K_scipy, "max_coeff_error": err,
            "max_ripple_pp_db": ripple, "f_40db": f40, "omega3": omega3,
            "f_omega3": f_omega3, "omega_at_F3": C_EXACT * math.tan(math.pi * F_3 / F_D),
            "points": points,
        },
        "methodology_examples": {"chebyshev_hpf": ex_ch, "butterworth_hpf": ex_bw},
        "lr3": {"K": lr3_K, "a1": lr3_a1, "a2": lr3_a2,
                "f1": lr3_f1, "f3": lr3_f3, "constant": F_D / (math.pi * F_1)},
    }
    (HERE / "variant_data_lab4_24_53.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 6. Текстовый файл с коэффициентами для «Спектр-2» ------------------
    def ru(x, p=5):
        return f"{x:.{p}f}".replace(".", ",").replace("-", "−")

    txt = []
    txt.append("Коэффициенты для «Спектр-2» — ЛР №4, вариант 24, зачётка 53")
    txt.append("ФНЧ Чебышёва 6-го порядка, билинейное z-преобразование с предыскажениями")
    txt.append("")
    txt.append(f"Частота дискретизации системы: {int(F_D)} Гц")
    txt.append(f"Константа Константинидиса C = ctg(pi*F1/Fд) = {ru(C)};  C^2 = {ru(C2)}")
    txt.append(f"Общий коэффициент усиления (отдельный усилитель): K = {ru(K_report, 8)}")
    txt.append(f"Если в поле усилителя удобнее масштабированный ввод (как в ЛР №3): K*10^4 = {ru(K_report * 1e4, 5)}")
    txt.append("")
    txt.append("Прямая ветвь КАЖДОГО звена:  b0 = 1,  b1 = 2,  b2 = 1")
    txt.append("Обратная связь (ВАЖНО: коэффициент a, кроме a0, вводится с противоположным знаком):")
    txt.append("")
    txt.append("Звено |  -a1     |  -a2      |   a1 (в ПФ)  |  a2 (в ПФ)")
    txt.append("------+----------+-----------+--------------+-----------")
    for i, (x, y) in enumerate(zip(a1, a2), 1):
        txt.append(f"  {i}   | {ru(-x, 5):>8} | {ru(-y, 5):>9} | {ru(x, 5):>12} | {ru(y, 5):>9}")
    txt.append("")
    txt.append("ГТИ: период = размер пачки системы, ширина импульса = 1.")
    txt.append("Для АЧХ добавить спектроанализатор; три звена прямой формы I включены каскадно.")
    txt.append("")
    txt.append("Контрольные точки АЧХ (расчёт):")
    for p in points:
        if p["f"] in (0.0, F_1, F_3, F_D / 2) or abs(p["f"] - f40) < 0.01:
            if p["a_db"] is None or p["a_db"] > 500:
                txt.append(f"  f = {int(p['f']):>5} Гц : |H| = {ru(p['H'], 6)}")
            else:
                txt.append(f"  f = {int(p['f']):>5} Гц : |H| = {ru(p['H'], 6)}, a = {ru(p['a_db'], 4)} дБ")
    txt.append(f"  уровень ровно 40 дБ достигается на f = {ru(f40, 2)} Гц")
    txt.append(f"  граница ПП = {int(F_1)} Гц (точно по заданию), в ЛР №3 без предыскажений была {ru(lr3_f1, 1)} Гц")
    txt.append("")
    txt.append("Сравнение с ЛР №3 (тот же вариант, но без предыскажений):")
    const_lr3 = F_D / (math.pi * F_1)
    txt.append(f"  ЛР3: p = {ru(const_lr3)}*(1-z^-1)/(1+z^-1); K = 0,0004522;")
    txt.append("        a1 = −1,1831 / −1,2959 / −1,4619;  a2 = 0,8840 / 0,6914 / 0,5718")
    txt.append(f"  ЛР4: p = {ru(C)}*(1-z^-1)/(1+z^-1); K = {ru(K_report, 8)};")
    txt.append("        a1 = " + " / ".join(ru(x) for x in a1) + ";  a2 = " + " / ".join(ru(x) for x in a2))
    txt.append("  => схема собирается заново, скриншоты АЧХ отличаются (граница ПП сдвинута).")
    (LAB_DIR / "Коэффициенты для Спектр-2 (ЛР4, вариант 24, зачётка 53).txt").write_text(
        "\n".join(txt) + "\n", encoding="utf-8")

    # ---- 7. Печать сводки ---------------------------------------------------
    print(f"T = {T:.11f} c;  w1 = {W1:.5f} рад/с;  w1*T/2 = {ARG:.8f}")
    print(f"C = ctg(w1*T/2) = {C_EXACT:.10f} -> {C};  C^2 = {C2}")
    print("Звено |   c0    |    c1    |   c2    |     a1     |    a2")
    for i, s in enumerate(secs, 1):
        print(f"  {i}   | {s['c0']:8.5f} | {s['c1']:9.5f} | {s['c2']:7.5f} | {s['a1']:11.8f} | {s['a2']:.8f}")
    print(f"prod c0 = {prod_c0};  K = {K:.10f} -> {K_report}")
    print(f"a1(таблица) = {a1};  a2(таблица) = {a2}")
    print("--- проверки ---")
    print(f"методичка: ФВЧ Чебышёва K = {ex_ch['K']:.5f} (0,0371); ФВЧ Баттерворта K = {ex_bw['K']:.5f} (0,0239)")
    print(f"scipy bilinear: K = {K_scipy:.10f}; макс. расхождение коэффициентов = {err:.2e}")
    print(f"max|полюс| = {max_pole:.8f} < 1  -> фильтр устойчив")
    print(f"max неравномерность в ПП = {ripple:.5f} дБ (требуется <= {A_MAX})")
    for p in points:
        if p["a_db"] is not None and p["a_db"] < 500:
            print(f"  f = {p['f']:8.2f} Гц: |H| = {p['H']:.6f}, a = {p['a_db']:.4f} дБ")
    print(f"f(-40 дБ) = {f40:.2f} Гц;  Omega(F3) = {data['check']['omega_at_F3']:.6f};  f(Omega3) = {f_omega3:.2f} Гц")
    print("JSON и TXT записаны.")


if __name__ == "__main__":
    main()
