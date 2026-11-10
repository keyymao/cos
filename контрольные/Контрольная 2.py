#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрольная работа №2 по ЦОС.
Разработка эквалайзера с возможностью подавления тональной помехи.

Дано: WAV-файл с аудиозаписью сигнала с шумом (тональным).
Требуется разработать систему, выполняющую функции:
  1. Разложение сигнала в спектр, построение спектрограммы;
  2. Регулировку усиления (ослабления) частотных диапазонов (эквалайзер);
  3. Подавление помехи в виде тонального сигнала;
  4. Синтез результирующего сигнала в формате WAV.

Архитектура системы (4 модуля):
  [Модуль анализа]        осциллограмма, спектр, спектрограмма сигнала
  [Модуль эквалайзера]    разбивка спектра на 3 полосы (НЧ/СЧ/ВЧ) и применение маски усилений
  [Модуль подавителя]     обнуление спектральных составляющих в полосе тональной помехи
  [Модуль синтеза]        обратное БПФ + запись результирующего WAV

Если входной WAV не задан, генерируется демонстрационный сигнал
(сумма гармоник + белый шум + тональная помеха) — код сигнала на Python.

Запуск:
  python3 "Контрольная 2.py"                          # демо-сигнал, выход в ./output
  python3 "Контрольная 2.py" --input input.wav        # свой WAV
  python3 "Контрольная 2.py" --tone 3000 --bw 200 --gains -6,0,6

Зависимости: numpy, matplotlib (чтение/запись WAV — стандартный модуль wave).
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 10, "figure.dpi": 140})

# ================= Параметры по умолчанию =================
FS = 48000                 # частота дискретизации, Гц
DURATION = 4.0             # длительность демо-сигнала, с
TONE_FREQ = 14000.0        # частота тональной помехи в демо-сигнале, Гц
TONE_AMP = 0.5             # амплитуда тональной помехи
NOISE_AMP = 0.02           # амплитуда белого шума
BAND_EDGES = (8000.0, 16000.0)   # границы полос эквалайзера: НЧ [0,8k), СЧ [8k,16k), ВЧ [16k,24k] Гц
GAINS_DB = (-6.0, 0.0, 6.0)      # усиление полос эквалайзера, дБ (НЧ, СЧ, ВЧ)
NOTCH_BW = 250.0           # ширина полосы подавления вокруг тональной помехи, Гц
FRAME = 1024               # длина кадра для спектрограммы
HOP = 256                  # шаг кадра для спектрограммы


# ================= Модуль синтеза тестового сигнала (Python) =================
def make_demo_signal(fs: int = FS, duration: float = DURATION,
                     tone_freq: float = TONE_FREQ) -> np.ndarray:
    """Демонстрационный сигнал: сумма гармоник с амплитудной модуляцией
    (имитация полезного сигнала) + белый шум + тональная помеха."""
    t = np.arange(int(fs * duration)) / fs
    useful = (np.sin(2 * np.pi * 220 * t)
              + 0.5 * np.sin(2 * np.pi * 330 * t)
              + 0.3 * np.sin(2 * np.pi * 440 * t)) * (0.7 + 0.3 * np.sin(2 * np.pi * 5 * t))
    useful *= 0.6
    noise = NOISE_AMP * np.random.default_rng(42).standard_normal(len(t))
    tone = TONE_AMP * np.sin(2 * np.pi * tone_freq * t)
    return useful + noise + tone


# ================= Чтение/запись WAV =================
def read_wav(path: str | Path) -> tuple[int, np.ndarray]:
    """Чтение WAV (PCM 8/16/32 бит, моно/стерео) -> (частота дискретизации, сигнал float64 в [-1, 1])."""
    with wave.open(str(path), "rb") as w:
        fs = w.getframerate()
        n_ch = w.getnchannels()
        width = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"Неподдержанный sampwidth={width}")
    if n_ch > 1:
        data = data.reshape(-1, n_ch).mean(axis=1)   # стерео -> моно
    return fs, data


