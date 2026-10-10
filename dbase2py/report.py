"""REPORT FORM: lê FRM binário do dBASE III PLUS/Clipper ou o formato texto (JSON) deste projeto.

CREATE REPORT/MODIFY REPORT fazem o diálogo do dBASE II e gravam o formato JSON.
"""
import datetime as dt
import json
import struct
from pathlib import Path
from .syntax import XBaseError, split

DEFAULT={'title':[],'width':80,'lines':57,'left':8,'right':0,'double':False,'plain':False,'summary':False,
    'eject_before':True,'eject_after':False,'group':'','group_header':'','subgroup':'','subgroup_header':'','group_eject':False,'columns':[]}


def read_binary(data):
    """FRM de 1990 bytes: expressões, 25 colunas de 12 bytes e parâmetros."""
    lengths=struct.unpack_from('<55H',data,4); offsets=struct.unpack_from('<55H',data,114); pool=data[224:1664]
    def text(index):
        if index<0 or index>=55: return ''
        return pool[offsets[index]:offsets[index]+lengths[index]].split(b'\0',1)[0].decode('cp850','replace')
    page,group,subgroup,group_header,subgroup_header=struct.unpack_from('<5h',data,1964)
    width,lines,left,right,count=struct.unpack_from('<5H',data,1974)
    columns=[]
    for n in range(min(count,25)):
        block=data[1664+12*n:1676+12*n]
        size=struct.unpack_from('<H',block,0)[0]
        if not size: break
        decimals,content,header=struct.unpack_from('<3H',block,6)
        columns.append({'expr':text(content),'width':size,'header':[h for h in text(header).split(';')] if text(header) else [],'decimals':decimals,'total':block[5:6]==b'Y'})
    option=data[1987]
    return {**DEFAULT,'title':[t for t in text(page).split(';')] if text(page) else [],'width':width or 80,'lines':lines or 58,'left':left,'right':right,
        'double':data[1984:1985]==b'Y','summary':data[1985:1986]==b'Y','group_eject':data[1986:1987]==b'Y','eject_before':not option&1,'eject_after':bool(option&2),
        'plain':bool(option&4),'group':text(group),'group_header':text(group_header),'subgroup':text(subgroup),'subgroup_header':text(subgroup_header),'columns':columns}


def load(path):
    data=Path(path).read_bytes()
    if data[:2]==b'\x02\x00' and len(data)>=1988: return read_binary(data)
    try: return {**DEFAULT,**json.loads(data.decode('utf-8'))}
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise XBaseError('Formulário de relatório inválido: '+Path(path).name) from exc


def save(path,definition):
    path=Path(path)
    if path.exists() and path.read_bytes()[:2]==b'\x02\x00': path.replace(path.with_suffix('.fr3'))
    path.write_text(json.dumps(definition,ensure_ascii=False,indent=2),encoding='utf-8')


def yes(answer): return str(answer).strip()[:1].upper() in ('Y','S','T')


def dialog(engine,definition=None):
    """Perguntas do REPORT do dBASE II (curso MarMSX), em português."""
    d={**DEFAULT,**(definition or {})}; ask=engine.input
    options=ask(f"Entre opções, M=margem esq. ({d['left']}), L=linhas/pág. ({d['lines']}), W=largura pág. ({d['width']}): ")
    for item in split(options.replace(' ',',')) if options.strip() else []:
        key,_,value=item.partition('=')
        if key.upper() in ('M','L','W') and value.strip().isdigit(): d[{'M':'left','L':'lines','W':'width'}[key.upper()]]=int(value)
    if yes(ask('Cabeçalho (Y/N) ? ')): d['title']=ask('Entre com o cabeçalho da página: ').split(';')
    d['double']=yes(ask('Relatório com espaço duplo (Y/N) ? '))
    totals=yes(ask('Totais requeridos (Y/N) ? '))
    d['group']=d['group_header']=''
    if totals:
        d['group']=ask('Subtotal por campo/expressão (Enter = nenhum): ').strip()
        if d['group']:
            d['summary']=yes(ask('Somente resumo (Y/N) ? '))
            d['group_eject']=yes(ask('Saltar página após subtotal (Y/N) ? '))
            d['group_header']=ask('Entre com o cabeçalho do subtotal: ')
    columns=[]
    engine.emit('Coluna, Tamanho, Conteúdo')
    while True:
        spec=ask(f'{len(columns)+1:03}     ').strip()
        if not spec: break
        width,_,content=spec.partition(',')
        if not width.strip().isdigit() or not content.strip(): engine.emit('Use largura,conteúdo. Ex: 30,NOME'); continue
        value=engine.expr(content.strip()) if engine.area in engine.areas else ''
        numeric=isinstance(value,(int,float)) and not isinstance(value,bool)
        column={'expr':content.strip(),'width':int(width),'header':ask('Entre com o cabeçalho: ').split(';'),'decimals':getattr(value,'decimals',0) if numeric else 0,'total':False}
        if totals and numeric: column['total']=yes(ask('Totalizar (Y/N) ? '))
        columns.append(column)
    if not columns: raise XBaseError('Relatório sem colunas.')
    d['columns']=columns
    return d


