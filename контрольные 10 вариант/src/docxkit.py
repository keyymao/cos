# -*- coding: utf-8 -*-
"""
Рендерер блоков Doc в .docx (Word) для контрольных работ по ЦОС.

Формулы собираются как настоящие Word-формулы (OMML) через расчёт/mathast.py.
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
from docx.shared import Cm, Pt
from lxml import etree

MATH_DIR = Path(__file__).resolve().parents[2] / "расчёт"
if str(MATH_DIR) not in sys.path:
    sys.path.insert(0, str(MATH_DIR))
from mathast import omml_para  # noqa: E402

FONT = "Times New Roman"
MONO = "Courier New"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SZ = 14


def _set_run(run, bold=False, italic=False, sub=False, sup=False, size=SZ, font=FONT):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(attr), font)
    if sub:
        run.font.subscript = True
    if sup:
        run.font.superscript = True


TOKEN = re.compile(r"(<sub>|</sub>|<super>|</super>|<i>|</i>|<b>|</b>)")


def add_markup(p, text, size=SZ, font=FONT, bold=False, italic=False):
    """Добавляет текст с простой разметкой (<sub>, <super>, <i>, <b>)."""
    state = {"sub": False, "sup": False, "i": italic, "b": bold}
    for part in TOKEN.split(str(text)):
        if part in ("<sub>", "<super>", "<i>", "<b>"):
            state[{"<sub>": "sub", "<super>": "sup", "<i>": "i", "<b>": "b"}[part]] = True
        elif part in ("</sub>", "</super>", "</i>", "</b>"):
            state[{"</sub>": "sub", "</super>": "sup", "</i>": "i", "</b>": "b"}[part]] = False
        elif part:
            r = p.add_run(part)
            _set_run(r, bold=state["b"], italic=state["i"], sub=state["sub"],
                     sup=state["sup"], size=size, font=font)


class Report:
    """Рендерер блоков Doc в .docx."""

    def __init__(self, doc_obj):
        self.doc = Document()
        self.src = doc_obj
        st = self.doc.styles["Normal"]
        st.font.name = FONT
        st.font.size = Pt(SZ)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.element.rPr.rFonts.set(qn("w:cs"), FONT)
        pf = st.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing = 1.5

        sec = self.doc.sections[0]
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.0)
        sec.bottom_margin = Cm(2.0)
        sec.left_margin = Cm(3.0)
        sec.right_margin = Cm(1.5)
        self.sec = sec
        self._page_numbers()

    # ------------------------------ служебное ------------------------------
    def _page_numbers(self):
        p = self.sec.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
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

    def _p(self, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=Cm(1.25), spacing=1.5,
           before=0, after=0, keep_next=False, keep_together=True):
        p = self.doc.add_paragraph()
        p.alignment = align
        pf = p.paragraph_format
        pf.line_spacing = spacing
        pf.first_line_indent = indent
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.keep_with_next = keep_next
        pf.keep_together = keep_together
        return p

    # ------------------------------ элементы -------------------------------
    def title(self, b):
        for line in b["lines"]:
            p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.0, 0, 0)
            r = p.add_run(line)
            _set_run(r, size=13)
        for txt, bold, size in ((b["work"], True, 16),
                                ("по дисциплине «Цифровая обработка сигналов»", False, 14)):
            p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.15, 24, 6)
            r = p.add_run(txt)
            _set_run(r, bold=bold, size=size)
        for line in b["theme"].split("\n"):
            p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.15, 0, 0)
            r = p.add_run(line)
            _set_run(r, bold=True)
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.15, 24, 24)
        r = p.add_run(f"ВАРИАНТ {b['variant']}")
        _set_run(r, bold=True, size=15)
        for txt in (f"№ группы  {b['group']}", f"ФИО  {b['fio']}"):
            p = self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(0), 1.15, 4, 4)
            r = p.add_run(txt)
            _set_run(r)
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.0, 100, 0)
        r = p.add_run(b["city"])
        _set_run(r)
        self.doc.add_page_break()

    def h1(self, text):
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.5, 12, 10, keep_next=True)
        add_markup(p, text, bold=True)

    def h2(self, text):
        p = self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(0), 1.5, 10, 6, keep_next=True)
        add_markup(p, text, bold=True)

    def p(self, text, indent=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        add_markup(self._p(align, Cm(1.25) if indent else Cm(0)), text)

    def bullet(self, text):
        p = self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(0), 1.5, 0, 0)
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.4)
        add_markup(p, f"• {text}")

    def eq(self, node):
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.0, 4, 4)
        xml = f'<root xmlns:m="{M_NS}" xmlns:w="{W_NS}">{omml_para(node)}</root>'
        el = etree.fromstring(xml.encode("utf-8"))
        p._p.append(el.find(f"{{{M_NS}}}oMath"))

    def eq_text(self, text):
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.0, 4, 4)
        add_markup(p, text)

    def caption(self, text, kind="Рисунок"):
        p = self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(1.25), 1.15, 10 if kind == "Таблица" else 4,
                    3 if kind == "Таблица" else 10, keep_next=(kind == "Таблица"))
        add_markup(p, text, size=12)

    def table(self, b):
        if b["caption"]:
            self.caption(b["caption"], "Таблица")
        headers, rows, size = b["headers"], b["rows"], b["size"]
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "6")
            e.set(qn("w:color"), "000000")
            borders.append(e)
        t._tbl.tblPr.append(borders)

        hdr = t.rows[0]
        trPr = hdr._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trPr.append(th)
        for i, htext in enumerate(headers):
            cell = hdr.cells[i]
            tcPr = cell._tc.get_or_add_tcPr()
            sh = OxmlElement("w:shd")
            sh.set(qn("w:val"), "clear")
            sh.set(qn("w:fill"), "EDEDED")
            tcPr.append(sh)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.first_line_indent = Cm(0)
            add_markup(p, str(htext), size=size, bold=True)
        for row in rows:
            tr = t.add_row()
            tr._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            for i, val in enumerate(row):
                p = tr.cells[i].paragraphs[0]
                p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if b["align_center"]
                               else WD_ALIGN_PARAGRAPH.LEFT)
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.first_line_indent = Cm(0)
                add_markup(p, str(val), size=size)
        if b["widths"]:
            for i, w in enumerate(b["widths"]):
                for row in t.rows:
                    row.cells[i].width = Cm(w)
        self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(0), 1.0, 0, 0)

    def figure(self, b):
        p = self._p(WD_ALIGN_PARAGRAPH.CENTER, Cm(0), 1.0, 8, 2, keep_next=True)
        p.add_run().add_picture(b["path"], width=Cm(b["width_cm"]))
        self.caption(b["caption"], "Рисунок")

    def code(self, text: str, size=9):
        for line in text.rstrip("\n").split("\n"):
            p = self._p(WD_ALIGN_PARAGRAPH.LEFT, Cm(0), 1.0, 0, 0)
            r = p.add_run(line if line.strip() else " ")
            _set_run(r, size=size, font=MONO)

    def pagebreak(self):
        self.doc.add_page_break()

    # ------------------------------ сборка --------------------------------
    def render(self):
        dispatch = {
            "title": self.title,
            "h1": lambda b: self.h1(b["text"]),
            "h2": lambda b: self.h2(b["text"]),
            "p": lambda b: self.p(b["text"], b.get("indent", True)),
            "bullet": lambda b: self.bullet(b["text"]),
            "eq": lambda b: self.eq(b["math"]) if b.get("math") else self.eq_text(b["text"]),
            "table": self.table,
            "figure": self.figure,
            "code": lambda b: self.code(b["text"]),
            "pagebreak": lambda b: self.pagebreak(),
        }
        for b in self.src.blocks:
            dispatch[b["type"]](b)
        return self

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path))
        return path
