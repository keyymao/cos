# -*- coding: utf-8 -*-
"""
==========================================================================
 КОНТРОЛЬНАЯ РАБОТА №2 (ЦОС)
 Система цифровой обработки аудиосигнала.  Вариант 10.
--------------------------------------------------------------------------
 Программа реализует все четыре функции задания:
   1) разложение сигнала в спектр и построение спектрограммы;
   2) регулировку усиления/ослабления диапазонов (эквалайзер);
   3) подавление помехи в виде тонального сигнала (режекция);
   4) синтез результирующего сигнала в формате WAV.

 Запуск:
   python kr2_signal_system.py --in kr2_input.wav --out kr2_output.wav
   (без аргументов обрабатывается kr2_input.wav рядом со скриптом)

 Зависимости: numpy, scipy, matplotlib
==========================================================================
"""
import argparse
import os

import numpy as np
from scipy import signal
from scipy.io import wavfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 11, "font.family": "DejaVu Sans",
                     "axes.grid": True, "grid.alpha": .3, "figure.dpi": 150})

# ------------------------- ПАРАМЕТРЫ СИСТЕМЫ -----------------------------
# Полосы эквалайзера: (f нижн., f верхн., усиление в дБ)
EQ_BANDS = [
    (0.0,    300.0,   +6.0),   # низкие частоты  - подъём +6 дБ
    (300.0,  3000.0,   0.0),   # средние         - без изменений
    (3000.0, 8000.0,  -6.0),   # высокие         - спад -6 дБ
]
EQ_TRANSITION_HZ = 200.0     # ширина перехода между полосами, Гц
NOTCH_Q = 35.0               # добротность режекторного фильтра
TONE_SEARCH_BAND = (60.0, 0.45)   # поиск помехи: 60 Гц ... 0.45*fs
TONE_EXCESS_DB = 12.0        # требуемое превышение над "подложкой"
STFT_NPERSEG = 1024          # длина окна спектрограммы, отсчётов
STFT_OVERLAP = 768           # перекрытие окон (75 %)

# ============================ 1. ВВОД / ВЫВОД ============================
def read_wav(path):
    """Чтение WAV -> (fs, x); x - нормированный моно-сигнал в [-1, 1]."""
    fs, data = wavfile.read(path)
    if data.dtype == np.uint8:                 # 8-битный беззнаковый
        x = (data.astype(np.float64) - 128.0) / 128.0
    elif data.dtype == np.int16:
        x = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        x = data.astype(np.float64) / 2147483648.0
    else:                                      # float32 / float64
        x = data.astype(np.float64)
    if x.ndim > 1:                             # стерео -> моно
        x = x.mean(axis=1)
    return fs, x


def write_wav(path, fs, x):
    """Синтез результата в WAV (PCM 16 бит), защита от перегрузки."""
    peak = np.max(np.abs(x))
    if peak > 0.999:
        x = x * 0.999 / peak
    wavfile.write(path, fs, np.round(x * 32767).astype(np.int16))

# ====================== 2. СПЕКТР И СПЕКТРОГРАММА ======================
def amplitude_spectrum(x, fs, win="hann"):
    """Односторонний амплитудный спектр (в дБ), весовое окно.

    X(k) = sum_n x(n) w(n) e^{-j 2 pi k n / N},
    w(n) = 0.5 [1 - cos(2 pi n / (N-1))]  (окно Ханна),
    A(k) = 2 |X(k)| / sum_n w(n),  A_dB = 20 lg A(k).
    """
    N = x.size
    w = signal.get_window(win, N, fftbins=True)
    X = np.fft.rfft(x * w)
    f = np.fft.rfftfreq(N, 1.0 / fs)
    # нормировка на усиление окна -> амплитуда синусоиды
    A = 2.0 * np.abs(X) / np.sum(w)
    AdB = 20 * np.log10(np.maximum(A, 1e-12))
    return f, A, AdB


def spectrogram(x, fs, nperseg=STFT_NPERSEG, noverlap=STFT_OVERLAP):
    """КВПФ (STFT): f, t, |S| в дБ."""
    f, t, S = signal.spectrogram(x, fs, window="hann", nperseg=nperseg,
                                 noverlap=noverlap, scaling="spectrum",
                                 mode="magnitude")
    return f, t, 20 * np.log10(np.maximum(S, 1e-10))


