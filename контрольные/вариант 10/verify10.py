#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
НЕЗАВИСИМАЯ ПРОВЕРКА результатов контрольных работ №1 и №2, вариант 10.

КР1: коэффициенты b0..a2 проверяются по таблице вариантов (жёстко заданы),
полюсы/нули — через numpy.roots и аналитически; ИХ — через scipy.signal.lfilter
(независимо от формулы в kr1_variant10.py); АЧХ/ФЧХ — через scipy.signal.freqz.
КР2: входной/выходной WAV читаются заново; уровни помехи, полос эквалайзера и
ОСШ пересчитываются отдельными процедурами; коэффициенты режектора — через
scipy.signal.iirnotch.

Запуск:  python3 verify10.py
Вывод:   таблица PASS/FAIL + файл verify10_results.json рядом со скриптом.
"""
import json
import wave
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
results = []


def check(name, ok, detail=""):
    results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def close(a, b, tol):
    return abs(a - b) <= tol


# ============================ КР1, вариант 10 ============================
b0, b1, b2 = 1.0, -0.7234, -0.4231
a1, a2 = 0.7234, 0.9234
b = [b0, b1, b2]
a = [1.0, a1, a2]

# --- полюсы/нули: корни + аналитические формулы ---
poles = np.roots(a)
zeros = np.roots(b)
r = float(np.sqrt(a2))
phi = float(np.arccos(-a1 / (2 * r)))
check("КР1: полюсы p = -a1/2 ± j*sqrt(4a2-a1^2)/2",
      close(poles[0].real, -a1 / 2, 1e-12) and close(poles[0].imag, np.sqrt(4 * a2 - a1**2) / 2, 1e-12),
      f"p = {poles[0].real:.4f} ± j{poles[0].imag:.4f}")
check("КР1: r = sqrt(a2), phi_p = arccos(-a1/(2r))",
      close(r, abs(poles[0]), 1e-12) and close(phi, np.angle(poles[0]), 1e-12),
      f"r = {r:.4f}, phi_p = {phi:.4f} рад = {phi/np.pi:.4f} pi")
check("КР1: нули действительные, z1*z2 = b2/b0, z1+z2 = -b1/b0",
      abs(zeros.imag).max() < 1e-12 and close(zeros.prod(), b2 / b0, 1e-12)
      and close(zeros.sum(), -b1 / b0, 1e-12),
      f"z1 = {zeros[0].real:.4f}, z2 = {zeros[1].real:.4f}")

# --- ИХ: формула vs lfilter (независимый расчёт по РУ) ---
NMAX = 40
sin_phi = np.sin(phi)


def h_formula(n):
    v = b0 * r**n * np.sin((n + 1) * phi) / sin_phi
    if n >= 1:
        v += b1 * r**(n - 1) * np.sin(n * phi) / sin_phi
    if n >= 2:
        v += b2 * r**(n - 2) * np.sin((n - 1) * phi) / sin_phi
    return v


imp = np.zeros(NMAX + 1); imp[0] = 1.0
h_lf = signal.lfilter(b, a, imp)          # независимо: РУ через scipy
h_f = np.array([h_formula(n) for n in range(NMAX + 1)])
check("КР1: h(n) по формуле == h(n) по РУ (lfilter), n=0..40",
      np.max(np.abs(h_f - h_lf)) < 1e-12,
      f"max|dh| = {np.max(np.abs(h_f - h_lf)):.2e}; h[0..4] = "
      + ", ".join(f"{v:.4f}" for v in h_f[:5]))

# --- АЧХ/ФЧХ: freqz vs прямая подстановка z=e^{jw} ---
def Hjw(wv):
    z = np.exp(1j * wv)
    return (b0 + b1 / z + b2 / z**2) / (1 + a1 / z + a2 / z**2)


pts = {"0": 0.0, "pi/4": np.pi / 4, "pi/2": np.pi / 2, "phi_p": phi, "pi": np.pi}
wl = list(pts.values())
w, H = signal.freqz(b, a, worN=wl, fs=2 * np.pi)      # w в рад/отсчёт: fs=2π
A_fz = np.abs(H)
PH_fz = np.angle(H)
ok = True
detail = []
for i, (name, wv) in enumerate(pts.items()):
    dphi = abs(np.angle(np.exp(1j * (PH_fz[i] - np.angle(Hjw(wv))))))   # фаза по модулю 2π
    ok &= close(A_fz[i], abs(Hjw(wv)), 1e-9) and dphi < 1e-9
    detail.append(f"{name}: A={abs(Hjw(wv)):.4f}, phi={np.angle(Hjw(wv)):+.4f}")
check("КР1: АЧХ/ФЧХ в 5 точках — freqz == прямая подстановка z=e^{jw}", ok, "; ".join(detail))
check("КР1: A(0) = |1+b1+b2|/|1+a1+a2|",
      close(abs(Hjw(0)), abs((1 + b1 + b2) / (1 + a1 + a2)), 1e-12),
      f"A(0) = {abs(Hjw(0)):.4f}")
check("КР1: A(pi) = |1-b1+b2|/|1-a1+a2|",
      close(abs(Hjw(np.pi)), abs((1 - b1 + b2) / (1 - a1 + a2)), 1e-12),
      f"A(pi) = {abs(Hjw(np.pi)):.4f}")
wgrid = np.linspace(0, np.pi, 200001)
Amax = max(abs(Hjw(wv)) for wv in wgrid[::50])
wmax = wgrid[::50][int(np.argmax([abs(Hjw(wv)) for wv in wgrid[::50]]))]
check("КР1: максимум АЧХ вблизи phi_p", close(wmax, phi, 0.02),
      f"max A = {Amax:.4f} при w = {wmax:.4f} (phi_p = {phi:.4f})")
check("КР1: устойчивость (все полюсы внутри единичной окружности)",
      np.all(np.abs(poles) < 1), f"max|p| = {np.abs(poles).max():.4f} < 1")

# ============================ КР2, вариант 10 ============================
# --- входной WAV ---
with wave.open(str(HERE / "kr2_input.wav"), "rb") as wf:
    fs_in = wf.getframerate(); n_in = wf.getnframes(); sw = wf.getsampwidth(); ch = wf.getnchannels()
    raw_in = wf.readframes(n_in)
x_in = np.frombuffer(raw_in, dtype=np.int16).astype(np.float64) / 32768.0
check("КР2: входной WAV — PCM 16 бит, моно, 16 кГц, 48 000 отсчётов (3.0 с)",
      fs_in == 16000 and n_in == 48000 and sw == 2 and ch == 1,
      f"fs={fs_in}, N={n_in}, sampwidth={sw}, ch={ch}")

# --- выходной WAV ---
out_wav = HERE / "output" / "kr2_output.wav"
with wave.open(str(out_wav), "rb") as wf:
    fs_o = wf.getframerate(); n_o = wf.getnframes()
check("КР2: выходной WAV существует, PCM 16 бит, 16 кГц, 48 000 отсчётов, 96 044 байт",
      fs_o == 16000 and n_o == 48000 and out_wav.stat().st_size == 96044,
      f"fs={fs_o}, N={n_o}, размер={out_wav.stat().st_size} байт")
y_out = np.frombuffer(wave.open(str(out_wav), "rb").readframes(n_o), dtype=np.int16).astype(np.float64) / 32768.0

# --- спектр входного сигнала: окно Ханна, уровни 1500/3000 Гц ---
def amp_db(x, fs):
    N = x.size
    w = signal.get_window("hann", N, fftbins=True)
    X = np.fft.rfft(x * w)
    f = np.fft.rfftfreq(N, 1.0 / fs)
    A = 2 * np.abs(X) / np.sum(w)
    return f, A, 20 * np.log10(np.maximum(A, 1e-12))


f, A, AdB = amp_db(x_in, fs_in)
i1500 = int(np.argmin(np.abs(f - 1500.0)))
i3000 = int(np.argmin(np.abs(f - 3000.0)))
check("КР2: пик спектра входа на 1500 Гц, уровень около -11.7 дБ",
      close(f[np.argmax(AdB)], 1500.0, 1.0) and close(AdB[i1500], -11.7, 0.5),
      f"max на {f[np.argmax(AdB)]:.1f} Гц ({AdB.max():.2f} дБ); 1500 Гц: {AdB[i1500]:.2f} дБ; "
      f"3000 Гц: {AdB[i3000]:.2f} дБ")
# обнаружение: превышение над медианой окна ±150 Гц >= 12 дБ
k = max(int(150.0 / (fs_in / x_in.size)), 5)
base = np.median(AdB[i1500 - k:i1500 + k + 1])
excess = AdB[i1500] - base
check("КР2: обнаружение помехи (превышение над медианой ±150 Гц >= 12 дБ)",
      excess >= 12.0, f"f0 = {f[i1500]:.1f} Гц, подложка {base:.1f} дБ, превышение {excess:.1f} дБ")

# --- эквалайзер: фактические усиления полос ---
def band_level_db(x, fs, f1, f2, nper=2048):
    ff, P = signal.welch(x, fs=fs, window="hann", nperseg=nper,
                         noverlap=nper // 2, scaling="spectrum")
    m = (ff >= f1) & (ff <= min(f2, fs / 2))
    return float(10 * np.log10(max(np.sum(P[m]), 1e-20)))


# эквалайзер пересчитываем независимо (маска в частотной области)
N = x_in.size
X = np.fft.rfft(x_in)
fr = np.fft.rfftfreq(N, 1.0 / fs_in)
g = np.zeros_like(fr)
bands = [(0.0, 300.0, 6.0), (300.0, 3000.0, 0.0), (3000.0, 8000.0, -6.0)]
T = 200.0
for i, (f1, f2, gg) in enumerate(bands):
    wgt = np.zeros_like(fr)
    wgt[(fr >= f1) & (fr <= f2)] = 1.0
    if f1 > 0:
        m = (fr >= f1 - T) & (fr < f1)
        wgt[m] = 0.5 - 0.5 * np.cos(np.pi * (fr[m] - (f1 - T)) / T)
    if i < len(bands) - 1:
        m = (fr > f2) & (fr <= f2 + T)
        wgt[m] = 0.5 + 0.5 * np.cos(np.pi * (fr[m] - f2) / T)
    g += gg * wgt
x_eq = np.fft.irfft(X * 10 ** (g / 20.0), n=N)
ok = True
det = []
for f1, f2, gg in bands:
    d = band_level_db(x_eq, fs_in, f1, f2) - band_level_db(x_in, fs_in, f1, f2)
    ok &= abs(d - gg) < 0.5
    det.append(f"{f1:.0f}..{f2:.0f}: {d:+.2f} дБ (задание {gg:+.1f})")
check("КР2: фактическое усиление полос эквалайзера совпадает с заданным (±0.5 дБ)",
      ok, "; ".join(det))

# --- режектор: коэффициенты iirnotch + подавление на 1500 Гц ---
bn, an = signal.iirnotch(1500.0, 35.0, fs_in)
w0 = 2 * np.pi * 1500.0 / fs_in
beta = np.tan(np.pi * (2 * 1500.0 / fs_in) / 35.0 / 2)   # формула Орфанидиса: bw=w0/Q, beta=tan(bw/2)
gain = 1.0 / (1.0 + beta)
check("КР2: коэффициенты режектора iirnotch(1500, Q=35, fs=16k) — формула Орфанидиса",
      close(bn[0], gain, 1e-9) and close(bn[1], -2 * gain * np.cos(w0), 1e-9)
      and close(bn[2], gain, 1e-9) and close(an[1], -2 * gain * np.cos(w0), 1e-9)
      and close(an[2], 2 * gain - 1, 1e-9),
      f"w0={w0:.5f} рад ({np.degrees(w0):.2f}°), beta={beta:.6f}, "
      f"b0=b2={bn[0]:.6f}, b1=a1={bn[1]:.6f}, a2={an[2]:.6f}")
# классическая форма с alpha=sin(w0)/(2Q) даёт близкие значения (ср. в docx)
alpha = np.sin(w0) / (2 * 35.0)
check("КР2: классическая форма alpha=sin(w0)/(2Q) согласуется с iirnotch (расхождение < 0.001)",
      abs(1 / (1 + alpha) - bn[0]) < 0.001,
      f"alpha={alpha:.6f}, 1/(1+alpha)={1/(1+alpha):.6f} vs scipy b0={bn[0]:.6f}")
y_ref = signal.filtfilt(bn, an, x_eq)
y_ref = signal.filtfilt(*signal.iirnotch(3000.0, 35.0, fs_in), y_ref)
f2, A2, AdB2 = amp_db(y_ref, fs_in)
i15 = int(np.argmin(np.abs(f2 - 1500.0)))
before = AdB[i1500]
after = AdB2[i15]
check("КР2: подавление помехи 1500 Гц режектором (filtfilt, 2 прохода) > 60 дБ",
      before - after > 60, f"уровень {before:.1f} -> {after:.1f} дБ, подавление {before-after:.1f} дБ")
# выходной файл после квантования: уровень 1500 Гц в выходном WAV
f3, A3, AdB3 = amp_db(y_out, fs_o)
i3 = int(np.argmin(np.abs(f3 - 1500.0)))
check("КР2: в выходном WAV (после квантования 16 бит) уровень 1500 Гц < -60 дБ",
      AdB3[i3] < -60, f"уровень в выходном WAV: {AdB3[i3]:.1f} дБ")

# --- ОСШ вне полосы помехи ---
def snr_db(x, fs, f0=1500.0):
    ff, AA, _ = amp_db(x, fs)
    m = ~((ff > f0 - 25) & (ff < f0 + 25))
    return float(10 * np.log10(np.sum(AA[m] ** 2) / max(np.sum(AA[~m] ** 2), 1e-20)))

s_in = snr_db(x_eq, fs_in)
s_out = snr_db(y_ref, fs_in)
check("КР2: ОСШ вне полосы помехи выросло (вход -> выход)",
      s_out - s_in > 20, f"{s_in:.1f} -> {s_out:.1f} дБ")

# --- наличие 7 рисунков ---
pngs = sorted((HERE / "output").glob("kr2_output_*.png"))
check("КР2: созданы 7 рисунков kr2_output_1..7_*.png", len(pngs) == 7,
      ", ".join(p.name for p in pngs))

# ============================ Итог ============================
n_pass = sum(1 for r in results if r["status"] == "PASS")
print(f"\nИТОГ: {n_pass}/{len(results)} проверок PASS")
out_json = HERE / "verify10_results.json"
out_json.write_text(json.dumps({"variant": 10, "passed": n_pass, "total": len(results),
                                "results": results}, ensure_ascii=False, indent=2))
print("Сохранено:", out_json)
