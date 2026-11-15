# -*- coding: utf-8 -*-
"""
Рендерер блоков Doc в .pdf (ReportLab + DejaVu Serif).

Формулы OMML отображаются в PDF линейной записью (та же формула, но без
двухэтажных дробей) — это соответствует виду формул в бланке задания и не
требует встроенного движка TeX.
"""
from __future__ import annotations

import html as _html
import os
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Preformatted, Spacer, Table,
                                TableStyle)

FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, fn in [("Serif", "DejaVuSerif.ttf"), ("Serif-B", "DejaVuSerif-Bold.ttf"),
                 ("Serif-I", "DejaVuSerif-Italic.ttf"),
                 ("Serif-BI", "DejaVuSerif-BoldItalic.ttf"),
                 ("Mono", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, fn)))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif-I",
                              boldItalic="Serif-BI")

PW, PH = A4
LM, RM, TM, BM = 3.0 * cm, 1.5 * cm, 2.0 * cm, 2.0 * cm
FW = PW - LM - RM

body = ParagraphStyle("body", fontName="Serif", fontSize=12, leading=18, alignment=TA_JUSTIFY,
                      firstLineIndent=1.1 * cm)
body_ni = ParagraphStyle("body_ni", parent=body, firstLineIndent=0)
bullet = ParagraphStyle("bullet", parent=body_ni, alignment=TA_LEFT, leftIndent=0.8 * cm,
                        bulletIndent=0.2 * cm)
h1 = ParagraphStyle("h1", fontName="Serif-B", fontSize=13, leading=19, alignment=TA_CENTER,
                    spaceBefore=12, spaceAfter=8)
h2 = ParagraphStyle("h2", fontName="Serif-B", fontSize=12, leading=18, alignment=TA_LEFT,
                    spaceBefore=10, spaceAfter=4)
eq = ParagraphStyle("eq", fontName="Serif", fontSize=11, leading=16, alignment=TA_CENTER,
                    spaceBefore=4, spaceAfter=4)
tcap = ParagraphStyle("tcap", fontName="Serif", fontSize=10.5, leading=14, alignment=TA_LEFT,
                      firstLineIndent=1.1 * cm, spaceBefore=6, spaceAfter=2)
fcap = ParagraphStyle("fcap", fontName="Serif", fontSize=10.5, leading=14, alignment=TA_LEFT,
                      firstLineIndent=1.1 * cm, spaceBefore=2, spaceAfter=8)
cell = ParagraphStyle("cell", fontName="Serif", fontSize=9, leading=11, alignment=TA_CENTER)
cellb = ParagraphStyle("cellb", fontName="Serif-B", fontSize=9, leading=11, alignment=TA_CENTER)
tc = ParagraphStyle("tc", fontName="Serif", fontSize=11, leading=15, alignment=TA_CENTER)
tcb = ParagraphStyle("tcb", fontName="Serif-B", fontSize=15, leading=20, alignment=TA_CENTER)
code = ParagraphStyle("code", fontName="Mono", fontSize=6.4, leading=7.4, alignment=TA_LEFT)

_OPS_SPACE = {"=", "+", "−", "-", "±", "≥", "≤", "≠", "<", ">", "≈", "·", "×", ","}


def _markup(text: str) -> str:
    """Перевод простой разметки (<sub>, <super>, <i>, <b>) в теги ReportLab."""
    s = _html.unescape(str(text))
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for tag in ("sub", "super", "i", "b"):
        s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    return s


# ------------------------- линейная запись формул -------------------------
def _is_op(node, chars) -> bool:
    return node[0] == "r" and node[2] == "op" and node[1] in chars


def _tight(node) -> str:
    """Индекс/показатель без лишних пробелов: «−1», «n−1»."""
    s = linear(node)
    return s.replace(" ", "") if len(s) <= 5 else s


def linear(node) -> str:
    """Линейная (однострочная) запись формулы для PDF."""
    k = node[0]
    if k == "r":
        txt = _html.escape(str(node[1]))
        return f"<i>{txt}</i>" if node[2] == "var" else txt
    if k == "row":
        out = []
        for x in node[1]:
            if x[0] == "r" and x[2] == "op" and x[1] in _OPS_SPACE and x[1] != "·":
                out.append(f" {_html.escape(x[1])} ")
            elif _is_op(x, {"·", "×"}):
                out.append("·")
            else:
                out.append(linear(x))
        s = "".join(out)
        while "  " in s:
            s = s.replace("  ", " ")
        return s.strip()
    if k == "frac":
        num, den = node[1], node[2]
        a, b = linear(num), linear(den)
        for part, txt in ((num, a), (den, b)):
            if part[0] in ("row", "frac") or any(
                    _is_op(x, {"+", "−", "-", "±"}) for x in (part[1] if part[0] == "row" else [])):
                pass
        if num[0] in ("row", "frac") or any(_is_op(x, {"+", "−", "-", "±"}) for x in
                                            (num[1] if num[0] == "row" else [])):
            a = f"({a})"
        if den[0] in ("row", "frac") or any(_is_op(x, {"+", "−", "-", "±"}) for x in
                                            (den[1] if den[0] == "row" else [])):
            b = f"({b})"
        return f"{a}/{b}"
    if k == "sub":
        return f"{linear(node[1])}<sub>{_tight(node[2])}</sub>"
    if k == "sup":
        return f"{linear(node[1])}<super>{_tight(node[2])}</super>"
    if k == "subsup":
        return (f"{linear(node[1])}<sub>{_tight(node[2])}</sub>"
                f"<super>{_tight(node[3])}</super>")
    if k == "sqrt":
        return f"√({linear(node[1])})"
    if k == "root":
        return f"<super>{_tight(node[2])}</super>√({linear(node[1])})"
    if k == "d":
        return f"{_html.escape(node[2])}{linear(node[1])}{_html.escape(node[3])}"
    if k == "nary":
        return (f"{_html.escape(node[1])}<sub>{_tight(node[2])}</sub>"
                f"<super>{_tight(node[3])}</super>{linear(node[4])}")
    raise ValueError(node)


