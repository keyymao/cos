#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ЛР №6, вариант 24 / зачётка 53: синтез ФНЧ методом окна Кайзера.

Запуск из любого каталога: python3 расчёт/lab6_24_53/calculate.py
Результаты:
  * variant_data_lab6_24_53.json и coefficients_lab6_24_53.csv — рядом со скриптом;
  * TXT с коэффициентами — в лабораторные/лаба6/.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy import signal, special

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAB_DIR = ROOT / "лабораторные" / "лаба6"

NBR = 24
ZACHET = "53"
GROUP = "БРВ2402"
DELTA1 = 0.05
DELTA2 = 0.01


def attenuation(magnitude: float) -> float:
    return math.inf if magnitude == 0 else -20.0 * math.log10(magnitude)


def response_at(b: np.ndarray, frequency: float, fd: float) -> complex:
    k = np.arange(len(b))
    return np.sum(b * np.exp(-2j * np.pi * frequency * k / fd))


def metrics(b: np.ndarray, frequencies: np.ndarray, f1: float, f3: float, fd: float) -> dict:
    """Проверка требований к ФНЧ: ПП 0…F1, ПЗ F3…Fд/2."""
    _, response = signal.freqz(b, worN=2.0 * np.pi * frequencies / fd)
    magnitude = np.abs(response)
    pass_mask = frequencies <= f1
    stop_mask = frequencies >= f3
    passed = magnitude[pass_mask]
    stop = magnitude[stop_mask]
    pass_frequencies = frequencies[pass_mask]
    stop_frequencies = frequencies[stop_mask]
    pass_min_index = int(np.argmin(passed))
    pass_max_index = int(np.argmax(passed))
    stop_index = int(np.argmax(stop))
    stop_max = float(stop[stop_index])
    pass_min = float(passed[pass_min_index])
    pass_max = float(passed[pass_max_index])
    return {
        "stop_max": stop_max,
        "stop_max_frequency": float(stop_frequencies[stop_index]),
        "stop_attenuation_db": attenuation(stop_max),
        "pass_min": pass_min,
        "pass_min_frequency": float(pass_frequencies[pass_min_index]),
        "pass_max": pass_max,
        "pass_max_frequency": float(pass_frequencies[pass_max_index]),
        "pass_max_deviation": float(np.max(np.abs(passed - 1.0))),
        "requirements_met": bool(
            stop_max <= DELTA2 and pass_min >= 1.0 - DELTA1 and pass_max <= 1.0 + DELTA1
        ),
    }


