"""LABEL FORM: etiquetas do dBASE III PLUS (.LBL binário) ou formato JSON deste projeto.

CREATE LABEL/MODIFY LABEL fazem um diálogo de dimensões e linhas e gravam JSON.
"""
import json
import struct
from pathlib import Path
from .syntax import XBaseError, split

DEFAULT={'remarks':'','height':5,'width':35,'left':0,'lines_between':1,'spaces_between':0,'across':1,'lines':[]}


def read_binary(data):
    """LBL de 1034 bytes: observação, dimensões e 16 linhas de 60 caracteres."""
    remarks=data[1:61].decode('cp850','replace').rstrip()
    height,width,left,lines_between,spaces_between,across=struct.unpack_from('<6H',data,61)
    lines=[data[73+60*i:133+60*i].decode('cp850','replace').rstrip(' \0') for i in range(16)]
    return {**DEFAULT,'remarks':remarks,'height':height or 1,'width':width or 35,'left':left,'lines_between':lines_between,
        'spaces_between':spaces_between,'across':across or 1,'lines':lines[:height or 1]}


def load(path):
    data=Path(path).read_bytes()
    if data[:1]==b'\x02' and len(data)>=1033: return read_binary(data)
    try: return {**DEFAULT,**json.loads(data.decode('utf-8'))}
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise XBaseError('Formulário de etiquetas inválido: '+Path(path).name) from exc


def save(path,definition):
    path=Path(path)
    if path.exists() and path.read_bytes()[:1]==b'\x02': path.replace(path.with_suffix('.lb3'))
    path.write_text(json.dumps(definition,ensure_ascii=False,indent=2),encoding='utf-8')


def dialog(engine,definition=None):
    d={**DEFAULT,**(definition or {})}; ask=engine.input
    for key,label in (('width','Largura da etiqueta'),('height','Altura (linhas)'),('left','Margem esquerda'),
            ('lines_between','Linhas entre etiquetas'),('spaces_between','Espaços entre etiquetas'),('across','Etiquetas por linha')):
        answer=ask(f'{label} ({d[key]}): ').strip()
        if answer:
            if not answer.isdigit(): raise XBaseError(label+' deve ser número.')
            d[key]=int(answer)
    if not 1<=d['height']<=16 or not 1<=d['width']<=120 or not 1<=d['across']<=5: raise XBaseError('Etiqueta: altura 1-16, largura 1-120, 1-5 por linha.')
    engine.emit('Conteúdo de cada linha (expressões separadas por vírgula; Enter mantém).')
    lines=[]
    for n in range(d['height']):
        current=d['lines'][n] if n<len(d['lines']) else ''
        answer=ask(f'{n+1:2}: {current} > ')
        lines.append(answer if answer.strip() else current)
    d['lines']=lines
    return d


def line_text(engine,expression,row):
    """Itens separados por vírgula são aparados e unidos por um espaço, como no dBASE III."""
    if not expression.strip(): return ''
    parts=[]
    for item in split(expression):
        value=engine.expr(item,row)
        text=value.strip() if isinstance(value,str) else engine.format(value).strip()
        if text: parts.append(text)
    return ' '.join(parts)


def render(engine,d,rows,write,sample=False):
    margin=' '*d['left']; width=d['width']; gap=' '*d['spaces_between']
    def block(labels):
        for n in range(d['height']):
            write((margin+gap.join(label[n][:width].ljust(width) for label in labels)).rstrip())
        for _ in range(d['lines_between']): write('')
    if sample: block([['X'*width]*d['height']]*d['across'])
    pending=[]
    for row in rows:
        engine.position(row)
        # Linhas vazias sobem, como no LABEL FORM do dBASE III PLUS.
        lines=[t for t in (line_text(engine,e,row) for e in d['lines'][:d['height']]) if t]
        pending.append(lines+['']*(d['height']-len(lines)))
        if len(pending)==d['across']: block(pending); pending=[]
    if pending: block(pending+[['']*d['height']]*(d['across']-len(pending)))
