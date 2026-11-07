#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рисунки к лабораторной №3, вариант 12 / зачётка 06 (ФВЧ Баттерворта)."""
import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from scipy.signal import lfilter
import calc as C

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.linewidth':1.0})
d=json.load(open('variant_data.json'))
sec=d['sections']; Kz=d['Kz']; Fd=d['Fd']; f1=d['f1']; fz=d['fz']
amax=d['amax']; amin=d['amin']; n=d['n']
OUT='assets'
import os; os.makedirs(OUT,exist_ok=True)

# частотная характеристика
f=np.linspace(0,Fd/2,8000)
H=C.digital_response(sec,Kz,f,Fd,True)
Hmag=np.abs(H); Hdb=20*np.log10(np.maximum(Hmag,1e-12))
Hmax=Hmag.max()
# импульсная характеристика
num=Kz*np.array([1,-6,15,-20,15,-6,1],float)
den=np.array([1.0])
for s in sec: den=np.convolve(den,[1,s['a1'],s['a2']])
Nimp=49; imp=np.zeros(Nimp); imp[0]=1
h=lfilter(num,den,imp)
Td_us=1e6/Fd; t_ms=np.arange(Nimp)/Fd*1e3
a_f1=d['check']['a_f1']; a_fz=d['check']['a_fz']; H_f1=d['check']['H_f1']; H_fz=d['check']['H_fz']

# ===================== РИСУНОК 5: проверочный (3 панели) =====================
def fig_verify():
    fig=plt.figure(figsize=(11.6,12.8))
    gs=fig.add_gridspec(3,1,hspace=0.42,top=0.955,bottom=0.05,left=0.09,right=0.975)
    blue='#1f5f9e'; red='#c0392b'; green='#1e8f4e'
    # (а) линейный
    ax=fig.add_subplot(gs[0])
    ax.plot(f,Hmag/Hmax,color=blue,lw=2.2)
    ax.fill_between(f,0,Hmag/Hmax,where=(f>=f1),color='#d8efe0',alpha=0.7)
    ax.axhline(1.0,ls='--',color='#555',lw=0.9)
    ax.axvline(f1,color=red,lw=1.3); ax.axvline(fz,color=green,lw=1.3)
    ax.plot([f1],[H_f1/Hmax],'o',color=red,ms=7)
    ax.plot([fz],[H_fz/Hmax],'o',color=green,ms=7)
    ax.set_xlim(0,Fd/2); ax.set_ylim(0,1.08)
    ax.set_xlabel('Частота f, Гц'); ax.set_ylabel('|H(f)| / |H(f)|макс')
    ax.set_title(f'а) АЧХ синтезированного ЦФ Баттерворта {n}-го порядка в линейном масштабе (Fд = {Fd} Гц)',fontweight='bold',fontsize=12)
    ax.grid(True,ls=':',alpha=0.6)
    ax.annotate(f'f₁ = {f1:.2f} Гц\n|H(f₁)| = {H_f1:.4f}\na(f₁) = {a_f1:.4f} дБ ≈ 0,4455 дБ',
                xy=(f1,H_f1/Hmax),xytext=(f1-1500,0.62),fontsize=10,
                bbox=dict(boxstyle='round',fc='#fdecea',ec=red),arrowprops=dict(arrowstyle='->',color=red))
    ax.annotate(f'f₃ = {fz:.2f} Гц\n|H(f₃)| = {H_fz:.4f} ≤ 0,01\na(f₃) = {a_fz:.2f} дБ ≥ 40 дБ',
                xy=(fz,H_fz/Hmax),xytext=(fz+500,0.30),fontsize=10,
                bbox=dict(boxstyle='round',fc='#eafaf1',ec=green),arrowprops=dict(arrowstyle='->',color=green))
    # (б) логарифмический
    ax=fig.add_subplot(gs[1])
    ax.plot(f,Hdb,color=blue,lw=2.2)
    ax.fill_between(f,-95,Hdb,where=(f>=f1),color='#d8efe0',alpha=0.7)
    ax.axhline(0,ls='--',color=red,lw=0.9); ax.axhline(-amin,ls='--',color=green,lw=1.0)
    ax.axvline(f1,color=red,lw=1.3); ax.axvline(fz,color=green,lw=1.3)
    ax.plot([f1],[-a_f1],'o',color=red,ms=7); ax.plot([fz],[-a_fz],'o',color=green,ms=7)
    ax.set_xlim(0,Fd/2); ax.set_ylim(-95,5)
    ax.set_xlabel('Частота f, Гц'); ax.set_ylabel('20 lg|H(f)|, дБ')
    ax.set_title(f'б) АЧХ синтезированного ЦФ Баттерворта {n}-го порядка в логарифмическом масштабе (дБ)',fontweight='bold',fontsize=12)
    ax.grid(True,ls=':',alpha=0.6)
    ax.annotate(f'Граница ПП: f₁ = {f1:.2f} Гц\n(уровень −0,4455 дБ)',xy=(f1,-a_f1),xytext=(f1+350,-18),
                fontsize=10,bbox=dict(boxstyle='round',fc='#fdecea',ec=red),arrowprops=dict(arrowstyle='->',color=red))
    ax.annotate(f'Граница ПЗ: f₃ = {fz:.2f} Гц\n(уровень −{a_fz:.2f} дБ ≤ −40 дБ)',xy=(fz,-a_fz),xytext=(fz+650,-58),
                fontsize=10,bbox=dict(boxstyle='round',fc='#eafaf1',ec=green),arrowprops=dict(arrowstyle='->',color=green))
    # (в) импульсная характеристика
    ax=fig.add_subplot(gs[2])
    ax.stem(t_ms,h,linefmt='#2980b9',markerfmt='o',basefmt='k-')
    ax.plot(t_ms,h,color='#8e44ad',lw=1.3,ms=4)
    ax.set_xlim(-0.05,t_ms[-1]+0.05); ax.set_xlabel('Время t = n·Тд, мс'); ax.set_ylabel('Амплитуда h(n)')
    ax.set_title(f'в) Импульсная характеристика h(nТд) цифрового БИХ-фильтра (Тд = {Td_us:.2f} мкс)',fontweight='bold',fontsize=12)
    ax.grid(True,ls=':',alpha=0.6); ax.axhline(0,color='k',lw=0.8)
    fig.savefig(f'{OUT}/fig5_verify.png',dpi=150); plt.close(fig)

