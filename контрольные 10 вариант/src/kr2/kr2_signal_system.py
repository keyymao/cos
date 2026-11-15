# -*- coding: utf-8 -*-
"""
КОНТРОЛЬНАЯ РАБОТА №2 по ЦОС, вариант 10.
Система обработки аудиосигнала:
 
    1) разложение сигнала в спектр и построение спектрограммы;
    2) регулировка усиления (ослабления) частотных диапазонов — эквалайзер;
    3) подавление тональной помехи режекторным БИХ-фильтром;
    4) синтез результирующего сигнала в формате WAV.
 
Запуск:      python3 kr2_signal_system.py
             python3 kr2_signal_system.py --in kr2_input.wav --out kr2_output.wav
Результат:   kr2_output.wav + рисунки в figures/, протокол в консоль и
             kr2_results.json.
"""
from __future__ import annotations
 
import argparse
import json
from pathlib import Path
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile
 
HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 11, "figure.dpi": 150, "font.family": "DejaVu Sans",
                     "axes.grid": True, "grid.alpha": 0.3, "axes.unicode_minus": False})
 
# ------------------------- параметры системы ------------------------------
EQ_BANDS = [(0.0, 1000.0, +6.0),        # НЧ: подъём +6 дБ
            (1000.0, 3000.0, 0.0),      # СЧ: без изменений
            (3000.0, 8000.0, -6.0)]     # ВЧ: спад −6 дБ
EQ_TRANSITION_HZ = 200.0                # плавный переход между полосами
NOTCH_Q = 35.0                          # добротность режекторного фильтра
TONE_SEARCH_BAND = (100.0, 0.45)        # поиск помехи: 100 Гц … 0,45·fд
TONE_EXCESS_DB = 12.0                   # требуемое превышение над «подложкой»
STFT_NPERSEG = 512                      # окно спектрограммы
STFT_OVERLAP = 384                      # перекрытие 75 %
 
