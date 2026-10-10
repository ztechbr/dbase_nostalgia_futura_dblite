"""Interpretador dBASE II/III PLUS sobre o armazenamento SQLite da versão 1."""
import bisect
import datetime as dt
import itertools
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from .storage import DBaseEngine as StorageEngine, Field
from .syntax import XBaseError, split, clauses, outside_words, uncomment, command_parts, subscript, lex, COMMANDS
from .memory import Memory, Cell, XArray
from .expressions import Expression
from .functions import functions, EMPTY_DATE, ctod, dtoc, str_value, xround, FieldInt, FieldFloat
from .program import Program, Routine, execute_nodes, ReturnSignal, LoopSignal, ExitSignal, CancelSignal, RetrySignal, ReturnMasterSignal

# Comandos SET aceitos apenas para que programas legados rodem; o valor fica em DISPLAY STATUS.
SET_STORED={'BELL','ESCAPE','STATUS','SCOREBOARD','ECHO','STEP','DEBUG','MENU','MENUS','HELP','HISTORY','DOHISTORY','TYPEAHEAD','CLOCK','FUNCTION','CATALOG','VIEW','ENCRYPTION','TITLE','AUTOSAVE','SCREEN','RAW','EXCLUSIVE','MEMOWIDTH','INSTRUCT','LOCK','REPROCESS','REFRESH','RETRY','PAUSE','NEAR','WRAP','ODOMETER','SPACE','HOURS','MARK','POINT','SEPARATOR','CURRENCY','PRECISION','FULLPATH','DESIGN','DISPLAY','BORDER','SQL','SKIP','EXPORT'}
DIALECTS=('DBASE2','DBASE3')
BARE_FUNCTIONS=('EOF','BOF','DELETED','RECNO','DATE','TIME','FOUND','RECCOUNT')


