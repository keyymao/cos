#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Хелперы для сборки .docx (Word-формулы OMML, таблицы, рисунки, листинги).
Шрифт Times New Roman 14, A4, поля 3/1.5/2/2 см, выравнивание по ширине, интервал 1.5.
Использует расчёт/mathast.py для OMML-формул.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "расчёт"))
from mathast import omml_para  # noqa: E402

FONT = "Times New Roman"
SZ = 14
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_doc():
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
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(3.0)
    sec.right_margin = Cm(1.5)
    return doc, sec


def set_run(r, bold=False, italic=False, sub=False, sup=False, size=SZ):
    r.font.name = FONT
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
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


TOKEN = re.compile(r"(<sub>|</sub>|<super>|</super>|<i>|</i>|<b>|</b>)")


def add_markup(p, text, size=SZ, base_bold=False):
    state = {"sub": False, "sup": False, "i": False, "b": base_bold}
    parts = TOKEN.split(text)
    for part in parts:
        if part in ("<sub>", "<super>", "<i>", "<b>"):
            state[{"<sub>": "sub", "<super>": "sup", "<i>": "i", "<b>": "b"}[part]] = True
        elif part in ("</sub>", "</super>", "</i>", "</b>"):
            state[{"</sub>": "sub", "</super>": "sup", "</i>": "i", "</b>": "b"}[part]] = False
        elif part:
            r = p.add_run(part)
            set_run(r, bold=state["b"], italic=state["i"], sub=state["sub"], sup=state["sup"], size=size)


class Doc:
    def __init__(self):
        self.doc, self.sec = make_doc()

    def body(self, text, indent=True):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.first_line_indent = Cm(1.25) if indent else Cm(0)
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        add_markup(p, text)
        return p

    def h1(self, text):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.space_before = Pt(12)
        pf.space_after = Pt(12)
        pf.first_line_indent = Cm(0)
        r = p.add_run(text)
        set_run(r, bold=True)
        return p

    def h2(self, text):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.space_before = Pt(10)
        pf.space_after = Pt(4)
        pf.first_line_indent = Cm(0)
        r = p.add_run(text)
        set_run(r, bold=True)
        return p

    def center(self, text, bold=False, size=SZ, before=0, after=0):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.line_spacing = 1.15
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.first_line_indent = Cm(0)
        r = p.add_run(text)
        set_run(r, bold=bold, size=size)
        return p

    def left(self, text, before=0, after=0):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf = p.paragraph_format
        pf.line_spacing = 1.15
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.first_line_indent = Cm(0)
        r = p.add_run(text)
        set_run(r)
        return p

    def equation(self, node):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.line_spacing = 1.0
        pf.space_before = Pt(4)
        pf.space_after = Pt(4)
        pf.first_line_indent = Cm(0)
        xml = f'<root xmlns:m="{M_NS}" xmlns:w="{W_NS}">{omml_para(node)}</root>'
        el = etree.fromstring(xml.encode("utf-8"))
        om = el.find(f"{{{M_NS}}}oMath")
        p._p.append(om)
        return p

    @staticmethod
    def shade(cell, fill):
        tcPr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear")
        sh.set(qn("w:fill"), fill)
        tcPr.append(sh)

    @staticmethod
    def set_borders(table):
        tbl = table._tbl
        tblPr = tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "6")
            e.set(qn("w:color"), "000000")
            borders.append(e)
        tblPr.append(borders)

    def table(self, cap, headers, rows, widths=None, size=12):
        cp = self.doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cpf = cp.paragraph_format
        cpf.line_spacing = 1.5
        cpf.space_before = Pt(6)
        cpf.space_after = Pt(2)
        cpf.first_line_indent = Cm(1.25)
        r = cp.add_run(cap)
        set_run(r)
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        self.set_borders(t)
        hdr = t.rows[0].cells
        for i, htext in enumerate(headers):
            self.shade(hdr[i], "E8E8E8")
            p = hdr[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(htext)
            set_run(r, bold=True, size=size)
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                p = cells[i].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_after = Pt(0)
                add_markup(p, str(val), size=size)
        if widths:
            for i, w in enumerate(widths):
                for row in t.rows:
                    row.cells[i].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)
        return t

    def figure(self, path, cap, width):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.first_line_indent = Cm(0)
        r = p.add_run()
        r.add_picture(str(path), width=Cm(width))
        cp = self.doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.line_spacing = 1.0
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(10)
        cp.paragraph_format.first_line_indent = Cm(0)
        r = cp.add_run(cap)
        set_run(r, size=13)

    def pagebreak(self):
        self.doc.add_page_break()

    def code_listing(self, path, size=8):
        """Листинг файла моноширинным шрифтом."""
        text = Path(path).read_text(encoding="utf-8")
        for line in text.rstrip("\n").split("\n"):
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.line_spacing = 1.0
            pf.space_after = Pt(0)
            pf.space_before = Pt(0)
            pf.first_line_indent = Cm(0)
            r = p.add_run(line if line else " ")
            r.font.name = "Consolas"
            r.font.size = Pt(size)
            rpr = r._element.get_or_add_rPr()
            rf = rpr.find(qn("w:rFonts"))
            if rf is None:
                rf = OxmlElement("w:rFonts")
                rpr.append(rf)
            for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rf.set(qn(a), "Consolas")

    def page_numbers(self):
        footer = self.sec.footer
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
        t.text = "1"
        r.append(t)
        fld.append(r)
        p._p.append(fld)

    def save(self, path):
        self.doc.save(str(path))
        print("saved", path)


def ru(x, d=4):
    """Число -> строка с русской десятичной запятой."""
    return f"{x:.{d}f}".replace(".", ",")