C_BLUE, C_RED, C_GREEN = "#2f6fdb", "#d62728", "#2ca02c"
 
 
# ============================ 1. ввод / вывод =============================
def read_wav(path: str | Path):
    """Чтение WAV → (fд, x); x — нормированный моно-сигнал."""
    fs, data = wavfile.read(str(path))
    if data.dtype == np.uint8:
        x = (data.astype(np.float64) - 128.0) / 128.0
    elif data.dtype == np.int16:
        x = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        x = data.astype(np.float64) / 2147483648.0
    else:
        x = data.astype(np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return int(fs), x
 
 
def write_wav(path: str | Path, fs: int, x: np.ndarray) -> dict:
    """Запись WAV (PCM 16 бит) с защитой от перегрузки."""
    peak = float(np.max(np.abs(x)))
    scale = 1.0
    if peak > 0.999:
        scale = 0.999 / peak
        x = x * scale
    pcm = np.round(x * 32767).astype(np.int16)
    wavfile.write(str(path), fs, pcm)
    return {"peak_before": peak, "scale": scale, "bytes": int(Path(path).stat().st_size),
            "samples": int(pcm.size), "fs": fs}
 
 
# ======================= 2. спектр и спектрограмма ========================
def amplitude_spectrum(x: np.ndarray, fs: int, win: str = "hann"):
    """Односторонний амплитудный спектр с весовым окном.
 
    A(k) = 2·|X(k)| / Σw(n),  X(k) = Σ x(n)w(n)e^(−j2πkn/N).
    """
    n = x.size
    w = signal.get_window(win, n, fftbins=True)
    X = np.fft.rfft(x * w)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    a = 2.0 * np.abs(X) / np.sum(w)
    return f, a, 20 * np.log10(np.maximum(a, 1e-12))
 
 
def stft_db(x: np.ndarray, fs: int, nperseg: int = STFT_NPERSEG, noverlap: int = STFT_OVERLAP):
    """КВПФ: f, t, |S| в дБ."""
    f, t, S = signal.spectrogram(x, fs, window="hann", nperseg=nperseg,
                                 noverlap=noverlap, scaling="spectrum", mode="magnitude")
    return f, t, 20 * np.log10(np.maximum(S, 1e-10))
 
 
# ========================== 3. эквалайзер =================================
def eq_gain_db(freqs: np.ndarray, bands=EQ_BANDS, transition: float = EQ_TRANSITION_HZ):
    """Кривая усиления g(f) в дБ с косинусными переходами между полосами."""
    freqs = np.asarray(freqs, dtype=float)
    g = np.full_like(freqs, bands[-1][2])
    for i, (f1, f2, gdb) in enumerate(bands):
        top = freqs <= f2 if i == len(bands) - 1 else freqs < f2
        g = np.where((freqs >= f1) & top, gdb, g)
    g = np.where(freqs < bands[0][0], bands[0][2], g)
    # сглаживание ступенек косинусным переходом
    for (f1, f2, g1), (f3, f4, g2) in zip(bands[:-1], bands[1:]):
        edge = f2
        m = (freqs > edge - transition / 2) & (freqs < edge + transition / 2)
        u = (freqs[m] - (edge - transition / 2)) / transition
        g[m] = g1 + (g2 - g1) * 0.5 * (1 - np.cos(np.pi * u))
    return g
 
 
def apply_eq(x: np.ndarray, fs: int, bands=EQ_BANDS) -> np.ndarray:
    """Эквалайзер в частотной области: обнуление фазы, симметричная маска."""
    n = x.size
    f = np.fft.rfftfreq(n, 1.0 / fs)
    g = 10 ** (eq_gain_db(f, bands) / 20.0)
    spec = np.fft.rfft(x) * g
    return np.fft.irfft(spec, n=n)
 
 
# ====================== 4. обнаружение и подавление помехи ================
def detect_tone(x: np.ndarray, fs: int, band=TONE_SEARCH_BAND, excess_db=TONE_EXCESS_DB):
    """Поиск тональной помехи: максимум с превышением над локальной медианой."""
    f, a, _ = amplitude_spectrum(x, fs)
    lo, hi = band[0], band[1] * fs
    m = (f >= lo) & (f <= hi)
    idx = np.flatnonzero(m)
    k = int(idx[np.argmax(a[m])])
    half = max(int(round(150.0 / (f[1] - f[0]))), 1)
    left = np.arange(max(k - half, 0), k - 20)
    right = np.arange(k + 20, min(k + half, f.size))
    neigh = np.concatenate([left, right])
    floor = float(np.median(a[neigh] ** 2))
    level = float(a[k] ** 2)
    excess = 10 * np.log10(level / floor) if floor > 0 else np.inf
    return {"f0": float(f[k]), "index": k, "level_db": float(20 * np.log10(a[k])),
            "floor_db": float(10 * np.log10(floor)), "excess_db": float(excess),
            "detected": bool(excess >= excess_db)}
 
 
def notch_filter(fs: int, f0: float, q: float = NOTCH_Q):
    """Режекторный БИХ-фильтр 2-го порядка (нуль на единичной окружности)."""
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * q)
    b = np.array([1.0, -2 * np.cos(w0), 1.0]) / (1 + alpha)
    a = np.array([1.0, -2 * np.cos(w0) / (1 + alpha), (1 - alpha) / (1 + alpha)])
    return b, a
 
 
def suppress_tones(x: np.ndarray, fs: int, count: int = 2, q: float = NOTCH_Q):
    """Последовательное подавление помехи и её гармоник режекторами."""
    y = x.copy()
    notes, params = [], []
    for _ in range(count):
        d = detect_tone(y, fs)
        if not d["detected"]:
            notes.append(d["f0"])
            continue
        b, a = notch_filter(fs, d["f0"], q)
        y = signal.filtfilt(b, a, y)        # прямой и обратный проход: фаза 0
        after = tone_level_db(y, fs, d["f0"])
        params.append({"f0": d["f0"], "b": b.tolist(), "a": a.tolist(),
                       "level_before_db": d["level_db"], "level_after_db": after,
                       "suppression_db": d["level_db"] - after,
                       "floor_db": d["floor_db"], "excess_db": d["excess_db"]})
    return y, params
 
 
# ============================ измерения ===================================
def tone_level_db(x: np.ndarray, fs: int, f0: float) -> float:
    """Уровень узкополосной составляющей f0 (дБ) по спектру с окном Ханна."""
    n = x.size
    w = signal.get_window("hann", n)
    spec = np.abs(np.fft.rfft(x * w)) * 2 / np.sum(w)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    k = int(np.argmin(np.abs(f - f0)))
    k = int(np.argmax(spec[max(k - 3, 0):k + 4]) + max(k - 3, 0))
    return float(20 * np.log10(max(spec[k], 1e-12)))
 
 
