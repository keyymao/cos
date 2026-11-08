#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка .pdf ЛР №6 (вариант 24 / зачётка 53) из content.blocks.

Тот же набор пунктов и то же оформление, что в build_docx.py; формулы
набираются в строку, крупные дроби — «в две строки», как в образце.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)

import content  # локальный content.py

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mathast import inline  # noqa: E402

FD = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, fn in [
    ("Serif", "STIXGeneral.ttf"), ("Serif-B", "STIXGeneralBol.ttf"),
    ("Serif-I", "STIXGeneralItalic.ttf"), ("Serif-BI", "STIXGeneralBolIta.ttf"),
]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FD, fn)))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B",
                              italic="Serif-I", boldItalic="Serif-BI")

PW, PH = A4
LM, RM, TM, BM = 3.0 * cm, 1.5 * cm, 2.0 * cm, 2.0 * cm
FW = PW - LM - RM

body = ParagraphStyle("body", fontName="Serif", fontSize=14, leading=21,
                      alignment=TA_JUSTIFY, firstLineIndent=1.25 * cm)
plain = ParagraphStyle("plain", fontName="Serif", fontSize=14, leading=21, alignment=TA_LEFT)
h1 = ParagraphStyle("h1", fontName="Serif-B", fontSize=14, leading=21,
                    alignment=TA_LEFT, firstLineIndent=1.25 * cm, spaceAfter=12)
cap = ParagraphStyle("cap", fontName="Serif", fontSize=14, leading=21,
                     alignment=TA_CENTER, spaceBefore=4, spaceAfter=10)
eq = ParagraphStyle("eq", fontName="Serif", fontSize=12.5, leading=18,
                    alignment=TA_CENTER, spaceBefore=6, spaceAfter=6)
eqfrac = ParagraphStyle("eqfrac", fontName="Serif", fontSize=11.5, leading=15,
                        alignment=TA_CENTER)
eqside = ParagraphStyle("eqside", fontName="Serif", fontSize=12.5, leading=18,
                        alignment=TA_CENTER)
note = ParagraphStyle("note", fontName="Serif-I", fontSize=11.5, leading=15,
                      alignment=TA_CENTER, textColor=colors.HexColor("#808080"))
tc = ParagraphStyle("tc", fontName="Serif", fontSize=14, leading=18, alignment=TA_CENTER)
tcb = ParagraphStyle("tcb", fontName="Serif-B", fontSize=14, leading=18, alignment=TA_CENTER)
tl = ParagraphStyle("tl", fontName="Serif", fontSize=14, leading=18, alignment=TA_LEFT)
tcap = ParagraphStyle("tcap", fontName="Serif", fontSize=14, leading=21, alignment=TA_LEFT,
                      firstLineIndent=1.25 * cm, spaceBefore=6, spaceAfter=3, keepWithNext=1)
cell = ParagraphStyle("cell", fontName="Serif", fontSize=11.5, leading=14, alignment=TA_CENTER)
cellb = ParagraphStyle("cellb", fontName="Serif-B", fontSize=11.5, leading=14, alignment=TA_CENTER)

story: list = []


def render_title():
    for line in [
        "Министерство цифрового развития, связи и массовых коммуникаций",
        "Российской Федерации",
        "Ордена Трудового Красного Знамени федеральное государственное",
        "бюджетное образовательное учреждение высшего образования",
        "Московский технический университет связи и информатики",
        "Кафедра «Радиотехнических систем»",
    ]:
        story.append(Paragraph(line, tc))
    story.append(Spacer(1, 62))
    story.append(Paragraph("Лабораторная работа №6", tcb))
    story.append(Paragraph("«СИНТЕЗ ЦИФРОВЫХ КИХ-ФИЛЬТРОВ", tcb))
    story.append(Paragraph("МЕТОДОМ ОКОН С ПРИМЕНЕНИЕМ ОКНА КАЙЗЕРА»", tcb))
    story.append(Spacer(1, 52))
    story.append(Paragraph("По дисциплине:", tc))
    story.append(Paragraph("«Цифровая обработка сигналов»", tc))
    story.append(Spacer(1, 40))
    story.append(Paragraph("Выполнил:", tl))
    story.append(Paragraph("Студент гр. БРВ2402__________________________________ № зачётки 53", tl))
    story.append(Spacer(1, 26))
    story.append(Paragraph("Проверил:", tl))
    story.append(Paragraph("Преподаватель______________________________________ Варламов В.О.", tl))
    story.append(Spacer(1, 52))
    story.append(Paragraph("Москва 2026", tc))


