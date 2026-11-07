#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мини-AST для формул: сериализация в OMML (Word) и в inline-разметку ReportLab (PDF)."""
from xml.sax.saxutils import escape

# ---------- конструкторы узлов ----------
def V(s): return ('r', str(s), 'var')      # переменная (курсив)
def N(s): return ('r', str(s), 'num')      # число (прямой)
def O(s): return ('r', str(s), 'op')       # оператор
def F(s): return ('r', str(s), 'func')     # имя функции (прямой): cos, lg, arctg...
def L(s): return ('r', str(s), 'lbl')      # текстовая метка индекса (прямой): д, бр, max
def ROW(*xs):
    nodes=[]
    for x in xs:
        if isinstance(x,(list,tuple)) and x and isinstance(x[0],str) and x[0] in ('r','row','frac','sub','sup','subsup','sqrt','root','d','nary'):
            nodes.append(x)
        elif isinstance(x,list):
            nodes.extend(x)
        else:
            nodes.append(x)
    return ('row', nodes)
def FRAC(a,b): return ('frac',a,b)
def SUB(a,b): return ('sub',a,b)
def SUP(a,b): return ('sup',a,b)
def SUBSUP(a,b,c): return ('subsup',a,b,c)
def SQRT(a): return ('sqrt',a)
def ROOT(a,n): return ('root',a,n)
def D(a,l='(',r=')'): return ('d',a,l,r)
def NARY(ch,a,b,body): return ('nary',ch,a,b,body)

# удобные короткие обозначения
EQ=O('='); PLUS=O('+'); MINUS=O('−'); MUL=O('·'); COMMA=O(',')

# ---------- OMML ----------
def _mr(text, style):
    text=escape(str(text))
    rpr='<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
    msty='' if style=='var' else '<m:rPr><m:sty m:val="p"/></m:rPr>'
    return f'<m:r>{msty}{rpr}<m:t xml:space="preserve">{text}</m:t></m:r>'

def omml(node):
    k=node[0]
    if k=='r':
        return _mr(node[1],node[2])
    if k=='row':
        return ''.join(omml(x) for x in node[1])
    if k=='frac':
        return f'<m:f><m:num>{omml(node[1])}</m:num><m:den>{omml(node[2])}</m:den></m:f>'
    if k=='sub':
        return f'<m:sSub><m:e>{omml(node[1])}</m:e><m:sub>{omml(node[2])}</m:sub></m:sSub>'
    if k=='sup':
        return f'<m:sSup><m:e>{omml(node[1])}</m:e><m:sup>{omml(node[2])}</m:sup></m:sSup>'
    if k=='subsup':
        return f'<m:sSubSup><m:e>{omml(node[1])}</m:e><m:sub>{omml(node[2])}</m:sub><m:sup>{omml(node[3])}</m:sup></m:sSubSup>'
    if k=='sqrt':
        return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{omml(node[1])}</m:e></m:rad>'
    if k=='root':
        return f'<m:rad><m:radPr/><m:deg>{omml(node[2])}</m:deg><m:e>{omml(node[1])}</m:e></m:rad>'
    if k=='d':
        l=escape(node[2]); r=escape(node[3])
        return (f'<m:d><m:dPr><m:begChr m:val="{l}"/><m:endChr m:val="{r}"/></m:dPr>'
                f'<m:e>{omml(node[1])}</m:e></m:d>')
    if k=='nary':
        ch=escape(node[1])
        return (f'<m:nary><m:naryPr><m:chr m:val="{ch}"/><m:limLoc m:val="undOvr"/></m:naryPr>'
                f'<m:sub>{omml(node[2])}</m:sub><m:sup>{omml(node[3])}</m:sup><m:e>{omml(node[4])}</m:e></m:nary>')
    raise ValueError(node)

def omml_para(node):
    return '<m:oMath>'+omml(node)+'</m:oMath>'

# ---------- inline (ReportLab Paragraph markup) ----------
def _esc(s):
    return escape(str(s))

def _needs_parens(node):
    if node[0]=='row':
        # есть ли на верхнем уровне + или − или пробел-разделённые слагаемые
        for x in node[1]:
            if x[0]=='r' and x[2]=='op' and x[1] in ('+','−','-'):
                return True
        return len(node[1])>1 and any(x[0]=='r' and x[2]=='op' and x[1] in ('+','−') for x in node[1])
    return node[0] in ('frac',)

def inline(node, wrap=False):
    k=node[0]
    if k=='r':
        s=_esc(node[1]); st=node[2]
        if st=='var':
            return f'<i>{s}</i>'
        return s
    if k=='row':
        return ''.join(inline(x) for x in node[1])
    if k=='frac':
        a=inline(node[1]); b=inline(node[2])
        if _needs_parens(node[1]) or node[1][0] in ('frac','row') and len(node[1][1])>2:
            a='('+a+')'
        if _needs_parens(node[2]) or node[2][0]=='frac':
            b='('+b+')'
        return f'{a}/{b}'
    if k=='sub':
        return f'{inline(node[1])}<sub>{inline(node[2])}</sub>'
    if k=='sup':
        base=inline(node[1])
        if node[1][0]=='d' or node[1][0]=='row' and len(node[1][1])>1:
            base=base
        return f'{base}<super>{inline(node[2])}</super>'
    if k=='subsup':
        return f'{inline(node[1])}<sub>{inline(node[2])}</sub><super>{inline(node[3])}</super>'
    if k=='sqrt':
        return f'√({inline(node[1])})'
    if k=='root':
        return f'<super>{inline(node[2])}</super>√({inline(node[1])})'
    if k=='d':
        return f'{_esc(node[2])}{inline(node[1])}{_esc(node[3])}'
    if k=='nary':
        ch=_esc(node[1])
        return f'{ch}<sub>{inline(node[2])}</sub><super>{inline(node[3])}</super>{inline(node[4])}'
    raise ValueError(node)

if __name__=='__main__':
    # тест
    e=FRAC(N(1),ROW(N(1),PLUS,SUP(V('ε'),N(2)),SUP(ROW(F('ch'),D(ROW(V('n'),F('Arch'),V('Ω')))),N(2))))
    print('INLINE:',inline(e))
    print('OMML len:',len(omml_para(e)))
    e2=ROW(V('p'),SUB(V(''),V('k')))
    print(inline(SUB(V('F'),L('д'))))
