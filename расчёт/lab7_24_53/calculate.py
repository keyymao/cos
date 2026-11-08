#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ЛР №7, вариант 24 / зачётка 53: ДПФ и БПФ Кули–Тьюки.

Запуск из любого каталога: python3 расчёт/lab7_24_53/calculate.py
Создаёт variant_data_lab7_24_53.json, dft_8point.csv и TXT с параметрами эксперимента.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAB_DIR = ROOT / "лабораторные" / "лаба7"

NBR = 24
ZACHET = "53"
GROUP = "БРВ2402"
N = 1024


def dft_direct(samples: np.ndarray) -> np.ndarray:
    """Прямой расчёт ДПФ по общей формуле, без np.fft."""
    samples = np.asarray(samples, dtype=complex)
    length = len(samples)
    n = np.arange(length)
    matrix = np.exp(-2j * np.pi * np.outer(n, n) / length)
    return matrix @ samples


def fft_dit(samples: np.ndarray) -> np.ndarray:
    """Рекурсивное БПФ Кули–Тьюки с прореживанием по времени."""
    samples = np.asarray(samples, dtype=complex)
    length = len(samples)
    if length == 1:
        return samples.copy()
    if length % 2:
        raise ValueError("Для алгоритма по основанию 2 длина должна быть степенью двойки")
    even = fft_dit(samples[::2])
    odd = fft_dit(samples[1::2])
    out = np.empty(length, dtype=complex)
    for k in range(length // 2):
        rotated = np.exp(-2j * np.pi * k / length) * odd[k]
        out[k] = even[k] + rotated
        out[k + length // 2] = even[k] - rotated
    return out


def complex_row(value: complex) -> dict:
    return {
        "re": float(np.real(value)),
        "im": float(np.imag(value)),
        "magnitude": float(abs(value)),
        "phase_rad": float(np.angle(value)),
    }


def sequence_data(name: str, samples: np.ndarray) -> dict:
    values = dft_direct(samples)
    return {
        "name": name,
        "samples": [int(v) for v in samples],
        "dft": [complex_row(v) for v in values],
    }


def harmonic_case(n: np.ndarray, fd: float, components: list[dict]) -> dict:
    samples = np.zeros(N, dtype=float)
    for component in components:
        samples += component["amplitude"] * np.cos(
            2.0 * np.pi * component["frequency"] * n / fd
        )
    spectrum = np.fft.fft(samples)
    magnitude = np.abs(spectrum)
    peak_bins = set()
    peaks = []
    for component in components:
        k = int(round(N * component["frequency"] / fd))
        for bin_index in (k, N - k):
            peak_bins.add(bin_index)
        peaks.append({
            **component,
            "k": k,
            "mirror_k": N - k,
            "expected_peak": component["amplitude"] * N / 2.0,
            "measured_peak": float(magnitude[k]),
            "measured_mirror_peak": float(magnitude[N - k]),
        })
    mask = np.ones(N, dtype=bool)
    mask[list(peak_bins)] = False
    off_peak_max = float(np.max(magnitude[mask]))
    for peak in peaks:
        assert math.isclose(peak["measured_peak"], peak["expected_peak"], rel_tol=0, abs_tol=1e-7)
        assert math.isclose(peak["measured_mirror_peak"], peak["expected_peak"], rel_tol=0, abs_tol=1e-7)
    assert off_peak_max < 1e-7
    return {"components": peaks, "off_peak_max": off_peak_max}


def main() -> None:
    fd = float(2000 * ((NBR % 5) + 1))
    sampling_period = 1.0 / fd
    a1 = 1.0 + 0.01 * NBR
    a2 = 2.0 * a1
    f1 = fd / 8.0
    f2 = fd / 16.0
    assert (fd, a1, a2, f1, f2) == (10000.0, 1.24, 2.48, 1250.0, 625.0)

    # Таблица 2 методички, вариант 24: x(n) = [0 0 0 1 1 1 1 0].
    x = np.array([0, 0, 0, 1, 1, 1, 1, 0], dtype=float)
    x10 = x[::2]
    x11 = x[1::2]
    x20 = x10[::2]
    x21 = x10[1::2]
    x22 = x11[::2]
    x23 = x11[1::2]
    bit_reversed = x[[0, 4, 2, 6, 1, 5, 3, 7]]

    direct = dft_direct(x)
    fast = fft_dit(x)
    numpy_reference = np.fft.fft(x)
    direct_error = float(np.max(np.abs(direct - numpy_reference)))
    fft_error = float(np.max(np.abs(fast - numpy_reference)))
    inverse_error = float(np.max(np.abs(np.fft.ifft(direct) - x)))
    symmetry_error = float(max(abs(direct[8 - k] - np.conj(direct[k])) for k in range(1, 8)))
    assert direct_error < 1e-12 and fft_error < 1e-12
    assert inverse_error < 1e-12 and symmetry_error < 1e-12

    sqrt2 = math.sqrt(2.0)
    expected = np.array([
        4.0 + 0.0j,
        -(1.0 + sqrt2) + 1.0j,
        0.0 + 0.0j,
        (sqrt2 - 1.0) - 1.0j,
        0.0 + 0.0j,
        (sqrt2 - 1.0) + 1.0j,
        0.0 + 0.0j,
        -(1.0 + sqrt2) - 1.0j,
    ])
    analytic_error = float(np.max(np.abs(direct - expected)))
    assert analytic_error < 1e-12

    intermediate = [sequence_data(name, seq) for name, seq in [
        ("x20", x20), ("x21", x21), ("x22", x22), ("x23", x23),
        ("x10", x10), ("x11", x11),
    ]]
    intermediate_map = {row["name"]: row for row in intermediate}
    for row in intermediate:
        reference = fft_dit(np.array(row["samples"], dtype=float))
        calculated = np.array([complex(v["re"], v["im"]) for v in row["dft"]])
        assert np.max(np.abs(reference - calculated)) < 1e-12

    # Четыре операции объединения последнего этапа БПФ.
    combinations = []
    x10_dft = dft_direct(x10)
    x11_dft = dft_direct(x11)
    for k in range(4):
        twiddle = np.exp(-2j * np.pi * k / 8.0)
        combinations.append({
            "k": k,
            "twiddle": complex_row(twiddle),
            "X10": complex_row(x10_dft[k]),
            "X11": complex_row(x11_dft[k]),
            "X_k": complex_row(direct[k]),
            "X_k_plus_4": complex_row(direct[k + 4]),
        })
        assert abs(x10_dft[k] + twiddle * x11_dft[k] - direct[k]) < 1e-12
        assert abs(x10_dft[k] - twiddle * x11_dft[k] - direct[k + 4]) < 1e-12

    n = np.arange(N)
    harmonic = {
        "single": harmonic_case(n, fd, [{"frequency": f1, "amplitude": a1}]),
        "sum_variant": harmonic_case(n, fd, [
            {"frequency": f1, "amplitude": a1},
            {"frequency": f2, "amplitude": a2},
        ]),
        "gain4": harmonic_case(n, fd, [
            {"frequency": f1, "amplitude": a1},
            {"frequency": f2, "amplitude": 4.0 * a2},
        ]),
    }

    # Вторая схема из методички: один прямоугольный импульс длиной 16 в блоке 1024.
    pulse_width = 16
    pulse = np.zeros(N, dtype=float)
    pulse[:pulse_width] = 1.0
    pulse_spectrum = np.fft.fft(pulse)
    pulse_magnitude = np.abs(pulse_spectrum)
    assert abs(pulse_magnitude[0] - 16.0) < 1e-12
    assert np.max(np.abs(pulse_spectrum[64::64])) < 1e-10
    parseval_error = abs(float(np.sum(pulse ** 2)) - float(np.sum(pulse_magnitude ** 2) / N))
    assert parseval_error < 1e-9
    side_region = pulse_magnitude[65:128]
    side_max = float(np.max(side_region))
    side_k = int(65 + np.argmax(side_region))

    data = {
        "Nbr": NBR,
        "zachet": ZACHET,
        "group": GROUP,
        "N": N,
        "Fd": fd,
        "T": sampling_period,
        "A1": a1,
        "A2": a2,
        "f1": f1,
        "f2": f2,
        "k1": int(N * f1 / fd),
        "k2": int(N * f2 / fd),
        "df": fd / N,
        "x": [int(v) for v in x],
        "bit_reversed": [int(v) for v in bit_reversed],
        "dft": [complex_row(v) for v in direct],
        "intermediate": intermediate,
        "intermediate_map": intermediate_map,
        "combinations": combinations,
        "validation": {
            "direct_vs_numpy": direct_error,
            "fft_dit_vs_numpy": fft_error,
            "analytic_expected": analytic_error,
            "inverse_dft": inverse_error,
            "conjugate_symmetry": symmetry_error,
        },
        "complexity": {
            "dft8_multiplications": 8 ** 2,
            "fft8_multiplications": int(8 / 2 * math.log2(8)),
            "dft1024_multiplications": N ** 2,
            "fft1024_multiplications": int(N / 2 * math.log2(N)),
            "speedup1024": N ** 2 / (N / 2 * math.log2(N)),
        },
        "harmonic": harmonic,
        "rectangular": {
            "width": pulse_width,
            "period": N,
            "X0": float(pulse_magnitude[0]),
            "first_zero_k": 64,
            "first_zero_frequency": 64 * fd / N,
            "side_lobe_max": side_max,
            "side_lobe_k": side_k,
            "side_lobe_frequency": side_k * fd / N,
            "parseval_error": parseval_error,
        },
    }
    (HERE / "variant_data_lab7_24_53.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    with (HERE / "dft_8point_24_53.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["k", "Re X(k)", "Im X(k)", "|X(k)|", "phase, rad"])
        for k, value in enumerate(data["dft"]):
            writer.writerow([
                k, f"{value['re']:.12f}", f"{value['im']:.12f}",
                f"{value['magnitude']:.12f}", f"{value['phase_rad']:.12f}",
            ])

    def c(value: dict) -> str:
        return f"{value['re']:+.9f}{value['im']:+.9f}j"

    lines = [
        "ЛР №7 — параметры и результаты ДПФ для «Спектр-2»",
        "Вариант 24, зачётка 53",
        f"N = {N}; Fд = {fd:.0f} Гц; T = {sampling_period:.6f} с; Δf = {fd/N:.6f} Гц",
        f"A1 = {a1:.2f}; A2 = {a2:.2f}; f1 = {f1:.0f} Гц; f2 = {f2:.0f} Гц",
        f"Частота f1 соответствует k = {data['k1']} и N-k = {N-data['k1']}",
        f"Частота f2 соответствует k = {data['k2']} и N-k = {N-data['k2']}",
        "x(n) = [0 0 0 1 1 1 1 0]",
        "Настройка системы: частота дискретизации 10000 Гц, размер блока ДПФ 1024.",
        "",
        "ДПФ восьмиточечной последовательности:",
    ]
    for k, value in enumerate(data["dft"]):
        lines.append(f"X({k}) = {c(value)}; |X| = {value['magnitude']:.9f}; phase = {value['phase_rad']:+.9f}")
    lines += ["", "Промежуточные последовательности:"]
    for row in intermediate:
        spectrum = ", ".join(c(v) for v in row["dft"])
        lines.append(f"{row['name']} = {row['samples']}; ДПФ = [{spectrum}]")
    lines += [
        "",
        "Эксперимент с гармониками (амплитуда пика = A*N/2):",
        f"1) K2 = 0 (одна гармоника A1, f1 = {f1:.0f} Гц): k=128 и 896, пик = {a1*N/2:.2f}",
        f"2) K2 = 1 (сумма по варианту, амплитуды A1 и A2): k=128/896 пик = {a1*N/2:.2f}; "
        f"k=64/960 пик = {a2*N/2:.2f}",
        f"3) K2 = 4 (как в примере методички): k=128/896 пик = {a1*N/2:.2f}; "
        f"k=64/960 пик = {4*a2*N/2:.2f}",
        "",
        "Прямоугольные импульсы: ГТИ, ширина = 16 отсчётов, период = 1024 отсчёта, амплитуда = 1.",
        f"X(0) = 16; нули при k = 64m; первый нуль k=64, f = {64*fd/N:.0f} Гц.",
        f"Первый боковой лепесток: max = {side_max:.9f} при k = {side_k}, f = {side_k*fd/N:.3f} Гц.",
        "",
        "В отчёте на месте рисунков 2-9 оставлены заглушки под скриншоты «Спектр-2»;",
        "положения и высоты линий на них должны совпадать с пиками, указанными выше.",
    ]
    (LAB_DIR / "Параметры для Спектр-2 (ЛР7, вариант 24, зачётка 53).txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print("ЛР №7, вариант 24 / зачётка 53")
    print(f"N={N}; Fд={fd:.0f} Гц; A1={a1:.2f}; A2={a2:.2f}; f1={f1:.0f}; f2={f2:.0f}")
    print("x(n) =", data["x"])
    print("max errors: direct", direct_error, "FFT", fft_error, "analytic", analytic_error)
    print(f"Пики: одна гармоника {a1*N/2:.2f}; A2 {a2*N/2:.2f}; K2=4 {4*a2*N/2:.2f}")
    print(f"Прямоугольный импульс: X(0)=16, первый нуль k=64, Parseval error={parseval_error:.3e}")
    print("saved:", HERE / "variant_data_lab7_24_53.json")
    print("saved:", HERE / "dft_8point_24_53.csv")
    print("saved:", LAB_DIR / "Параметры для Спектр-2 (ЛР7, вариант 24, зачётка 53).txt")


if __name__ == "__main__":
    main()