def welch_db(x, fs, nper=2048):
    """Сглаженный спектр мощности (метод Уэлча) в дБ."""
    f, P = signal.welch(x, fs, window="hann", nperseg=nper,
                        noverlap=nper // 2, scaling="spectrum")
    return f, 10 * np.log10(np.maximum(P, 1e-14))

# ==================== 3. ЭКВАЛАЙЗЕР (АЧХ ПОЛОС) =========================
def eq_gain_db(freqs, bands=EQ_BANDS, transition=EQ_TRANSITION_HZ):
    """Кривая усиления эквалайзера (дБ) для массива частот.

    Каждая полоса задаётся усилением внутри [f1, f2] и плавными
    (косинусными) фронтами шириной transition по краям. Соседние
    полосы "перекрещиваются" так, что сумма их весовых функций
    равна 1, поэтому кривая усиления непрерывна.
    """
    freqs = np.asarray(freqs, dtype=float)
    g_db = np.zeros_like(freqs)
    T = float(transition)
    last = len(bands) - 1
    for i, (f1, f2, g) in enumerate(bands):
        w = np.zeros_like(freqs)
        w[(freqs >= f1) & (freqs <= f2)] = 1.0
        if f1 > 0:                          # нарастающий фронт снизу
            m = (freqs >= f1 - T) & (freqs < f1)
            w[m] = 0.5 - 0.5 * np.cos(np.pi * (freqs[m] - (f1 - T)) / T)
        if i < last:                        # спадающий фронт сверху
            m = (freqs > f2) & (freqs <= f2 + T)
            w[m] = 0.5 + 0.5 * np.cos(np.pi * (freqs[m] - f2) / T)
        g_db += g * w
    return g_db


def apply_eq(x, fs, bands=EQ_BANDS):
    """Эквалайзер с нулевой фазой: умножение спектра на маску.

    Y(k) = X(k) G(k),  G(f) = 10^{g(f)/20},  y(n) = ОДПФ{Y(k)}.
    """
    N = x.size
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(N, 1.0 / fs)
    g = 10 ** (eq_gain_db(f, bands) / 20.0)
    return np.fft.irfft(X * g, n=N)

# ========== 4. ОБНАРУЖЕНИЕ И ПОДАВЛЕНИЕ ТОНАЛЬНОЙ ПОМЕХИ ============
def detect_tone(x, fs, band=TONE_SEARCH_BAND, excess_db=TONE_EXCESS_DB):
    """Поиск тональной помехи: максимум спектра над локальной медианой."""
    f, A, AdB = amplitude_spectrum(x, fs)
    f1, f2 = band[0], band[1] * fs
    idx = np.nonzero((f >= f1) & (f <= f2))[0]
    i0 = idx[np.argmax(AdB[idx])]
    # локальная "подложка": медиана спектра в окне +-150 Гц
    k = max(int(150.0 / (fs / x.size)), 5)
    base = np.median(AdB[max(i0 - k, 0):i0 + k + 1])
    excess = AdB[i0] - base
    return f[i0], AdB[i0], base, excess, (excess >= excess_db)


def notch_filter(x, fs, f0, Q=NOTCH_Q):
    """Режекторный БИХ-фильтр 2-го порядка + filtfilt (два прохода)."""
    b, a = signal.iirnotch(f0, Q, fs)
    return signal.filtfilt(b, a, x), (b, a)


def suppress_tone(x, fs, harmonics=2, Q=NOTCH_Q, verbose=True):
    """Обнаружение и подавление помехи и её гармоник."""
    f0, lvl, base, excess, found = detect_tone(x, fs)
    if verbose:
        print(f"  обнаружена помеха: f0 = {f0:.1f} Гц, уровень {lvl:.1f} дБ "
              f"(подложка {base:.1f} дБ, превышение {excess:.1f} дБ)")
    y, freqs = x, []
    if found:
        for h in range(1, harmonics + 1):
            fh = h * f0
            if fh < 0.45 * fs:
                y, _ = notch_filter(y, fs, fh, Q)
                freqs.append(fh)
                if verbose:
                    print(f"  режекторный фильтр: f = {fh:.1f} Гц, Q = {Q}")
    return y, freqs, (f0, lvl, base, excess, found)

# ============================== 5. ГРАФИКИ ===============================
def plot_wave(fs, x, x_eq, y, out_png):
    t = np.arange(x.size) / fs
    fig, axs = plt.subplots(3, 1, figsize=(9, 6.4), sharex=True)
    for ax, sig, ttl in zip(axs, [x, x_eq, y],
                            ["входной сигнал + тональная помеха",
                             "после эквалайзера (усиление полос)",
                             "на выходе (помеха подавлена)"]):
        ax.plot(t, sig, lw=.5, color="C0")
        ax.set_ylabel("s(t)")
        ax.set_title(ttl, fontsize=11)
    axs[-1].set_xlabel("t, c")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_spectrum(x, fs, out_png):
    """Обзорный спектр входного сигнала + увеличение у помехи."""
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.9),
                            gridspec_kw={"width_ratios": [1.35, 1]})
    f, PdB = welch_db(x, fs)
    axs[0].plot(f, PdB, "C0", lw=.9)
    axs[0].set_xlim(0, fs / 2)
    axs[0].set_ylim(-120, -10)
    axs[0].set_xlabel("f, Гц")
    axs[0].set_ylabel("S(f), дБ")
    axs[0].set_title("Спектр мощности входа (Уэлч, N=2048)", fontsize=11)
    for fh in (1500, 3000):
        axs[0].annotate(f"{fh} Гц", (fh, -12), fontsize=8,
                        rotation=90, ha="right", va="top")
    fa, A, AdB = amplitude_spectrum(x, fs)
    m = (fa > 1150) & (fa < 1850)
    axs[1].plot(fa[m], AdB[m], "C3", lw=.9)
    axs[1].set_xlabel("f, Гц")
    axs[1].set_ylabel("A(f), дБ")
    axs[1].set_ylim(-120, -5)
    axs[1].set_title("Увеличение: помеха 1500 Гц", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_spectra_compare(fs, x, x_eq, y, f0, out_png):
    """Спектры до/после обработки + увеличение у помехи."""
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.9),
                            gridspec_kw={"width_ratios": [1.2, 1]})
    for sig, c, lab in [(x, "C0", "входной сигнал"),
                        (x_eq, "C1", "после эквалайзера"),
                        (y, "C3", "выход (после режекции)")]:
        f, PdB = welch_db(sig, fs)
        axs[0].plot(f, PdB, c, lw=.9, label=lab)
    axs[0].set_xlim(0, fs / 2)
    axs[0].set_ylim(-120, -10)
    axs[0].set_xlabel("f, Гц")
    axs[0].set_ylabel("S(f), дБ")
    axs[0].set_title("Спектры мощности до/после обработки", fontsize=11)
    axs[0].legend(fontsize=8)
    for sig, c, lab in [(x_eq, "C1", "после экв."), (y, "C3", "выход")]:
        fa, A, AdB = amplitude_spectrum(sig, fs)
        m = (fa > f0 - 150) & (fa < f0 + 150)
        axs[1].plot(fa[m], A[m], c, lw=.9, label=lab)
    axs[1].set_ylim(-0.01, 0.34)
    axs[1].set_xlabel("f, Гц")
    axs[1].set_ylabel("A(f)")
    axs[1].set_title(f"Режекция: полоса {f0-150:.0f}...{f0+150:.0f} Гц",
                     fontsize=11)
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_specgram(sig, fs, out_png, title="спектрограмма сигнала"):
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ff, tt, SdB = spectrogram(sig, fs)
    im = ax.pcolormesh(tt, ff, SdB, shading="nearest", cmap="inferno",
                       vmin=-110, vmax=-20)
    ax.set_xlabel("t, c")
    ax.set_ylabel("f, Гц")
    ax.set_title(title, fontsize=11)
    fig.colorbar(im, ax=ax, pad=.01, label="дБ")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_eq_curve(fs, out_png):
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    fq = np.linspace(0, fs / 2, 3000)
    ax.plot(fq, eq_gain_db(fq), "C2", lw=1.9)
    ax.set_title("АЧХ эквалайзера (кривая усиления)", fontsize=11)
    ax.set_xlabel("f, Гц")
    ax.set_ylabel("усиление, дБ")
    ax.set_ylim(-10, 10)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_notch_curve(fs, f0, out_png):
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    b, a = signal.iirnotch(f0, NOTCH_Q, fs)
    w, h = signal.freqz(b, a, worN=8192, fs=fs)
    hdB = 20 * np.log10(np.maximum(np.abs(h), 1e-12))
    ax.plot(w, hdB, "C3", lw=1.7, label="один проход: H(z)")
    ax.plot(w, 2 * hdB, "C0", lw=1.2, ls="--", label="два прохода (filtfilt)")
    ax.set_xlim(max(0, f0 - 300), f0 + 300)
    ax.set_ylim(-90, 5)
    ax.set_title(f"АЧХ режекторного фильтра: f0 = {f0:.0f} Гц, "
                 f"Q = {NOTCH_Q:g}", fontsize=11)
    ax.set_xlabel("f, Гц")
    ax.set_ylabel("дБ")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)