class DBaseEngine(StorageEngine):
    def __init__(self,cwd='.',output=print,input_fn=input,plain=False,encoding='auto',max_steps=100000,max_depth=64,key_reader=None,dialect='DBASE3',monitor='NENHUM'):
        super().__init__(cwd,output,input_fn)
        self.variables=Memory()
        self.key_reader=key_reader
        self.settings={'CONFIRM':False,'TALK':True,'SAFETY':True,'CONSOLE':True,'ALTERNATE':False,'DATE':'AMERICAN','CENTURY':False,'DECIMALS':2,'DELETED':False,'EXACT':False,'UNIQUE':False,'SOFTSEEK':False,
            'LINKAGE':False,'CARRY':False,'DELIMITERS':True,'DELIMITER_CHARS':'::','INTENSITY':True,'BELL':True,'HEADING':True,'FIXED':False,'MARGIN':0,'PRINT':False,'PRINTER':'impressora.txt','DEVICE':'SCREEN',
            'MESSAGE':'','PATH':'','DEFAULT':'','FIELDS':'','DIALECT':dialect.upper()}
        if self.settings['DIALECT'] not in DIALECTS: raise XBaseError('Dialeto desconhecido: '+dialect)
        self.plain,self.encoding=plain,encoding
        self.max_steps,self.max_depth=max_steps,max_depth
        self.steps=0; self.calls=[]; self.procedure_program=None; self.format_program=None
        self.screen_row=self.screen_col=0; self.screen=[[' ']*80 for _ in range(25)]
        self.gets=[]; self.prompts=[]; self.form_record=None; self.last_key=0; self.alternate=None; self.printer=None; self.printer_row=self.printer_col=0
        self.compiled={}; self._syncing=set(); self.warnings=[]
        self.on_error=''; self.handling_error=False; self.last_error=None
        self._functions=functions(self)
        self.monitor_scheme=self.scheme=None; self.set_monitor(monitor)

    @property
    def dbase2(self): return self.settings['DIALECT']=='DBASE2'

    def path(self,name,suffix='.sqlite',search=True):
        name=str(name).strip()
        if name.startswith(('"',"'",'[')):
            from .syntax import lex
            tokens=lex(name)
            if tokens[0].kind!='string' or tokens[1].kind!='end': raise XBaseError('Nome de arquivo inválido.')
            name=tokens[0].value
        name=name.replace('\\','/')
        # Unidade DOS/MSX relativa (B:VENDA) aponta para o diretório de trabalho.
        name=re.sub(r'^[A-Za-z]:(?!/)','',name)
        if Path(name).suffix.lower()=='.dbf': name=str(Path(name).with_suffix('.sqlite'))
        candidates=[name]
        if search and not Path(name).is_absolute() and '/' not in name:
            # SET DEFAULT e SET PATH são subdiretórios dentro de --cwd.
            folders=[self.settings['DEFAULT']]+[p for p in re.split(r'[;,]',self.settings['PATH']) if p.strip()]
            candidates=[str(Path(d.strip().replace('\\','/'))/name) if d.strip() else name for d in folders]
        found=None
        for candidate in candidates:
            p=super().path(candidate,suffix)
            if not p.exists() and p.parent.exists():
                matches=[f for f in p.parent.iterdir() if f.name.casefold()==p.name.casefold()]
                if len(matches)==1: p=matches[0].resolve()
            if not p.is_relative_to(self.cwd): raise XBaseError('Caminho fora do diretório de trabalho.')
            if found is None: found=p
            if p.exists(): return p
        return found

    def set_monitor(self,name):
        """SET MONITOR TO VERDE|AMBAR|BRANCO|CORES|NENHUM: fósforo verde/âmbar/branco sobre fundo preto."""
        from .colors import monitor_scheme, color_scheme
        self.monitor_scheme=monitor_scheme(name); self.settings['MONITOR']=name.upper()
        self.scheme=color_scheme(self.settings['COLOR'],self.monitor_scheme) if self.settings.get('COLOR') else self.monitor_scheme

    def interactive(self):
        """Edição por tecla: teclas injetadas ou console real nas duas pontas, sem --plain."""
        return self.key_reader is not None or self.input is input and not self.plain and sys.stdin.isatty() and sys.stdout.isatty()

    def paint(self,kind='standard'):
        if self.plain or not self.scheme: return ''
        return self.scheme.get(kind) or self.scheme['standard']

    def styled(self,text,kind):
        """Texto na cor do esquema; sem esquema, o realce continua sendo vídeo reverso."""
        if not self.scheme: return '\033[7m'+text+'\033[0m' if kind=='enhanced' else text
        return self.paint(kind)+text+self.paint()

    def close(self):
        if self.scheme and not self.plain: self.emit('\033[0m',False); self.scheme=None
        super().close()
        if self.alternate: self.alternate.close(); self.alternate=None
        if self.printer: self.printer.close(); self.printer=None

    def tick(self):
        self.steps+=1
        if self.steps>self.max_steps: raise XBaseError(f'Limite global de {self.max_steps} passos excedido.')

    def area_number(self,name):
        if isinstance(name,(int,float)) or str(name).isdigit():
            n=int(name)
            if n==0: return next((i for i in range(1,11) if i not in self.areas),1)
            if not 1<=n<=10: raise XBaseError('dBASE III PLUS usa áreas de 1 a 10.')
            return n
        name=str(name).upper()
        if name in ('PRIMARY','SECONDARY'): return 1 if name=='PRIMARY' else 2
        for n,s in self.areas.items():
            if s['alias'].upper()==name: return n
        if len(name)==1 and name in 'ABCDEFGHIJ': return ord(name)-ord('A')+1
        # dBASE II: P.campo e S.campo referenciam as áreas primária e secundária.
        if name in ('P','S'): return 1 if name=='P' else 2
        raise XBaseError('Área/alias desconhecido: '+name)

    def fields(self):
        s=self.state
        if 'fields' not in s: s['fields']=super().fields()
        return s['fields']

    def view(self):
        """Registros tipados na ordem do índice controlador, sem filtro, reaproveitados até a próxima escrita."""
        s=self.state; db=s['db']
        key=(db.total_changes,db.execute('PRAGMA data_version').fetchone()[0],s['order'],bool(s.get('unique_order')))
        cache=s.get('cache')
        if cache and cache['key']==key: return cache
        rows=[self.typed(r) for r in db.execute('SELECT * FROM records ORDER BY _recno')]
        count=len(rows); keys=None
        if s['order']:
            keys=[self.expr(s['order'],r) for r in rows]
            try: order=sorted(range(count),key=lambda i:(keys[i],rows[i]['_recno']))
            except TypeError as exc: raise XBaseError('Chave de índice com tipos misturados: '+s['order']) from exc
            rows=[rows[i] for i in order]; keys=[keys[i] for i in order]
            if s.get('unique_order'):
                kept=[i for i in range(count) if i==0 or keys[i]!=keys[i-1]]
                rows=[rows[i] for i in kept]; keys=[keys[i] for i in kept]
        cache={'key':key,'rows':rows,'keys':keys,'pos':{r['_recno']:i for i,r in enumerate(rows)},'count':count}
        s['cache']=cache
        return cache

    def write_record(self,recno,values):
        """Atualiza um registro da área atual e ajusta o cache sem reler a tabela."""
        if not values: return
        s=self.state; db=s['db']; cache=s.get('cache')
        fresh=cache is not None and cache['key'][0]==db.total_changes
        with db: db.execute('UPDATE records SET '+','.join('"'+k+'"=?' for k in values)+' WHERE _recno=?',[*values.values(),recno])
        if not fresh or recno not in cache['pos']: return
        i=cache['pos'][recno]; row=dict(cache['rows'][i]); row.update(self.typed(values))
        if cache['keys'] is not None:
            key=self.expr(s['order'],row)
            if key!=cache['keys'][i]:
                if s.get('unique_order'): return
                del cache['rows'][i]; del cache['keys'][i]
                at=bisect.bisect_left([(k,r['_recno']) for k,r in zip(cache['keys'],cache['rows'])],(key,recno))
                cache['rows'].insert(at,row); cache['keys'].insert(at,key)
                cache['pos']={r['_recno']:n for n,r in enumerate(cache['rows'])}
            else: cache['rows'][i]=row
        else: cache['rows'][i]=row
        cache['key']=(db.total_changes,)+cache['key'][1:]

    def record_count(self): return self.view()['count']
    def eof(self): return self.state['pointer']>self.record_count() or self.record_count()==0
    def bof(self): return self.state.get('bof',False) or self.record_count()==0

    def typed(self,row):
        row=dict(row)
        for f in self.fields():
            if f.name not in row: continue
            if f.type=='D': row[f.name]=dt.date.fromisoformat(row[f.name]) if row[f.name] else EMPTY_DATE
            elif f.type=='L': row[f.name]=bool(row[f.name])
            elif f.type=='N': row[f.name]=FieldFloat(row[f.name],f.length,f.decimals) if f.decimals else FieldInt(int(row[f.name]),f.length)
            elif f.type=='C': row[f.name]=row[f.name].ljust(f.length)
        return row

    def current(self):
        self.sync_relations()
        cache=self.view(); i=cache['pos'].get(self.state['pointer'])
        if i is not None: return cache['rows'][i]
        # Registro oculto por índice UNIQUE continua acessível por GO.
        r=self.state['db'].execute('SELECT * FROM records WHERE _recno=?',(self.state['pointer'],)).fetchone()
        return self.typed(r) if r else {}

    def visible(self,row):
        s=self.state
        if self.deleted and row['_deleted']: return False
        return not s['filter'] or bool(self.expr(s['filter'],row))

    def rows(self,visible=True):
        rows=self.view()['rows']
        return [r for r in rows if self.visible(r)] if visible else list(rows)

    def linked(self):
        """SET LINKAGE do dBASE II: áreas primária e secundária andam juntas."""
        return self.settings['LINKAGE'] and self.area in (1,2) and 3-self.area in self.areas

    def position(self,row):
        """Posiciona o ponteiro no registro avaliado quando outras áreas dependem dele."""
        if self.state.get('relations') or self.linked(): self.move(row['_recno'])

    def coerce(self,f,value):
        if f.type=='D':
            if value==EMPTY_DATE or value=='': return ''
            if isinstance(value,dt.date): return value.isoformat()
            return ctod(self,value).isoformat()
        if f.type=='C':
            value=str(value)
            # REPLACE no dBASE III PLUS trunca caracteres e preenche o campo.
            return value[:f.length].ljust(f.length)
        if f.type=='N':
            number=xround(float(value),f.decimals)
            if len(f'{number:.{f.decimals}f}')>f.length: raise XBaseError('Número excede largura: '+f.name)
            return int(number) if not f.decimals else number
        return super().coerce(f,value)

    def resolve(self,name,row=None,alias=None):
        name=name.upper()
        if alias in ('M','MEMVAR'):
            try: return self.variables[name]
            except KeyError: raise XBaseError('Variável desconhecida: '+name)
        if alias:
            old=self.area
            try:
                self.area=self.area_number(alias)
                r=self.current(); fs={f.name:f for f in self.fields()}
                if name not in fs: raise XBaseError('Campo desconhecido: '+alias+'->'+name)
                return r.get(name,self.blank_value(fs[name]))
            finally: self.area=old
        r=row if row is not None else self.current() if self.area in self.areas else {}
        if name in r: return r[name]
        if self.area in self.areas:
            fs={f.name:f for f in self.fields()}
            if name in fs: return self.blank_value(fs[name])
        try: return self.variables[name]
        except KeyError: pass
        # dBASE II escreve EOF, BOF, DATE etc. sem parênteses.
        if name in BARE_FUNCTIONS: return self.function(name,[],row)
        raise XBaseError('Campo/variável desconhecido: '+name)

    def blank_value(self,f): return EMPTY_DATE if f.type=='D' else False if f.type=='L' else 0 if f.type=='N' else ' '*f.length if f.type=='C' else ''

    def type_code(self,value):
        if isinstance(value,XArray): return 'A'
        return 'L' if isinstance(value,bool) else 'D' if isinstance(value,dt.date) else 'N' if isinstance(value,(int,float)) else 'C' if isinstance(value,str) else 'U'

    # Arrays (dBASE IV, Clipper e FoxPro)
    def make_array(self,items): return XArray(items)

    def date_literal(self,text): return ctod(self,text) if any(c.isdigit() for c in text) else EMPTY_DATE

    def array_variable(self,name):
        try: value=self.variables[name]
        except KeyError: return None
        return value if isinstance(value,XArray) else None

    def element(self,array,indexes,parent=False):
        """Elemento arr[i,j]; com parent=True devolve (lista, posição) para gravação."""
        if not isinstance(array,XArray): raise XBaseError('Índice aplicado a algo que não é array.')
        for depth,index in enumerate(indexes):
            if isinstance(index,bool) or not isinstance(index,(int,float)): raise XBaseError('Índice de array deve ser numérico.')
            n=int(index)
            if not 1<=n<=len(array): raise XBaseError(f'Índice {n} fora dos limites do array (1..{len(array)}).')
            if parent and depth==len(indexes)-1: return array,n-1
            array=array[n-1]
            if depth<len(indexes)-1 and not isinstance(array,XArray): raise XBaseError('Array tem menos dimensões que os índices.')
        return array

    def set_element(self,target,value):
        """Grava em arr[i], arr[i,j], arr[i][j] ou arr(i)."""
        expression=Expression(self.expand(target)); tree=expression.tree
        if tree[0]=='call':
            array=self.array_variable(tree[1])
            if array is None: raise XBaseError('Array desconhecido: '+tree[1])
            indexes=[expression.evaluate(self,node=n) for n in tree[2]]
        elif tree[0]=='index':
            array=expression.evaluate(self,node=tree[1]); indexes=[expression.evaluate(self,node=n) for n in tree[2]]
        else: raise XBaseError('Destino de array inválido: '+target)
        container,position=self.element(array,indexes,True)
        container[position]=value

    def element_target(self,text):
        """Reconhece 'arr[...]' ou 'arr(...)' (array existente) no início de uma atribuição."""
        tokens=lex(text)
        if len(tokens)<4 or tokens[0].kind!='name' or tokens[1].value not in ('[','('): return None
        if tokens[1].value=='(' and self.array_variable(tokens[0].value) is None: return None
        depth=0
        for k,token in enumerate(tokens[1:],1):
            if token.value in ('[','('): depth+=1
            elif token.value in (']',')'): depth-=1
            if depth==0:
                if tokens[k+1].value=='[': continue
                return k
        return None

    def declare(self,cmd,tail):
        """DECLARE/DIMENSION/PUBLIC/PRIVATE/LOCAL com arrays e inicializadores (x := valor)."""
        for item in split(tail):
            m=re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)\s*(?:[\[(](.*)[\])])?\s*(?:(?::=|=)\s*(.+))?',item.strip(),re.S)
            if not m: raise XBaseError(cmd+': declaração inválida: '+item)
            name=m[1].upper()
            if cmd=='PUBLIC': self.variables.declare_public([name])
            elif cmd in ('PRIVATE','LOCAL'): self.variables.private([name])
            if m[2] is not None:
                dims=[int(self.expr(d)) for d in split(m[2])]
                if not dims or any(not 0<=d<=65535 for d in dims) or len(dims)>2 and cmd!='LOCAL': raise XBaseError('Dimensões de array inválidas: '+item)
                self.variables[name]=XArray.build(dims)
            if m[3] is not None: self.variables[name]=self.expr(m[3])

    def expand(self,text):
        """Macros não expandem dentro de literais. Ponto após &nome termina a macro."""
        for _ in range(16):
            result=[]; quote=None; i=0; changed=False
            while i<len(text):
                ch=text[i]
                if quote:
                    result.append(ch)
                    if ch==quote:
                        if quote!=']' and i+1<len(text) and text[i+1]==quote: result.append(ch); i+=2; continue
                        quote=None
                    i+=1; continue
                if ch in "'\"[" and not subscript(text,i): quote=']' if ch=='[' else ch
                if ch=='&':
                    m=re.match(r'&([A-Za-z_][A-Za-z_0-9]*)(\.)?',text[i:])
                    if not m: raise XBaseError('Macro inválida.')
                    try: value=self.variables[m[1]]
                    except KeyError: raise XBaseError('Macro desconhecida: '+m[1])
                    if not isinstance(value,str): raise XBaseError('Macro exige variável de texto.')
                    result.append(value.rstrip()); i+=len(m[0]); changed=True; continue
                result.append(ch); i+=1
            text=''.join(result)
            if not changed: return text
            if len(text)>1000000: raise XBaseError('Expansão de macro excessiva.')
        raise XBaseError('Macro recursiva excede limite.')

    def expr(self,text,row=None):
        text=self.expand(str(text)); expression=self.compiled.get(text)
        if expression is None:
            expression=Expression(text)
            if len(self.compiled)>4096: self.compiled.clear()
            self.compiled[text]=expression
        return expression.evaluate(self,row)

    def function(self,name,args,row=None):
        if row is not None and not args:
            if name=='RECNO': return row.get('_recno',self.state['pointer'])
            if name=='DELETED': return bool(row.get('_deleted',False))
        if name in self._functions:
            try: return self._functions[name](*args)
            except TypeError as exc: raise XBaseError(f'{name}: argumentos inválidos ({exc}).') from exc
        routine=self.find_routine(name)
        if routine and routine.is_function: return self.invoke(routine,[Cell(v) for v in args])
        raise XBaseError('Função não suportada: '+name)

    def date_order(self):
        return {'AMERICAN':'MDY','USA':'MDY','BRITISH':'DMY','FRENCH':'DMY','GERMAN':'DMY','ITALIAN':'DMY','ANSI':'YMD','JAPAN':'YMD'}[self.settings['DATE']]
    def date_separator(self): return '.' if self.settings['DATE'] in ('GERMAN','ANSI') else '-' if self.settings['DATE'] in ('ITALIAN','USA') else '/'

    def format(self,value):
        """Apresentação de ?, SAY e LIST: números à direita, como no dBASE."""
        if isinstance(value,bool): return '.T.' if value else '.F.'
        if isinstance(value,dt.date): return dtoc(self,value)
        if isinstance(value,(int,float)):
            width=getattr(value,'width',None)
            if width: return (f'{value:.{value.decimals}f}' if value.decimals else str(int(value))).rjust(width)
            if isinstance(value,int): return str(value).rjust(10)
            return f'{value:.{self.settings["DECIMALS"]}f}'.rjust(11+self.settings['DECIMALS'])
        if isinstance(value,XArray): return '{...}'
        return str(value)

    def talk(self,text):
        if self.settings['TALK']: self.emit(text)

    def emit(self,text='',newline=True):
        text=str(text)
        if self.alternate and self.settings['ALTERNATE']:
            self.alternate.write(text+('\n' if newline else '')); self.alternate.flush()
        if self.settings['PRINT']: self.print_text(text+('\n' if newline else ''))
        if self.settings['CONSOLE']:
            if self.output is print: print(text,end='\n' if newline else '',flush=True)
            else: self.output(text)

    def print_text(self,text):
        """Impressora emulada: texto acrescentado ao arquivo de SET PRINTER TO."""
        if not self.printer:
            self.printer=self.path(self.settings['PRINTER'],'.txt',False).open('a',encoding='utf-8')
            self.printer_row=self.printer_col=0
        margin=' '*int(self.settings['MARGIN'])
        for piece in re.split(r'(\n|\f)',text):
            if piece in ('\n','\f'):
                self.printer.write(piece); self.printer_col=0
                self.printer_row=0 if piece=='\f' else self.printer_row+1
            elif piece:
                if self.printer_col==0 and margin: self.printer.write(margin)
                self.printer.write(piece); self.printer_col+=len(piece)
        self.printer.flush()

    def print_at(self,row,col,text):
        """@ SAY com SET DEVICE TO PRINT: avança linhas/colunas e ejeta ao voltar para cima."""
        if not self.printer: self.print_text('')
        if row<self.printer_row: self.print_text('\f')
        while self.printer_row<row: self.print_text('\n')
        if col>self.printer_col: self.print_text(' '*(col-self.printer_col))
        self.print_text(text)

    def show(self,rows,expressions='',off=False):
        """LIST/DISPLAY no formato do dBASE: cabeçalho no III PLUS, número com zeros no II."""
        if not expressions and self.settings['FIELDS']: expressions=self.settings['FIELDS']
        es=split(expressions) if expressions else [f.name for f in self.fields()]
        memo={f.name for f in self.fields() if f.type=='M'}
        lines=[]
        for r in rows:
            self.position(r); cells=[]
            for e in es:
                value=self.expr(e,r)
                text=value.replace('\n',' ')[:50] if e.upper() in memo else self.format(value)
                cells.append((text,isinstance(value,(int,float)) and not isinstance(value,bool)))
            prefix='' if off else (f"{r['_recno']:05} {'*' if r['_deleted'] else ' '} " if self.dbase2 else f"{r['_recno']:7} {'*' if r['_deleted'] else ' '}")
            lines.append((prefix,cells))
        heading=self.settings['HEADING'] and not self.dbase2
        widths=[max([len(e) if heading else 0]+[len(c[i][0]) for _,c in lines]) for i,e in enumerate(es)]
        if heading: self.emit(('' if off else 'Record#  ')+' '.join(e.upper().ljust(w) for e,w in zip(es,widths)).rstrip())
        for prefix,cells in lines:
            self.emit(prefix+' '.join(t.rjust(w) if numeric else t.ljust(w) for (t,numeric),w in zip(cells,widths)).rstrip())
        return rows

    def move(self,recno,bof=False):
        self.state['pointer']=recno; self.state['bof']=bof
        if self.linked():
            other=self.areas[3-self.area]; other['pointer']=recno; other['bof']=bof
        self.sync_relations()

    def scope(self,tail,default_all=False):
        head,c=clauses(tail,{'FOR','WHILE'})
        words=list(outside_words(head)); scope=None; amount=None; remove=[]
        for word,start,end in words:
            if word in ('ALL','REST','NEXT','RECORD'):
                if scope is not None: raise XBaseError('Escopo duplicado.')
                scope=word; stop=end
                if word in ('NEXT','RECORD'):
                    m=re.match(r'\s+([A-Za-z_][A-Za-z_0-9]*|\d+)',head[end:])
                    if not m: raise XBaseError(word+' exige número/variável.')
                    amount=int(self.expr(m[1])); stop=end+len(m[0])
                    if amount<0: raise XBaseError('Escopo negativo.')
                remove.append((start,stop))
        for start,end in reversed(remove): head=head[:start]+head[end:]
        cache=self.view(); rows=cache['rows']; pointer=self.state['pointer']
        start=cache['pos'].get(pointer,len(rows))
        implicit_all=default_all or bool(c.get('FOR'))
        if scope=='ALL' or scope is None and implicit_all and not c.get('WHILE'): selected=(r for r in rows if self.visible(r))
        elif scope=='NEXT': selected=itertools.islice((r for r in rows[start:] if self.visible(r)),amount)
        elif scope=='RECORD': selected=[r for r in rows[cache['pos'][amount]:cache['pos'][amount]+1] if self.visible(r)] if amount in cache['pos'] else []
        elif scope=='REST' or c.get('WHILE'): selected=(r for r in rows[start:] if self.visible(r))
        else: selected=[rows[start]] if start<len(rows) and self.visible(rows[start]) else []
        result=[]
        for r in selected:
            if c.get('WHILE') or c.get('FOR'): self.position(r)
            if c.get('WHILE') and not self.expr(c['WHILE'],r): break
            if not c.get('FOR') or self.expr(c['FOR'],r): result.append(r)
        return result,head.strip()

    def scope_end(self,tail,rows,default_all=False):
        # Comandos de múltiplos registros deixam o ponteiro em EOF quando percorrem ALL.
        words={w for w,_,_ in outside_words(tail)}
        if default_all and not words.intersection({'NEXT','RECORD','REST','WHILE'}) or 'ALL' in words or ('FOR' in words and not words.intersection({'NEXT','RECORD','REST','WHILE'})):
            self.move(self.record_count()+1)
        elif rows and words.intersection({'NEXT','REST','RECORD','WHILE'}): self.move(rows[-1]['_recno'])

    def read_program(self,name,suffix='.prg'):
        p=self.path(name,suffix)
        if not p.exists() and p.suffix.lower()=='.prg':
            alternate=self.path(str(p.with_suffix('.cmd')),'.cmd')
            if alternate.exists(): p=alternate
        if self.encoding=='auto':
            raw=p.read_bytes()
            try: text=raw.decode('utf-8-sig')
            except UnicodeDecodeError: text=raw.decode('cp850')
        else: text=p.read_text(encoding=self.encoding)
        return Program(p,text)

    def find_routine(self,name):
        name=name.upper()
        if self.procedure_program and name in self.procedure_program.routines: return self.procedure_program.routines[name]
        for call in reversed(self.calls):
            if call['program'] and name in call['program'].routines: return call['program'].routines[name]
        return None

    def arguments(self,tail):
        cells=[]
        for exp in split(tail) if tail.strip() else []:
            name=re.fullmatch(r'(?:M->|M\.)?([A-Za-z_][A-Za-z_0-9]*)',exp,re.I)
            # Um campo sem qualificação é sempre passado por valor, mesmo com variável homônima.
            is_field=name and self.area in self.areas and name[1].upper() in {f.name for f in self.fields()} and not exp.upper().startswith(('M.','M->'))
            if name and not is_field:
                try: cells.append(self.variables.cell(name[1])); continue
                except KeyError: pass
            cells.append(Cell(self.expr(exp)))
        return cells

    def invoke(self,routine,args,program=None):
        if len(self.calls)>=self.max_depth: raise XBaseError('Limite de profundidade de chamadas excedido.')
        outer=bool(self.calls)
        if not outer: self.steps=0
        if program is None:
            program=next((c['program'] for c in reversed(self.calls) if c['program'] and c['program'].source==routine.source),None)
            if program is None and self.procedure_program and self.procedure_program.source==routine.source: program=self.procedure_program
        if args:
            first=routine.body[0] if routine.body else None
            if not first or first.kind!='command' or command_parts(first.text)[0]!='PARAMETERS': raise XBaseError('PARAMETERS deve ser o primeiro comando executável quando há argumentos.',routine.source)
        self.variables.push(); self.calls.append({'program':program,'args':args,'parameters':False})
        try:
            execute_nodes(self,routine.body,routine.source)
            if args and not self.calls[-1]['parameters']: raise XBaseError('Argumentos recebidos sem PARAMETERS.',routine.source)
        except ReturnSignal as signal: return signal.value
        except ReturnMasterSignal:
            if len(self.calls)>2: raise
            return
        finally: self.calls.pop(); self.variables.pop()

    def run_file(self,name,depth=0,args=None):
        program=self.read_program(name)
        try: return self.invoke(Routine('<MAIN>',program.source,program.main),args or [],program)
        except CancelSignal:
            if self.calls: raise
            return

    def use(self,tail):
        name,options=clauses(tail,{'ALIAS','INDEX','EXCLUSIVE','SHARED','NOUPDATE','AGAIN'})
        if not name: return super().execute('USE')
        if any(options.get(k) for k in ('EXCLUSIVE','SHARED','NOUPDATE','AGAIN')): raise XBaseError('EXCLUSIVE/SHARED/NOUPDATE não recebem argumento.')
        p=self.path(name)
        legacy=self.legacy_dbf(p)
        if legacy:
            # Primeiro USE de um DBF legado: converte para SQLite e passa a usar o banco convertido.
            old=self.area
            try: self.import_dbf(legacy,p.name)
            finally: self.area=old
        alias=options.get('ALIAS',p.stem).upper()
        if not re.fullmatch(r'[A-Z_][A-Z_0-9]*',alias): raise XBaseError('Alias inválido: '+alias)
        if any(n!=self.area and s['alias'].upper()==alias for n,s in self.areas.items()): raise XBaseError('Alias já aberto: '+alias)
        super().execute('USE "'+str(p)+'" ALIAS '+alias)
        # WAL com synchronous=NORMAL: cada comando continua atômico, sem fsync por registro gravado.
        self.state['db'].execute('PRAGMA journal_mode=WAL'); self.state['db'].execute('PRAGMA synchronous=NORMAL')
        cols={r[1] for r in self.state['db'].execute('PRAGMA table_info(_indexes)')}
        if 'unique_key' not in cols:
            with self.state['db']: self.state['db'].execute('ALTER TABLE _indexes ADD COLUMN unique_key INTEGER NOT NULL DEFAULT 0')
        if 'EXCLUSIVE' in options:
            self.state['db'].execute('PRAGMA locking_mode=EXCLUSIVE')
            self.state['db'].execute('BEGIN EXCLUSIVE'); self.state['db'].commit()
        self.state.update({'order_name':'','found':False,'bof':False,'indexes':[],'relations':[],'unique_order':False})
        if 'INDEX' in options: self.set_indexes(options['INDEX'])
        self.go('TOP')

    def go(self,tail):
        tail=re.sub(r'^RECORD\s+','',tail.strip(),flags=re.I)
        if tail.upper() in ('TOP','BOTTOM'):
            rows=self.view()['rows']
            ordered=rows if tail.upper()=='TOP' else reversed(rows)
            found=next((r for r in ordered if self.visible(r)),None)
            self.move(found['_recno'] if found else self.record_count()+1)
        else:
            n=int(self.expr(tail))
            if not 1<=n<=self.record_count(): raise XBaseError('Número de registro fora do banco.')
            self.move(n)

    def skip(self,tail):
        n=int(self.expr(tail or '1')); cache=self.view(); rows=cache['rows']; p=self.state['pointer']
        if n==0: self.move(p,self.state.get('bof',False)); return
        i=cache['pos'].get(p)
        if i is None: i=len(rows) if p>cache['count'] else -1
        step=1 if n>0 else -1; remaining=abs(n)
        while remaining:
            i+=step
            if i<0:
                first=next((r for r in rows if self.visible(r)),None)
                self.move(first['_recno'] if first else 1,True); return
            if i>=len(rows): self.move(cache['count']+1); return
            if self.visible(rows[i]): remaining-=1
        self.move(rows[i]['_recno'])

    def index_name(self,name): return Path(str(name).strip().strip("\"'")).stem.upper()

    def set_indexes(self,text):
        names=[self.index_name(n) for n in split(text) if n]
        available={r[0]:(r[1],r[2]) for r in self.state['db'].execute('SELECT name,expression,unique_key FROM _indexes')}
        for name in names:
            if name not in available and self.register_legacy_index(name):
                available={r[0]:(r[1],r[2]) for r in self.state['db'].execute('SELECT name,expression,unique_key FROM _indexes')}
            if name not in available: raise XBaseError('Índice não encontrado neste SQLite: '+name)
        self.state['indexes']=names
        self.state['order_name']=names[0] if names else ''
        self.state['order']=available[names[0]][0] if names else ''
        self.state['unique_order']=bool(available[names[0]][1]) if names else False
        self.go('TOP')

    def seek(self,value):
        """Busca binária na chave do índice controlador; prefixo com EXACT OFF."""
        if not self.state['order']: raise XBaseError('SEEK exige índice ativo.')
        cache=self.view(); keys=cache['keys']; rows=cache['rows']; found=None
        text=isinstance(value,str)
        if keys and isinstance(keys[0],str)!=text: raise XBaseError('Tipo da chave de SEEK difere do índice.')
        try: i=bisect.bisect_left(keys,value)
        except TypeError as exc: raise XBaseError('Tipo da chave de SEEK difere do índice.') from exc
        start=i
        while i<len(keys):
            key=keys[i]
            if text: match=key.rstrip()==value.rstrip() if self.exact else key.startswith(value)
            else: match=key==value
            if not match: break
            if self.visible(rows[i]): found=rows[i]; break
            i+=1
        self.state['found']=bool(found)
        if found: self.move(found['_recno'])
        elif self.settings['SOFTSEEK']:
            following=next((r for r in rows[start:] if self.visible(r)),None); self.move(following['_recno'] if following else self.record_count()+1)
        else: self.move(self.record_count()+1)
        return bool(found)

    def sync_relations(self):
        if self.area not in self.areas or self.area in self._syncing: return
        parent=self.area; state=self.areas[parent]
        if not state.get('relations'): return
        self._syncing.add(parent)
        try:
            raw=state['db'].execute('SELECT * FROM records WHERE _recno=?',(state['pointer'],)).fetchone()
            row=self.typed(raw) if raw else {}
            for expression,child in state['relations']:
                if child not in self.areas: continue
                value=self.expr(expression,row)
                self.area=child
                if not raw: self.move(self.record_count()+1)
                elif self.state['order']: self.seek(value)
                else: self.move(int(value) if 1<=int(value)<=self.record_count() else self.record_count()+1)
                self.area=parent
        finally: self.area=parent; self._syncing.remove(parent)

    def picture(self,value,picture):
        from .forms import transform
        return transform(value,picture,self.format)

    def screen_text(self,row,col,text,reverse=False):
        """Escreve no buffer 25x80 e no terminal; com SET DEVICE TO PRINT vai para a impressora."""
        if self.settings['DEVICE']=='PRINT': self.print_at(row,col,text); return
        visible=text[:max(0,80-col)]
        self.screen[row][col:col+len(visible)]=list(visible)
        if not self.plain: self.emit(f'\033[{row+1};{col+1}H'+self.styled(visible,'enhanced' if reverse else 'standard'),False)
        self.screen_row,self.screen_col=row,min(79,col+len(text))

    def clear_screen(self):
        self.screen=[[' ']*80 for _ in range(25)]; self.screen_row=self.screen_col=0
        if not self.plain: self.emit(self.paint()+'\033[2J\033[H',False)

    def box(self,row,col,r2,c2,style,clear=False):
        if not row<=r2<25 or not col<=c2<80: raise XBaseError('Retângulo fora da tela.')
        h,v,tl,tr,bl,br={'DOUBLE':'═║╔╗╚╝','PANEL':'██████'}.get(style,'─│┌┐└┘')
        for r in range(row,r2+1):
            for c in range(col,c2+1):
                if clear: ch=' '
                elif row==r2: ch=h
                elif col==c2: ch=v
                elif (r,c)==(row,col): ch=tl
                elif (r,c)==(row,c2): ch=tr
                elif (r,c)==(r2,col): ch=bl
                elif (r,c)==(r2,c2): ch=br
                elif r in (row,r2): ch=h
                elif c in (col,c2): ch=v
                else: continue
                self.screen[r][c]=ch
        if not self.plain: self.render_screen()

    def at(self,tail):
        coords,main=clauses(tail,{'SAY','GET','CLEAR','TO','PROMPT','DOUBLE','PANEL'})
        opts={k:v for k,v in main.items() if k not in ('SAY','GET','PROMPT')}
        pair=split(coords)
        if len(pair)!=2: raise XBaseError('@ exige linha,coluna.')
        row,col=(int(self.expr(v)) for v in pair)
        printing=self.settings['DEVICE']=='PRINT'
        if not 0<=row<(255 if printing else 25) or not 0<=col<(255 if printing else 80): raise XBaseError('Coordenada fora da tela 25x80.')
        self.screen_row,self.screen_col=row,col
        if 'TO' in opts:
            end=split(opts['TO'])
            if len(end)!=2: raise XBaseError('@ TO exige linha,coluna final.')
            r2,c2=(int(self.expr(v)) for v in end)
            return self.box(row,col,r2,c2,'DOUBLE' if 'DOUBLE' in opts else 'PANEL' if 'PANEL' in opts else 'SINGLE','CLEAR' in opts)
        if 'PROMPT' in main:
            text,popts=clauses(main['PROMPT'],{'MESSAGE'})
            label=str(self.expr(text))
            self.prompts.append({'row':row,'col':col,'text':label,'message':self.expr(popts['MESSAGE']) if popts.get('MESSAGE') else ''})
            self.screen_text(row,col,label)
            if self.plain: self.emit(label)
            return
        if 'SAY' not in main and 'GET' not in main:
            if printing: return
            # @ l,c apaga o resto da linha; @ l,c CLEAR apaga até o canto inferior direito.
            if 'CLEAR' in opts: return self.box(row,col,24,79,'SINGLE',True)
            self.screen[row][col:]=[' ']*(80-col)
            if not self.plain: self.emit(f'\033[{row+1};{col+1}H\033[K',False)
            return
        if 'SAY' in main:
            expression,say=clauses(main['SAY'],{'PICTURE','USING','FUNCTION','COLOR'})
            value=self.expr(expression)
            picture=self.expr(say['PICTURE']) if 'PICTURE' in say else self.expr(say['USING']) if 'USING' in say else ''
            if 'FUNCTION' in say: picture='@'+str(self.expr(say['FUNCTION']))+(' '+picture if picture else '')
            text=self.picture(value,picture) if picture else self.format(value)
            if printing: self.print_at(row,col,text); return
            self.screen_text(row,col,text)
            if self.plain: self.emit(text,'GET' not in main)
        if 'GET' in main and not printing:
            target,get=clauses(main['GET'],{'PICTURE','RANGE','VALID','WHEN','COLOR','FUNCTION','MESSAGE','ERROR'})
            target=target.strip()
            if not re.fullmatch(r'(?:(?:[A-Za-z_][A-Za-z_0-9]*)(?:->|\.))?[A-Za-z_][A-Za-z_0-9]*',target) and self.element_target(target) is None: raise XBaseError('GET exige campo, variável ou elemento de array.')
            self.expr(target)  # GET requer variável já inicializada.
            picture=self.expr(get['PICTURE']) if 'PICTURE' in get else ''
            if 'FUNCTION' in get: picture='@'+str(self.expr(get['FUNCTION']))+(' '+picture if picture else '')
            item={'target':target,'picture':picture,'range':get.get('RANGE',''),'valid':get.get('VALID',''),'when':get.get('WHEN',''),
                'message':get.get('MESSAGE',''),'error':get.get('ERROR',''),'row':row,'col':self.screen_col if 'SAY' in main else col}
            self.gets.append(item); self.draw_get(item)

    def render_screen(self): self.emit(self.paint()+'\033[H'+'\n'.join(''.join(r) for r in self.screen),False)

    def assign_target(self,target,value):
        if re.search(r'[\[(]',target): return self.set_element(target,value)
        m=re.fullmatch(r'(?:([A-Za-z_][A-Za-z_0-9]*)(?:->|\.))?([A-Za-z_][A-Za-z_0-9]*)',target)
        if not m: raise XBaseError('Destino inválido: '+target)
        alias,name=m[1],m[2].upper()
        old=self.area
        try:
            if alias and alias.upper() not in ('M','MEMVAR'): self.area=self.area_number(alias)
            fs={f.name:f for f in self.fields()} if self.area in self.areas else {}
            if alias and alias.upper() in ('M','MEMVAR') or name not in fs:
                self.variables[name]=value; return
            if not self.current(): raise XBaseError('Sem registro para atualizar GET.')
            self.write_record(self.state['pointer'],{name:self.coerce(fs[name],value)})
        finally: self.area=old

    def require_field_type(self,f,value):
        code=self.type_code(value)
        if code != ('C' if f.type=='M' else f.type): raise XBaseError('Tipo incompatível em '+f.name+': esperado '+f.type+', recebido '+code)

    def get_mask(self,item):
        from .forms import PictureMask
        value=self.expr(item['target']); width=None; decimals=0
        match=re.fullmatch(r'(?:(\w+)(?:->|\.))?(\w+)',item['target'])
        if not match: return PictureMask(value,item['picture'],self.format)
        old=self.area
        try:
            if match[1] and match[1].upper() not in ('M','MEMVAR'): self.area=self.area_number(match[1])
            if self.area in self.areas and (not match[1] or match[1].upper() not in ('M','MEMVAR')):
                field=next((f for f in self.fields() if f.name==match[2].upper()),None)
                if field: width=field.length if field.type!='D' else None; decimals=field.decimals
        finally: self.area=old
        return PictureMask(value,item['picture'],self.format,width,decimals)

    def delimiters(self):
        if not self.settings['DELIMITERS']: return '',''
        chars=self.settings['DELIMITER_CHARS']
        return chars[0],chars[-1]

    def draw_get(self,item,text=None,cursor=None):
        mask=self.get_mask(item)
        text=mask.initial() if text is None else text
        row,col=item['row'],item['col']; left,right=self.delimiters()
        display=left+text+right
        visible=display[:max(0,80-col)]
        self.screen[row][col:col+len(visible)]=list(visible)
        if not self.plain:
            reverse=not left and self.settings['INTENSITY']
            self.emit(f'\033[{row+1};{col+1}H'+self.styled(visible,'enhanced' if reverse else 'standard'),False)
            if cursor is not None: self.emit(f'\033[{row+1};{min(80,col+cursor+len(left)+1)}H',False)
        elif cursor is None: self.emit(display)
        self.screen_row=row; self.screen_col=min(79,col+len(display))

    def get_value(self,item,mask,text):
        value=mask.decode(text)
        if isinstance(mask.value,dt.date): value=ctod(self,value)
        if item['range']:
            bounds=split(item['range'])
            if len(bounds)!=2: raise XBaseError('RANGE exige mínimo,máximo.')
            if bounds[0] and value<self.expr(bounds[0]) or bounds[1] and value>self.expr(bounds[1]): raise XBaseError('Valor fora do RANGE.')
        return value

    def beep(self):
        if self.settings['BELL']: self.emit('\a',False)

    def message_line(self,text):
        if self.plain or not text: return
        self.emit(self.paint()+'\033[25;1H\033[K'+str(text)[:79],False)

    def accept_value(self,item,value):
        """Grava o valor e aplica VALID; valor recusado é restaurado."""
        previous=self.expr(item['target'])
        self.assign_target(item['target'],value)
        if item.get('valid') and not self.expr(item['valid']):
            self.assign_target(item['target'],previous)
            error=self.expr(item['error']) if item.get('error') else 'Valor inválido.'
            if self.plain: self.emit('Erro: '+str(error))
            else: self.message_line(error)
            self.beep(); return False
        return True

    def read_gets(self,append_mode=False,save=False):
        """Edita os GETs pendentes e retorna quantos campos foram alterados."""
        from .forms import FieldEditor, terminal_keys, normalize_key
        if not self.gets and self.format_program: self.run_format()
        if not self.gets: raise XBaseError('READ exige ao menos um GET pendente.')
        gets=self.gets
        if not save: self.gets=[]
        changed=0
        interactive=self.interactive()
        if not interactive:
            for index,item in enumerate(gets):
                if item.get('when') and not self.expr(item['when']): continue
                mask=self.get_mask(item)
                while True:
                    raw=self.input(item['target']+' :'+mask.initial()+': ')
                    if raw=='':
                        if append_mode and index==0: self.last_key=13; return 0
                        break
                    try:
                        text=mask.input_text(raw)
                        if not self.accept_value(item,self.get_value(item,mask,text)): continue
                        changed+=1; self.draw_get(item,self.get_mask(item).initial()); break
                    except (ValueError,TypeError) as exc: self.emit('Erro: '+str(exc))
            self.last_key=13; return changed
        codes={'ENTER':13,'TAB':9,'PGDN':3,'PGUP':18,'SAVE':23,'ESC':27}
        def edit(read_key):
            nonlocal changed
            index=0; direction=1
            while index<len(gets):
                item=gets[index]
                if item.get('when') and not self.expr(item['when']):
                    index+=direction
                    if index<0: index=0; direction=1
                    continue
                mask=self.get_mask(item); editor=FieldEditor(mask,self.settings['CONFIRM'])
                self.message_line(self.expr(item['message']) if item.get('message') else self.settings['MESSAGE'])
                while True:
                    self.draw_get(item,editor.text,editor.position)
                    key=read_key()
                    if len(key)==1: key=normalize_key(key)
                    if key=='MARK' and self.form_record:
                        row=self.current(); self.write_record(row['_recno'],{'_deleted':int(not row['_deleted'])}); continue
                    action='leave' if key in ('PGDN','PGUP','SAVE') else editor.event(key)
                    if action=='cancel': self.last_key=27; return
                    if action=='invalid': self.beep(); continue
                    if action not in ('next','previous','leave'): continue
                    if append_mode and index==0 and key=='ENTER' and not editor.changed: self.last_key=13; return
                    try:
                        if editor.changed:
                            if not self.accept_value(item,self.get_value(item,mask,editor.text)): continue
                            changed+=1
                    except (ValueError,TypeError): self.beep(); continue
                    self.draw_get(item,self.get_mask(item).initial(),None)
                    self.last_key=codes.get(key,0)
                    if action=='leave': return
                    if action=='previous': direction=-1; index=max(0,index-1)
                    else: direction=1; index+=1
                    break
        if self.key_reader is not None: edit(self.key_reader)
        else:
            with terminal_keys() as read_key: edit(read_key)
        return changed

    def run_format(self):
        """SET FORMAT TO arquivo.fmt: executa os @ SAY/GET do formato antes de READ/APPEND/EDIT."""
        execute_nodes(self,self.format_program.main,self.format_program.source)

    def record_form(self,names=None,append_mode=False):
        """Tela de registro de APPEND/EDIT/INSERT: formato ativo ou um GET por campo."""
        self.form_record=self.state['pointer']
        try:
            if self.format_program:
                self.gets=[]; self.run_format()
                return self.read_gets(append_mode=append_mode)
            fs=[f for f in self.fields() if f.type!='M' and (not names or f.name in names)]
            if not fs: raise XBaseError('Nenhum campo editável.')
            changed=0
            for page in range(0,len(fs),20):
                self.clear_screen(); self.gets=[]
                recno=self.state['pointer']
                title=(f'Registro {recno:05}' if self.dbase2 else f'Registro {recno:7}')+('  *APAGADO*' if self.current().get('_deleted') else '')
                self.screen_text(0,0,title)
                if self.plain: self.emit(title)
                for i,f in enumerate(fs[page:page+20]):
                    self.screen_text(i+2,0,f.name.ljust(10)+' ')
                    if self.plain: self.emit(f.name.ljust(10)+' ',False)
                    item={'target':f.name,'picture':'','range':'','valid':'','when':'','message':'','error':'','row':i+2,'col':11}
                    self.gets.append(item); self.draw_get(item)
                changed+=self.read_gets(append_mode=append_mode and page==0)
                if self.last_key in (27,3,18,23) or append_mode and changed==0: break
            return changed
        finally: self.form_record=None

    def append_form(self):
        """APPEND interativo: Enter no primeiro campo vazio de um registro novo encerra."""
        while True:
            row=self.current() if self.area in self.areas else {}
            carry={k:v for k,v in row.items() if not k.startswith('_')} if self.settings['CARRY'] and row else None
            self.append(carry)
            recno=self.state['pointer']
            changed=self.record_form(append_mode=True)
            if changed==0:
                with self.state['db']: self.state['db'].execute('DELETE FROM records WHERE _recno=?',(recno,))
                self.go('BOTTOM'); return
            if self.last_key==27: return

    def edit_form(self,tail):
        """EDIT/CHANGE [n|escopo] [FIELDS lista] [FOR/WHILE]; PgUp/PgDn trocam de registro."""
        head,opts=clauses(tail,{'FIELDS','FIELD','FOR','WHILE'})
        names=None
        for key in ('FIELDS','FIELD'):
            if key in opts: names=[n.upper() for n in split(opts.pop(key))]
        if re.fullmatch(r'\d+',head.strip()): self.go(head); head=''
        explicit=bool(head.strip() or opts)
        rows,_=self.scope(' '.join([head]+[k+' '+v for k,v in opts.items()]))
        if not rows: raise XBaseError('Sem registro atual.')
        i=0
        while 0<=i<len(rows):
            self.move(rows[i]['_recno']); self.record_form(names)
            if self.last_key in (27,23): return
            if explicit: i+=-1 if self.last_key==18 else 1; continue
            if self.last_key not in (3,18): return
            self.skip('1' if self.last_key==3 else '-1')
            if self.eof() or self.bof() and self.last_key==18: return
            rows=[self.current()]

    def insert_record(self,tail):
        """INSERT [BEFORE] [BLANK]: abre espaço renumerando os registros seguintes."""
        words={w for w,_,_ in outside_words(tail)}
        if words-{'BEFORE','BLANK'}: raise XBaseError('INSERT [BEFORE] [BLANK]')
        db=self.state['db']; count=self.record_count()
        row=self.current()
        carry={k:v for k,v in row.items() if not k.startswith('_')} if self.settings['CARRY'] and row else {}
        if count==0 or self.eof(): self.append(carry or None)
        else:
            target=self.state['pointer']+(0 if 'BEFORE' in words else 1)
            fs=self.fields(); values=[self.coerce(f,carry.get(f.name,self.blank_value(f))) for f in fs]
            with db:
                db.execute('UPDATE records SET _recno=-(_recno+1) WHERE _recno>=?',(target,))
                db.execute('UPDATE records SET _recno=-_recno WHERE _recno<0')
                db.execute('INSERT INTO records (_recno,'+','.join('"'+f.name+'"' for f in fs)+') VALUES (?,'+','.join('?' for _ in fs)+')',[target,*values])
            self.move(target)
        if 'BLANK' not in words: self.record_form()

    def record(self,recno):
        cache=self.view(); i=cache['pos'].get(recno)
        if i is not None: return cache['rows'][i]
        r=self.state['db'].execute('SELECT * FROM records WHERE _recno=?',(recno,)).fetchone()
        return self.typed(r) if r else {}

    def browse(self,tail):
        """BROWSE em grade editável: setas/Tab movem, Enter ou digitação editam, Ctrl+U apaga, Esc/Ctrl+W saem."""
        from .forms import FieldEditor, terminal_keys, normalize_key
        head,opts=clauses(tail,{'FIELDS','FREEZE','LOCK','NOAPPEND','NOMENU','NOFOLLOW','WIDTH','NOEDIT','NODELETE','NOCLEAR'})
        interactive=self.interactive()
        if not interactive: return self.list_command('BROWSE',head+(' '+opts['FIELDS'] if opts.get('FIELDS') else ''))
        if head.strip(): raise XBaseError('BROWSE [FIELDS lista] [FREEZE campo] [WIDTH n] [NOAPPEND] [NOEDIT] [NODELETE]')
        by_name={f.name:f for f in self.fields()}
        names=[n.upper() for n in split(opts['FIELDS'])] if opts.get('FIELDS') else list(by_name)
        if any(n not in by_name for n in names): raise XBaseError('BROWSE FIELDS contém campo desconhecido.')
        fields=[by_name[n] for n in names]
        limit=max(1,min(76,int(self.expr(opts['WIDTH'])) if opts.get('WIDTH') else 76))
        sizes={'M':4,'L':3,'D':10 if self.settings['CENTURY'] else 8}
        widths=[min(limit,max(len(f.name),sizes.get(f.type,f.length))) for f in fields]
        frozen=None
        if opts.get('FREEZE'):
            if opts['FREEZE'].strip().upper() not in names: raise XBaseError('FREEZE exige campo da lista.')
            frozen=names.index(opts['FREEZE'].strip().upper())
        recnos=[r['_recno'] for r in self.rows()]
        state={'row':0,'col':frozen or 0,'top':0,'first':0,'appended':None,'touched':False}
        if not recnos:
            if 'NOAPPEND' in opts: raise XBaseError('BROWSE: banco sem registros visíveis.')
            self.append(); recnos.append(self.state['pointer']); state['appended']=recnos[0]
        elif self.state['pointer'] in recnos: state['row']=recnos.index(self.state['pointer'])
        height=20
        def shown():
            col=state['col']
            if col<state['first']: state['first']=col
            while True:
                used=2; visible=[]
                for i in range(state['first'],len(fields)):
                    if visible and used+widths[i]+1>80: break
                    visible.append(i); used+=widths[i]+1
                if col in visible: return visible
                state['first']+=1
        def cell(record,i):
            f=fields[i]; value=record.get(f.name,'')
            if f.type=='M': text='MEMO' if str(value).strip() else 'memo'
            else: text=self.format(value).strip() if f.type=='N' else self.format(value)
            text=text[:widths[i]]
            return text.rjust(widths[i]) if f.type=='N' else text.ljust(widths[i])
        def line(r,text): self.screen_text(r,0,text[:80].ljust(80))
        def offset(visible): return 2+sum(widths[i]+1 for i in visible[:visible.index(state['col'])])
        def draw():
            row=state['row']
            if row<state['top']: state['top']=row
            if row>=state['top']+height: state['top']=row-height+1
            visible=shown(); recno=recnos[row]; self.move(recno); current=self.record(recno)
            line(0,f' BROWSE  {self.state["alias"]}   Registro {recno}/{self.record_count()}'+('   *APAGADO*' if current.get('_deleted') else ''))
            line(1,'  '+'│'.join(fields[i].name[:widths[i]].ljust(widths[i]) for i in visible))
            line(2,'──'+'┼'.join('─'*widths[i] for i in visible))
            for k in range(height):
                index=state['top']+k
                if index>=len(recnos): line(3+k,''); continue
                record=self.record(recnos[index])
                line(3+k,('*' if record.get('_deleted') else ' ')+' '+'│'.join(cell(record,i) for i in visible))
                if index==row: self.screen_text(3+k,offset(visible),cell(record,state['col']),True)
            line(24,' ↑↓ PgUp PgDn registro  ←→ Tab campo  Enter/digitar edita  Ctrl+U apaga  Esc sai')
            return visible
        def forget_blank():
            """Registro incluído pela seta para baixo e não preenchido é descartado."""
            appended=state['appended']
            if appended is None or state['touched'] or recnos[state['row']]!=appended: return False
            with self.state['db']: self.state['db'].execute('DELETE FROM records WHERE _recno=?',(appended,))
            recnos.pop(state['row']); state['appended']=None
            return True
        def go_row(target):
            if target!=state['row'] and forget_blank(): target=min(target,len(recnos)-1)
            state['row']=max(0,min(target,len(recnos)-1))
        def down():
            if state['row']<len(recnos)-1: return go_row(state['row']+1)
            if 'NOAPPEND' in opts or state['appended'] is not None: return self.beep()
            self.append(); recnos.append(self.state['pointer']); state.update(appended=self.state['pointer'],touched=False,row=len(recnos)-1)
        def edit(read_key,first_key):
            f=fields[state['col']]; self.move(recnos[state['row']])
            item={'target':f.name,'picture':'','range':'','valid':'','when':'','message':'','error':''}
            mask=self.get_mask(item); editor=FieldEditor(mask,True)
            if first_key!='ENTER' and editor.event(first_key)=='invalid': return self.beep()
            while True:
                visible=shown(); y=3+state['row']-state['top']; x=offset(visible)
                self.screen_text(y,x,editor.text[:widths[state['col']]].ljust(widths[state['col']]),True)
                if not self.plain: self.emit(f'\033[{y+1};{x+min(editor.position,widths[state["col"]]-1)+1}H',False)
                key=read_key()
                if len(key)==1: key=normalize_key(key)
                if key=='ESC': return
                action=editor.event(key)
                if action=='invalid': self.beep(); continue
                if action not in ('next','previous'): continue
                if editor.changed:
                    try:
                        if not self.accept_value(item,self.get_value(item,mask,editor.text)): continue
                    except (ValueError,TypeError): self.beep(); continue
                    if recnos[state['row']]==state['appended']: state['touched']=True
                if key=='UP': go_row(state['row']-1)
                elif key=='DOWN': down()
                elif key=='SHIFT_TAB':
                    if frozen is None: state['col']=max(0,state['col']-1)
                elif frozen is None and state['col']<len(fields)-1: state['col']+=1
                elif state['row']<len(recnos)-1: go_row(state['row']+1); state['col']=frozen or 0
                return
        def run(read_key):
            while True:
                draw()
                key=read_key()
                if len(key)==1: key=normalize_key(key)
                if key in ('ESC','SAVE'): return
                if key=='UP': go_row(state['row']-1)
                elif key=='DOWN': down()
                elif key=='PGUP': go_row(state['row']-height)
                elif key=='PGDN': go_row(state['row']+height)
                elif key in ('LEFT','SHIFT_TAB') and frozen is None: state['col']=max(0,state['col']-1)
                elif key in ('RIGHT','TAB') and frozen is None: state['col']=min(len(fields)-1,state['col']+1)
                elif key=='HOME' and frozen is None: state['col']=0
                elif key=='END' and frozen is None: state['col']=len(fields)-1
                elif key=='MARK' and 'NODELETE' not in opts:
                    record=self.record(recnos[state['row']]); self.write_record(record['_recno'],{'_deleted':int(not record['_deleted'])})
                elif key=='ENTER' or len(key)==1 and key.isprintable():
                    if 'NOEDIT' in opts or fields[state['col']].type=='M': self.beep()
                    else: edit(read_key,key)
        try:
            if self.key_reader is not None: run(self.key_reader)
            else:
                with terminal_keys() as read_key: run(read_key)
        finally:
            forget_blank()
            if recnos: self.move(recnos[min(state['row'],len(recnos)-1)])
            if 'NOCLEAR' not in opts: self.clear_screen()
        self.last_key=27

    def menu_to(self,name):
        """MENU TO variável (extensão Clipper) sobre os @ PROMPT pendentes."""
        from .forms import terminal_keys, normalize_key
        prompts=self.prompts; self.prompts=[]
        if not prompts: raise XBaseError('MENU TO exige @ ... PROMPT.')
        try: current=int(self.variables[name])
        except (KeyError,TypeError,ValueError): current=1
        choice=min(max(1,current),len(prompts))
        interactive=self.interactive()
        if not interactive:
            raw=self.input('Opção (1-'+str(len(prompts))+'): ').strip()
            letters={p['text'].strip()[:1].upper():i for i,p in reversed(list(enumerate(prompts,1))) if p['text'].strip()}
            choice=int(raw) if raw.isdigit() and 1<=int(raw)<=len(prompts) else letters.get(raw[:1].upper(),0) if raw else choice
            self.variables[name]=choice; self.last_key=13 if choice else 27; return choice
        def run(read_key):
            nonlocal choice
            while True:
                for i,p in enumerate(prompts,1): self.screen_text(p['row'],p['col'],p['text'],i==choice)
                self.message_line(prompts[choice-1]['message'] or self.settings['MESSAGE'])
                key=read_key()
                if len(key)==1: key=normalize_key(key)
                if key in ('DOWN','RIGHT','TAB'): choice=choice%len(prompts)+1
                elif key in ('UP','LEFT','SHIFT_TAB'): choice=(choice-2)%len(prompts)+1
                elif key=='HOME': choice=1
                elif key=='END': choice=len(prompts)
                elif key=='ENTER': return choice
                elif key=='ESC': return 0
                elif len(key)==1:
                    hit=next((i for i,p in enumerate(prompts,1) if p['text'].strip()[:1].upper()==key.upper()),None)
                    if hit: return hit
        if self.key_reader is not None: result=run(self.key_reader)
        else:
            with terminal_keys() as read_key: result=run(read_key)
        self.last_key=13 if result else 27; self.variables[name]=result; return result

    def inkey(self,seconds=0):
        # Em entrada redirecionada/injetada, usa uma linha. CLI interativo preserva uma tecla.
        if self.input is not input or not sys.stdin.isatty():
            if seconds: return 0
            raw=self.input(''); self.last_key=ord(raw[0]) if raw else 13; return self.last_key
        if sys.platform=='win32':
            import msvcrt
            deadline=time.monotonic()+float(seconds)
            while not msvcrt.kbhit():
                if seconds and time.monotonic()>=deadline: return 0
                time.sleep(.01)
            value=ord(msvcrt.getwch())
        else:
            import termios,tty,select
            fd=sys.stdin.fileno(); state=termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ready,_,_=select.select([sys.stdin],[],[],float(seconds) if seconds else None)
                value=ord(sys.stdin.read(1)) if ready else 0
            finally: termios.tcsetattr(fd,termios.TCSADRAIN,state)
        self.last_key=value; return value

    def confirm(self,prompt):
        return self.input(prompt).strip()[:1].upper() in ('S','Y','T')

    def new_table(self,name,fields,records=()):
        """Cria cópia sem trocar a área selecionada ou perder a conexão do chamador."""
        p=self.path(name,search=False)
        if p.exists():
            if any(s['path']==p for s in self.areas.values()): raise XBaseError('Destino está aberto: '+p.name)
            if self.settings['SAFETY'] and not self.confirm(p.name+' já existe. Sobrescrever? (S/N) '): raise XBaseError('Destino já existe: '+p.name)
            p.unlink()
        old_area=self.area
        temporary=next((i for i in range(11,100) if i not in self.areas),99)
        self.area=temporary
        try:
            super().create(str(p),[Field(**vars(f)) for f in fields])
            self.append_many([{f.name:r.get(f.name,self.blank_value(f)) for f in fields}|{'_deleted':r.get('_deleted',0)} for r in records],True)
        except Exception:
            if temporary in self.areas: self.areas.pop(temporary)['db'].close()
            p.unlink(missing_ok=True)
            raise
        finally:
            if temporary in self.areas: self.areas.pop(temporary)['db'].close()
            self.area=old_area
        return p

    def append(self,values=None):
        """APPEND BLANK com ajuste do cache, para laços APPEND BLANK/REPLACE não relerem a tabela."""
        s=self.state; db=s['db']; cache=s.get('cache')
        fresh=cache is not None and cache['key'][0]==db.total_changes
        super().append(values)
        recno=s['pointer']
        if fresh and not s.get('unique_order'):
            row=self.typed(db.execute('SELECT * FROM records WHERE _recno=?',(recno,)).fetchone())
            if cache['keys'] is None: cache['rows'].append(row); cache['pos'][recno]=len(cache['rows'])-1
            else:
                key=self.expr(s['order'],row); at=bisect.bisect_right(cache['keys'],key)
                cache['rows'].insert(at,row); cache['keys'].insert(at,key)
                cache['pos']={r['_recno']:n for n,r in enumerate(cache['rows'])}
            cache['count']+=1; cache['key']=(db.total_changes,)+cache['key'][1:]
        self.move(recno)

    def append_many(self,records,keep_deleted=False):
        fs=self.fields()
        data=[[self.coerce(f,r.get(f.name,self.blank_value(f))) for f in fs]+([int(bool(r.get('_deleted')))] if keep_deleted else []) for r in records]
        if not data: return 0
        names=['"'+f.name+'"' for f in fs]+(['_deleted'] if keep_deleted else [])
        sql='INSERT INTO records ('+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')'
        with self.state['db']:
            cur=self.state['db'].executemany(sql,data)
            last=self.state['db'].execute('SELECT MAX(_recno) FROM records').fetchone()[0]
        self.move(last)
        return len(data)

    def check(self,name):
        from .compatibility import inspect_program
        return inspect_program(self,self.read_program(name))

    def locate(self,cmd,tail):
        """LOCATE/CONTINUE percorrem a partir do ponteiro e param no primeiro registro encontrado."""
        s=self.state
        if cmd=='LOCATE': s['locate_tail']=tail
        if 'locate_tail' not in s: raise XBaseError('CONTINUE exige LOCATE anterior.')
        head,c=clauses(s['locate_tail'],{'FOR','WHILE'})
        words=[w for w,_,_ in outside_words(head)]
        if not c.get('FOR') and not c.get('WHILE') or set(words)-{'ALL','REST','NEXT','RECORD'} and not re.fullmatch(r'(?:ALL|REST|NEXT\s+\S+)?',head.strip(),re.I): raise XBaseError('LOCATE [escopo] FOR condição [WHILE condição]')
        cache=self.view(); rows=cache['rows']; p=cache['pos'].get(s['pointer'])
        if cmd=='CONTINUE': start=len(rows) if p is None else p+1
        elif 'REST' in words or 'NEXT' in words or c.get('WHILE') and 'ALL' not in words: start=len(rows) if p is None else p
        else: start=0
        if cmd=='LOCATE':
            limit=int(self.expr(head.split()[-1])) if 'NEXT' in words else None
            s['locate_end']=start+limit if limit is not None else None
        end=s.get('locate_end') or len(rows)
        found=None
        for r in rows[start:min(end,len(rows))]:
            if not self.visible(r): continue
            self.position(r)
            if c.get('WHILE') and not self.expr(c['WHILE'],r): break
            if not c.get('FOR') or self.expr(c['FOR'],r): found=r; break
        self.move(found['_recno'] if found else self.record_count()+1); self.state['found']=bool(found)
        if found: self.talk(f"Registro :{found['_recno']:05}" if self.dbase2 else f"Registro = {found['_recno']:7}")
        else: self.talk('Fim do escopo do LOCATE')
        return bool(found)

    def structure_lines(self):
        fs=self.fields(); s=self.state
        lines=[f'Estrutura do banco de dados : {s["path"].name}',f'Número de registros  : {self.record_count():8}',
            f'Última atualização   : {dtoc(self,dt.date.fromtimestamp(s["path"].stat().st_mtime))}','Campo  Nome        Tipo       Largura   Dec']
        names={'C':'Caractere','N':'Numérico','L':'Lógico','D':'Data','M':'Memo'}
        for i,f in enumerate(fs,1): lines.append(f'{i:5}  {f.name:<11} {names.get(f.type,f.type):<10} {f.length:5}   {f.decimals if f.type=="N" else "":>3}')
        lines.append(f'** Total **                    {1+sum(8 if f.type=="D" else 10 if f.type=="M" else f.length for f in fs):5}')
        return lines

    def status_lines(self):
        lines=[]
        for n in sorted(self.areas):
            s=self.areas[n]; mark=' => ' if n==self.area else '    '
            lines.append(f'{mark}Área {n:2}: {s["path"].name}  Alias: {s["alias"]}  Registro: {s["pointer"]}')
            for name in s.get('indexes',[]):
                expression=s['db'].execute('SELECT expression FROM _indexes WHERE name=?',(name,)).fetchone()
                lines.append(f'        {"Índice controlador" if name==s.get("order_name") else "Índice"}: {name}  Chave: {expression[0] if expression else ""}')
            if s.get('filter'): lines.append('        Filtro: '+s['filter'])
            for expression,child in s.get('relations',[]): lines.append(f'        Relação: {expression} INTO {self.areas[child]["alias"] if child in self.areas else child}')
        if self.procedure_program: lines.append('Arquivo de procedimentos: '+Path(self.procedure_program.source).name)
        if self.format_program: lines.append('Formato: '+Path(self.format_program.source).name)
        lines.append('Dialeto: '+self.settings['DIALECT'])
        flags=[f'{k:<11} {"ON " if v else "OFF"}' for k,v in sorted(self.settings.items()) if isinstance(v,bool)]
        for i in range(0,len(flags),4): lines.append('   '.join(flags[i:i+4]))
        others=[f'{k}: {v}' for k,v in sorted(self.settings.items()) if not isinstance(v,bool) and v not in ('',None)]
        lines.extend(others)
        return lines

    def output_to(self,target,action):
        """LIST/DISPLAY/REPORT ... TO PRINT|TO FILE arquivo."""
        target=target.strip()
        if not target: return action()
        word,_,rest=target.partition(' ')
        if word.upper() in ('PRINT','PRINTER'):
            old=self.settings['PRINT']; self.settings['PRINT']=True
            try: return action()
            finally: self.settings['PRINT']=old
        if word.upper()=='FILE':
            p=self.path(rest,'.txt',False)
            old=self.alternate,self.settings['ALTERNATE']
            self.alternate=p.open('w',encoding='utf-8'); self.settings['ALTERNATE']=True
            try: return action()
            finally:
                self.alternate.close(); self.alternate,self.settings['ALTERNATE']=old
        raise XBaseError('Use TO PRINT ou TO FILE arquivo.')

    def list_command(self,cmd,tail):
        kind=tail.strip().upper()
        if kind=='FILES' or kind.startswith('FILES '): return self.directory(re.sub(r'^FILES\s*(?:LIKE\s*)?','',tail.strip(),flags=re.I))
        if kind=='STRUCTURE': self.emit('\n'.join(self.structure_lines())); return
        if kind=='MEMORY': self.emit('\n'.join(self.memory_lines())); return
        if kind=='STATUS': self.emit('\n'.join(self.status_lines())); return
        if kind=='HISTORY': return
        text=re.sub(r'(?i)(?<![\w.])FIELDS(?![\w])',' ',tail)
        head,opts=clauses(text,{'OFF','TO'})
        target=''
        if 'TO' in opts:
            word,_,rest=opts['TO'].partition(' ')
            if word.upper() in ('PRINT','PRINTER'): target='PRINT'; head+=' '+rest
            elif word.upper()=='FILE':
                name,_,rest=rest.strip().partition(' '); target='FILE '+name; head+=' '+rest
            else: raise XBaseError('LIST/DISPLAY TO PRINT ou TO FILE arquivo.')
        if opts.get('OFF'): head+=' '+opts['OFF']
        def run():
            rows,ex=self.scope(head,cmd in ('LIST','BROWSE'))
            result=self.show(rows,ex,'OFF' in opts)
            self.scope_end(head,rows,cmd in ('LIST','BROWSE')); return result
        return self.output_to(target,run)

    def memory_lines(self):
        lines=[]
        def show(label,value,indent):
            prefix=indent+label if indent else f'{label:<12}'
            if isinstance(value,XArray):
                lines.append(f'{prefix} (A) [{len(value)}]')
                for i,item in enumerate(value,1): show(f'[{i}]',item,indent+'  ')
                return
            text=self.format(value).strip() if isinstance(value,(int,float)) and not isinstance(value,bool) else self.format(value)
            lines.append(f'{prefix} ({self.type_code(value)}) {text}')
        for k,v in self.variables.items(): show(k,v,'')
        return lines

    def encode_value(self,value):
        if isinstance(value,XArray): return {'type':'A','value':[self.encode_value(v) for v in value]}
        return {'type':self.type_code(value),'value':value.isoformat() if isinstance(value,dt.date) else value}

    def decode_value(self,data):
        if not isinstance(data,dict) or 'type' not in data: return data
        if data['type']=='A': return XArray(self.decode_value(v) for v in data['value'])
        if data['type']=='D': return dt.date.fromisoformat(data['value'])
        return data['value']

    def array_command(self,cmd,tail):
        """COPY TO ARRAY, APPEND FROM ARRAY (dBASE IV) e SCATTER/GATHER (FoxPro)."""
        fs=[f for f in self.fields() if f.type!='M']
        if cmd in ('SCATTER','GATHER'):
            head,opts=clauses(tail,{'FIELDS','TO','FROM','MEMVAR','BLANK'})
            if opts.get('FIELDS'):
                names=[n.upper() for n in split(opts['FIELDS'])]; fs=[f for f in self.fields() if f.name in names]
            row=self.current()
            if cmd=='SCATTER':
                values=[self.blank_value(f) if 'BLANK' in opts else row.get(f.name,self.blank_value(f)) for f in fs]
                if 'MEMVAR' in opts:
                    for f,v in zip(fs,values): self.variables[f.name]=v
                elif opts.get('TO'): self.variables[opts['TO'].strip()]=XArray(values)
                else: raise XBaseError('SCATTER [FIELDS lista] TO array | MEMVAR')
                return
            if not row: raise XBaseError('GATHER exige registro atual.')
            if 'MEMVAR' in opts: values={f.name:self.variables[f.name] for f in fs}
            elif opts.get('FROM'):
                array=self.array_variable(opts['FROM'].strip())
                if array is None: raise XBaseError('GATHER FROM exige array.')
                values={f.name:v for f,v in zip(fs,array)}
            else: raise XBaseError('GATHER FROM array | MEMVAR [FIELDS lista]')
            for f in fs:
                if f.name in values: self.require_field_type(f,values[f.name])
            self.write_record(row['_recno'],{k:self.coerce(next(f for f in fs if f.name==k),v) for k,v in values.items()}); return
        if cmd=='COPY':
            text=re.sub(r'^TO\s+ARRAY\s+','',tail,flags=re.I)
            name,opts=clauses(text,{'FIELDS','FIELD','FOR','WHILE','ALL','NEXT','RECORD','REST'})
            listed=opts.pop('FIELDS',None) or opts.pop('FIELD',None)
            if listed:
                names=[n.upper() for n in split(listed)]; fs=[f for f in self.fields() if f.name in names]
            rows,_=self.scope(' '.join(k+(' '+v if v else '') for k,v in opts.items()),True)
            target=self.array_variable(name.strip())
            data=[[r[f.name] for f in fs] for r in rows]
            if target is None:
                self.variables[name.strip()]=XArray(XArray(values) for values in data); return len(data)
            two=target and isinstance(target[0],XArray)
            for i,values in enumerate(data if two else data[:1]):
                if i>=len(target): break
                row=target[i] if two else target
                for j,v in enumerate(values[:len(row)]): row[j]=v
            return min(len(data),len(target) if two else 1)
        text=re.sub(r'^FROM\s+ARRAY\s+','',tail,flags=re.I)
        name,opts=clauses(text,{'FOR','FIELDS'})
        array=self.array_variable(name.strip())
        if array is None: raise XBaseError('APPEND FROM ARRAY exige array.')
        records=array if array and isinstance(array[0],XArray) else [array]
        typed=[]
        for values in records:
            record={f.name:v for f,v in zip(fs,values)}
            values_ok={f.name:self.coerce(f,record.get(f.name,self.blank_value(f))) for f in self.fields()}
            if not opts.get('FOR') or self.expr(opts['FOR'],self.typed({'_recno':0,'_deleted':0,**values_ok})): typed.append(values_ok)
        return self.append_many(typed)

    def directory(self,pattern):
        pattern=pattern.strip() or '*.sqlite'
        if pattern.lower()=='*.sqlite' or pattern.lower().endswith(('.sqlite','.dbf')):
            pattern=re.sub(r'\.dbf$','.sqlite',pattern,flags=re.I)
            self.emit('Arquivo de dados        # Registros   Última atualização')
            for p in sorted(self.cwd.glob(pattern)):
                try:
                    db=sqlite3.connect(p)
                    try: count=db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
                    finally: db.close()
                except sqlite3.Error: continue
                self.emit(f'{p.stem:<22} {count:12}   {dtoc(self,dt.date.fromtimestamp(p.stat().st_mtime))}')
            return
        self.emit('\n'.join(p.name for p in sorted(self.cwd.glob(pattern)) if p.is_file()))

    def import_dbf(self,source,target=None):
        """Converte DBF (dBASE II/III/IV, FoxPro) em SQLite; índices NDX/NTX de mesmo nome são registrados."""
        from .dbf import read_dbf
        encoding='cp850' if self.encoding=='auto' else self.encoding
        version,fields,records=read_dbf(source,encoding)
        if not fields: raise XBaseError('DBF sem campos: '+source.name)
        destination=self.new_table(str(target or source.with_suffix('.sqlite').name),fields,records)
        self.emit(f'{source.name} ({version}) importado para {destination.name}: {len(records)} registro(s).')
        return destination

    def legacy_dbf(self,p):
        """Arquivo DBF com o mesmo nome de um banco SQLite ainda inexistente."""
        if p.exists() or not p.parent.exists(): return None
        return next((f for f in p.parent.iterdir() if f.stem.casefold()==p.stem.casefold() and f.suffix.lower()=='.dbf'),None)

    def register_legacy_index(self,name):
        """SET INDEX TO arquivo.ndx/.ntx legado: a expressão-chave do cabeçalho é registrada no SQLite."""
        from .dbf import index_expression
        folder=self.state['path'].parent
        legacy=next((f for f in folder.iterdir() if f.stem.upper()==name and f.suffix.lower() in ('.ndx','.ntx')),None)
        if not legacy: return False
        expression,unique=index_expression(legacy)
        for row in self.rows(False)[:1]: self.expr(expression,row)
        with self.state['db']: self.state['db'].execute('INSERT OR REPLACE INTO _indexes (name,expression,unique_key) VALUES (?,?,?)',(name,expression,int(unique)))
        self.emit(f'Índice {legacy.name} registrado com a chave {expression}.')
        return True

    def modify_structure(self,tail):
        """MODIFY STRUCTURE preservando os dados por nome de campo (o dBASE II apagava os registros)."""
        old=self.fields(); s=self.state
        m=re.fullmatch(r'\s*\((.*)\)\s*',tail,re.S)
        if m:
            fields=[]
            for item in split(m[1]):
                t=item.split()
                if len(t)<2: raise XBaseError('Campo: NOME TIPO LARGURA DECIMAIS')
                fields.append(Field(t[0],t[1],int(t[2]) if len(t)>2 else {'L':1,'D':8,'M':10}.get(t[1].upper(),10),int(t[3]) if len(t)>3 else 0))
        elif tail.strip(): raise XBaseError('MODIFY STRUCTURE [(NOME TIPO LARGURA DEC, ...)]')
        else:
            self.emit('Campo: NOME TIPO LARGURA DECIMAIS. Enter mantém, "-" remove, linha vazia no final conclui.')
            fields=[]
            for i,f in enumerate(old,1):
                raw=self.input(f'{i:03} {f.name} {f.type} {f.length} {f.decimals}: ').strip()
                if raw=='-': continue
                if not raw: fields.append(Field(f.name,f.type,f.length,f.decimals)); continue
                t=raw.replace(',',' ').split()
                fields.append(Field(t[0],t[1] if len(t)>1 else f.type,int(t[2]) if len(t)>2 else f.length,int(t[3]) if len(t)>3 else 0))
            while True:
                raw=self.input(f'{len(fields)+1:03}: ').strip()
                if not raw: break
                t=raw.replace(',',' ').split()
                fields.append(Field(t[0],t[1] if len(t)>1 else 'C',int(t[2]) if len(t)>2 else {'L':1,'D':8,'M':10}.get((t[1] if len(t)>1 else 'C').upper(),10),int(t[3]) if len(t)>3 else 0))
        types={f.name:f for f in old}
        def convert(f,value):
            source=types.get(f.name)
            if source is None or isinstance(value,str) and value=='': return self.blank_value(f)
            if f.type==source.type or f.type=='M' and source.type=='C' or f.type=='C' and source.type=='M': return value
            if f.type in ('C','M'): return self.format(value).strip()
            if f.type=='N': return float(re.sub(r'[^0-9.+-]','',str(value)) or 0) if not isinstance(value,(int,float)) else value
            if f.type=='L': return str(value).strip().upper() in ('T','Y','S','.T.')
            if f.type=='D':
                try: return ctod(self,value) if isinstance(value,str) else self.blank_value(f)
                except (XBaseError,ValueError): return self.blank_value(f)
            return self.blank_value(f)
        records=[{**{f.name:convert(f,r.get(f.name)) for f in fields},'_deleted':r['_deleted']} for r in self.rows(False)]
        path,alias,area=s['path'],s['alias'],self.area
        indexes=list(s['db'].execute('SELECT name,expression,unique_key FROM _indexes'))
        backup=path.with_name(path.stem+'_bak.sqlite')
        temporary=path.with_name(path.stem+'_tmp.sqlite'); temporary.unlink(missing_ok=True)
        self.new_table(temporary.name,fields,records)
        super().execute('USE')
        db=sqlite3.connect(temporary)
        try:
            with db:
                for row in indexes: db.execute('INSERT OR REPLACE INTO _indexes (name,expression,unique_key) VALUES (?,?,?)',row)
        finally: db.close()
        backup.unlink(missing_ok=True); path.replace(backup); temporary.replace(path)
        self.use(f'"{path.name}" ALIAS {alias}')
        self.talk(f'{len(records)} registro(s) preservado(s); cópia anterior em {backup.name}.')

    def modify_file(self,name,suffix):
        """MODIFY COMMAND/FILE: abre o editor do sistema (EDITOR, VISUAL; Bloco de Notas no Windows)."""
        import shlex,subprocess
        p=self.path(name,suffix,False)
        if not p.exists(): p.write_text('',encoding='utf-8')
        editor=os.environ.get('VISUAL') or os.environ.get('EDITOR') or ('notepad' if sys.platform=='win32' else 'vi')
        subprocess.call([*shlex.split(editor,posix=sys.platform!='win32'),str(p)])
        self.compiled.clear()

    def report_command(self,cmd,tail):
        from . import report
        if cmd in ('CREATE','MODIFY'):
            p=self.path(tail,'.frm',False)
            definition=self.report_dialog(report,report.load(p) if p.exists() else None)
            report.save(p,definition); return p
        text=re.sub(r'^FORM\s+','',tail.strip(),flags=re.I)
        name,_,rest=text.partition(' ')
        p=self.path(name,'.frm')
        if not p.exists():
            if not self.dbase2: raise XBaseError('REPORT FORM: arquivo não encontrado: '+p.name+'. Use CREATE REPORT '+name+'.')
            report.save(p,self.report_dialog(report))
        definition=report.load(p)
        head,opts=clauses(rest,{'TO','PLAIN','HEADING','NOEJECT','SUMMARY','FOR','WHILE'})
        head=self.flag_clauses(head,opts,('PLAIN','NOEJECT','SUMMARY'))
        scope_text=' '.join([head]+[k+' '+v for k,v in opts.items() if k in ('FOR','WHILE')])
        heading=str(self.expr(opts['HEADING'])) if opts.get('HEADING') else ''
        target=opts.get('TO','')
        def run():
            rows,_=self.scope(scope_text,True)
            printing=self.settings['PRINT']
            report.render(self,definition,rows,self.emit_report,heading,'PLAIN' in opts,'NOEJECT' in opts,'SUMMARY' in opts,printing)
            self.scope_end(scope_text,rows,True)
        return self.output_to(target,run)

    def flag_clauses(self,head,opts,flags):
        """Palavras sem argumento (PLAIN, SAMPLE...) devolvem ao escopo o texto que as segue."""
        for flag in flags:
            if opts.get(flag): head+=' '+opts[flag]; opts[flag]=''
        return head

    def label_command(self,cmd,tail):
        """LABEL FORM nome [escopo] [FOR] [WHILE] [SAMPLE] [TO PRINT|TO FILE arq]; CREATE/MODIFY LABEL."""
        from . import label
        if cmd in ('CREATE','MODIFY'):
            if self.area not in self.areas: raise XBaseError('Abra o banco das etiquetas com USE.')
            p=self.path(tail,'.lbl',False)
            label.save(p,label.dialog(self,label.load(p) if p.exists() else None)); return p
        text=re.sub(r'^FORM\s+','',tail.strip(),flags=re.I)
        name,_,rest=text.partition(' ')
        p=self.path(name,'.lbl')
        if not p.exists(): raise XBaseError('LABEL FORM: arquivo não encontrado: '+p.name+'. Use CREATE LABEL '+name+'.')
        definition=label.load(p)
        head,opts=clauses(rest,{'TO','SAMPLE','FOR','WHILE'})
        head=self.flag_clauses(head,opts,('SAMPLE',))
        scope_text=' '.join([head]+[k+' '+v for k,v in opts.items() if k in ('FOR','WHILE')])
        def run():
            rows,_=self.scope(scope_text,True)
            label.render(self,definition,rows,self.emit,'SAMPLE' in opts)
            if self.settings['PRINT']: self.print_text('\f')
            self.scope_end(scope_text,rows,True)
        return self.output_to(opts.get('TO',''),run)

    def emit_report(self,text):
        if text=='\f':
            if self.settings['PRINT']: self.print_text('\f')
            return
        self.emit(text)

    def report_dialog(self,report,definition=None):
        if self.area not in self.areas: raise XBaseError('Abra o banco do relatório com USE.')
        return report.dialog(self,definition)

    def secret(self,row,col,prompt):
        """Senha sem eco (PLUS CODE); em entrada redirecionada lê uma linha."""
        self.screen_text(min(row,24),min(col,79),prompt)
        if self.interactive() and self.key_reader is None:
            import getpass
            return getpass.getpass('')
        if self.plain: self.emit(prompt,False)
        return self.input('')

    def text_records(self,p,kind,separator=None):
        """APPEND FROM ... SDF/DELIMITED: registros posicionais no formato do dBASE."""
        import csv
        fs=[f for f in self.fields() if f.type!='M']
        encoding='utf-8-sig'
        raw=p.read_bytes()
        try: lines=raw.decode(encoding).splitlines()
        except UnicodeDecodeError: lines=raw.decode('cp850').splitlines()
        records=[]
        for line in lines:
            if not line.strip() or line=='\x1a': continue
            if kind=='SDF':
                values=[]; pos=0
                for f in fs:
                    size=8 if f.type=='D' else f.length
                    values.append(line[pos:pos+size]); pos+=size
            elif separator=='BLANK': values=line.split(' ')
            else: values=next(csv.reader([line],delimiter=',',quotechar=separator or '"'))
            record={}
            for f,value in zip(fs,values):
                value=value.strip() if f.type!='C' else value.rstrip()
                if f.type=='N': record[f.name]=float(value or 0) if f.decimals else int(float(value or 0))
                elif f.type=='L': record[f.name]=value.upper() in ('T','Y','S')
                elif f.type=='D': record[f.name]=dt.date(int(value[:4]),int(value[4:6]),int(value[6:8])) if len(value)==8 and value.isdigit() else EMPTY_DATE
                else: record[f.name]=value
            records.append(record)
        return records

    def append_from(self,tail):
        import csv
        name,opts=clauses(tail,{'FROM','FOR','WHILE','DELIMITED','SDF','TYPE','FIELDS','FIELD'})
        source=opts['FROM']
        kind=(opts.get('TYPE') or '').upper()
        if 'SDF' in opts: kind='SDF'
        if 'DELIMITED' in opts: kind='DELIMITED'
        suffix=Path(re.sub(r'^["\'\[]|["\'\]]$','',source)).suffix.lower()
        if not kind: kind={'.dbf':'DBF','.csv':'CSV','.txt':'SDF'}.get(suffix,'SQLITE')
        if kind=='DBF':
            from .dbf import read_dbf
            p=super().path(re.sub(r'^[A-Za-z]:(?!/)','',source.strip().strip('"\'')),'.dbf')
            records=[r for r in read_dbf(p,'cp850' if self.encoding=='auto' else self.encoding)[2]]
        elif kind=='CSV':
            p=self.path(source,'.csv')
            with p.open(newline='',encoding='utf-8-sig') as f: records=list(csv.DictReader(f))
        elif kind in ('SDF','DELIMITED'):
            p=self.path(source,'.txt')
            separator=re.sub(r'^WITH\s+','',opts.get('DELIMITED',''),flags=re.I).strip() or None
            records=self.text_records(p,kind,separator.upper() if separator and separator.upper()=='BLANK' else separator)
        else:
            p=self.path(source)
            db=sqlite3.connect(p); db.row_factory=sqlite3.Row
            try: records=[dict(r) for r in db.execute('SELECT * FROM records ORDER BY _recno')]
            finally: db.close()
        names=None
        for key in ('FIELDS','FIELD'):
            if opts.get(key): names={n.upper() for n in split(opts[key])}
        fs=self.fields(); typed=[]
        for r in records:
            if r.get('_deleted') and (kind!='DBF' or self.deleted): continue
            values={f.name:self.coerce(f,r.get(f.name,self.blank_value(f)) if (names is None or f.name in names) else self.blank_value(f)) for f in fs}
            row=self.typed({'_recno':0,'_deleted':0,**values})
            if opts.get('WHILE') and not self.expr(opts['WHILE'],row): break
            if not opts.get('FOR') or self.expr(opts['FOR'],row): typed.append(values)
        count=self.append_many(typed)
        self.talk(f'{count} registro(s) adicionado(s)')
        return count

    def execute(self,line):
        line=uncomment(str(line)).strip()
        if not line: return
        line=self.expand(line)
        # Atribuição é distinta de comparação em expressões.
        m=re.fullmatch(r'((?:M->|M\.)?[A-Za-z_][A-Za-z_0-9]*)\s*(?::=|=)\s*(.+)',line,re.I|re.S)
        if m:
            name=re.sub(r'^M(?:->|\.)','',m[1],flags=re.I)
            value=self.variables[name]=self.expr(m[2]); self.talk(self.format(value)); return
        if re.fullmatch(r'\d+',line): return self.go(line)  # dBASE II: número no prompt equivale a GO.
        end=self.element_target(line) if re.match(r'[A-Za-z_]\w*\s*[\[(]',line) else None
        if end is not None:
            tokens=lex(line)
            if tokens[end+1].value in ('=',':='):
                value=self.expr(line[tokens[end+1].end:]); self.set_element(line[:tokens[end].end],value); self.talk(self.format(value)); return
        cmd,tail=command_parts(line)
        if cmd in ('?','??'):
            values=[self.format(self.expr(e)) for e in split(tail)] if tail else ['']
            self.emit(' '.join(values),cmd=='?'); return
        if cmd=='???': self.print_text(''.join(str(self.expr(e)) for e in split(tail)) if tail else ''); return
        if cmd=='@': return self.at(tail)
        if cmd=='QUIT': self.running=False; self.close(); return
        if cmd=='CANCEL': raise CancelSignal()
        if cmd=='ON':
            key,_,handler=tail.partition(' ')
            if key.upper()=='ERROR': self.on_error=handler.strip(); return
            if key.upper() in ('ESCAPE','KEY'): self.settings['ON_'+key.upper()]=handler.strip(); return
            raise XBaseError('ON implementado para ERROR; ESCAPE/KEY são aceitos sem disparo.')
        if cmd=='RETRY':
            if not self.handling_error: raise XBaseError('RETRY exige ON ERROR ativo em tratamento.')
            raise RetrySignal()
        if cmd=='RETURN':
            if tail.upper()=='TO MASTER': raise ReturnMasterSignal()
            raise ReturnSignal(self.expr(tail) if tail else None)
        if cmd=='LOOP': raise LoopSignal()
        if cmd=='EXIT':
            if not self.calls: self.running=False; self.close(); return
            raise ExitSignal()
        if cmd=='HELP': self.emit(HELP); return
        if cmd=='REMARK': self.emit(tail); return
        if cmd=='SELECT': self.area=self.area_number(tail); return
        if cmd=='USE': return self.use(tail)
        if cmd in ('GO','GOTO'): return self.go(tail)
        if cmd=='SKIP': return self.skip(tail)
        if cmd=='DO':
            name,opts=clauses(tail,{'WITH'})
            args=self.arguments(opts.get('WITH',''))
            routine=self.find_routine(name) if re.fullmatch(r'\w+',name) else None
            if routine: return self.invoke(routine,args)
            return self.run_file(name,args=args)
        if cmd=='PARAMETERS':
            if not self.calls: raise XBaseError('PARAMETERS fora de programa/procedimento.')
            call=self.calls[-1]; names=split(tail)
            if call['parameters']: raise XBaseError('PARAMETERS repetido.')
            if len(names)<len(call['args']): raise XBaseError('Número de PARAMETERS difere de DO ... WITH.')
            for i,name in enumerate(names):
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name): raise XBaseError('Nome de parâmetro inválido.')
                # Parâmetros não recebidos ficam .F., como no dBASE IV/Clipper (PCOUNT() informa a quantidade).
                self.variables.bind(name,call['args'][i] if i<len(call['args']) else Cell(False))
            call['parameters']=True; return
        if cmd in ('DECLARE','DIMENSION','LOCAL') or cmd in ('PRIVATE','PUBLIC') and re.search(r'[\[(]|:=|=',tail) and not re.match(r'ALL\b',tail,re.I):
            return self.declare(cmd,tail)
        if cmd in ('PRIVATE','PUBLIC'):
            names=self.variables.names(tail)
            if cmd=='PRIVATE': self.variables.private(names)
            else: self.variables.declare_public(names)
            return
        if cmd=='STORE':
            expression,opts=clauses(tail,{'TO'})
            if 'TO' not in opts: raise XBaseError('STORE expressão TO variáveis')
            value=self.expr(expression)
            for name in split(opts['TO']):
                if re.search(r'[\[(]',name): self.set_element(name,value)
                else: self.variables[self.variables.names(name)[0]]=value
            self.talk(self.format(value)); return
        if cmd=='RELEASE':
            for name in self.variables.names(tail):
                try: del self.variables[name]
                except KeyError: pass
            return
        if cmd=='SET': return self.set_command(tail)
        if cmd=='ERASE' and not tail: self.clear_screen(); return
        if cmd=='CLEAR':
            kind=tail.upper()
            if not kind and self.dbase2:
                # dBASE II: CLEAR fecha os bancos e apaga as variáveis; ERASE limpa a tela.
                for s in self.areas.values(): s['db'].close()
                self.areas.clear(); self.variables.clear(); self.gets=[]; self.area=1; return
            if not kind or kind=='SCREEN': self.clear_screen(); self.gets=[]
            elif kind=='GETS': self.gets=[]
            elif kind=='MEMORY': self.variables.clear()
            elif kind=='ALL':
                for s in self.areas.values(): s['db'].close()
                self.areas.clear(); self.variables.clear(); self.gets=[]; self.procedure_program=None; self.format_program=None
            elif kind in ('TYPEAHEAD','FIELDS'):
                if kind=='FIELDS': self.settings['FIELDS']=''
            else: raise XBaseError('CLEAR suportado: SCREEN, GETS, MEMORY, ALL, TYPEAHEAD, FIELDS.')
            return
        if cmd=='CLOSE':
            kind=tail.upper()
            if kind in ('ALL','DATABASES'):
                for s in self.areas.values(): s['db'].close()
                self.areas.clear()
                if kind=='ALL': self.procedure_program=None; self.format_program=None; self.gets=[]
            elif kind=='PROCEDURE': self.procedure_program=None
            elif kind in ('INDEX','INDEXES'): self.set_indexes('')
            elif kind=='FORMAT': self.format_program=None
            elif kind=='ALTERNATE':
                if self.alternate: self.alternate.close(); self.alternate=None
                self.settings['ALTERNATE']=False
            elif kind=='PRINTER':
                if self.printer: self.printer.close(); self.printer=None
            elif not kind: super().execute('USE')
            else: raise XBaseError('CLOSE suportado: ALL, DATABASES, PROCEDURE, INDEX, FORMAT, ALTERNATE, PRINTER.')
            return
        if cmd=='READ':
            if tail and tail.upper()!='SAVE': raise XBaseError('READ [SAVE]')
            return self.read_gets(save=bool(tail))
        if cmd=='MENU':
            m=re.fullmatch(r'TO\s+([A-Za-z_][A-Za-z_0-9]*)',tail,re.I)
            if not m: raise XBaseError('MENU TO variável')
            return self.menu_to(m[1])
        if cmd=='CREATE':
            word,_,rest=tail.partition(' ')
            if word.upper()=='REPORT': return self.report_command('CREATE',rest)
            if word.upper()=='LABEL': return self.label_command('CREATE',rest)
            name,opts=clauses(tail,{'FROM'})
            if 'FROM' in opts:
                source=self.path(opts['FROM']); db=sqlite3.connect(source)
                try:
                    db.row_factory=sqlite3.Row; records=[dict(r) for r in db.execute('SELECT * FROM records ORDER BY _recno')]
                    fs=[Field(str(r['FIELD_NAME']).strip(),str(r['FIELD_TYPE']).strip(),int(r['FIELD_LEN']),int(r['FIELD_DEC'])) for r in records]
                finally: db.close()
                return self.create(name,fs)
            return super().execute('CREATE '+tail)
        if cmd=='MODIFY':
            word,_,rest=tail.partition(' ')
            word=word.upper()
            if word.startswith('STRU'): return self.modify_structure(rest)
            if word.startswith('COMM'): return self.modify_file(rest,'.prg')
            if word=='FILE': return self.modify_file(rest,'')
            if word=='REPORT': return self.report_command('MODIFY',rest)
            if word=='LABEL': return self.label_command('MODIFY',rest)
            raise XBaseError('MODIFY STRUCTURE, COMMAND, FILE, REPORT ou LABEL.')
        if cmd=='REPORT': return self.report_command('REPORT',tail)
        if cmd=='LABEL': return self.label_command('LABEL',tail)
        if cmd=='PLUS':
            from .plus import plus_command
            return plus_command(self,tail)
        if cmd=='BROWSE': return self.browse(tail)
        if cmd in ('LIST','DISPLAY'): return self.list_command(cmd,tail)
        if cmd=='APPEND':
            if tail.upper()=='BLANK': self.append(); return
            if re.match(r'FROM\s+ARRAY\b',tail,re.I): return self.array_command('APPEND',tail)
            if re.search(r'(?i)\bFROM\b',tail): return self.append_from(tail)
            if tail: raise XBaseError('APPEND, APPEND BLANK ou APPEND FROM arquivo.')
            return self.append_form()
        if cmd=='INSERT': return self.insert_record(tail)
        if cmd=='IMPORT':
            name,opts=clauses(tail,{'FROM','TYPE','TO'})
            source=super().path(re.sub(r'^[A-Za-z]:(?!/)','',opts.get('FROM','').strip().strip('"\'')),'.dbf')
            if not source.exists(): raise XBaseError('Arquivo não encontrado: '+source.name)
            return self.import_dbf(source,opts.get('TO'))
        if cmd=='REPLACE':
            rows,assignments=self.scope(tail)
            if any('->' in clauses(a,{'WITH'})[0] for a in split(assignments)):
                if len(rows)>1: raise XBaseError('REPLACE com destino alias->campo suporta um registro por comando; use DO WHILE para múltiplos.')
                plans=[]
                for assignment in split(assignments):
                    target,parts=clauses(assignment,{'WITH'})
                    if 'WITH' not in parts: raise XBaseError('REPLACE exige WITH.')
                    value=self.expr(parts['WITH'],rows[0] if rows else None)
                    old=self.area
                    try:
                        name=target
                        if '->' in target:
                            alias,name=target.split('->',1); self.area=self.area_number(alias)
                        fs={f.name:f for f in self.fields()}; name=name.upper().strip()
                        if name not in fs: raise XBaseError('Campo desconhecido: '+target)
                        if not self.current(): raise XBaseError('Destino sem registro atual: '+target)
                        self.require_field_type(fs[name],value)
                        plans.append((self.area,name,self.coerce(fs[name],value),self.state['pointer']))
                    finally: self.area=old
                for area,name,value,recno in plans:
                    old=self.area; self.area=area
                    try: self.write_record(recno,{name:value})
                    finally: self.area=old
                return
            fs={f.name:f for f in self.fields()}; updates=[]
            for r in rows:
                self.position(r)
                vals={}; evaluation=dict(r)
                for assignment in split(assignments):
                    name,parts=clauses(assignment,{'WITH'})
                    if len(parts)!=1 or 'WITH' not in parts: raise XBaseError('REPLACE campo WITH expressão')
                    name=name.upper()
                    if name not in fs: raise XBaseError('Campo desconhecido: '+name)
                    expression_value=self.expr(parts['WITH'],evaluation)
                    self.require_field_type(fs[name],expression_value)
                    value=self.coerce(fs[name],expression_value); vals[name]=value
                    evaluation[name]=self.typed({name:value})[name]
                updates.append((r,vals))
            if len(updates)==1: self.write_record(updates[0][0]['_recno'],updates[0][1])
            elif updates:
                with self.state['db']:
                    for r,values in updates:
                        sql='UPDATE records SET '+','.join('"'+name+'"=?' for name in values)+' WHERE _recno=?'
                        self.state['db'].execute(sql,[*values.values(),r['_recno']])
            self.talk(f'{len(updates)} registro(s) alterado(s)')
            self.scope_end(tail,rows); return
        if cmd in ('DELETE','RECALL') and not tail.upper().startswith('FILE '):
            rows,extra=self.scope(tail)
            if extra: raise XBaseError('Escopo inválido: '+extra)
            if len(rows)==1: self.write_record(rows[0]['_recno'],{'_deleted':int(cmd=='DELETE')})
            elif rows:
                with self.state['db']: self.state['db'].executemany('UPDATE records SET _deleted=? WHERE _recno=?',[(cmd=='DELETE',r['_recno']) for r in rows])
            self.talk(f'{len(rows)} registro(s) '+('marcado(s) para exclusão' if cmd=='DELETE' else 'recuperado(s)'))
            self.scope_end(tail,rows); return
        if cmd=='PACK':
            super().execute('PACK'); self.state['bof']=False
            self.talk(f'{self.record_count()} registro(s) copiado(s)'); return
        if cmd=='ZAP':
            if self.settings['SAFETY'] and self.input('Apagar todos os registros? Digite SIM: ')!='SIM': return
            with self.state['db']: self.state['db'].execute('DELETE FROM records')
            self.move(1); return
        if cmd in ('EDIT','CHANGE'): return self.edit_form(tail)
        if cmd in ('LOCATE','CONTINUE'): return self.locate(cmd,tail)
        if cmd in ('SEEK','FIND'):
            # FIND aceita texto sem aspas ou &macro; espaços finais do literal são ignorados.
            return self.seek(self.expr(tail) if cmd=='SEEK' else tail.strip().strip("\"'"))
        if cmd in ('COUNT','SUM','AVERAGE'):
            expression,opts=clauses(tail,{'TO'})
            rows,ex=self.scope(expression,True)
            if cmd=='COUNT' and ex: raise XBaseError('COUNT não aceita lista de campos.')
            if cmd=='COUNT': values=[len(rows)]
            else:
                values=[]
                for e in split(ex) if ex else [f.name for f in self.fields() if f.type=='N']:
                    total=0
                    for r in rows: self.position(r); total+=self.expr(e,r)
                    values.append(total/(len(rows) or 1) if cmd=='AVERAGE' else total)
            if 'TO' in opts:
                names=self.variables.names(opts['TO'])
                if len(names)!=len(values): raise XBaseError('Número de variáveis TO difere das expressões.')
                for name,value in zip(names,values): self.variables[name]=value
            self.last_count=len(rows)
            if cmd=='COUNT': self.talk(f'Contagem ={len(rows):05}' if self.dbase2 else f'{len(rows):7} registro(s)')
            else: self.talk(' '.join(self.format(v) for v in values))
            self.scope_end(expression,rows,True); return values[0] if len(values)==1 else values
        if cmd=='INDEX':
            head,opts=clauses(tail,{'ON','TO','UNIQUE'})
            if head or 'ON' not in opts or 'TO' not in opts: raise XBaseError('INDEX ON expressão TO nome [UNIQUE]')
            name=self.index_name(opts['TO'])
            if not re.fullmatch(r'[A-Z_][A-Z_0-9]*',name): raise XBaseError('Nome de índice inválido.')
            rows=self.rows(False)
            for row in rows: self.expr(opts['ON'],row)
            with self.state['db']:
                self.state['db'].execute('INSERT OR REPLACE INTO _indexes (name,expression,unique_key) VALUES (?,?,?)',(name,opts['ON'],int('UNIQUE' in opts or self.settings['UNIQUE'])))
                self.state['db'].execute('DROP INDEX IF EXISTS "idx_'+name+'"')
                if opts['ON'].upper() in {f.name for f in self.fields()}:
                    self.state['db'].execute('CREATE INDEX IF NOT EXISTS "idx_'+name+'" ON records ("'+opts['ON'].upper()+'")')
            self.state['indexes']=[name]; self.state['order_name']=name; self.state['order']=opts['ON']; self.state['unique_order']='UNIQUE' in opts or self.settings['UNIQUE']; self.go('TOP')
            self.talk(f'{len(rows)} registro(s) indexado(s)'); return
        if cmd=='REINDEX': self.state.pop('cache',None); self.view(); return
        if cmd=='COPY' and re.match(r'TO\s+ARRAY\b',tail,re.I) or cmd in ('SCATTER','GATHER'): return self.array_command(cmd,tail)
        if cmd=='COPY': return self.copy_command(tail)
        if cmd=='SORT':
            _,opts=clauses(tail,{'TO','ON','FOR','WHILE','ASCENDING','DESCENDING'})
            if 'TO' not in opts or 'ON' not in opts: raise XBaseError('SORT ON campo TO nome [ASCENDING|DESCENDING] [FOR condição]')
            filter_text=' '.join(k+' '+v for k,v in opts.items() if k in ('FOR','WHILE'))
            rows,_=self.scope(filter_text,True)
            for key in reversed(split(opts['ON'])):
                m=re.fullmatch(r'(\w+)\s*(?:/\s*(A|D|C|AC|DC|CA|CD))?',key,re.I)
                if not m: raise XBaseError('SORT suporta campo[/A|/D|/C].')
                flags=(m[2] or '').upper()
                descending='D' in flags or 'DESCENDING' in opts and 'A' not in flags
                rows.sort(key=lambda r,f=m[1],c='C' in flags:self.expr(f,r).upper() if c else self.expr(f,r),reverse=descending)
            p=self.new_table(opts['TO'],self.fields(),rows)
            self.talk(f'{len(rows)} registro(s) ordenado(s)'); return p
        if cmd=='TOTAL':
            _,opts=clauses(tail,{'ON','TO','FIELDS','FIELD','FOR','WHILE'})
            if not all(k in opts for k in ('ON','TO')): raise XBaseError('TOTAL ON chave TO nome [FIELDS campos] [FOR condição]')
            fields={f.name:f for f in self.fields()}
            listed=opts.get('FIELDS') or opts.get('FIELD')
            totals=[n.upper() for n in split(listed)] if listed else [f.name for f in self.fields() if f.type=='N']
            if any(n not in fields or fields[n].type!='N' for n in totals): raise XBaseError('TOTAL exige campos numéricos.')
            rows,_=self.scope(' '.join(k+' '+v for k,v in opts.items() if k in ('FOR','WHILE')),True)
            groups={}
            for row in rows:
                key=self.expr(opts['ON'],row)
                if key not in groups: groups[key]=dict(row)
                else:
                    for name in totals: groups[key][name]+=row[name]
            # O total pode exceder a largura do campo de origem: o destino é alargado.
            out=[]
            for f in self.fields():
                width=f.length
                if f.name in totals:
                    for g in groups.values(): width=max(width,len(f'{g[f.name]:.{f.decimals}f}'))
                out.append(Field(f.name,f.type,min(width,20),f.decimals))
            p=self.new_table(opts['TO'],out,[{**g,'_deleted':0} for g in groups.values()])
            self.talk(f'{len(groups)} registro(s) gerado(s)'); return p
        if cmd in ('SAVE','RESTORE'):
            if re.match(r'SCREEN\b',tail,re.I):
                m=re.fullmatch(r'SCREEN(?:\s+(?:TO|FROM)\s+([A-Za-z_][A-Za-z_0-9]*))?',tail,re.I)
                if not m: raise XBaseError(cmd+' SCREEN [TO|FROM variável]')
                name=(m[1] or '_SCREEN').upper()
                if cmd=='SAVE': self.variables[name]='\n'.join(''.join(r) for r in self.screen); return
                lines=str(self.variables[name]).split('\n')
                self.screen=[list(l.ljust(80)[:80]) for l in lines[:25]]+[[' ']*80 for _ in range(25-len(lines[:25]))]
                if not self.plain: self.render_screen()
                return
            stripped=re.sub(r'^(TO|FROM)\s+','',tail,flags=re.I)
            name,opts=clauses(stripped,{'ADDITIVE','ALL'})
            p=self.path(name,'.json')
            if cmd=='SAVE':
                names=self.variables.names('ALL '+opts['ALL']) if 'ALL' in opts else list(self.variables)
                payload={k:self.encode_value(self.variables[k]) for k in names}
                p.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
            else:
                legacy=self.path(name,'.mem')
                if not p.exists() and legacy.exists() or p.suffix.lower()=='.mem' and p.read_bytes()[:1]!=b'{':
                    from .dbf import read_mem
                    values=read_mem(legacy if not p.exists() else p,'cp850' if self.encoding=='auto' else self.encoding)
                else:
                    data=json.loads(p.read_text(encoding='utf-8'))
                    values={k:self.decode_value(v) for k,v in data.items()}
                if 'ADDITIVE' not in opts: self.variables.clear()
                self.variables.update(values)
            return
        if cmd in ('ACCEPT','INPUT'):
            prompt,opts=clauses(tail,{'TO'})
            if 'TO' not in opts: raise XBaseError(cmd+' "texto" TO variável')
            # O dBASE II acrescenta dois-pontos à mensagem.
            text=(self.format(self.expr(prompt)) if prompt else '')+(':' if self.dbase2 and prompt else '')
            value=self.input(text)
            while cmd=='INPUT' and not value.strip(): value=self.input(text)
            parsed=self.expr(value) if cmd=='INPUT' else value
            if cmd=='INPUT' and (not isinstance(parsed,(int,float)) or isinstance(parsed,bool)): raise XBaseError('INPUT exige valor numérico.')
            self.variables[opts['TO']]=parsed; return
        if cmd=='WAIT':
            prompt,opts=clauses(tail,{'TO'})
            self.emit(self.format(self.expr(prompt)) if prompt else 'Pressione uma tecla para continuar...',False)
            key=self.inkey(0)
            if 'TO' in opts: self.variables[opts['TO']]=chr(key) if key else ''
            return
        if cmd in ('DIR','DIRECTORY'): return self.directory(re.sub(r'^LIKE\s+','',tail.strip(),flags=re.I))
        if cmd in ('ERASE','RENAME') or cmd=='DELETE' and tail.upper().startswith('FILE '):
            return self.file_command(cmd,tail)
        if cmd in ('IF','DO','ELSE','ELSEIF','ENDIF','CASE','OTHERWISE','ENDCASE','ENDDO','TEXT','ENDTEXT','PROCEDURE','FUNCTION','SCAN','ENDSCAN','FOR','NEXT','ENDFOR'):
            raise XBaseError('Estrutura requer execução de arquivo PRG: '+cmd)
        if cmd=='JOIN': return self.join_command(tail)
        if cmd=='UPDATE': return self.update_command(tail)
        if cmd=='EJECT':
            if self.settings['PRINT'] or self.settings['DEVICE']=='PRINT' or self.printer: self.print_text('\f')
            else: self.emit('\f')
            return
        if cmd in ('UNLOCK','RESET'): return
        if cmd in ('RUN','!'): raise XBaseError('RUN/! não executa comandos do sistema operacional neste interpretador.')
        raise XBaseError('Comando não suportado: '+cmd+'. Consulte HELP/COMPATIBILITY.md.')

    def set_command(self,tail):
        key,_,value=tail.partition(' '); key=key.upper(); value=value.strip()
        if key=='ALTERNATE' and re.match(r'^TO(?:\s|$)',value,re.I):
            dest=re.sub(r'^TO(?:\s+|$)','',value,flags=re.I).strip()
            name,options=clauses(dest,{'ADDITIVE'})
            if self.alternate: self.alternate.close(); self.alternate=None
            if name:
                p=self.path(name,'.txt',False)
                if p.exists() and self.settings['SAFETY'] and 'ADDITIVE' not in options: raise XBaseError('Arquivo de saída existe; use ADDITIVE ou SET SAFETY OFF.')
                self.alternate=p.open('a' if 'ADDITIVE' in options else 'w',encoding='utf-8')
            else: self.settings['ALTERNATE']=False
            return
        value=re.sub(r'^TO(?:\s+|$)','',value,flags=re.I).strip()
        if key in ('COLON','DELIMITERS'):
            if value.upper() in ('ON','OFF'): self.settings['DELIMITERS']=value.upper()=='ON'; return
            if key=='DELIMITERS':
                chars=':' if value.upper()=='DEFAULT' else str(self.expr(value)) if value else ':'
                self.settings['DELIMITER_CHARS']=(chars or ':')[:2]; return
            raise XBaseError('SET COLON exige ON/OFF.')
        if key in ('CONFIRM','DELETED','EXACT','TALK','SAFETY','CONSOLE','ALTERNATE','UNIQUE','SOFTSEEK','CENTURY','LINKAGE','CARRY','INTENSITY','BELL','HEADING','FIXED','PRINT'):
            if value.upper() not in ('ON','OFF'): raise XBaseError('SET '+key+' exige ON/OFF.')
            self.settings[key]=value.upper()=='ON'
            if key in ('DELETED','EXACT'): setattr(self,key.lower(),self.settings[key])
            if key=='ALTERNATE' and self.settings[key] and not self.alternate: raise XBaseError('SET ALTERNATE TO arquivo antes de ON.')
            return
        if key=='PRINTER':
            if value.upper() in ('ON','OFF'): self.settings['PRINT']=value.upper()=='ON'; return
            if self.printer: self.printer.close(); self.printer=None
            name=re.sub(r'^\\\\.*|^(PRN|LPT\d|COM\d):?$','',value,flags=re.I).strip()
            self.settings['PRINTER']=name or 'impressora.txt'; return
        if key=='DEVICE':
            device=value.upper()
            if device.startswith('PRINT'): self.settings['DEVICE']='PRINT'
            elif device=='SCREEN': self.settings['DEVICE']='SCREEN'
            elif device.startswith('FILE'):
                self.set_command('PRINTER TO '+value[4:].strip()); self.settings['DEVICE']='PRINT'
            else: raise XBaseError('SET DEVICE TO SCREEN|PRINT|FILE arquivo')
            return
        if key=='FORMAT':
            # dBASE II: SET FORMAT TO PRINTER/SCREEN escolhe o destino do @ SAY.
            if value.upper() in ('PRINT','PRINTER','SCREEN'): self.settings['DEVICE']='SCREEN' if value.upper()=='SCREEN' else 'PRINT'; return
            self.format_program=self.read_program(value,'.fmt') if value else None; return
        if key=='DIALECT':
            dialect=value.upper().replace(' ','').replace('III','3').replace('II','2')
            if dialect not in DIALECTS: raise XBaseError('SET DIALECT TO DBASE2|DBASE3')
            self.settings['DIALECT']=dialect; return
        if key=='FILTER':
            if value: Expression(self.expand(value))
            self.state['filter']=value; return
        if key=='INDEX': return self.set_indexes(value)
        if key=='ORDER':
            if not value or value=='0': self.state['order']=''; self.state['order_name']=''; self.state['unique_order']=False; self.go('TOP'); return
            names=self.state['indexes']
            if value.isdigit():
                n=int(value)
                if not 1<=n<=len(names): raise XBaseError('Ordem fora dos índices abertos.')
                name=names[n-1]
            else: name=self.index_name(re.sub(r'^TAG\s+','',value,flags=re.I))
            r=self.state['db'].execute('SELECT expression,unique_key FROM _indexes WHERE name=?',(name,)).fetchone()
            if not r: raise XBaseError('Índice desconhecido: '+name)
            if name not in names: names.append(name)
            self.state['order']=r[0]; self.state['order_name']=name; self.state['unique_order']=bool(r[1]); self.go('TOP'); return
        if key=='PROCEDURE': self.procedure_program=self.read_program(value) if value else None; return
        if key=='RELATION':
            if not value: self.state['relations']=[]; return
            relations=[]
            for item in split(value):
                name,opts=clauses(item,{'INTO'})
                if 'INTO' not in opts: raise XBaseError('SET RELATION TO expressão INTO alias')
                child=self.area_number(opts['INTO'])
                if child==self.area: raise XBaseError('Relação circular.')
                def reaches(area,target,seen):
                    if area==target: return True
                    if area in seen: return False
                    seen.add(area)
                    return any(reaches(n,target,seen) for _,n in self.areas.get(area,{}).get('relations',[]))
                if reaches(child,self.area,set()): raise XBaseError('Relação circular.')
                relations.append((name,child))
            self.state['relations']=relations; self.sync_relations(); return
        if key=='DATE':
            if value.upper() not in ('AMERICAN','USA','BRITISH','FRENCH','GERMAN','ITALIAN','ANSI','JAPAN'): raise XBaseError('Formato de data não suportado.')
            self.settings['DATE']=value.upper(); return
        if key=='DECIMALS':
            n=int(self.expr(value))
            if not 0<=n<=20: raise XBaseError('DECIMALS entre 0 e 20.')
            self.settings['DECIMALS']=n; return
        if key=='MARGIN': self.settings['MARGIN']=int(self.expr(value or '0')); return
        if key=='MESSAGE': self.settings['MESSAGE']=str(self.expr(value)) if value else ''; return
        if key in ('PATH','DEFAULT'):
            folder=re.sub(r'^[A-Za-z]:','',value.strip().strip('"\'')).replace('\\','/').strip('/')
            for part in re.split(r'[;,]',folder) if key=='PATH' else [folder]:
                if part.strip() and not (self.cwd/part.strip()).resolve().is_relative_to(self.cwd): raise XBaseError('Caminho fora do diretório de trabalho.')
            self.settings[key]=folder; return
        if key=='FIELDS':
            if value.upper() in ('ON','OFF'): return
            self.settings['FIELDS']=value; return
        if key=='COLOR':
            # SET COLOR TO padrão,realçado[,borda] com os códigos do dBASE (W+/B, N/W, GR+...).
            from .colors import color_scheme
            self.scheme=color_scheme(value,self.monitor_scheme) if value else self.monitor_scheme
            self.settings['COLOR']=value
            if not self.plain and self.scheme: self.emit(self.paint(),False)
            return
        if key=='MONITOR':
            self.settings['COLOR']=''; self.set_monitor(value or 'NENHUM')
            if not self.plain: self.clear_screen()
            return
        if key in SET_STORED:
            self.settings[key]=value.upper() in ('ON',) if value.upper() in ('ON','OFF') else value; return
        raise XBaseError('SET não implementado: '+key+' '+value)

    def copy_command(self,tail):
        if tail.upper().startswith('FILE '):
            source,opts=clauses(tail[5:],{'TO'})
            if 'TO' not in opts: raise XBaseError('COPY FILE origem TO destino')
            import shutil
            p=self.path(source,''); dest=self.path(opts['TO'],'',False)
            if dest.exists() and self.settings['SAFETY']: raise XBaseError('Destino já existe.')
            if any(s['path']==p for s in self.areas.values()): raise XBaseError('Feche o banco antes de COPY FILE; prefira COPY TO.')
            shutil.copyfile(p,dest); return dest
        structure=tail.upper().startswith('STRUCTURE ')
        text=tail[10:] if structure else tail
        _,opts=clauses(text,{'TO','FIELDS','FIELD','STRUCTURE','DELIMITED','SDF','TYPE','FOR','WHILE','ALL','NEXT','RECORD','REST'})
        if 'TO' not in opts: raise XBaseError('COPY [STRUCTURE] TO nome')
        fs=self.fields()
        listed=opts.get('FIELDS') or opts.get('FIELD')
        if listed:
            names=[n.upper() for n in split(listed)]; by_name={f.name:f for f in fs}
            if any(n not in by_name for n in names): raise XBaseError('COPY FIELDS contém campo desconhecido.')
            fs=[by_name[n] for n in names]
        if opts.get('STRUCTURE','').upper()=='EXTENDED':
            fields=[Field('FIELD_NAME','C',10),Field('FIELD_TYPE','C',1),Field('FIELD_LEN','N',3),Field('FIELD_DEC','N',3)]
            return self.new_table(opts['TO'],fields,[{'FIELD_NAME':f.name,'FIELD_TYPE':f.type,'FIELD_LEN':f.length,'FIELD_DEC':f.decimals} for f in fs])
        kind=(opts.get('TYPE') or '').upper()
        if 'SDF' in opts: kind='SDF'
        if 'DELIMITED' in opts: kind='DELIMITED'
        target=opts['TO'].strip()
        if not kind and Path(target.strip('"\'')).suffix.lower()=='.csv': kind='CSV'
        if not kind and Path(target.strip('"\'')).suffix.lower()=='.dbf': kind='DBF'
        filter_text=' '.join(k+(' '+v if v else '') for k,v in opts.items() if k in ('FOR','WHILE','ALL','NEXT','RECORD','REST'))
        rows=[] if structure else self.scope(filter_text,True)[0]
        if kind in ('SDF','DELIMITED','CSV'):
            p=self.path(target,'.csv' if kind=='CSV' else '.txt',False)
            if p.exists() and self.settings['SAFETY']: raise XBaseError('Destino existente. SET SAFETY OFF para sobrescrever.')
            def text(f,value,quote):
                if f.type=='D' and kind=='CSV': return value.isoformat() if value!=EMPTY_DATE else ''
                if f.type=='D': return value.strftime('%Y%m%d') if value!=EMPTY_DATE else ' '*8 if kind=='SDF' else ''
                if f.type=='L': return 'T' if value else 'F'
                if f.type=='N': return (f'{value:.{f.decimals}f}' if f.decimals else str(int(value))).rjust(f.length if kind=='SDF' else 0)
                if f.type=='M': return value.replace('\n',' ')
                return value.ljust(f.length)[:f.length] if kind=='SDF' else quote+value.rstrip()+quote
            if kind=='CSV':
                import csv
                with p.open('w',newline='',encoding='utf-8') as file:
                    writer=csv.writer(file); writer.writerow([f.name for f in fs])
                    writer.writerows([text(f,r[f.name],'').strip() if f.type!='C' else r[f.name].rstrip() for f in fs] for r in rows)
            else:
                separator=re.sub(r'^WITH\s+','',opts.get('DELIMITED',''),flags=re.I).strip()
                blank=separator.upper()=='BLANK'; quote='' if blank else separator or '"'
                with p.open('w',newline='',encoding='utf-8') as file:
                    for r in rows:
                        values=[text(f,r[f.name],quote) for f in fs if not (kind=='SDF' and f.type=='M')]
                        file.write(('' if kind=='SDF' else ' ' if blank else ',').join(values)+'\r\n')
            self.talk(f'{len(rows)} registro(s) copiado(s)')
            return p
        if kind=='DBF':
            from .dbf import write_dbf
            p=super().path(re.sub(r'^[A-Za-z]:(?!/)','',target.strip('"\'')),'.dbf')
            if p.exists() and self.settings['SAFETY']: raise XBaseError('Destino existente. SET SAFETY OFF para sobrescrever.')
            write_dbf(p,fs,rows,'cp850' if self.encoding=='auto' else self.encoding)
            self.talk(f'{len(rows)} registro(s) copiado(s)'); return p
        p=self.new_table(target,fs,rows)
        if not structure: self.talk(f'{len(rows)} registro(s) copiado(s)')
        return p

    def file_command(self,cmd,tail):
        if cmd=='DELETE': tail=tail[5:]
        source,opts=clauses(tail,{'TO'})
        p=self.path(source,'')
        if not p.exists() and not p.suffix:
            # DELETE FILE alunos (dBASE II) apaga o banco de dados de mesmo nome.
            p=self.path(source)
        if any(s['path']==p for s in self.areas.values()): raise XBaseError('Feche o banco antes de alterar o arquivo.')
        if not p.exists(): raise XBaseError('Arquivo não encontrado: '+p.name)
        if cmd=='RENAME':
            if 'TO' not in opts: raise XBaseError('RENAME origem TO destino')
            dest=self.path(opts['TO'],p.suffix if not Path(opts['TO'].strip('"\'')).suffix else '',False)
            if dest.exists(): raise XBaseError('Destino já existe.')
            p.rename(dest); return
        if self.settings['SAFETY'] and self.input('Apagar '+p.name+'? Digite SIM: ')!='SIM': return
        p.unlink()

    def join_command(self,tail):
        head,opts=clauses(tail,{'WITH','TO','FOR','FIELDS','FIELD'})
        if head or not all(k in opts for k in ('TO','FOR')): raise XBaseError('JOIN [WITH alias] TO nome FOR condição [FIELDS campos]')
        parent=self.area
        # dBASE II: sem WITH, junta a área primária com a secundária.
        child=self.area_number(opts['WITH']) if opts.get('WITH') else 2 if parent==1 else 1
        if child==parent or child not in self.areas: raise XBaseError('JOIN exige outra área aberta.')
        parent_fields=self.fields(); parent_rows=self.rows()
        self.area=child
        try: child_fields=self.fields(); child_rows=self.rows()
        finally: self.area=parent
        specs=[]
        listed=opts.get('FIELDS') or opts.get('FIELD')
        if listed:
            for expression in split(listed):
                m=re.fullmatch(r'(?:(\w+)(?:->|\.))?(\w+)',expression.strip())
                if not m: raise XBaseError('JOIN FIELDS exige campo ou alias->campo.')
                area=self.area_number(m[1]) if m[1] else parent; fieldname=m[2].upper()
                if area not in (parent,child): raise XBaseError('JOIN FIELDS referencia uma terceira área.')
                field=next((f for f in (parent_fields if area==parent else child_fields) if f.name==fieldname),None)
                if not field and not m[1]:
                    field=next((f for f in child_fields if f.name==fieldname),None); area=child
                if not field or field.type=='M': raise XBaseError('JOIN: campo desconhecido ou memo não permitido.')
                specs.append((area,field))
        else: specs=[(parent,f) for f in parent_fields if f.type!='M']+[(child,f) for f in child_fields if f.type!='M']
        fields=[]; used=set(); output_specs=[]
        for area,f in specs:
            name=f.name
            n=2
            while name in used: name=f.name[:26]+'_'+str(n); n+=1
            used.add(name); fields.append(Field(name,f.type,f.length,f.decimals)); output_specs.append((area,f.name,name))
        if len(parent_rows)*len(child_rows)>self.max_steps*100: raise XBaseError('JOIN excede limite de combinações; ajuste --max-steps.')
        saved={parent:self.areas[parent]['pointer'],child:self.areas[child]['pointer']}
        old_relations=self.areas[parent].get('relations',[]); self.areas[parent]['relations']=[]
        result=[]
        try:
            for row in parent_rows:
                self.areas[parent]['pointer']=row['_recno']
                for other in child_rows:
                    self.areas[child]['pointer']=other['_recno']
                    if self.expr(opts['FOR'],row): result.append({name:(row if area==parent else other)[source] for area,source,name in output_specs})
        finally:
            for area,pointer in saved.items(): self.areas[area]['pointer']=pointer
            self.areas[parent]['relations']=old_relations
        p=self.new_table(opts['TO'],fields,result)
        self.talk(f'{len(result)} registro(s) gerado(s)'); return p

    def update_command(self,tail):
        head,opts=clauses(tail,{'ON','FROM','REPLACE','RANDOM'})
        if head or not all(k in opts for k in ('ON','FROM','REPLACE')): raise XBaseError('UPDATE ON campo FROM alias REPLACE campo WITH expressão [RANDOM]')
        parent=self.area; child=self.area_number(opts['FROM']); key=opts['ON'].upper()
        if child==parent or child not in self.areas: raise XBaseError('UPDATE exige outra área aberta.')
        fields={f.name:f for f in self.fields()}
        if key not in fields: raise XBaseError('UPDATE ON exige campo simples.')
        rows=self.rows(False)
        if [r[key] for r in rows]!=sorted(r[key] for r in rows): raise XBaseError('UPDATE: destino precisa estar ordenado/indexado pela chave.')
        self.area=child
        try:
            if key not in {f.name for f in self.fields()}: raise XBaseError('Chave ausente na origem UPDATE.')
            source_rows=self.rows()
            if 'RANDOM' not in opts and [r[key] for r in source_rows]!=sorted(r[key] for r in source_rows): raise XBaseError('UPDATE: origem precisa estar ordenada ou usar RANDOM.')
        finally: self.area=parent
        by_key={}
        for row in rows: by_key.setdefault(row[key],dict(row))
        saved={parent:self.areas[parent]['pointer'],child:self.areas[child]['pointer']}
        old_relations=self.areas[parent].get('relations',[]); self.areas[parent]['relations']=[]
        changed={}
        try:
            for other in source_rows:
                row=by_key.get(other[key])
                if not row: continue
                self.areas[parent]['pointer']=row['_recno']; self.areas[child]['pointer']=other['_recno']
                for assignment in split(opts['REPLACE']):
                    name,parts=clauses(assignment,{'WITH'}); name=name.upper()
                    if name not in fields or fields[name].type=='M' or 'WITH' not in parts: raise XBaseError('UPDATE exige campos locais não memo e WITH.')
                    value=self.expr(parts['WITH'],row); self.require_field_type(fields[name],value)
                    stored=self.coerce(fields[name],value); row[name]=self.typed({name:stored})[name]
                    changed.setdefault(row['_recno'],{})[name]=stored
        finally:
            for area,pointer in saved.items(): self.areas[area]['pointer']=pointer
            self.areas[parent]['relations']=old_relations
        with self.state['db']:
            for recno,values in changed.items():
                self.state['db'].execute('UPDATE records SET '+','.join('"'+name+'"=?' for name in values)+' WHERE _recno=?',[*values.values(),recno])
        return len(changed)

    def handle_error(self,error):
        self.last_error=error
        self.handling_error=True
        try:
            self.execute(self.on_error)
            return 'continue'
        except RetrySignal: return 'retry'
        finally: self.handling_error=False


