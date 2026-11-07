#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Построение .pdf из content.blocks (ReportLab, шрифт DejaVu Serif, формулы inline)."""
import os, matplotlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Image, Table, TableStyle, PageBreak, KeepTogether)
import content
from mathast import inline

FD=os.path.join(os.path.dirname(matplotlib.__file__),'mpl-data','fonts','ttf')
pdfmetrics.registerFont(TTFont('Serif',os.path.join(FD,'DejaVuSerif.ttf')))
pdfmetrics.registerFont(TTFont('Serif-B',os.path.join(FD,'DejaVuSerif-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Serif-I',os.path.join(FD,'DejaVuSerif-Italic.ttf')))
pdfmetrics.registerFont(TTFont('Serif-BI',os.path.join(FD,'DejaVuSerif-BoldItalic.ttf')))
pdfmetrics.registerFontFamily('Serif',normal='Serif',bold='Serif-B',italic='Serif-I',boldItalic='Serif-BI')

PW,PH=A4
LM=3.0*cm; RM=1.5*cm; TM=2.0*cm; BM=2.0*cm
FW=PW-LM-RM

body=ParagraphStyle('body',fontName='Serif',fontSize=14,leading=21,alignment=TA_JUSTIFY,
                    firstLineIndent=1.25*cm,spaceBefore=0,spaceAfter=0)
h1=ParagraphStyle('h1',fontName='Serif-B',fontSize=14,leading=21,alignment=TA_CENTER,
                  spaceBefore=12,spaceAfter=12)
h2=ParagraphStyle('h2',fontName='Serif-B',fontSize=14,leading=21,alignment=TA_LEFT,
                  spaceBefore=10,spaceAfter=4)
eq=ParagraphStyle('eq',fontName='Serif',fontSize=12.5,leading=17,alignment=TA_CENTER,
                  spaceBefore=4,spaceAfter=4)
cap=ParagraphStyle('cap',fontName='Serif',fontSize=13,leading=16,alignment=TA_CENTER,
                   spaceBefore=2,spaceAfter=10)
tcap=ParagraphStyle('tcap',fontName='Serif',fontSize=13,leading=18,alignment=TA_LEFT,
                    firstLineIndent=1.25*cm,spaceBefore=6,spaceAfter=3)
cell=ParagraphStyle('cell',fontName='Serif',fontSize=11.5,leading=14,alignment=TA_CENTER)
cellb=ParagraphStyle('cellb',fontName='Serif-B',fontSize=11.5,leading=14,alignment=TA_CENTER)
# титул
tc=ParagraphStyle('tc',fontName='Serif',fontSize=14,leading=17,alignment=TA_CENTER)
tcb=ParagraphStyle('tcb',fontName='Serif-B',fontSize=14,leading=18,alignment=TA_CENTER)
tl=ParagraphStyle('tl',fontName='Serif',fontSize=14,leading=18,alignment=TA_LEFT)

story=[]
def esc_amp(t):  # ReportLab: & должен быть &amp; если не часть тега; наши теги уже валидны
    return t

def render_title(dd):
    for line in ['Министерство цифрового развития, связи и массовых коммуникаций',
                 'Российской Федерации',
                 'Ордена Трудового Красного Знамени федеральное государственное',
                 'бюджетное образовательное учреждение высшего образования',
                 'Московский технический университет связи и информатики',
                 'Кафедра «Радиотехнических систем»']:
        story.append(Paragraph(line,tc))
    story.append(Spacer(1,62))
    story.append(Paragraph('Лабораторная работа №3',tcb))
    story.append(Paragraph('«СИНТЕЗ ЦИФРОВЫХ БИХ-ФИЛЬТРОВ',tcb))
    story.append(Paragraph('МЕТОДОМ БИЛИНЕЙНОГО Z-ПРЕОБРАЗОВАНИЯ»',tcb))
    story.append(Spacer(1,52))
    story.append(Paragraph('По дисциплине:',tc))
    story.append(Paragraph('«Цифровая обработка сигналов»',tc))
    story.append(Spacer(1,62))
    story.append(Paragraph('Выполнил:',tl))
    story.append(Paragraph('студент гр. БРВ2402 ______________  № зачётки 06',tl))
    story.append(Spacer(1,16))
    story.append(Paragraph('Проверил:',tl))
    story.append(Paragraph('преподаватель ______________  Варламов В.О.',tl))
    story.append(Spacer(1,78))
    story.append(Paragraph('Москва 2026',tc))
    story.append(PageBreak())

def render_table(b):
    story.append(Paragraph(b['caption'],tcap))
    headers=b['headers']; rows=b['rows']; widths=b.get('widths')
    data=[[Paragraph(str(h),cellb) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c),cell) for c in row])
    if widths:
        cw=[w*cm for w in widths]
    else:
        cw=[FW/len(headers)]*len(headers)
    t=Table(data,colWidths=cw,hAlign='CENTER')
    t.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.6,colors.black),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E8E8E8')),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
    ]))
    story.append(t)
    story.append(Spacer(1,8))

def render_figure(b):
    from PIL import Image as PILImage
    path=b['path']; w=b['width']*cm
    iw,ih=PILImage.open(path).size; h=w*ih/iw
    maxh=PH-TM-BM-40
    if h>maxh:
        h=maxh; w=h*iw/ih
    img=Image(path,width=w,height=h); img.hAlign='CENTER'
    story.append(Spacer(1,4))
    story.append(img)
    story.append(Paragraph(b['caption'],cap))

for b in content.blocks:
    ty=b['type']
    if ty=='title': render_title(b['data'])
    elif ty=='h1': story.append(Paragraph(b['text'],h1))
    elif ty=='h2': story.append(Paragraph(b['text'],h2))
    elif ty=='p': story.append(Paragraph(b['text'],body))
    elif ty=='eq': story.append(Paragraph(inline(b['math']),eq))
    elif ty=='table': render_table(b)
    elif ty=='figure': render_figure(b)
    elif ty=='pagebreak': story.append(PageBreak())

# ---- шаблон с нумерацией страниц (со второй) ----
def on_page(canvas,doc):
    if doc.page>1:
        canvas.saveState()
        canvas.setFont('Serif',12)
        canvas.drawCentredString(PW/2,BM/2+6,str(doc.page))
        canvas.restoreState()

out='../Лабораторная работа №3 (вариант 12, зачётка 06).pdf'
doc=BaseDocTemplate(out,pagesize=A4,leftMargin=LM,rightMargin=RM,topMargin=TM,bottomMargin=BM,
                    title='Лабораторная работа №3 (вариант 12, зачётка 06)',author='студент гр. БРВ2402')
frame=Frame(LM,BM,FW,PH-TM-BM,id='main',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
doc.addPageTemplates([PageTemplate(id='all',frames=[frame],onPage=on_page)])
doc.build(story)
print('saved',out)