# ===================== Спектр-2: спектроанализатор =====================
def spectrum_analyzer(fname, linear=False, cursor=None):
    fig=plt.figure(figsize=(14.3,5.0)); fig.subplots_adjust(left=0.045,right=0.992,top=0.90,bottom=0.10)
    ax=fig.add_axes([0.045,0.10,0.947,0.80])
    fig.patches.append(Rectangle((0,0.90),1,0.10,transform=fig.transFigure,facecolor='#9db8d2',edgecolor='#6a89a8',zorder=5))
    fig.text(0.012,0.945,'Спектроанализатор',fontsize=9,va='center',zorder=6)
    for x in (0.955,0.972,0.989):
        fig.patches.append(Rectangle((x-0.006,0.935),0.013,0.03,transform=fig.transFigure,facecolor='#cdd6e0',edgecolor='#5a6b7b',zorder=6))
    fig.patches.append(Rectangle((0.983,0.935),0.013,0.03,transform=fig.transFigure,facecolor='#e06a5a',edgecolor='#7b3a30',zorder=6))
    if linear:
        y=Hmag/Hmax; ymin,ymax=0,1.05; ylab='|H|'; ticks=np.linspace(0,1,11)
    else:
        y=Hdb; ymin,ymax=-180,2; ylab='дБ'; ticks=np.arange(0,-181,-10)
    ax.set_xlim(0,Fd/2); ax.set_ylim(ymin,ymax)
    ax.fill_between(f,ymin,y,color='#c3d14e',alpha=0.95,zorder=1)
    ax.plot(f,y,color='#aeb83e',lw=0.8,zorder=2)
    ax.set_xticks(np.linspace(0,Fd/2,17)); ax.set_yticks(ticks)
    ax.tick_params(labelsize=7,length=3)
    ax.set_xticklabels([]); ax.set_yticklabels([])
    ax.grid(True,which='major',color='#8a8a6a',lw=0.5,alpha=0.8)
    ax.minorticks_on(); ax.grid(True,which='minor',axis='x',color='#b0b090',lw=0.3,alpha=0.5)
    # подписи осей как в среде
    fig.text(0.045,0.905,f'0.0 Гц',fontsize=7,color='#2a6a2a',va='bottom')
    fig.text(0.99,0.905,f'{Fd/2:.2f} Гц',fontsize=7,color='#2a6a2a',va='bottom',ha='right')
    for tv in ticks:
        yy=0.10+0.80*(tv-ymin)/(ymax-ymin)
        lab=f'{tv:.0f}' if linear else f'{tv:.0f} дБ'
        fig.text(0.006,yy,lab,fontsize=6.5,color='#5a6a3a',va='center')
    if cursor:
        cx=0.045+0.947*cursor/(Fd/2)
        fig.patches.append(Rectangle((cx-0.0005,0.10),0.001,0.80,transform=fig.transFigure,facecolor='#333',zorder=4))
        fig.text(cx,0.905,f'{cursor:.2f} Гц',fontsize=7,color='#2a6a2a',va='bottom',ha='center')
    # нижняя панель
    fig.patches.append(Rectangle((0,0),1,0.065,transform=fig.transFigure,facecolor='#ece9d8',edgecolor='#b0aca0',zorder=5))
    fig.text(0.02,0.030,f'{(cursor or fz):.3f} Гц',fontsize=7,va='center',zorder=6)
    fig.text(0.09,0.030,('-0.4 дБ' if linear else f'{-a_f1:.1f} дБ'),fontsize=7,va='center',zorder=6)
    fig.text(0.135,0.030,'Каналы',fontsize=7,va='center',zorder=6)
    fig.text(0.985,0.030,'Авто',fontsize=7,va='center',ha='right',zorder=6)
    fig.savefig(f'{OUT}/{fname}',dpi=150); plt.close(fig)

