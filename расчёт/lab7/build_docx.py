#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Построение .docx из content.blocks (Word-формулы OMML, таблицы, рисунки)."""
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree
import content
from mathast import omml_para

FONT='Times New Roman'; SZ=14
doc=Document()
# ---- базовый стиль ----
st=doc.styles['Normal']; st.font.name=FONT; st.font.size=Pt(SZ)
st.element.rPr.rFonts.set(qn('w:eastAsia'),FONT); st.element.rPr.rFonts.set(qn('w:cs'),FONT)
pf=st.paragraph_format; pf.space_after=Pt(0); pf.space_before=Pt(0); pf.line_spacing=1.5
sec=doc.sections[0]
sec.page_width=Cm(21.0); sec.page_height=Cm(29.7)
sec.top_margin=Cm(2.0); sec.bottom_margin=Cm(2.0); sec.left_margin=Cm(3.0); sec.right_margin=Cm(1.5)
sec.different_first_page_header_footer=True

M_NS='http://schemas.openxmlformats.org/officeDocument/2006/math'
W_NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def set_run(r,bold=False,italic=False,sub=False,sup=False,size=SZ):
    r.font.name=FONT; r.font.size=Pt(size); r.bold=bold; r.italic=italic
    rpr=r._element.get_or_add_rPr(); rf=rpr.find(qn('w:rFonts'))
    if rf is None:
        rf=OxmlElement('w:rFonts'); rpr.append(rf)
    for a in ('w:ascii','w:hAnsi','w:cs','w:eastAsia'): rf.set(qn(a),FONT)
    if sub: r.font.subscript=True
    if sup: r.font.superscript=True

TOKEN=re.compile(r'(<sub>|</sub>|<super>|</super>|<i>|</i>|<b>|</b>)')
def add_markup(p,text,size=SZ,base_bold=False):
    state={'sub':False,'sup':False,'i':False,'b':base_bold}
    parts=TOKEN.split(text)
    for part in parts:
        if part in ('<sub>','<super>','<i>','<b>'):
            state[{'<sub>':'sub','<super>':'sup','<i>':'i','<b>':'b'}[part]]=True
        elif part in ('</sub>','</super>','</i>','</b>'):
            state[{'</sub>':'sub','</super>':'sup','</i>':'i','</b>':'b'}[part]]=False
        elif part:
            r=p.add_run(part)
            set_run(r,bold=state['b'],italic=state['i'],sub=state['sub'],sup=state['sup'],size=size)