def gain_at(x_in: np.ndarray, x_out: np.ndarray, fs: int, f: float) -> float:
    """Измеренный коэффициент передачи на частоте f (дБ) по отношению спектров."""
    n = min(x_in.size, x_out.size)
    w = signal.get_window("hann", n)
    f_in = np.abs(np.fft.rfft(x_in[:n] * w))
    f_out = np.abs(np.fft.rfft(x_out[:n] * w))
    fr = np.fft.rfftfreq(n, 1.0 / fs)
    k = int(np.argmin(np.abs(fr - f)))
    band = slice(max(k - 2, 0), k + 3)
    ratio = np.sum(f_out[band]) / max(np.sum(f_in[band]), 1e-20)
    return float(20 * np.log10(ratio))
 
 
def band_level_db(x: np.ndarray, fs: int, f1: float, f2: float, nper: int = 2048) -> float:
    """Уровень мощности в полосе f1…f2 (дБ, метод Уэлча)."""
    f, p = signal.welch(x, fs, window="hann", nperseg=nper, noverlap=nper // 2)
    m = (f >= f1) & (f <= f2)
    return float(10 * np.log10(np.sum(p[m]) + 1e-20))
 
 
def snr_out_of_tone_db(x: np.ndarray, fs: int, f0: float, half: float = 200.0) -> float:
    """Отношение мощности вне полосы помехи к мощности в полосе ±half (дБ)."""
    f, p = signal.welch(x, fs, nperseg=4096, noverlap=2048)
    tone = (f >= f0 - half) & (f <= f0 + half)
    speech = (f >= 60) & (f <= 0.9 * fs / 2) & ~tone
    return float(10 * np.log10(np.sum(p[speech]) / (np.sum(p[tone]) + 1e-20)))
 
 
# ============================== рисунки ===================================
def _save(fig, name: str):
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
 
 
def plot_wave(fs: int, x_in, x_eq, y, name="fig2_1_wave.png"):
    t = np.arange(x_in.size) / fs
    fig, ax = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
    for a, sig, lab in zip(ax, (x_in, x_eq, y),
                           ("входной сигнал", "после эквалайзера", "на выходе системы")):
        a.plot(t, sig, lw=0.5, color=C_BLUE)
        a.set_ylabel("амплитуда")
        a.set_title(lab, fontsize=10)
    ax[-1].set_xlabel("время, с")
    ax[0].set_title("Осциллограммы: входной сигнал (вверху), после эквалайзера, на выходе системы")
    _save(fig, name)
 
 
def plot_spectrum(fs: int, x, f0, name="fig1_1_spectrum.png"):
    f, a, adb = amplitude_spectrum(x, fs)
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2))
    ax[0].plot(f, adb, lw=0.7, color=C_BLUE)
    ax[0].set_xlim(0, 4000)
    ax[0].set_ylim(max(adb) - 90, max(adb) + 5)
    ax[0].set_xlabel("частота, Гц")
    ax[0].set_ylabel("амплитуда, дБ")
    ax[0].set_title("спектр в полосе 0…4 кГц")
    ax[1].plot(f, adb, lw=0.7, color=C_BLUE)
    ax[1].set_xlim(f0 - 400, f0 + 400)
    ax[1].set_ylim(max(adb) - 80, max(adb) + 5)
    ax[1].set_xlabel("частота, Гц")
    ax[1].set_title(f"увеличение вблизи помехи {f0:.0f} Гц")
    ax[1].axvline(f0, color=C_RED, ls="--", lw=1)
    _save(fig, name)
 
 
def plot_specgram(fs: int, x, title, name):
    f, t, db = stft_db(x, fs)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    vmax = np.percentile(db, 99.5)
    im = ax.imshow(db, origin="lower", aspect="auto", cmap="viridis",
                   extent=[t[0], t[-1], f[0], f[-1]], vmin=vmax - 80, vmax=vmax)
    fig.colorbar(im, ax=ax, label="|S|, дБ")
    ax.set_xlabel("время, с")
    ax.set_ylabel("частота, Гц")
    ax.set_title(title)
    ax.grid(False)
    _save(fig, name)
 
 