class PdfReport:
    """Рендерер блоков Doc в PDF."""

    def __init__(self, doc_obj, title: str = ""):
        self.src = doc_obj
        self._title_text = title
        self.story: list = []

    def title(self, b):
        for line in b["lines"]:
            self.story.append(Paragraph(_markup(line), tc))
        self.story.append(Spacer(1, 34))
        self.story.append(Paragraph(_markup(b["work"]), tcb))
        self.story.append(Paragraph("по дисциплине «Цифровая обработка сигналов»", tc))
        self.story.append(Spacer(1, 10))
        for line in b["theme"].split("\n"):
            self.story.append(Paragraph(_markup(line), ParagraphStyle(
                "tt", parent=tc, fontName="Serif-B", fontSize=12.5, leading=17)))
        self.story.append(Spacer(1, 26))
        self.story.append(Paragraph(f"ВАРИАНТ {b['variant']}", ParagraphStyle(
            "v", parent=tcb, fontSize=14)))
        self.story.append(Spacer(1, 26))
        for txt in (f"№ группы  {b['group']}", f"ФИО  {b['fio']}"):
            self.story.append(Paragraph(_markup(txt), ParagraphStyle(
                "l", parent=tc, alignment=TA_LEFT, fontSize=12)))
        self.story.append(Spacer(1, 110))
        self.story.append(Paragraph(_markup(b["city"]), tc))
        self.story.append(PageBreak())

    def table(self, b):
        fl = []
        if b["caption"]:
            fl.append(Paragraph(_markup(b["caption"]), tcap))
        data = [[Paragraph(_markup(h), cellb) for h in b["headers"]]]
        for row in b["rows"]:
            data.append([Paragraph(_markup(c), cell) for c in row])
        widths = ([w * cm for w in b["widths"]] if b["widths"]
                  else [FW / len(b["headers"])] * len(b["headers"]))
        scale = FW / sum(widths)
        if scale < 1:
            widths = [w * scale for w in widths]
        t = Table(data, colWidths=widths, hAlign="CENTER", repeatRows=1)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        fl.append(t)
        fl.append(Spacer(1, 8))
        self.story.append(KeepTogether(fl))

    def figure(self, b):
        path = Path(b["path"])
        iw, ih = ImageReader(str(path)).getSize()
        width = b["width_cm"] * cm
        height = width * ih / iw
        max_h = 12.0 * cm
        if height > max_h:
            height = max_h
            width = height * iw / ih
        self.story.append(KeepTogether([
            Spacer(1, 4),
            Image(str(path), width=width, height=height),
            Paragraph(_markup(b["caption"]), fcap),
        ]))

    def code(self, text: str, per_page: int = 58):
        """Листинг: страница целиком отдаётся коду, чтобы не оставалось пустых листов."""
        lines = text.rstrip("\n").split("\n")
        n_pages = max(1, -(-len(lines) // per_page))
        step = -(-len(lines) // n_pages)          # ровные страницы без «хвостиков»
        for i, start in enumerate(range(0, len(lines), step)):
            chunk = "\n".join(line[:120] for line in lines[start:start + step])
            if i:
                self.story.append(PageBreak())
            self.story.append(Preformatted(chunk, code, maxLineLength=118))

    def render(self):
        dispatch = {
            "title": self.title,
            "h1": lambda b: self.story.append(Paragraph(_markup(b["text"]), h1)),
            "h2": lambda b: self.story.append(Paragraph(_markup(b["text"]), h2)),
            "p": lambda b: self.story.append(Paragraph(
                _markup(b["text"]), body if b.get("indent", True) else body_ni)),
            "bullet": lambda b: self.story.append(Paragraph(_markup("• " + b["text"]), bullet)),
            "eq": lambda b: self.story.append(Paragraph(
                _markup(linear(b["math"])) if b.get("math") else _markup(b["text"]), eq)),
            "table": self.table,
            "figure": self.figure,
            "code": lambda b: self.code(b["text"]),
            "pagebreak": lambda b: self.story.append(PageBreak()),
        }
        for b in self.src.blocks:
            dispatch[b["type"]](b)
        return self

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        def on_page(canvas, doc):
            if doc.page > 1:
                canvas.saveState()
                canvas.setFont("Serif", 10)
                canvas.drawCentredString(PW / 2, BM / 2, str(doc.page))
                canvas.restoreState()

        doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=LM, rightMargin=RM,
                              topMargin=TM, bottomMargin=BM, title=self._title_text)
        frame = Frame(LM, BM, FW, PH - TM - BM, id="main", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])
        doc.build(self.story)
        return path