def write_wav(path: str | Path, fs: int, x: np.ndarray) -> None:
    """Запись сигнала в WAV (16-бит PCM, моно) с нормализацией пика до 0,95."""
    x = np.asarray(x, dtype=np.float64)
    peak = np.max(np.abs(x))
    if peak > 0:
        x = x / peak * 0.95
    pcm = (x * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(pcm.tobytes())


# ================= Модуль анализа: спектр и спектрограмма =================
def fft_spectrum(x: np.ndarray) -> np.ndarray:
    """Полный спектр (комплексный) — используется для фильтрации и синтеза."""
    return np.fft.fft(x)


def one_sided_db(X: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Односторонний спектр в дБ по полному комплексному спектру X = fft(x):
    частоты 0..fs/2 и |X| в дБ."""
    n = len(X)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(X[: n // 2 + 1]) / n * 2.0
    mag[0] /= 2.0
    db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    return freqs, db


def spectrogram_db(x: np.ndarray, fs: int, frame: int = FRAME, hop: int = HOP):
    """Кратковременное преобразование Фурье (ручная реализация): время, частоты, S в дБ."""
    win = np.hanning(frame)
    n_frames = 1 + max(0, (len(x) - frame) // hop)
    times, freqs = [], np.fft.rfftfreq(frame, d=1.0 / fs)
    S = np.empty((len(freqs), n_frames))
    for i in range(n_frames):
        seg = x[i * hop:i * hop + frame] * win
        S[:, i] = np.abs(np.fft.rfft(seg))
    times = (np.arange(n_frames) * hop + frame / 2.0) / fs
    S_db = 20.0 * np.log10(np.maximum(S, 1e-12))
    return times, freqs, S_db


def plot_time(x: np.ndarray, fs: int, path: Path, title: str) -> None:
    t = np.arange(len(x)) / fs
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(t, x, lw=0.5)
    ax.set_xlabel("Время, с"); ax.set_ylabel("Амплитуда")
    ax.set_title(title); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def plot_spectrum(X: np.ndarray, fs: int, path: Path, title: str,
                  marks: dict[float, str] | None = None) -> tuple[np.ndarray, np.ndarray]:
    freqs, db = one_sided_db(X, fs)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(freqs, db, lw=0.8)
    for f0, label in (marks or {}).items():
        ax.axvline(f0, color="red", ls="--", lw=1)
        ax.annotate(label, (f0, ax.get_ylim()[1]), textcoords="offset points",
                    xytext=(4, -14), color="red", fontsize=9)
    ax.set_xlabel("Частота, Гц"); ax.set_ylabel("Уровень, дБ")
    ax.set_title(title); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
    return freqs, db


def plot_spectrogram(x: np.ndarray, fs: int, path: Path, title: str) -> None:
    times, freqs, S_db = spectrogram_db(x, fs)
    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.pcolormesh(times, freqs, S_db, shading="auto", cmap="viridis")
    ax.set_xlabel("Время, с"); ax.set_ylabel("Частота, Гц")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="Уровень, дБ")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


# ================= Модуль эквалайзера: 3 полосы + маска усилений =================
def equalizer_mask(n: int, fs: int,
                   edges: tuple[float, float] = BAND_EDGES,
                   gains_db: tuple[float, float, float] = GAINS_DB) -> np.ndarray:
    """Маска усиления по полной оси частот БПФ (обе половины спектра)."""
    freqs = np.fft.fftfreq(n, d=1.0 / fs)
    af = np.abs(freqs)
    gains = 10.0 ** (np.asarray(gains_db) / 20.0)
    mask = np.ones_like(af)
    mask[af < edges[0]] = gains[0]                    # НЧ
    mask[(af >= edges[0]) & (af < edges[1])] = gains[1]  # СЧ
    mask[af >= edges[1]] = gains[2]                    # ВЧ
    return mask


def apply_equalizer(X: np.ndarray, fs: int,
                    edges: tuple[float, float] = BAND_EDGES,
                    gains_db: tuple[float, float, float] = GAINS_DB) -> np.ndarray:
    """Регулировка усиления (ослабления) частотных диапазонов: X * маска."""
    mask = equalizer_mask(len(X), fs, edges, gains_db)
    return X * mask


# ================= Модуль подавителя помех: обнуление полосы тонального шума =================
def detect_tone(X: np.ndarray, fs: int, fmin: float = 500.0) -> float:
    """Автоопределение частоты тональной помехи — самый высокий пик спектра выше fmin."""
    freqs, db = one_sided_db(X, fs)
    band = freqs >= fmin
    return float(freqs[band][np.argmax(db[band])])


def suppress_tonal_noise(X: np.ndarray, fs: int,
                         tone_freq: float | None = None,
                         bw: float = NOTCH_BW) -> tuple[np.ndarray, float]:
    """Подавление тональной помехи: спектральные составляющие в полосе
    [tone-bw/2, tone+bw/2] (с обеих сторон спектра) умножаются на 0."""
    if tone_freq is None:
        tone_freq = detect_tone(X, fs)
    freqs = np.fft.fftfreq(len(X), d=1.0 / fs)
    notch = (np.abs(freqs - tone_freq) <= bw / 2.0) | (np.abs(freqs + tone_freq) <= bw / 2.0)
    X_clean = X.copy()
    X_clean[notch] = 0.0
    return X_clean, float(tone_freq)


# ================= Модуль синтеза: ОБПФ -> WAV =================
def synthesize(X: np.ndarray) -> np.ndarray:
    """Восстановление сигнала из спектра обратным БПФ."""
    return np.fft.ifft(X).real


def level_at(X: np.ndarray, fs: int, f0: float) -> float:
    """Уровень (дБ) спектральной составляющей на частоте f0 — для контроля подавления."""
    freqs, db = one_sided_db(X, fs)
    k = int(np.argmin(np.abs(freqs - f0)))
    return float(db[k])


# ================= Основной конвейер =================
def main() -> None:
    ap = argparse.ArgumentParser(description="КР №2: эквалайзер с подавлением тональной помехи (WAV)")
    ap.add_argument("--input", type=str, default=None, help="входной WAV (если не задан — генерируется демо-сигнал)")
    ap.add_argument("--outdir", type=str, default=str(Path(__file__).resolve().parent / "output"),
                    help="каталог для результатов (по умолчанию ./output рядом со скриптом)")
    ap.add_argument("--tone", type=float, default=None, help="частота тональной помехи, Гц (по умолчанию автоопределение)")
    ap.add_argument("--bw", type=float, default=NOTCH_BW, help="ширина полосы подавления, Гц")
    ap.add_argument("--gains", type=str, default=",".join(str(g) for g in GAINS_DB),
                    help="усиление полос эквалайзера в дБ через запятую: НЧ,СЧ,ВЧ")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    gains_db = tuple(float(g) for g in args.gains.split(","))
    assert len(gains_db) == 3, "ожидается 3 значения усиления: НЧ,СЧ,ВЧ"

    # ---- входной сигнал ----
    if args.input:
        fs, x = read_wav(args.input)
        print(f"Входной файл: {args.input}  (fs = {fs} Гц, {len(x)} отсчётов, {len(x)/fs:.2f} с)")
        in_wav = outdir / "input.wav"
        write_wav(in_wav, fs, x)
    else:
        fs = FS
        x = make_demo_signal(fs, DURATION, TONE_FREQ)
        in_wav = outdir / "input_noisy.wav"
        write_wav(in_wav, fs, x)
        print(f"Входной WAV не задан — сгенерирован демо-сигнал: {in_wav} "
              f"(fs = {fs} Гц, {len(x)} отсчётов, тональная помеха {TONE_FREQ:.0f} Гц)")

    # ---- 1. Модуль анализа: разложение в спектр + спектрограмма ----
    X = fft_spectrum(x)
    freqs, db_in = one_sided_db(X, fs)
    tone_detected = detect_tone(X, fs)
    plot_time(x, fs, outdir / "1_input_time.png", "Модуль анализа. Осциллограмма входного сигнала")
    plot_spectrum(X, fs, outdir / "2_input_spectrum.png", "Модуль анализа. Спектр входного сигнала (с тональной помехой)",
                  marks={tone_detected: f"помеха {tone_detected:.0f} Гц"})
    plot_spectrogram(x, fs, outdir / "3_input_spectrogram.png", "Модуль анализа. Спектрограмма входного сигнала")
    print(f"[Анализ] спектр и спектрограмма построены; обнаружен пик помехи на {tone_detected:.1f} Гц "
          f"({level_at(X, fs, tone_detected):.1f} дБ)")

    # ---- 2. Модуль эквалайзера: 3 полосы, регулировка усиления ----
    X_eq = apply_equalizer(X, fs, BAND_EDGES, gains_db)
    plot_spectrum(X_eq, fs, outdir / "4_after_equalizer_spectrum.png",
                  f"Модуль эквалайзера. Спектр после регулировки полос "
                  f"(НЧ {gains_db[0]:+.0f} дБ / СЧ {gains_db[1]:+.0f} дБ / ВЧ {gains_db[2]:+.0f} дБ, границы {BAND_EDGES[0]:.0f}/{BAND_EDGES[1]:.0f} Гц)")
    print(f"[Эквалайзер] полосы: НЧ [0,{BAND_EDGES[0]:.0f}) Гц — {gains_db[0]:+.1f} дБ, "
          f"СЧ [{BAND_EDGES[0]:.0f},{BAND_EDGES[1]:.0f}) Гц — {gains_db[1]:+.1f} дБ, "
          f"ВЧ [{BAND_EDGES[1]:.0f},{fs/2:.0f}] Гц — {gains_db[2]:+.1f} дБ")

    # ---- 3. Модуль подавителя помех: обнуление полосы тонального сигнала ----
    tone = args.tone if args.tone is not None else tone_detected
    X_clean, tone = suppress_tonal_noise(X_eq, fs, tone_freq=tone, bw=args.bw)
    plot_spectrum(X_clean, fs, outdir / "5_after_notch_spectrum.png",
                  f"Модуль подавителя помех. Спектр после подавления тональной помехи "
                  f"{tone:.0f} Гц (полоса ±{args.bw/2:.0f} Гц обнулена)",
                  marks={tone: f"помеха {tone:.0f} Гц"})
    before = level_at(X_eq, fs, tone)
    after = level_at(X_clean, fs, tone)
    print(f"[Подавитель] тональная помеха {tone:.1f} Гц: уровень {before:.1f} дБ -> {after:.1f} дБ "
          f"(подавление {before - after:.1f} дБ)")

    # ---- 4. Модуль синтеза: ОБПФ -> WAV ----
    y = synthesize(X_clean)
    out_wav = outdir / "output_clean.wav"
    write_wav(out_wav, fs, y)
    plot_time(y, fs, outdir / "6_output_time.png", "Модуль синтеза. Осциллограмма результирующего сигнала")
    plot_spectrum(fft_spectrum(y), fs, outdir / "7_output_spectrum.png", "Модуль синтеза. Спектр результирующего сигнала")
    plot_spectrogram(y, fs, outdir / "8_output_spectrogram.png", "Модуль синтеза. Спектрограмма результирующего сигнала")

    rms_in = 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12)
    rms_out = 20 * np.log10(np.sqrt(np.mean(y**2)) + 1e-12)
    print(f"[Синтез] результирующий WAV: {out_wav} (fs = {fs} Гц, {len(y)} отсчётов)")
    print(f"RMS входного сигнала {rms_in:.1f} дБ, выходного {rms_out:.1f} дБ")
    print("\nГотово. Файлы в каталоге", outdir)


if __name__ == "__main__":
    main()