def cell(engine,column,value):
    width=column['width']
    if isinstance(value,bool): text='.T.' if value else '.F.'
    elif isinstance(value,(int,float)): return (f"{value:.{column['decimals']}f}" if column['decimals'] else str(int(round(value))) if float(value).is_integer() else str(value)).rjust(width)[-width:]
    elif isinstance(value,dt.date): text=engine.format(value)
    else: text=str(value).replace('\n',' ')
    return text[:width].ljust(width)


def render(engine,d,rows,write,heading='',plain=False,noeject=False,summary=False,to_printer=False):
    """Escreve o relatório: cabeçalho de página, colunas, subtotais e total geral."""
    plain=plain or d['plain']; summary=summary or d['summary']
    margin=' '*d['left']; area=max(10,d['width']-d['left']-d['right'])
    columns=d['columns']; height=max(1,max((len(c['header']) for c in columns),default=1))
    state={'page':0,'line':0}
    def out(text=''):
        write(margin+text.rstrip()); state['line']+=1
    def header():
        state['page']+=1
        if state['page']>1 or to_printer and d['eject_before'] and not noeject: write('\f'); state['line']=0
        if not plain:
            out(f"Página No. {state['page']:5}"+('   '+heading if heading else ''))
            out(engine.format(dt.date.today()))
            out()
        elif heading and state['page']==1: out(heading)
        for title in d['title']:
            title=title.rstrip()
            if title.startswith('<'): out(title[1:])
            elif title.startswith('>'): out(title[1:].strip().rjust(area))
            else: out(title.strip().center(area))
        if d['title']: out()
        for n in range(height):
            parts=[]
            for c in columns:
                lines=c['header']+['']*(height-len(c['header']))
                text=lines[n][:c['width']]
                parts.append(text.rjust(c['width']) if c['total'] else text.ljust(c['width']))
            out(' '.join(parts))
        out()
    def check_page():
        if state['line']==0 or not plain and state['line']>=d['lines']-2: header()
    def totals_line(label,values):
        check_page()
        parts=[]
        for c,v in zip(columns,values):
            parts.append(cell(engine,c,v) if c['total'] else ' '*c['width'])
        out(label); out(' '.join(parts))
    grand=[0]*len(columns); group=[0]*len(columns); current=None; started=False
    header()
    for row in rows:
        engine.position(row)
        if d['group']:
            key=engine.expr(d['group'],row)
            if not started or key!=current:
                if started:
                    totals_line('** Subtotal **',group); group=[0]*len(columns)
                    if d['group_eject']: state['line']=0
                current=key; started=True; check_page()
                out('** '+(d['group_header']+' ' if d['group_header'] else '')+engine.format(key).strip())
        values=[engine.expr(c['expr'],row) for c in columns]
        for i,(c,v) in enumerate(zip(columns,values)):
            if c['total'] and isinstance(v,(int,float)) and not isinstance(v,bool): grand[i]+=v; group[i]+=v
        if not summary:
            check_page(); out(' '.join(cell(engine,c,v) for c,v in zip(columns,values)))
            if d['double']: out()
    if started: totals_line('** Subtotal **',group)
    if any(c['total'] for c in columns): out(); totals_line('*** Total ***',grand)
    if to_printer and d['eject_after']: write('\f')
