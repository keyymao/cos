#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка .docx ЛР №4 (вариант 24 / зачётка 53) из content.blocks.

Оформление повторяет образец `лаба №3.pdf`: A4, Times New Roman 14,
интервал 1,5, отступ 1,25 см, заголовки разделов жирным по левому краю,
каждый раздел с новой страницы. Формулы — объекты Word (OMML).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from lxml import etree

import content  # локальный content.py

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mathast import omml_para  # noqa: E402

FONT = "Times New Roman"
SZ = 14
OUT = Path(__file__).resolve().parent.parent.parent / "Лабораторная работа №4 (вариант 24, зачётка 53).docx"

doc = Document()
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(SZ)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.element.rPr.rFonts.set(qn("w:cs"), FONT)
pf = st.paragraph_format
pf.space_after = Pt(0)
pf.space_before = Pt(0)
pf.line_spacing = 1.5
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
sec.left_margin, sec.right_margin = Cm(3.0), Cm(1.5)
sec.different_first_page_header_footer = True

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def set_run(r, bold=False, italic=False, sub=False, sup=False, size=SZ, gray=False):
    r.font.name = FONT
    r.font.size = Pt(size)
    r.bold, r.italic = bold, italic
    rpr = r._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), FONT)
    if sub:
        r.font.subscript = True
    if sup:
        r.font.superscript = True
    if gray:
        r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


TOKEN = re.compile(r"(<sub>|</sub>|<super>|</super>|<i>|</i>|<b>|</b>)")


def add_markup(p, text, size=SZ, base_bold=False, base_italic=False, gray=False):
    state = {"sub": False, "sup": False, "i": base_italic, "b": base_bold}
    for part in TOKEN.split(text):
        if part in ("<sub>", "<super>", "<i>", "<b>"):
            state[{"<sub>": "sub", "<super>": "sup", "<i>": "i", "<b>": "b"}[part]] = True
        elif part in ("</sub>", "</super>", "</i>", "</b>"):
            state[{"</sub>": "sub", "</super>": "sup", "</i>": "i", "</b>": "b"}[part]] = False
        elif part:
            r = p.add_run(part)
            set_run(r, bold=state["b"], italic=state["i"], sub=state["sub"],
                    sup=state["sup"], size=size, gray=gray)


def body(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    f = p.paragraph_format
    f.line_spacing, f.first_line_indent = 1.5, Cm(1.25)
    f.space_after = f.space_before = Pt(0)
    add_markup(p, text)
    return p


def plain(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    f = p.paragraph_format
    f.line_spacing = 1.5
    f.first_line_indent = Cm(0)
    f.space_after = f.space_before = Pt(0)
    add_markup(p, text)
    return p


def heading(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    f = p.paragraph_format
    f.line_spacing = 1.5
    f.first_line_indent = Cm(1.25)
    f.space_before, f.space_after = Pt(0), Pt(12)
    f.keep_with_next = True
    add_markup(p, text, base_bold=True)
    return p


def caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f = p.paragraph_format
    f.line_spacing = 1.5
    f.first_line_indent = Cm(0)
    f.space_before, f.space_after = Pt(4), Pt(10)
    add_markup(p, text)
    return p


def figure_placeholder(cap_text):
    """Пустое место под скриншот + подпись; всё держится вместе."""
    for _ in range(3):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    add_markup(p, "[место для скриншота из «Спектр-2»]", size=12,
               base_italic=True, gray=True)
    for _ in range(2):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
    cp = caption(cap_text)
    cp.paragraph_format.keep_with_next = False


def equation(node):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f = p.paragraph_format
    f.line_spacing = 1.0
    f.space_before = f.space_after = Pt(6)
    f.first_line_indent = Cm(0)
    f.keep_together = True
    xml = f'<root xmlns:m="{M_NS}" xmlns:w="{W_NS}">{omml_para(node)}</root>'
    el = etree.fromstring(xml.encode("utf-8"))
    p._p.append(el.find(f"{{{M_NS}}}oMath"))
    return p


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), fill)
    tcPr.append(sh)


def set_borders(table):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:color"), "000000")
        borders.append(e)
    table._tbl.tblPr.append(borders)


def table(headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_borders(t)
    hdr = t.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for i, htext in enumerate(headers):
        cell = hdr.cells[i]
        shade(cell, "E8E8E8")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        add_markup(p, htext, size=12, base_bold=True)
    for row in rows:
        tr = t.add_row()
        trPr = tr._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        for i, val in enumerate(row):
            p = tr.cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            add_markup(p, str(val), size=12)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def title():
    def cp(text, bold=False, before=0, after=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f = p.paragraph_format
        f.line_spacing, f.first_line_indent = 1.15, Cm(0)
        f.space_before, f.space_after = Pt(before), Pt(after)
        add_markup(p, text, base_bold=bold)
        return p

    def lp(text, before=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        f = p.paragraph_format
        f.line_spacing, f.first_line_indent = 1.15, Cm(0)
        f.space_before, f.space_after = Pt(before), Pt(0)
        add_markup(p, text)
        return p

    for line in [
        "Министерство цифрового развития, связи и массовых коммуникаций",
        "Российской Федерации",
        "Ордена Трудового Красного Знамени федеральное государственное",
        "бюджетное образовательное учреждение высшего образования",
        "Московский технический университет связи и информатики",
        "Кафедра «Радиотехнических систем»",
    ]:
        cp(line)
    cp("", before=34)
    cp("Лабораторная работа №4", bold=True)
    cp("«СИНТЕЗ ЦИФРОВЫХ БИХ-ФИЛЬТРОВ", bold=True)
    cp("МЕТОДОМ БИЛИНЕЙНОГО Z-ПРЕОБРАЗОВАНИЯ С ВНЕСЕНИЕМ", bold=True)
    cp("ПРЕДЫСКАЖЕНИЙ»", bold=True)
    cp("", before=26)
    cp("По дисциплине:")
    cp("«Цифровая обработка сигналов»")
    cp("", before=30)
    lp("Выполнил:", before=20)
    lp("Студент гр. БРВ2402__________________________________ № зачётки 53")
    lp("Проверил:", before=26)
    lp("Преподаватель______________________________________ Варламов В.О.")
    cp("", before=40)
    cp("Москва 2026")


def add_page_number():
    footer = sec.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    set_run(run, size=12)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:ascii"), FONT)
    rf.set(qn("w:hAnsi"), FONT)
    rpr.append(rf)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "24")
    rpr.append(sz)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = "2"
    r.append(t)
    fld.append(r)
    p._p.append(fld)


add_page_number()
for b in content.blocks:
    ty = b["type"]
    if ty == "title":
        title()
    elif ty == "h1":
        heading(b["text"])
    elif ty == "p":
        body(b["text"])
    elif ty == "plain":
        plain(b["text"])
    elif ty == "eq":
        equation(b["math"])
    elif ty == "table":
        table(b["headers"], b["rows"], b.get("widths"))
    elif ty == "figcap":
        figure_placeholder(b["text"])
    elif ty == "pagebreak":
        doc.add_page_break()
    else:
        raise ValueError(ty)

doc.save(OUT)
print("saved", OUT)
