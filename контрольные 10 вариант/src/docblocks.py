# -*- coding: utf-8 -*-
"""
Блоки документа для контрольных работ по ЦОС.

Здесь строится только *содержание* (список блоков), а оформление выполняют
рендереры: docxkit.py (Word) и pdfkit.py (PDF). Благодаря этому .docx и .pdf
всегда собираются из одних и тех же данных.
"""
from __future__ import annotations

TITLE_LINES = [
    "Министерство цифрового развития, связи и массовых коммуникаций",
    "Российской Федерации",
    "Ордена Трудового Красного Знамени федеральное государственное",
    "бюджетное образовательное учреждение высшего образования",
    "Московский технический университет связи и информатики",
    "Кафедра «Радиотехнических систем»",
]


class Doc:
    """Накопитель блоков документа."""

    def __init__(self, work: str, theme: str, variant: str,
                 group: str = "____________", fio: str = "____________________",
                 city: str = "Москва 2026"):
        self.work = work
        self.theme = theme
        self.variant = variant
        self.group = group
        self.fio = fio
        self.city = city
        self.blocks: list[dict] = []

    # ------------------------------ титул ---------------------------------
    def title(self):
        self.blocks.append({"type": "title", "work": self.work, "theme": self.theme,
                            "variant": self.variant, "group": self.group,
                            "fio": self.fio, "city": self.city, "lines": TITLE_LINES})

    # --------------------------- текст и формулы --------------------------
    def h1(self, text: str):
        self.blocks.append({"type": "h1", "text": text})

    def h2(self, text: str):
        self.blocks.append({"type": "h2", "text": text})

    def p(self, text: str):
        self.blocks.append({"type": "p", "text": text})

    def lead(self, text: str):
        self.blocks.append({"type": "p", "text": text, "indent": False})

    def bullets(self, items):
        for it in items:
            self.blocks.append({"type": "bullet", "text": it})

    def eq(self, node):
        self.blocks.append({"type": "eq", "math": node})

    def eq_text(self, text: str):
        self.blocks.append({"type": "eq", "text": text})

    def table(self, caption: str, headers, rows, widths=None, size=12, align_center=True):
        self.blocks.append({"type": "table", "caption": caption, "headers": list(headers),
                            "rows": [list(map(str, r)) for r in rows],
                            "widths": widths, "size": size, "align_center": align_center})

    def figure(self, path, caption: str, width_cm: float = 15.0):
        self.blocks.append({"type": "figure", "path": str(path), "caption": caption,
                            "width_cm": width_cm})

    def code(self, text: str):
        self.blocks.append({"type": "code", "text": text})

    def pagebreak(self):
        self.blocks.append({"type": "pagebreak"})
