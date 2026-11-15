# -*- coding: utf-8 -*-
"""
КОНТРОЛЬНАЯ РАБОТА №2 по ЦОС, вариант 10.
Формирование исходного WAV-файла kr2_input.wav.
 
Сигнал: речеподобный (основной тон 118…136 Гц, форманты 700/1220/2600 Гц,
5 слогов) + тональная помеха 1500 Гц (амплитуда 0,30) и её 2-я гармоника
3000 Гц (амплитуда 0,10) + слабый широкополосный шум.
 
Запуск:     python3 make_input_signal.py
Результат:  kr2_input.wav — PCM 16 бит, моно, fд = 16 000 Гц, 3,0 с.
"""
from __future__ import annotations
 
from pathlib import Path
 
import numpy as np
from scipy import signal
from scipy.io import wavfile
 
HERE = Path(__file__).resolve().parent
FS = 16000          # частота дискретизации, Гц
DUR = 3.0           # длительность, с
SEED = 10           # вариант 10 -> seed = 10
TONE_HZ = (1500.0, 3000.0)
TONE_AMP = (0.30, 0.10)
 
 
def make_signal(fs: int = FS, dur: float = DUR, seed: int = SEED):
    """Речеподобный сигнал + тональная помеха + шум (в диапазоне ±1)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(fs * dur)) / fs
 
    # 1. источник: последовательность импульсов основного тона (118…136 Гц)
    f0 = 118 + 18 * np.sin(2 * np.pi * 0.9 * t) + 6 * np.sin(2 * np.pi * 3.1 * t)
    phase = np.cumsum(f0) / fs
    src = np.zeros_like(t)
    idx = np.nonzero(np.diff(np.floor(phase)) > 0)[0] + 1
    src[idx] = 1.0
    src = signal.lfilter([1.0], [1.0, -0.97], src)          # наклон −6 дБ/окт
 
    # 2. формантный фильтр: каскад резонаторов
    def resonator(fc, bw):
        r = np.exp(-np.pi * bw / fs)
        th = 2 * np.pi * fc / fs
        return [1 - r], [1.0, -2 * r * np.cos(th), r * r]
 
    x = src.copy()
    for fc, bw in [(700, 130), (1220, 90), (2600, 160)]:
        x = signal.lfilter(*resonator(fc, bw), x)
 
    # 3. слоговая огибающая (5 слогов)
    env = np.zeros_like(t)
    for t0, d in [(0.15, 0.45), (0.65, 0.40), (1.10, 0.55), (1.75, 0.60), (2.45, 0.40)]:
        m = (t >= t0) & (t < t0 + d)
        env[m] = np.sin(np.pi * (t[m] - t0) / d) ** 0.7
    x = x * env
    x = x / np.max(np.abs(x))
 
    # 4. тональная помеха и её 2-я гармоника
    tone = (TONE_AMP[0] * np.sin(2 * np.pi * TONE_HZ[0] * t)
            + TONE_AMP[1] * np.sin(2 * np.pi * TONE_HZ[1] * t + 0.7))
 
    # 5. слабый широкополосный шум
    noise = 0.01 * rng.standard_normal(t.size)
 
    s = 0.8 * x + tone + noise
    s = s / np.max(np.abs(s)) * 0.95
    return fs, s
 
 
def main() -> None:
    fs, s = make_signal()
    out = HERE / "kr2_input.wav"
    wavfile.write(out, fs, np.round(s * 32767).astype(np.int16))
    print(f"записан {out.name}: fд = {fs} Гц, {s.size} отсчётов, {s.size / fs:.2f} с")
 
 
if __name__ == "__main__":
    main()
