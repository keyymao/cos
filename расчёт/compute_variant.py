#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Полный расчёт варианта 12 / зачётка 06 (ФВЧ Баттерворта) + проверка + JSON."""
import numpy as np, json
import calc as C

Nbr=12
Fd=10000+200*Nbr
F1t=1200+20*Nbr
Fzt=3120+50*Nbr+10*(Nbr//5)
amax=0.4455; amin=40.0
Fhigh=max(F1t,Fzt); Flow=min(F1t,Fzt)   # ФВЧ: ПП сверху, ПЗ снизу
Om3=Fhigh/Flow
pr=C.butterworth_lpf_prototype(Om3,amax,amin)
hp,numc=C.lp_to_hp(pr['pairs'],pr['K'],Om3,pr['n'])
Fs=Fd/(2*np.pi*Flow); A=2*Fs
sec,Kz=C.bilinear_hp(hp,A,pr['n'])
f1=C.freq_distortion(Fhigh,Fd); fz=C.freq_distortion(Flow,Fd)

a1db,m1=C.attenuation_db(sec,Kz,f1,Fd,True)
azdb,mz=C.attenuation_db(sec,Kz,fz,Fd,True)
ff=np.linspace(f1,Fd/2,6000)
adb=-20*np.log10(abs(C.digital_response(sec,Kz,ff,Fd,True)))

print('================ ВАРИАНТ 12 / ЗАЧЁТКА 06 — ФВЧ Баттерворта ================')
print(f'Fд={Fd}  F1(табл,ПП)={F1t}  Fз(табл,ПЗ)={Fzt}  floor(12/5)={Nbr//5}')
print(f'ФВЧ: F1(пп)={Fhigh}  Fз(пз)={Flow}  Omega1=Omega3={Om3:.6f}')
print(f'eps2={pr["eps2"]:.6f}  eps={pr["eps"]:.5f}  n_exact={pr["n_exact"]:.5f}  n={pr["n"]}')
print(f'R={pr["R"]:.5f}  R^2(b)={pr["R"]**2:.5f}  K_LP=1/eps={pr["K"]:.5f}')
print('--- ФНЧ прототип: 3 пары ---')
for i,(a,b,p) in enumerate(pr['pairs']):
    print(f'  пара {i+1}: p={p.real:.5f}{p.imag:+.5f}j  a={a:.5f} b={b:.5f}')
print('--- ФВЧ АФП: 3 пары ---')
for i,(ap,bp) in enumerate(hp):
    print(f'  звено {i+1}: a\'={ap:.5f} b\'={bp:.5f}')
print(f'Fs={Fs:.6f}  A=2Fs={A:.6f}  A^2={A*A:.6f}')
print('--- ЦФ: биквадратные звенья ---')
for i,s in enumerate(sec):
    print(f'  звено {i+1}: c0={s["c0"]:.5f} c1={s["c1"]:.5f} c2={s["c2"]:.5f}  a1={s["a1"]:.5f} a2={s["a2"]:.5f}')
print(f'prod c0={np.prod([s["c0"] for s in sec]):.4f}  A^6={A**6:.5f}  Kz={Kz:.7f}')
print(f'f1(пп)={f1:.4f}  fз(пз)={fz:.4f}')
print('--- ПРОВЕРКА ---')
print(f'  на f1={f1:.2f}: a={a1db:.4f} дБ (<= {amax}), |H|={m1:.5f}')
print(f'  на fз={fz:.2f}: a={azdb:.4f} дБ (>= {amin}), |H|={mz:.6f}')
print(f'  max|pole|={C.pole_max(sec):.5f}')
print(f'  ПП неравномерность: {adb.min():.4f}..{adb.max():.4f} дБ')
print(f'  |H|(Найквист)={abs(C.digital_response(sec,Kz,np.array([Fd/2]),Fd,True)[0]):.6f}  |H|(DC)={abs(C.digital_response(sec,Kz,np.array([0.0]),Fd,True)[0]):.8f}')

# Сохраняем всё в JSON для построителя документа
def cmpl(z): return [float(z.real),float(z.imag)]
data=dict(
  Nbr=Nbr, zachet="06", group="БРВ2402",
  Fd=Fd, F1t=F1t, Fzt=Fzt, floor5=Nbr//5, amax=amax, amin=amin,
  Fhigh=Fhigh, Flow=Flow, Omega3=Om3, Omega1=Om3,
  eps2=pr['eps2'], eps=pr['eps'], n=pr['n'], n_exact=pr['n_exact'],
  R=pr['R'], R2=pr['R']**2, K_LP=pr['K'],
  roots=[cmpl(r) for r in pr['roots']],
  lhp_pairs=[dict(re=p.real,im=p.imag,a=a,b=b) for a,b,p in pr['pairs']],
  hp_pairs=[dict(ap=ap,bp=bp) for ap,bp in hp],
  Fs=Fs, A=A, A2=A*A, A6=A**6,
  sections=[{k:float(v) for k,v in s.items()} for s in sec],
  prod_c0=float(np.prod([s['c0'] for s in sec])), Kz=float(Kz),
  f1=float(f1), fz=float(fz),
  check=dict(a_f1=float(a1db), H_f1=float(m1), a_fz=float(azdb), H_fz=float(mz),
             pole_max=float(C.pole_max(sec)), ripple_min=float(adb.min()), ripple_max=float(adb.max()),
             H_nyq=float(abs(C.digital_response(sec,Kz,np.array([Fd/2]),Fd,True)[0])),
             H_dc=float(abs(C.digital_response(sec,Kz,np.array([0.0]),Fd,True)[0]))),
)
json.dump(data,open('variant_data.json','w'),ensure_ascii=False,indent=2)
print('\nСохранено variant_data.json')