def plot_eq_curve(fs: int, name="fig2_2_eq_curve.png"):
    f = np.linspace(0, fs / 2, 4000)
    g = eq_gain_db(f)
    fig, ax = plt.subplots(figsize=(9.5, 3.9))
    ax.plot(f, g, lw=2, color=C_GREEN)
    ax.axhline(0, color="gray", lw=0.8)
    for f1, f2, gdb in EQ_BANDS:
        ax.axvspan(f1, min(f2, fs / 2), alpha=0.08)
        ax.text((f1 + min(f2, fs / 2)) / 2, gdb + 0.8, f"{gdb:+.0f} дБ",
                ha="center", fontsize=10)
    ax.set_xlabel("частота, Гц")
    ax.set_ylabel("усиление, дБ")
    ax.set_ylim(-8.5, 8.5)
    ax.set_title("Кривая усиления эквалайзера g(f)")
    _save(fig, name)
 
 
def plot_notch(fs: int, f0: float, q: float = NOTCH_Q, name="fig3_1_notch.png"):
    b, a = notch_filter(fs, f0, q)
    f = np.linspace(0, fs / 2, 8000)
    _, h1 = signal.freqz(b, a, worN=f, fs=fs)
    fig, ax = plt.subplots(figsize=(9.5, 3.9))
    ax.plot(f, 20 * np.log10(np.maximum(np.abs(h1), 1e-12)), lw=1.8, label="один проход H(z)")
    ax.plot(f, 40 * np.log10(np.maximum(np.abs(h1), 1e-12)), lw=1.4, ls="--",
            label="два прохода (filtfilt): |H|²")
    ax.axvline(f0, color=C_RED, ls=":", lw=1)
    ax.set_xlim(max(0, f0 - 500), f0 + 500)
    ax.set_ylim(-120, 5)
    ax.set_xlabel("частота, Гц")
    ax.set_ylabel("усиление, дБ")
    ax.set_title(f"АЧХ режекторного фильтра: f₀ = {f0:.0f} Гц, Q = {q:g}")
    ax.legend(loc="lower right")
    _save(fig, name)
 
 
def plot_compare(fs: int, x_in, y, f0, name="fig3_2_spectra.png"):
    f1, a1, d1 = amplitude_spectrum(x_in, fs)
    f2, a2, d2 = amplitude_spectrum(y, fs)
    top = max(d1.max(), d2.max()) + 5
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2))
    ax[0].plot(f1, d1, lw=0.7, color=C_BLUE, label="до обработки")
    ax[0].plot(f2, d2, lw=0.7, color=C_RED, alpha=0.8, label="после обработки")
    ax[0].set_xlim(0, 4000)
    ax[0].set_ylim(top - 95, top)
    ax[0].set_xlabel("частота, Гц")
    ax[0].set_ylabel("амплитуда, дБ")
    ax[0].set_title("спектры мощности до и после обработки")
    ax[0].legend(loc="upper right", fontsize=9)
    ax[1].plot(f1, d1, lw=0.8, color=C_BLUE, label="до")
    ax[1].plot(f2, d2, lw=0.8, color=C_RED, alpha=0.8, label="после")
    ax[1].set_xlim(f0 - 400, f0 + 400)
    ax[1].set_ylim(top - 110, top)
    ax[1].set_xlabel("частота, Гц")
    ax[1].set_title("увеличение в области помехи")
    ax[1].legend(loc="upper right", fontsize=9)
    _save(fig, name)
 
 