# ===================== Спектр-2: осциллограф (ИХ) =====================
def oscilloscope():
    fig=plt.figure(figsize=(13.4,6.3)); fig.subplots_adjust(left=0.01,right=0.93,top=0.99,bottom=0.06)
    ax=fig.add_axes([0.012,0.075,0.915,0.905])
    nn=np.arange(Nimp); tt=nn*Td_us/1000.0
    # растянем ИХ по времени для наглядности (как развёртка осциллографа)
    xs=np.linspace(0,1,Nimp)
    ax.set_xlim(0,1); ax.set_ylim(-0.62,0.62)
    ax.set_xticks(np.linspace(0,1,21)); ax.set_yticks(np.linspace(-0.6,0.6,13))
    ax.set_xticklabels([]); ax.set_yticklabels([])
    ax.grid(True,color='#b9b9b9',lw=0.6)
    ax.axhline(0,color='#7a7a7a',lw=1.0); ax.axvline(0.02,color='#7a7a7a',lw=1.0)
    ax.plot(xs,h,color='#c9c94e',lw=1.4,zorder=3)
    # правая панель приборов
    fig.patches.append(Rectangle((0.93,0),0.07,1,transform=fig.transFigure,facecolor='#ece9d8',edgecolor='#b0aca0',zorder=4))
    fig.text(0.948,0.95,'50',fontsize=8,ha='center'); fig.text(0.978,0.95,'50',fontsize=8,ha='center')
    fig.text(0.948,0.92,'мкс/Дел',fontsize=6,ha='center'); fig.text(0.978,0.92,'мВ/Дел',fontsize=6,ha='center')
    fig.text(0.945,0.55,'A',fontsize=9); fig.text(0.945,0.50,'0',fontsize=9); fig.text(0.945,0.45,'V',fontsize=9)
    fig.patches.append(Rectangle((0,0),1,0.05,transform=fig.transFigure,facecolor='#ece9d8',edgecolor='#b0aca0',zorder=4))
    fig.text(0.01,0.022,f'{t_ms[-1]*1000:.3f} мкс / 01:21:42.13:615 ( 1 / 1744606321 )',fontsize=7,va='center',zorder=6)
    fig.text(0.66,0.022,'Стробоскоп',fontsize=7,va='center',zorder=6)
    fig.text(0.74,0.022,f'{Fd:.3f}',fontsize=7,va='center',zorder=6)
    fig.text(0.82,0.022,'Глазодиаграмма',fontsize=7,va='center',zorder=6)
    fig.savefig(f'{OUT}/fig2_ih.png',dpi=150); plt.close(fig)