HELP='''dBASE SQLite PLUS 2.2 (dBASE II do MSX e dBASE III PLUS sobre SQLite)
CREATE / CREATE FROM / USE [ALIAS] [INDEX] [SHARED] / SELECT 0|A..J|1..10|PRIMARY|SECONDARY|alias
APPEND / APPEND BLANK / APPEND FROM arq [SDF|DELIMITED|TYPE DBF|CSV] / INSERT [BEFORE] [BLANK]
EDIT [n] / CHANGE [escopo] FIELDS lista / REPLACE / DELETE / RECALL / PACK / ZAP
LIST / DISPLAY [escopo] [campos] [FOR] [WHILE] [OFF] [TO PRINT|TO FILE arq] / DISPLAY STRUCTURE|STATUS|MEMORY|FILES
GO TOP|BOTTOM|n / n / SKIP / LOCATE / CONTINUE / SEEK / FIND / # = RECNO() / SET LINKAGE
COUNT / SUM / AVERAGE / COPY TO [SDF|DELIMITED|TYPE DBF|CSV] / SORT ON .. TO .. [DESCENDING] / TOTAL / JOIN / UPDATE
INDEX ON ... TO / SET INDEX TO (lê chave de NDX/NTX) / SET ORDER TO / REINDEX / SET RELATION TO
MODIFY STRUCTURE (preserva dados) / MODIFY COMMAND / IMPORT FROM arq.dbf / REPORT FORM / CREATE REPORT
STORE / = / PUBLIC / PRIVATE / RELEASE / SAVE / RESTORE (JSON ou MEM do dBASE III)
DO prog WITH ... / SET PROCEDURE TO / PARAMETERS / RETURN / FUNCTION (extensão)
IF/ELSE/ENDIF / DO CASE / DO WHILE/LOOP/EXIT/ENDDO / SCAN / FOR..NEXT (extensões)
@ l,c SAY .. USING|PICTURE .. GET .. PICTURE .. RANGE .. VALID .. WHEN / READ [SAVE] / CLEAR GETS
@ l,c TO l2,c2 [DOUBLE] / @ l,c PROMPT / MENU TO / SAVE SCREEN / SET FORMAT TO arq.fmt|PRINTER|SCREEN
BROWSE [FIELDS lista] [FREEZE campo] [NOAPPEND] [NOEDIT] / LABEL FORM / CREATE LABEL / REPORT FORM
DECLARE a[10] / DIMENSION m(2,3) / LOCAL v[5] / a[1]=.. / {1,2,3} / ALEN ASCAN ASORT AFILL AINS ADEL AADD
COPY TO ARRAY / APPEND FROM ARRAY / SCATTER TO|MEMVAR / GATHER FROM|MEMVAR
SET MONITOR TO VERDE|AMBAR|BRANCO|CORES|NENHUM / SET COLOR TO W+/B,N/W
? / ?? / ??? / TEXT..ENDTEXT / REMARK / ACCEPT / INPUT / WAIT / ERASE / EJECT
SET TALK/CONFIRM/CARRY/COLON/DELIMITERS/EXACT/DELETED/DATE/CENTURY/DECIMALS/PRINT/DEVICE/PRINTER/DIALECT
PLUS CDATE|DDATE|ADATE|TDATE|CHANGE|FORMAT|LZERO|MOD11|CPF|CGC|CODE ... TO variável
CLEAR / CLOSE / DIR / ERASE arq / DELETE FILE / RENAME / COPY FILE / HELP / CANCEL / QUIT
Funções dBASE II: !(texto) $(texto,i,n) @(a,b) # * RANK() TYPE(); EOF/BOF/DATE sem parênteses.
Consulte REVISAO.md e COMPATIBILITY.md para diferenças de SQLite, telas e dialetos.
CLI: python main.py --cwd data --cmd programa.prg [--plain] [--dialect dbase2] [--monitor verde] [--import-dbf arq.dbf]
Auditoria sem executar: python main.py --cwd data --check programa.prg'''
