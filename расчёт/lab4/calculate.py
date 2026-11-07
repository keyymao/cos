#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ЛР №4, вариант 12 / зачётка 06.

ФВЧ Баттерворта: аналоговый ФНЧ-прототип из ЛР №3 -> цифровой ФВЧ
преобразованием Константинидиса с предыскажением.  Рисунки не строятся.

Запуск:  python3 calculate.py
Выход:   variant_data_lab4.json, coefficients_lab4.csv,
         ../../Коэффициенты для Спектр-2 (ЛР4, вариант 12, зачётка 06).txt
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

NBR = 12
ZACHET = "06"
GROUP = "БРВ2402"


def ru(x: float, nd: int = 8) -> str:
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "−")


def attenuation(h: complex) -> float:
    mag = abs(h)
    return math.inf if mag == 0 else -20.0 * math.log10(mag)


def digital_response(f: float, fd: float, gain: float, sections) -> complex:
    q = np.exp(-2j * np.pi * f / fd)
    den = np.prod([1.0 + s["a1"] * q + s["a2"] * q * q for s in sections])
    return gain * (1.0 - q) ** 6 / den


def prototype(nbr: int = NBR):
    fd = 10000 + 200 * nbr
    f1_table = 1200 + 20 * nbr
    fz_table = 3120 + 50 * nbr + 10 * (nbr // 5)
    # Для ФВЧ большая из двух табличных частот становится границей ПП.
    fp = max(f1_table, fz_table)
    fs = min(f1_table, fz_table)
    amax, amin = 0.4455, 40.0
    eps2 = 10.0 ** (0.1 * amax) - 1.0
    eps = math.sqrt(eps2)
    omega_ratio = fp / fs
    n_exact = math.log10((10.0 ** (0.1 * amin) - 1.0) / eps2) / (
        2.0 * math.log10(omega_ratio)
    )
    n = math.ceil(n_exact)
    radius = eps ** (-1.0 / n)
    pairs = []
    # Комплексно-сопряжённые пары левой полуплоскости, по возрастанию |Re p|.
    for k in range(n // 2):
        theta = math.pi / 2.0 + (2 * k + 1) * math.pi / (2 * n)
        re = radius * math.cos(theta)
        im = radius * math.sin(theta)
        pairs.append({"re": re, "im": im, "a": -2.0 * re, "b": re * re + im * im})
    pairs.reverse()  # как в ЛР №3: наибольшая |Re p| первой
    return {
        "Nbr": nbr,
        "zachet": ZACHET,
        "group": GROUP,
        "filter_function": "Баттерворта",
        "selectivity": "ФВЧ",
        "Fd": fd,
        "F1_table": f1_table,
        "Fz_table": fz_table,
        "Fp": fp,
        "Fs": fs,
        "amax": amax,
        "amin": amin,
        "eps2": eps2,
        "eps": eps,
        "Omega_ratio_L3": omega_ratio,
        "n_exact_L3": n_exact,
        "n": n,
        "R": radius,
        "K_LP": 1.0 / eps,
        "lhp_pairs": pairs,
    }


def constantinides_hp(data):
    fd, fp = data["Fd"], data["Fp"]
    t = 1.0 / fd
    omega1 = 2.0 * math.pi * fp
    theta = omega1 * t / 2.0
    c = math.tan(theta)
    c2 = c * c
    sections = []
    prod_c0 = 1.0
    for pair in data["lhp_pairs"]:
        a, b = pair["a"], pair["b"]
        # p = C(1+q)/(1-q), q=z^-1:
        # p^2+a p+b = (c0+c1 q+c2 q^2)/(1-q)^2.
        c0 = c2 + a * c + b
        c1 = 2.0 * (c2 - b)
        c2coef = c2 - a * c + b
        prod_c0 *= c0
        sections.append(
            {
                "a_prototype": a,
                "b_prototype": b,
                "c0": c0,
                "c1": c1,
                "c2": c2coef,
                "b0": 1.0,
                "b1": -2.0,
                "b2": 1.0,
                "a0": 1.0,
                "a1": c1 / c0,
                "a2": c2coef / c0,
                "feedback_minus_a1": -c1 / c0,
                "feedback_minus_a2": -c2coef / c0,
            }
        )
    gain = data["K_LP"] / prod_c0
    omega_stop_mapped = c / math.tan(math.pi * data["Fs"] / fd)
    omega40 = ((10.0 ** (data["amin"] / 10.0) - 1.0) / data["eps2"]) ** (
        1.0 / (2.0 * data["n"])
    )
    f40 = fd / math.pi * math.atan(c / omega40)
    data.update(
        {
            "T": t,
            "omega1": omega1,
            "theta": theta,
            "C": c,
            "C2": c2,
            "Omega_stop_mapped": omega_stop_mapped,
            "Omega_40dB": omega40,
            "f_40dB": f40,
            "prod_c0": prod_c0,
            "K": gain,
            "sections": sections,
        }
    )
    return data


def rounded_sections(data, decimals=8):
    return [
        {
            **s,
            "a1": round(s["a1"], decimals),
            "a2": round(s["a2"], decimals),
            "feedback_minus_a1": -round(s["a1"], decimals),
            "feedback_minus_a2": -round(s["a2"], decimals),
        }
        for s in data["sections"]
    ]


def checks(data):
    fd, fp, fs = data["Fd"], data["Fp"], data["Fs"]
    sec, gain = data["sections"], data["K"]
    h_pass = digital_response(fp, fd, gain, sec)
    h_stop = digital_response(fs, fd, gain, sec)
    h_nyq = digital_response(fd / 2.0, fd, gain, sec)
    h_dc = digital_response(0.0, fd, gain, sec)
    pole_max = max(
        float(np.max(np.abs(np.roots([1.0, s["a1"], s["a2"]])))) for s in sec
    )
    rounded = rounded_sections(data)
    kr = round(gain, 10)
    rounded6 = rounded_sections(data, 6)
    kr6 = round(gain, 6)
    hp6 = digital_response(fp, fd, kr6, rounded6)
    hs6 = digital_response(fs, fd, kr6, rounded6)
    hn6 = digital_response(fd / 2.0, fd, kr6, rounded6)
    hp_r = digital_response(fp, fd, kr, rounded)
    hs_r = digital_response(fs, fd, kr, rounded)
    hn_r = digital_response(fd / 2.0, fd, kr, rounded)
    points = []
    for f in [0, 500, 1000, fs, 1800, 2000, 2500, 3000, fp, 4500, 5000, fd / 2]:
        h = digital_response(f, fd, gain, sec)
        mag = abs(h)
        points.append(
            {
                "f": f,
                "magnitude": mag,
                "attenuation_db": None if mag == 0 else attenuation(h),
            }
        )
    result = {
        "a_pass_db": attenuation(h_pass),
        "a_stop_db": attenuation(h_stop),
        "H_pass": abs(h_pass),
        "H_stop": abs(h_stop),
        "H_nyq": abs(h_nyq),
        "H_dc": abs(h_dc),
        "pole_max": pole_max,
        "rounded8": {
            "K": kr,
            "a_pass_db": attenuation(hp_r),
            "a_stop_db": attenuation(hs_r),
            "H_nyq": abs(hn_r),
            "nyq_gain_error": abs(abs(hn_r) - 1.0),
        },
        "rounded6_fallback": {
            "K": kr6,
            "a_pass_db": attenuation(hp6),
            "a_stop_db": attenuation(hs6),
            "H_nyq": abs(hn6),
            "nyq_gain_error": abs(abs(hn6) - 1.0),
        },
        "control_points": points,
    }
    assert abs(result["a_pass_db"] - data["amax"]) < 1e-7
    assert result["a_stop_db"] >= data["amin"]
    assert pole_max < 1.0
    assert abs(result["H_nyq"] - 1.0) < 1e-10
    assert result["H_dc"] < 1e-12
    assert result["rounded8"]["a_pass_db"] <= data["amax"] + 1e-9
    assert result["rounded8"]["a_stop_db"] >= data["amin"]
    assert result["rounded8"]["nyq_gain_error"] < 1e-6
    assert result["rounded6_fallback"]["a_pass_db"] <= data["amax"]
    assert result["rounded6_fallback"]["a_stop_db"] >= data["amin"]
    assert result["rounded6_fallback"]["nyq_gain_error"] < 1e-5
    data["check"] = result
    return result


def independent_scipy_check(data):
    """Независимая проверка через фиксированный n=6 analog butter + bilinear.

    Важно: частоту среза butter() нельзя путать с границей ПП при a_max != 3 дБ.
    Полюсы прототипа имеют радиус R=eps^(-1/n); после замены ФНЧ->ФВЧ радиус
    аналогового ФВЧ равен 1/R, поэтому wc_hp = (2 Fd C)/R.
    """
    fd, n = data["Fd"], data["n"]
    wc_hp = 2.0 * fd * data["C"] / data["R"]
    ba, aa = signal.butter(n, wc_hp, btype="highpass", analog=True)
    b, a = signal.bilinear(ba, aa, fs=fd)
    expected_b = data["K"] * np.array([1, -6, 15, -20, 15, -6, 1], dtype=float)
    expected_a = np.array([1.0])
    for s in data["sections"]:
        expected_a = np.convolve(expected_a, [1.0, s["a1"], s["a2"]])
    err_b = float(np.max(np.abs(b - expected_b)))
    err_a = float(np.max(np.abs(a - expected_a)))
    assert err_b < 1e-10 and err_a < 1e-10, (err_b, err_a)
    data["validation_scipy"] = {
        "method": "fixed n=6 scipy.signal.butter(highpass, analog=True) + bilinear",
        "wc_hp_rad_s": wc_hp,
        "max_abs_error_b": err_b,
        "max_abs_error_a": err_a,
        "b": b.tolist(),
        "a": a.tolist(),
    }


def methodology_example_check():
    """Контроль формулы на примере Баттерворта из методички ЛР №4 (не вариант 12)."""
    fd, fp, fs = 17000.0, 4940.0, 1900.0
    c = math.tan(math.pi * fp / fd)
    pairs = [(2.3314, 1.4564), (1.7067, 1.4564), (0.6247, 1.4564)]
    sec, prod = [], 1.0
    for a, b in pairs:
        c0 = c * c + a * c + b
        c1 = 2.0 * (c * c - b)
        c2 = c * c - a * c + b
        prod *= c0
        sec.append({"a1": c1 / c0, "a2": c2 / c0})
    gain = 3.0893 / prod
    printed_a1 = [0.0710, 0.0818, 0.1109]
    printed_a2 = [0.0186, 0.1728, 0.5896]
    assert all(abs(s["a1"] - x) < 2e-4 for s, x in zip(sec, printed_a1))
    assert all(abs(s["a2"] - x) < 2e-4 for s, x in zip(sec, printed_a2))
    assert abs(gain - 0.0239) < 2e-5
    ap = attenuation(digital_response(fp, fd, gain, sec))
    ast = attenuation(digital_response(fs, fd, gain, sec))
    hn = abs(digital_response(fd / 2, fd, gain, sec))
    # В примере методички коэффициенты прототипа уже округлены до 4 знаков,
    # поэтому единичное усиление на Найквисте воспроизводится с той же точностью.
    assert ap < 0.4455 and ast > 40 and abs(hn - 1) < 1e-4
    return {
        "C": c,
        "K": gain,
        "sections": sec,
        "a_pass_db": ap,
        "a_stop_db": ast,
        "H_nyq": hn,
        "note": "Знаки a1 положительные; в усилители ОС вводятся -a1. Мелкие отличия последних знаков — округление примера.",
    }


def write_outputs(data):
    (HERE / "variant_data_lab4.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with (HERE / "coefficients_lab4.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "section", "b0", "b1", "b2", "a0", "a1", "a2",
                "feedback_-a1", "feedback_-a2", "K",
            ]
        )
        for i, s in enumerate(data["sections"], 1):
            writer.writerow(
                [
                    i, "1", "-2", "1", "1",
                    f"{s['a1']:.8f}", f"{s['a2']:.8f}",
                    f"{-s['a1']:.8f}", f"{-s['a2']:.8f}",
                    f"{data['K']:.10f}" if i == 1 else "",
                ]
            )
    lines = [
        "ЛР №4 — коэффициенты для «Спектр-2»",
        "Вариант 12, зачётка 06: ФВЧ Баттерворта, n=6",
        f"Частота дискретизации: {data['Fd']} Гц; T = {data['T']:.11f} с = {data['T']*1e6:.8f} мкс",
        "Структура: 3 биквадратных звена прямой формы I, каскадно; общий усилитель K отдельно.",
        "Для каждого звена: b0=1, b1=-2, b2=1, a0=1.",
        "ВАЖНО: в усилители обратной связи вводятся -a1 и -a2 (противоположный знак).",
        "",
        "Рекомендуемый ввод (8 знаков для a, 10 знаков для K):",
        "Звено | a1         | a2         | усилитель -a1 | усилитель -a2",
    ]
    for i, s in enumerate(data["sections"], 1):
        lines.append(
            f"{i}     | {s['a1']:.8f} | {s['a2']:.8f} | {-s['a1']:.8f}   | {-s['a2']:.8f}"
        )
    lines += [
        f"Общий коэффициент усиления K = {data['K']:.10f}",
        "",
        "Если поле допускает только 6 знаков после запятой:",
    ]
    for i, s in enumerate(data["sections"], 1):
        lines.append(
            f"Звено {i}: -a1 = {-s['a1']:.6f}; -a2 = {-s['a2']:.6f}; "
            f"(a1={s['a1']:.6f}, a2={s['a2']:.6f})"
        )
    lines += [
        f"K = {data['K']:.6f}  (при a1/a2 с 6 знаками это даёт a(3740)≈0,445496 дБ)",
        "",
        "ГТИ: период = размер пачки системы; ширина импульса = 1.",
        "Контрольные точки: f=1440 Гц -> a≈57,7025 дБ; f=3740 Гц -> a≈0,4455 дБ; f=6200 Гц -> |H|≈1.",
        "Точка ровно -40 дБ лежит около 1943,36 Гц; это запас относительно заданной границы ПЗ 1440 Гц.",
        "Схема и графики АЧХ/ИХ выполняются пользователем самостоятельно в «Спектр-2».",
    ]
    out_txt = ROOT / "Коэффициенты для Спектр-2 (ЛР4, вариант 12, зачётка 06).txt"
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    data = prototype()
    assert data["zachet"][-1] in "02468" and data["zachet"][-2] in "02468"
    assert data["n"] == 6 and data["Fd"] == 12400
    assert data["Fp"] == 3740 and data["Fs"] == 1440
    constantinides_hp(data)
    checks(data)
    independent_scipy_check(data)
    data["validation_methodology_example"] = methodology_example_check()
    write_outputs(data)
    print("ЛР №4, вариант 12 / зачётка 06 — ФВЧ Баттерворта, n=6")
    print(f"T={data['T']:.11f} c; C={data['C']:.10f}; K={data['K']:.10f}")
    for i, s in enumerate(data["sections"], 1):
        print(
            f"звено {i}: a1={s['a1']:.8f}; a2={s['a2']:.8f}; "
            f"в Спектр: -a1={-s['a1']:.8f}; -a2={-s['a2']:.8f}"
        )
    c = data["check"]
    print(
        f"проверка: a(3740)={c['a_pass_db']:.8f} дБ; "
        f"a(1440)={c['a_stop_db']:.8f} дБ; max|полюс|={c['pole_max']:.8f}"
    )
    print(
        f"округление 8 знаков: a(3740)={c['rounded8']['a_pass_db']:.8f} дБ; "
        f"a(1440)={c['rounded8']['a_stop_db']:.8f} дБ"
    )
    print("независимая проверка scipy:", data["validation_scipy"]["max_abs_error_a"])
    print("контрольный пример методички: PASS")
    print("saved:", HERE / "variant_data_lab4.json")
    print("saved:", ROOT / "Коэффициенты для Спектр-2 (ЛР4, вариант 12, зачётка 06).txt")


if __name__ == "__main__":
    main()