def body(text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    pf=p.paragraph_format; pf.line_spacing=1.5; pf.first_line_indent=Cm(1.25); pf.space_after=Pt(0); pf.space_before=Pt(0)
    add_markup(p,text); return p

def h1(text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    pf=p.paragraph_format; pf.line_spacing=1.5; pf.space_before=Pt(12); pf.space_after=Pt(12); pf.first_line_indent=Cm(0); pf.keep_with_next=True
    r=p.add_run(text); set_run(r,bold=True); return p

def h2(text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
    pf=p.paragraph_format; pf.line_spacing=1.5; pf.space_before=Pt(10); pf.space_after=Pt(4); pf.first_line_indent=Cm(0); pf.keep_with_next=True
    r=p.add_run(text); set_run(r,bold=True); return p

def equation(node):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    pf=p.paragraph_format; pf.line_spacing=1.0; pf.space_before=Pt(4); pf.space_after=Pt(4); pf.first_line_indent=Cm(0)
    xml=f'<root xmlns:m="{M_NS}" xmlns:w="{W_NS}">{omml_para(node)}</root>'
    el=etree.fromstring(xml.encode('utf-8'))
    om=el.find(f'{{{M_NS}}}oMath')
    p._p.append(om)
    return p

def shade(cell,fill):
    tcPr=cell._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd')
    sh.set(qn('w:val'),'clear'); sh.set(qn('w:fill'),fill); tcPr.append(sh)

def set_borders(table):
    tbl=table._tbl; tblPr=tbl.tblPr; borders=OxmlElement('w:tblBorders')
    for edge in ('top','left','bottom','right','insideH','insideV'):
        e=OxmlElement(f'w:{edge}'); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'6'); e.set(qn('w:color'),'000000'); borders.append(e)
    tblPr.append(borders)

def table(cap,headers,rows,widths):
    cp=doc.add_paragraph(); cp.alignment=WD_ALIGN_PARAGRAPH.LEFT
    cpf=cp.paragraph_format; cpf.line_spacing=1.5; cpf.space_before=Pt(6); cpf.space_after=Pt(2); cpf.first_line_indent=Cm(1.25)
    r=cp.add_run(cap); set_run(r)
    t=doc.add_table(rows=1,cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER
    set_borders(t)
    hdr=t.rows[0].cells
    trPr=t.rows[0]._tr.get_or_add_trPr()
    tbl_header=OxmlElement('w:tblHeader'); tbl_header.set(qn('w:val'),'true'); trPr.append(tbl_header)
    for i,htext in enumerate(headers):
        shade(hdr[i],'E8E8E8')
        p=hdr[i].paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing=1.0; p.paragraph_format.space_after=Pt(0)
        r=p.add_run(htext); set_run(r,bold=True,size=12)
    for row in rows:
        cells=t.add_row().cells
        for i,val in enumerate(row):
            p=cells[i].paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing=1.0; p.paragraph_format.space_after=Pt(0)
            r=p.add_run(str(val)); set_run(r,size=12)
    if widths:
        for i,w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width=Cm(w)
    # пустая строка после таблицы
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
    return t

def figure(path,cap,width):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(6); p.paragraph_format.space_after=Pt(2); p.paragraph_format.first_line_indent=Cm(0)
    p.paragraph_format.keep_with_next=True
    r=p.add_run(); r.add_picture(path,width=Cm(width))
    cp=doc.add_paragraph(); cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.line_spacing=1.0; cp.paragraph_format.space_before=Pt(2); cp.paragraph_format.space_after=Pt(10); cp.paragraph_format.first_line_indent=Cm(0)
    r=cp.add_run(cap); set_run(r,size=13)

def pagebreak():
    doc.add_page_break()

def title(dd):
    def cp(text,bold=False,size=SZ,before=0,after=0):
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        pf=p.paragraph_format; pf.line_spacing=1.15; pf.space_before=Pt(before); pf.space_after=Pt(after); pf.first_line_indent=Cm(0)
        r=p.add_run(text); set_run(r,bold=bold,size=size); return p
    def lp(text,before=0,after=0):
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.LEFT
        pf=p.paragraph_format; pf.line_spacing=1.15; pf.space_before=Pt(before); pf.space_after=Pt(after); pf.first_line_indent=Cm(0)
        r=p.add_run(text); set_run(r); return p
    for line in ['Министерство цифрового развития, связи и массовых коммуникаций',
                 'Российской Федерации',
                 'Ордена Трудового Красного Знамени федеральное государственное',
                 'бюджетное образовательное учреждение высшего образования',
                 'Московский технический университет связи и информатики',
                 'Кафедра «Радиотехнических систем»']:
        cp(line)
    cp('',before=42)
    cp('Лабораторная работа №7',bold=True,before=28)
    cp('«ДИСКРЕТНОЕ ПРЕОБРАЗОВАНИЕ ФУРЬЕ.',bold=True)
    cp('АЛГОРИТМ БЫСТРОГО ПРЕОБРАЗОВАНИЯ ФУРЬЕ',bold=True)
    cp('КУЛИ–ТЬЮКИ»',bold=True)
    cp('',before=34)
    cp('По дисциплине:',before=28)
    cp('«Цифровая обработка сигналов»')
    cp('',before=42)
    lp('Выполнил:',before=34)
    lp('студент гр. БРВ2402 ______________  № зачётки 06')
    lp('Проверил:',before=18)
    lp('преподаватель ______________  Варламов В.О.')
    cp('',before=54)
    cp('Москва 2026',before=40)
    doc.add_page_break()

# ---- нумерация страниц (со второй) ----
def add_page_number():
    footer=sec.footer
    p=footer.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent=Cm(0)
    run=p.add_run(); set_run(run,size=12)
    fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE')
    r=OxmlElement('w:r'); rpr=OxmlElement('w:rPr')
    rf=OxmlElement('w:rFonts'); rf.set(qn('w:ascii'),FONT); rf.set(qn('w:hAnsi'),FONT); rpr.append(rf)
    sz=OxmlElement('w:sz'); sz.set(qn('w:val'),'24'); rpr.append(sz); r.append(rpr)
    t=OxmlElement('w:t'); t.text='2'; r.append(t); fld.append(r); p._p.append(fld)
add_page_number()

# ---- рендеринг ----
for b in content.blocks:
    ty=b['type']
    if ty=='title': title(b['data'])
    elif ty=='h1': h1(b['text'])
    elif ty=='h2': h2(b['text'])
    elif ty=='p': body(b['text'])
    elif ty=='eq': equation(b['math'])
    elif ty=='table': table(b['caption'],b['headers'],b['rows'],b.get('widths'))
    elif ty=='figure': figure(b['path'],b['caption'],b['width'])
    elif ty=='pagebreak': pagebreak()

out = (Path(__file__).resolve().parent.parent.parent / 'лабораторные' / 'лаба7'
       / 'Лабораторная работа №7 (вариант 12, зачётка 06).docx')
doc.save(out)
print('saved', out)
