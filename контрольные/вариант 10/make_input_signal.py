# -*- coding: utf-8 -*-
"""
КОНТРОЛЬНАЯ РАБОТА №2 (ЦОС), вариант 10.
Формирование исходного WAV-файла kr2_input.wav:
речеподобный сигнал (основной тон 118…136 Гц, форманты 700/1220/2600 Гц,
5 слогов) + тональная помеха 1500 Гц (амплитуда 0.30) и её 2-я гармоника
3000 Гц (0.10) + слабый широкополосный шум.

Запуск:  python make_input_signal.py
Результат: файл kr2_input.wav (PCM 16 бит, моно, fд = 16 000 Гц, 3.0 с)
"""
import numpy as np
from scipy import signal
from scipy.io import wavfile

FS = 16000          # частота дискретизации, Гц
DUR = 3.0           # длительность, с
OUT = "kr2_input.wav"
rng = np.random.default_rng(10)          # вариант 10 -> seed = 10
t = np.arange(int(FS * DUR)) / FS

# --- 1. Источник: импульсы основного тона с изменяющейся f0 -------------
f0 = 118 + 18*np.sin(2*np.pi*0.9*t) + 6*np.sin(2*np.pi*3.1*t)   # 118…136 Гц
phase = np.cumsum(f0) / FS
src = np.zeros_like(t)
idx = np.nonzero(np.diff(np.floor(phase)) > 0)[0] + 1
src[idx] = 1.0
src = signal.lfilter([1.0], [1.0, -0.97], src)      # наклон спектра -6 дБ/окт

# --- 2. Формантный фильтр (каскад резонаторов) ---------------------------
def resonator(fc, bw):
    r = np.exp(-np.pi * bw / FS)
    th = 2 * np.pi * fc / FS
    return [1 - r], [1.0, -2 * r * np.cos(th), r * r]

x = src.copy()
for fc, bw in [(700, 130), (1220, 90), (2600, 160)]:   # форманты 700/1220/2600 Гц
    x = signal.lfilter(*resonator(fc, bw), x)

# --- 3. Слоговая огибающая (5 слогов) ------------------------------------
env = np.zeros_like(t)
syllables = [(0.15, 0.45), (0.65, 0.40), (1.10, 0.55), (1.75, 0.60), (2.45, 0.40)]
for k, (t0, dur) in enumerate(syllables):
    m = (t >= t0) & (t < t0 + dur)
    tt = (t[m] - t0) / dur
    env[m] = np.sin(np.pi * tt) ** 0.7
x = x * env
x = x / np.max(np.abs(x))

# --- 4. Тональная помеха (1500 Гц + 2-я гармоника 3000 Гц) ----------------
tone = 0.30*np.sin(2*np.pi*1500*t) + 0.10*np.sin(2*np.pi*3000*t + 0.7)

# --- 5. Слабый широкополосный шум -----------------------------------------
noise = 0.01 * rng.standard_normal(t.size)

s = 0.8*x + tone + noise
s = s / np.max(np.abs(s)) * 0.95
wavfile.write(OUT, FS, (s * 32767).astype(np.int16))
print("written", OUT, FS, DUR, "s,", t.size, "отсчётов")