def _frac_table(frac, max_w):
    """Дробь «в две строки»: числитель, черта, знаменатель."""
    num = inline(frac[1])
    den = inline(frac[2])
    if len(den) > 60:
        den = den.replace(")(", ")<br/>(")

    def measured(markup):
        widths = [stringWidth(re.sub(r"<[^>]+>", "", part), "Serif", 11.5)
                  for part in markup.split("<br/>")]
        return max(widths)

    inner_w = min(max_w, max(1.6 * cm, max(measured(num), measured(den)) + 0.5 * cm))
    inner = Table(
        [[Paragraph(num, eqfrac)], [Paragraph(den, eqfrac)]],
        colWidths=[inner_w], hAlign="CENTER",
    )
    inner.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.7, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]))
    return inner, inner_w


def render_eq(b):
    """Формула по центру; дроби рисуются «в две строки», остальное — в строку."""
    node = b["math"]
    parts = node[1] if node[0] == "row" else [node]
    if not b.get("stack", True) or not any(x[0] == "frac" for x in parts):
        story.append(Paragraph(inline(node), eq))
        return

    max_frac_w = 11.0 * cm
    chunks, widths, buf = [], [], []

    def flush():
        if buf:
            text = inline(("row", list(buf)))
            w = max(stringWidth(re.sub(r"<[^>]+>", "", part), "Serif", 12.5)
                    for part in text.split("<br/>"))
            chunks.append(Paragraph(text, eqside))
            widths.append(w + 0.1 * cm)
            buf.clear()

    for x in parts:
        if x[0] == "frac":
            flush()
            table, w = _frac_table(x, max_frac_w)
            chunks.append(table)
            widths.append(w + 0.15 * cm)
        elif x[0] == "d" and any(y[0] == "frac" for y in x[1][1]):
            # скобки вокруг дроби не нужны
            for y in x[1][1]:
                if y[0] == "frac":
                    flush()
                    table, w = _frac_table(y, max_frac_w)
                    chunks.append(table)
                    widths.append(w + 0.15 * cm)
                else:
                    buf.append(y)
        else:
            buf.append(x)
    flush()

    outer = Table([chunks], colWidths=widths, hAlign="CENTER")
    outer.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(Spacer(1, 6))
    story.append(outer)
    story.append(Spacer(1, 6))


def render_table(b):
    headers, rows, widths = b["headers"], b["rows"], b.get("widths")
    story.append(Paragraph(b["caption"], tcap))
    data = [[Paragraph(h, cellb) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell) for c in row])
    cw = [w * cm for w in widths] if widths else [FW / len(headers)] * len(headers)
    t = Table(data, colWidths=cw, hAlign="CENTER", repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(Spacer(1, 6))
    story.append(t)
    story.append(Spacer(1, 8))


def render_figure(b):
    from PIL import Image as PILImage
    path, width, cap_text = b["path"], b["width"], b["caption"]
    iw, ih = PILImage.open(path).size
    w = width * cm
    h = w * ih / iw
    max_h = PH - TM - BM - 7 * cm
    if h > max_h:
        h = max_h
        w = h * iw / ih
    img = Image(path, width=w, height=h)
    img.hAlign = "CENTER"
    story.append(Spacer(1, 6))
    story.append(KeepTogether([img] + ([Paragraph(cap_text, cap)] if cap_text else [])))


def render_figcap(text):
    story.append(KeepTogether([
        Spacer(1, 14),
        Paragraph("[место для скриншота из «Спектр-2»]", note),
        Spacer(1, 12),
        Paragraph(text, cap),
    ]))


for b in content.blocks:
    ty = b["type"]
    if ty == "title":
        render_title()
    elif ty == "h1":
        story.append(Paragraph(b["text"], h1))
    elif ty == "p":
        story.append(Paragraph(b["text"], body))
    elif ty == "plain":
        story.append(Paragraph(b["text"], plain))
    elif ty == "eq":
        render_eq(b)
    elif ty == "table":
        render_table(b)
    elif ty == "figure":
        render_figure(b)
    elif ty == "figcap":
        render_figcap(b["text"])
    elif ty == "pagebreak":
        story.append(PageBreak())
    else:
        raise ValueError(ty)


def on_page(canvas, doc):
    if doc.page > 1:
        canvas.saveState()
        canvas.setFont("Serif", 12)
        canvas.drawCentredString(PW / 2, BM / 2 + 6, str(doc.page))
        canvas.restoreState()


OUT = (Path(__file__).resolve().parent.parent.parent / "лабораторные" / "лаба6"
       / "Лабораторная работа №6 (вариант 24, зачётка 53).pdf")
doc = BaseDocTemplate(
    str(OUT), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM,
    title="Лабораторная работа №6 (вариант 24, зачётка 53)", author="студент гр. БРВ2402",
)
frame = Frame(LM, BM, FW, PH - TM - BM, id="main",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])
doc.build(story)
print("saved", OUT)