# =============================== 6. МЕТРИКИ ==============================
def tone_level_db(x, fs, f0):
    """Уровень (дБ) составляющей на частоте f0 в спектре."""
    f, A, AdB = amplitude_spectrum(x, fs)
    m = (f > f0 - 6) & (f < f0 + 6)
    return float(AdB[m].max()) if np.any(m) else np.nan


def snr_estimate_db(x, fs, f0):
    """Оценка ОСШ: мощность вне полосы помехи / мощность в ней."""
    f, A, AdB = amplitude_spectrum(x, fs)
    m = ~((f > f0 - 25) & (f < f0 + 25))
    Ps = np.sum(A[m] ** 2)
    Pt = np.sum(A[~m] ** 2)
    return float(10 * np.log10(Ps / max(Pt, 1e-20)))


def band_level_db(x, fs, f1, f2, nper=2048):
    """Уровень (дБ) мощности сигнала в полосе [f1, f2] (метод Уэлча)."""
    f, P = signal.welch(x, fs=fs, window="hann", nperseg=nper,
                        noverlap=nper // 2, scaling="spectrum")
    m = (f >= f1) & (f <= min(f2, fs / 2))
    return float(10 * np.log10(max(np.sum(P[m]), 1e-20)))

# ================================ MAIN ===================================
def main():
    ap = argparse.ArgumentParser(
        description="ЦОС: спектр, эквалайзер, режекция тона, WAV")
    ap.add_argument("--in", dest="inp", default="kr2_input.wav")
    ap.add_argument("--out", dest="out", default="kr2_output.wav")
    args = ap.parse_args()

    print("=" * 70)
    print(" КР2, вариант 10. Обработка аудиосигнала")
    print("=" * 70)
    fs, x = read_wav(args.inp)
    print(f"1) Входной файл: {args.inp}")
    print(f"   fs = {fs} Гц, длительность = {x.size/fs:.3f} с, "
          f"отсчётов = {x.size}")

    # --- Задание 1: спектр и спектрограмма
    f, A, AdB = amplitude_spectrum(x, fs)
    print(f"2) Спектр: N = {x.size}, df = {fs/x.size:.3f} Гц, максимум "
          f"на {f[np.argmax(A)]:.1f} Гц ({AdB.max():.1f} дБ)")
    print("   спектрограмма: окно 1024 отсчёта, перекрытие 75 %")

    # --- Задание 2: усиление частотных диапазонов
    print("3) Эквалайзер, полосы (Гц, дБ):", EQ_BANDS)
    print("   полоса, Гц     задано  до, дБ  после, дБ  факт, дБ")
    x_eq = apply_eq(x, fs, EQ_BANDS)
    for f1, f2, g in EQ_BANDS:
        l1 = band_level_db(x, fs, f1, f2)
        l2 = band_level_db(x_eq, fs, f1, f2)
        print(f"   {f1:5.0f}...{f2:5.0f}  {g:+7.1f} {l1:8.2f} {l2:9.2f} "
              f"{l2-l1:+9.2f}")

    # --- Задание 3: подавление тональной помехи
    y, freq_det, info = suppress_tone(x_eq, fs)

    # --- Задание 4: синтез WAV
    write_wav(args.out, fs, y)
    print(f"4) Результат записан в {args.out} (PCM 16 бит, {fs} Гц)")

    # --- оценка качества подавления
    if freq_det:
        f0 = freq_det[0]
        before, after = tone_level_db(x_eq, fs, f0), tone_level_db(y, fs, f0)
        print(f"   уровень помехи на {f0:.1f} Гц: до {before:.1f} дБ -> "
              f"после {after:.1f} дБ (подавление {before-after:.1f} дБ)")
        print(f"   оценка ОСШ вне полосы помехи: "
              f"{snr_estimate_db(x_eq, fs, f0):.1f} -> "
              f"{snr_estimate_db(y, fs, f0):.1f} дБ")

    # --- графики
    base = os.path.splitext(args.out)[0]
    plot_wave(fs, x, x_eq, y, base + "_1_wave.png")
    plot_spectrum(x, fs, base + "_2_spectrum.png")
    plot_specgram(x, fs, base + "_3_specgram_in.png",
                  "спектрограмма входного сигнала")
    plot_specgram(y, fs, base + "_4_specgram_out.png",
                  "спектрограмма выходного сигнала")
    plot_eq_curve(fs, base + "_5_eq_curve.png")
    if freq_det:
        plot_notch_curve(fs, freq_det[0], base + "_6_notch_curve.png")
        plot_spectra_compare(fs, x, x_eq, y, freq_det[0],
                             base + "_7_spectra_compare.png")
    print("Графики сохранены: *_1_wave, *_2_spectrum, *_3_specgram_in,")
    print("                   *_4_specgram_out, *_5_eq_curve,")
    print("                   *_6_notch_curve, *_7_spectra_compare (.png)")
    print("=" * 70)


if __name__ == "__main__":
    main()