def design(order: int, fc: float, beta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """n, h_u, w и h для симметричного ФНЧ нечётной длины N = R + 1."""
    if order % 2:
        raise ValueError("Для симметричного ФНЧ нужен чётный порядок R")
    length = order + 1
    n = np.arange(-order // 2, order // 2 + 1, dtype=int)
    ideal = np.empty(length, dtype=float)
    nonzero = n != 0
    ideal[~nonzero] = 2.0 * fc
    ideal[nonzero] = np.sin(2.0 * np.pi * fc * n[nonzero]) / (np.pi * n[nonzero])
    window = special.i0(beta * np.sqrt(1.0 - (2.0 * n / (length - 1)) ** 2)) / special.i0(beta)
    return n, ideal, window, ideal * window


def main() -> None:
    # Исходные данные из таблицы 1 методических указаний для ФНЧ.
    fd = float(10000 + 50 * NBR)
    f1 = float(705 + 25 * NBR)   # граница полосы пропускания
    f3 = float(2100 + 35 * NBR)  # граница полосы задержания
    fc_physical = (f1 + f3) / 2.0
    fc = (f1 + f3) / (2.0 * fd)
    transition_width = (f3 - f1) / fd
    amin = -20.0 * math.log10(DELTA2)
    d_parameter = (amin - 7.95) / 14.36 if amin >= 21.0 else 0.9222
    order_estimate = d_parameter / transition_width + 1.0
    order = math.floor(order_estimate)
    if order % 2:
        order -= 1
    length = order + 1
    if amin > 50.0:
        beta = 0.1102 * (amin - 8.7)
    elif amin >= 21.0:
        beta = 0.5842 * (amin - 21.0) ** 0.4 + 0.07886 * (amin - 21.0)
    else:
        beta = 0.0

    assert (fd, f1, f3) == (11200.0, 1305.0, 2940.0)
    assert order == 16 and length == 17

    n, ideal, window, coefficients = design(order, fc, beta)
    # Шаг 0,01 Гц: обе заданные границы присутствуют на сетке точно.
    frequencies = np.linspace(0.0, fd / 2.0, 560001)
    check = metrics(coefficients, frequencies, f1, f3, fd)

    # Независимая проверка коэффициентов через scipy.signal.firwin (ФНЧ).
    scipy_coefficients = signal.firwin(
        length,
        fc_physical,
        window=("kaiser", beta),
        pass_zero=True,
        scale=False,
        fs=fd,
    )
    scipy_error = float(np.max(np.abs(scipy_coefficients - coefficients)))

    # Контрольный пример ФНЧ из п. 1.2 методички (Fд=48000, F1=12000, F3=19000).
    methodology_fc = (12000.0 + 19000.0) / (2.0 * 48000.0)
    *_, methodology_coefficients = design(16, methodology_fc, beta)
    methodology_published = np.array([
        -0.0029, 0.0121, -0.0082, -0.0230, 0.0529, -0.0169, -0.1154, 0.2792,
        0.6458, 0.2792, -0.1154, -0.0169, 0.0529, -0.0230, -0.0082, 0.0121, -0.0029,
    ])
    methodology_error = float(np.max(np.abs(methodology_coefficients - methodology_published)))

    rounded = np.round(coefficients, 8)
    rounded_check = metrics(rounded, frequencies, f1, f3, fd)

    # Проверка минимальности среди чётных порядков, необходимых для ФНЧ I типа.
    order_checks = []
    for candidate in range(2, order + 1, 2):
        *_, candidate_coefficients = design(candidate, fc, beta)
        candidate_metrics = metrics(candidate_coefficients, frequencies, f1, f3, fd)
        order_checks.append({"R": candidate, **candidate_metrics})
    assert all(not row["requirements_met"] for row in order_checks if row["R"] < order)
    assert order_checks[-1]["requirements_met"]

    points = []
    for label, frequency in [
        ("Постоянная составляющая", 0.0),
        ("Граница ПП F1", f1),
        ("Частота среза Fc", fc_physical),
        ("Граница ПЗ F3", f3),
        ("Частота Найквиста", fd / 2.0),
    ]:
        value = abs(response_at(coefficients, frequency, fd))
        points.append({
            "label": label,
            "frequency": frequency,
            "magnitude": float(value),
            "attenuation_db": attenuation(float(value)),
        })

    # Уровень 40 дБ в полосе задержания.
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(signal.freqz(
        coefficients, worN=2.0 * np.pi * frequencies / fd)[1]), 1e-12))
    stop_indices = np.where((frequencies >= f1) & (magnitude_db <= -amin))[0]
    attenuation_40db_frequency = float(frequencies[stop_indices[0]]) if stop_indices.size else None

    # Численная проверка ИХ каузальной реализации на единичный импульс.
    impulse = np.zeros(order + 9)
    impulse[0] = 1.0
    impulse_response = signal.lfilter(coefficients, [1.0], impulse)

    assert np.allclose(coefficients, coefficients[::-1], atol=1e-15)
    assert math.isclose(float(window[order // 2]), 1.0, abs_tol=1e-15)
    assert scipy_error < 1e-12
    assert methodology_error <= 5e-5  # расхождение только из-за 4 знаков в таблице методички
    assert check["requirements_met"] and rounded_check["requirements_met"]
    assert np.allclose(impulse_response[:length], coefficients, atol=1e-15)
    assert np.allclose(impulse_response[length:], 0.0, atol=1e-15)

    data = {
        "Nbr": NBR,
        "zachet": ZACHET,
        "group": GROUP,
        "filter_type": "ФНЧ",
        "window": "Кайзера",
        "Fd": fd,
        "F1": f1,
        "F3": f3,
        "Fc": fc_physical,
        "fc": fc,
        "delta1": DELTA1,
        "delta2": DELTA2,
        "amin": amin,
        "D": d_parameter,
        "delta_F": transition_width,
        "R_exact": order_estimate,
        "R": order,
        "N": length,
        "beta": beta,
        "group_delay": order // 2,
        "coefficients": [
            {
                "i": i,
                "n": int(n[i]),
                "h_ideal": float(ideal[i]),
                "w": float(window[i]),
                "h": float(coefficients[i]),
                "b": float(coefficients[i]),
            }
            for i in range(length)
        ],
        "points": points,
        "check": check,
        "rounded8": rounded_check,
        "order_checks": order_checks,
        "attenuation_40db_frequency": attenuation_40db_frequency,
        "validation_scipy": {
            "method": "scipy.signal.firwin(..., pass_zero=True, scale=False)",
            "max_abs_error": scipy_error,
        },
        "validation_methodology_example": {
            "Fd": 48000.0,
            "F1": 12000.0,
            "F3": 19000.0,
            "R": 16,
            "max_abs_error_to_published_4_decimals": methodology_error,
        },
        "impulse_response": [float(x) for x in impulse_response],
    }

    (HERE / "variant_data_lab6_24_53.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with (HERE / "coefficients_lab6_24_53.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["i", "n", "h_ideal(n)", "w(n)", "h(n)=b(i)"])
        for row in data["coefficients"]:
            writer.writerow([
                row["i"], row["n"],
                f"{row['h_ideal']:.12f}", f"{row['w']:.12f}", f"{row['h']:.12f}",
            ])

    lines = [
        "ЛР №6 — коэффициенты ФНЧ для «Спектр-2»",
        "Вариант 24, зачётка 53; окно Кайзера",
        f"Fд = {fd:.0f} Гц; F1(ПП) = {f1:.0f} Гц; F3(ПЗ) = {f3:.0f} Гц",
        f"Fc = {fc_physical:.1f} Гц; fc = {fc:.12f}",
        f"R = {order}; N = {length}; beta = {beta:.12f}; D = {d_parameter:.12f}",
        "Структура: прямой КИХ-фильтр; 16 линий задержки, 17 усилителей, сумматор на 17 входов.",
        "b(i) = h(n), где n = i - 8. Коэффициенты вводятся со своими знаками, инверсия не требуется.",
        "",
        "i  | n  | b(i) для усилителя",
        "---+----+-----------------------",
    ]
    for row in data["coefficients"]:
        lines.append(f"{row['i']:2d} | {row['n']:3d} | {row['b']:+.12f}")
    lines += [
        "",
        "ГТИ: период = размер пачки системы; ширина импульса = 1.",
        "После 17-го отсчёта ИХ каузальной реализации равна нулю.",
        "",
        "Контрольные точки численного расчёта:",
    ]
    for point in points:
        lines.append(
            f"f = {point['frequency']:7.1f} Гц: |H| = {point['magnitude']:.9f}; "
            f"a = {point['attenuation_db']:.6f} дБ"
        )
    lines.append(
        "  (на 0 и 1305 Гц |H| немного больше единицы — это пульсации в ПП, "
        "ослабления там нет)"
    )
    lines += [
        "",
        f"Максимум в ПЗ ({f3:.0f}...{fd/2:.0f} Гц): {check['stop_max']:.9f} <= 0,01.",
        f"Диапазон в ПП (0...{f1:.0f} Гц): {check['pass_min']:.9f}...{check['pass_max']:.9f}.",
        "Допуск в ПП: 0,95...1,05. Требования выполняются, в том числе после округления b(i) до 8 знаков.",
    ]
    (LAB_DIR / "Коэффициенты для Спектр-2 (ЛР6, вариант 24, зачётка 53).txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print("ЛР №6, вариант 24 / зачётка 53 — ФНЧ, окно Кайзера")
    print(f"Fд={fd:.0f} Гц; F1={f1:.0f} Гц; F3={f3:.0f} Гц; Fc={fc_physical:.1f} Гц")
    print(f"R={order}; N={length}; beta={beta:.12f}; D={d_parameter:.12f}")
    print(f"ПЗ: max|H|={check['stop_max']:.9f} <= 0,01; a_min={check['stop_attenuation_db']:.6f} дБ")
    print(f"ПП: {check['pass_min']:.9f} <= |H| <= {check['pass_max']:.9f}")
    print(f"Уровень 40 дБ достигается на {attenuation_40db_frequency:.2f} Гц")
    print(f"Независимая проверка scipy firwin: max error = {scipy_error:.3e}")
    print(f"Контрольный пример ФНЧ из методички: max error = {methodology_error:.3e}")
    print("Округление до 8 знаков: требования выполняются")
    print("saved:", HERE / "variant_data_lab6_24_53.json")
    print("saved:", HERE / "coefficients_lab6_24_53.csv")
    print("saved:", LAB_DIR / "Коэффициенты для Спектр-2 (ЛР6, вариант 24, зачётка 53).txt")


if __name__ == "__main__":
    main()