# =============================== главное ==================================
def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(
        description="КР2 ЦОС, вариант 10: анализ, эквалайзер, режекция, синтез")
    ap.add_argument("--in", dest="inp", default=str(HERE / "kr2_input.wav"))
    ap.add_argument("--out", dest="out", default=str(HERE / "kr2_output.wav"))
    args = ap.parse_args(argv)
 
    inp = Path(args.inp)
    if not inp.exists():
        here = HERE / "kr2_input.wav"
        if here.exists():
            inp = here
        else:
            import make_input_signal
            make_input_signal.main()
            inp = HERE / "kr2_input.wav"
 
    fs, x = read_wav(inp)
    print(f"вход: {inp.name}: fд = {fs} Гц, {x.size} отсчётов, {x.size / fs:.2f} с")
 
    # --- 1. анализ ---
    det = detect_tone(x, fs)
    plot_spectrum(fs, x, det["f0"])
    plot_specgram(fs, x, "Спектрограмма входного сигнала (окно 512, перекрытие 75 %)",
                  "fig1_2_specgram_in.png")
    plot_eq_curve(fs)
 
    # --- 2. эквалайзер ---
    x_eq = apply_eq(x, fs)
    eq_before = [band_level_db(x, fs, f1, min(f2, fs / 2)) for f1, f2, _ in EQ_BANDS]
    eq_after = [band_level_db(x_eq, fs, f1, min(f2, fs / 2)) for f1, f2, _ in EQ_BANDS]
    eq_probe_hz = [500.0, 2000.0, 5000.0]
    eq_measured = [gain_at(x, x_eq, fs, fc) for fc in eq_probe_hz]
 
    # --- 3. подавление помехи ---
    y, notch_params = suppress_tones(x_eq, fs, count=2)
    tone_in = tone_level_db(x, fs, notch_params[0]["f0"] if notch_params else 1500.0)
    tone_after = tone_level_db(y, fs, notch_params[0]["f0"] if notch_params else 1500.0)
    plot_notch(fs, notch_params[0]["f0"] if notch_params else 1500.0)
    plot_compare(fs, x, y, notch_params[0]["f0"] if notch_params else 1500.0)
    plot_specgram(fs, y, "Спектрограмма выходного сигнала (помеха удалена)",
                  "fig3_3_specgram_out.png")
    plot_wave(fs, x, x_eq, y)
 
    # --- 4. синтез ---
    info = write_wav(args.out, fs, y)
    fs_out, y_back = read_wav(args.out)
 
    res = {
        "input": {"name": inp.name, "fs": fs, "n": int(x.size), "dur": x.size / fs,
                  "peak": float(np.max(np.abs(x))), "rms": float(np.sqrt(np.mean(x ** 2)))},
        "detection": det,
        "eq": {"bands": EQ_BANDS, "transition_hz": EQ_TRANSITION_HZ,
               "before_db": eq_before, "after_db": eq_after,
               "delta_db": [b - a for a, b in zip(eq_before, eq_after)],
               "probe_hz": eq_probe_hz, "gain_measured_db": eq_measured},
        "notch": {"q": NOTCH_Q, "filters": notch_params,
                  "tone_level_in_db": tone_in, "tone_level_out_db": tone_after,
                  "suppression_db": tone_in - tone_after},
        "snr_in_db": snr_out_of_tone_db(x, fs, det["f0"]),
        "snr_out_db": snr_out_of_tone_db(y, fs, det["f0"]),
        "output": dict(info, name=Path(args.out).name,
                       readback_rms=float(np.sqrt(np.mean(y_back ** 2)))),
        "files": sorted(p.name for p in FIG.glob("*.png")),
    }
    (HERE / "kr2_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
 
    print(f"помеха: f0 = {det['f0']:.1f} Гц, уровень {det['level_db']:.1f} дБ, "
          f"подложка {det['floor_db']:.1f} дБ, превышение {det['excess_db']:.1f} дБ "
          f"({'обнаружена' if det['detected'] else 'не обнаружена'})")
    for (f1, f2, gdb), fc, gm in zip(EQ_BANDS, eq_probe_hz, eq_measured):
        print(f"полоса {f1:5.0f}…{min(f2, fs / 2):5.0f} Гц: задано {gdb:+.1f} дБ, "
              f"измерено {gm:+.2f} дБ на {fc:.0f} Гц")
    for p in notch_params:
        print(f"режектор f0 = {p['f0']:.1f} Гц: b = {np.round(p['b'], 6)}, "
              f"a = {np.round(p['a'], 6)}")
    print(f"уровень помехи {tone_in:.1f} → {tone_after:.1f} дБ "
          f"(подавление {tone_in - tone_after:.1f} дБ)")
    print(f"ОСШ вне полосы помехи: {res['snr_in_db']:.1f} → {res['snr_out_db']:.1f} дБ")
    print(f"выход: {Path(args.out).name}, PCM 16 бит, {info['fs']} Гц, {info['samples']} отсчётов, "
          f"{info['bytes']} байт")
    print("рисунки:", ", ".join(res["files"]))
    return res
 
 
if __name__ == "__main__":
    main()
