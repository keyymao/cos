#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтез цифрового БИХ-фильтра методом билинейного z-преобразования.
Лабораторная №3. Движок расчёта (Баттерворт / Чебышёв, ФНЧ / ФВЧ)."""
import numpy as np

def butterworth_lpf_prototype(Omega3, amax, amin):
    """Аналоговый ФНЧ-прототип Баттерворта. Возвращает n, eps, R, полюсы, пары (a,b)."""
    eps2 = 10**(0.1*amax) - 1.0
    eps = np.sqrt(eps2)
    # порядок
    num = (10**(0.1*amin) - 1.0)/eps2
    n_exact = np.log10(num)/(2*np.log10(Omega3))
    n = int(np.ceil(n_exact - 1e-9))
    R = eps**(-1.0/n)                      # радиус окружности полюсов
    # все 2n корней
    roots = []
    for k in range(1, 2*n+1):
        ang = (2*k-1)*np.pi/(2*n)
        roots.append(R*(np.cos(ang)+1j*np.sin(ang)))
    roots = np.array(roots)
    lhp = roots[roots.real < 0]
    # верхняя полуплоскость (Im>0), сортируем по возрастанию угла => по убыванию |Re|
    upper = lhp[lhp.imag > 0]
    upper = upper[np.argsort(-np.abs(upper.real))]   # наибольшая |Re| первой
    pairs = []
    for p in upper:
        a = -2*p.real
        b = abs(p)**2
        pairs.append((a, b, p))
    K = 1.0/eps                            # числитель ФНЧ (H(0)=1)
    return dict(n=n, n_exact=n_exact, eps=eps, eps2=eps2, R=R, roots=roots,
                lhp=lhp, pairs=pairs, K=K, Omega3=Omega3)

def lp_to_hp(pairs, K, Omega1, n):
    """Замена p_нч = Omega1/p_вч. H_HP(p)=p^n / prod(p^2+a'p+b')."""
    prod_b = np.prod([b for a,b,p in pairs])
    hp_pairs = []
    for a,b,p in pairs:
        ap = a*Omega1/b
        bp = Omega1**2/b
        hp_pairs.append((ap, bp))
    num_coef = K/prod_b                    # = 1 для Баттерворта
    return hp_pairs, num_coef

def bilinear_hp(hp_pairs, A, n):
    """p = A(1-z^-1)/(1+z^-1), A=2Fs. ФВЧ: числитель (1-z^-1)^n."""
    A2 = A*A
    sections = []
    c0prod = 1.0
    for ap,bp in hp_pairs:
        c0 = A2 + ap*A + bp
        c1 = -2*A2 + 2*bp
        c2 = A2 - ap*A + bp
        a1 = c1/c0
        a2 = c2/c0
        sections.append(dict(c0=c0,c1=c1,c2=c2,a1=a1,a2=a2,ap=ap,bp=bp))
        c0prod *= c0
    Kz = A**n/c0prod
    return sections, Kz

def bilinear_lp(pairs, A, n, K):
    """ФНЧ: числитель (1+z^-1)^n."""
    A2=A*A; sections=[]; c0prod=1.0
    for a,b,p in pairs:
        c0=A2+a*A+b; c1=-2*A2+2*b; c2=A2-a*A+b
        sections.append(dict(c0=c0,c1=c1,c2=c2,a1=c1/c0,a2=c2/c0))
        c0prod*=c0
    Kz=K*A**n/c0prod
    return sections,Kz

def freq_distortion(F, Fd):
    return (Fd/np.pi)*np.arctan(np.pi*F/Fd)

def digital_response(sections, Kz, f, Fd, hp=True):
    """|H| и дБ на частотах f (Гц). Каскад биквадратных звеньев."""
    z = np.exp(-1j*2*np.pi*f/Fd)           # z^-1
    zi = z; z2 = z*z
    num = (1-zi)**(2*len(sections)) if hp else (1+zi)**(2*len(sections))
    H = Kz*num.astype(complex)
    for s in sections:
        H = H/(1 + s['a1']*zi + s['a2']*z2)
    return H

def attenuation_db(sections,Kz,f,Fd,hp=True):
    H = digital_response(sections,Kz,np.array([f]),Fd,hp)[0]
    return -20*np.log10(abs(H)), abs(H)

def pole_max(sections):
    mx=0
    for s in sections:
        r=np.roots([1,s['a1'],s['a2']])
        mx=max(mx,max(abs(r)))
    return mx

# ===================== ВАЛИДАЦИЯ НА ПРИМЕРЕ МЕТОДИЧКИ =====================
if __name__=='__main__':
    print('=== ВАЛИДАЦИЯ: пример методички ФВЧ Баттерворта ===')
    # пример: Ф1(пп)=4940, Fз(пз)=1900, Fд=17000
    Fd=17000; Fhigh=4940; Flow=1900
    Om3=Fhigh/Flow
    pr=butterworth_lpf_prototype(Om3,0.4455,40)
    print('Omega3=',Om3,'n=',pr['n'],'n_exact=',round(pr['n_exact'],4),'eps=',round(pr['eps'],5),'R=',round(pr['R'],5))
    print('ФНЧ пары (a,b):',[(round(a,4),round(b,4)) for a,b,p in pr['pairs']],'K=',round(pr['K'],4))
    hp_pairs,numc=lp_to_hp(pr['pairs'],pr['K'],Om3,pr['n'])
    print('ФВЧ пары (a\',b\'):',[(round(a,4),round(b,4)) for a,b in hp_pairs],'num=',round(numc,5))
    Fs=Fd/(2*np.pi*Flow); A=2*Fs
    print('Fs=',round(Fs,5),'A=2Fs=',round(A,5))
    sec,Kz=bilinear_hp(hp_pairs,A,pr['n'])
    print('Kz=',round(Kz,6),'(методичка 0.063535)')
    for i,s in enumerate(sec):
        print(f'  звено {i+1}: a1={s["a1"]:.5f} a2={s["a2"]:.5f}')
    print('  (методичка: -0.28202/0.036546, -0.32382/0.19017, -0.43566/0.60121)')
    print('f1=',round(freq_distortion(Fhigh,Fd),4),'(методичка 4003.8081)')
    print('fз=',round(freq_distortion(Flow,Fd),4),'(методичка 1827.2311)')