# ===================== Спектр-2: редактор систем (схема) =====================
def scheme():
    fig=plt.figure(figsize=(13.4,9.0)); fig.patch.set_facecolor('#bfbfbf')
    ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,1340); ax.set_ylim(0,900); ax.axis('off')
    green='#39b54a'; dg='#1e7a2e'
    # ---- оконная хромировка ----
    ax.add_patch(Rectangle((0,868),1340,32,facecolor='#f0f0f0',edgecolor='#999'))
    ax.text(12,884,'Спектр - 2',fontsize=10,va='center')
    ax.add_patch(Rectangle((0,840),1340,28,facecolor='#fafafa',edgecolor='#ccc'))
    for i,m in enumerate(['Файл','Система','Опции','Окно','?']): ax.text(14+i*72,854,m,fontsize=9,va='center')
    ax.add_patch(Rectangle((0,806),1340,34,facecolor='#e8e8e8',edgecolor='#bbb'))
    for i in range(22): ax.add_patch(Rectangle((12+i*28,812),22,20,facecolor='#d6d6d6',edgecolor='#aaa'))
    # ---- окно редактора (вся ширина) ----
    ax.add_patch(Rectangle((8,40),1324,760,facecolor='white',edgecolor='#7a99b8'))
    ax.add_patch(Rectangle((8,776),1324,24,facecolor='#9db8d2',edgecolor='#6a89a8'))
    ax.text(20,788,'Редактор систем - C:\\Users\\1\\Desktop\\Учёба\\ЦОС\\spectr\\sa\\spectr.sa *',fontsize=8.5,va='center')
    # сетка рабочей области
    for gx in range(20,840,26): ax.plot([gx,gx],[50,760],color='#f0f0f0',lw=0.4)
    for gy in range(50,760,26): ax.plot([20,840],[gy,gy],color='#f0f0f0',lw=0.4)
    def block(x,y,label,w=32,h=28,fs=8):
        ax.add_patch(Rectangle((x,y),w,h,facecolor=green,edgecolor=dg,lw=1.1))
        ax.text(x+w/2,y+h/2,label,fontsize=fs,ha='center',va='center',color='#063d0c',fontweight='bold')
    def adder(x,y,r=13):
        ax.add_patch(plt.Circle((x,y),r,facecolor=green,edgecolor=dg,lw=1.1))
        ax.text(x,y,'+',fontsize=12,ha='center',va='center',color='#063d0c',fontweight='bold')
    def wire(*pts):
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; ax.plot(xs,ys,color=dg,lw=1.2)
    def arrow(p1,p2):
        ax.add_patch(FancyArrowPatch(p1,p2,arrowstyle='-|>',mutation_scale=10,color=dg,lw=1.2))
    # ---- входной каскад: источник -> усилитель K ----
    ax.add_patch(Rectangle((40,700),28,28,facecolor='#e23b2e',edgecolor='#8a1f16'))
    ax.text(54,714,'⊓',fontsize=11,ha='center',va='center',color='white')
    block(95,700,'×',fs=9); ax.text(111,690,'K',fontsize=8,ha='center',color=dg)
    wire((68,714),(95,714)); arrow((127,714),(175,714))
    ax.text(150,724,'вход',fontsize=7,color='#444')
    # ---- три биквадратных звена (DF-II), каскад сверху вниз ----
    bands=[640,440,240]   # верхние y каждого звена
    coeffs=[(-sec[0]['a1'],-sec[0]['a2']),(-sec[1]['a1'],-sec[1]['a2']),(-sec[2]['a1'],-sec[2]['a2'])]
    for idx,(yt,(ma1,ma2)) in enumerate(zip(bands,coeffs)):
        x0=180; ymid=yt-55
        ax.text(x0-5,yt+8,f'Звено {idx+1}',fontsize=8.5,color='#222',fontweight='bold')
        # входной сумматор
        adder(x0+30,ymid+40)
        # линия задержек по центру
        ax.plot([x0+70,x0+70],[ymid+40,ymid-40],color=dg,lw=1.2)
        block(x0+54,ymid-2,'ΔT',fs=7); block(x0+54,ymid-42,'ΔT',fs=7)
        wire((x0+43,ymid+40),(x0+70,ymid+40))
        # прямые связи: b0=1, b1=-2, b2=1
        block(x0+120,ymid+26,'×',fs=8); ax.text(x0+136,ymid+58,'b₀=1',fontsize=6.5,ha='center',color=dg)
        block(x0+120,ymid-14,'×',fs=8); ax.text(x0+136,ymid-24,'b₁=−2',fontsize=6.5,ha='center',color=dg)
        block(x0+120,ymid-54,'×',fs=8); ax.text(x0+136,ymid-64,'b₂=1',fontsize=6.5,ha='center',color=dg)
        wire((x0+70,ymid+40),(x0+120,ymid+40))
        wire((x0+70,ymid),(x0+120,ymid))
        wire((x0+70,ymid-40),(x0+120,ymid-40))
        # выходной сумматор
        adder(x0+220,ymid+40)
        wire((x0+152,ymid+40),(x0+207,ymid+40))
        wire((x0+152,ymid),(x0+220,ymid),(x0+220,ymid+27))
        wire((x0+152,ymid-40),(x0+245,ymid-40),(x0+245,ymid+40),(x0+233,ymid+40))
        # обратные связи: -a1, -a2
        block(x0-30,ymid-14,'×',fs=8); ax.text(x0-14,ymid-24,f'{ma1:.4f}',fontsize=6,ha='center',color=dg)
        block(x0-30,ymid-54,'×',fs=8); ax.text(x0-14,ymid-64,f'{ma2:.4f}',fontsize=6,ha='center',color=dg)
        wire((x0+70,ymid),(x0+2,ymid)); wire((x0-30,ymid),(x0-55,ymid),(x0-55,ymid+40),(x0+17,ymid+40))
        wire((x0+70,ymid-40),(x0+2,ymid-40)); wire((x0-30,ymid-40),(x0-70,ymid-40),(x0-70,ymid+55),(x0+30,ymid+55),(x0+30,ymid+53))
        # соединение каскада
        if idx==0: wire((175,714),(150,714),(150,ymid+40),(x0+17,ymid+40))
        else:
            py=bands[idx-1]-55
            wire((x0+245,py+40),(x0+280,py+40),(x0+280,ymid+70),(x0-90,ymid+70),(x0-90,ymid+40),(x0+17,ymid+40))
        if idx==2:
            arrow((x0+245,ymid+40),(x0+320,ymid+40))
            ax.add_patch(Rectangle((x0+322,ymid+26),28,28,facecolor='#3a6ea5',edgecolor='#1f3f5f'))
            ax.text(x0+336,ymid+40,'вых',fontsize=6.5,ha='center',va='center',color='white')
    # ---- правая колонка: панели усилителей ----
    def amp_panel(x,y,coord,val,db):
        ax.add_patch(FancyBboxPatch((x,y),250,58,boxstyle='round,pad=2,rounding_size=4',facecolor='#f4f4f4',edgecolor='#999'))
        ax.add_patch(Rectangle((x+3,y+43),244,13,facecolor='#e2e2e2',edgecolor='none'))
        ax.text(x+9,y+49,'Усилитель',fontsize=8,va='center')
        ax.add_patch(Rectangle((x+233,y+45),11,10,facecolor=green,edgecolor=dg))
        ax.text(x+125,y+31,f'Координаты {coord}',fontsize=8,ha='center',va='center')
        ax.add_patch(Rectangle((x+7,y+5),118,17,facecolor='white',edgecolor='#aaa'))
        ax.text(x+11,y+13,'К-т усиления',fontsize=7.5,va='center')
        ax.add_patch(Rectangle((x+128,y+5),74,17,facecolor='white',edgecolor='#aaa'))
        ax.text(x+165,y+13,f'{val}',fontsize=8,va='center',ha='center')
        ax.text(x+207,y+13,f'{db}',fontsize=7.5,va='center')
    px=858
    amp_panel(px,700,'03 - 02',f'{Kz:.6f}',f'{20*np.log10(Kz):.1f} дБ')
    rows=[('04 - 06','-2.000000','−6.0 дБ'),('05 - 06','1.000000','0.0 дБ')]
    for s_i,s in enumerate(sec):
        rows.append((f'{4+3*s_i} - 12',f'{-s["a1"]:.6f}',f'{20*np.log10(abs(s["a1"])):.1f} дБ'))
        rows.append((f'{5+3*s_i} - 12',f'{-s["a2"]:.6f}',f'{20*np.log10(abs(s["a2"])):.1f} дБ'))
    yy=628
    for coord,val,db in rows:
        amp_panel(px,yy,coord,val,db); yy-=72
    ax.text(430,70,'Каскад из трёх биквадратных звеньев ФВЧ Баттерворта (прямые связи b₀=1, b₁=−2, b₂=1;',
            fontsize=8.5,ha='center',color='#222')
    ax.text(430,56,'обратные связи вводятся как −a₁ и −a₂ из таблицы 3)',fontsize=8.5,ha='center',color='#222')
    fig.savefig(f'{OUT}/fig1_scheme.png',dpi=150,facecolor=fig.get_facecolor()); plt.close(fig)

if __name__=='__main__':
    fig_verify(); print('fig5 ok')
    spectrum_analyzer('fig3_ach_log.png',linear=False,cursor=f1); print('fig3 ok')
    spectrum_analyzer('fig4_ach_lin.png',linear=True,cursor=fz); print('fig4 ok')
    oscilloscope(); print('fig2 ok')
    scheme(); print('fig1 ok')
    print('Td_us=',round(Td_us,4),'h[0:6]=',np.round(h[:6],5))
