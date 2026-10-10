"""Interpretador dBASE III PLUS sobre o armazenamento SQLite da versão 1."""
import datetime as dt
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from .storage import DBaseEngine as StorageEngine, Field
from .syntax import XBaseError, split, clauses, outside_words, uncomment, command_parts, COMMANDS
from .memory import Memory, Cell
from .expressions import Expression
from .functions import functions, EMPTY_DATE, ctod, dtoc, str_value, xround
from .program import Program, Routine, execute_nodes, ReturnSignal, LoopSignal, ExitSignal, CancelSignal, RetrySignal, ReturnMasterSignal


class DBaseEngine(StorageEngine):
    def __init__(self,cwd='.',output=print,input_fn=input,plain=False,encoding='auto',max_steps=100000,max_depth=64,key_reader=None):
        super().__init__(cwd,output,input_fn)
        self.variables=Memory()
        self.key_reader=key_reader
        self.settings={'CONFIRM':False,'TALK':True,'SAFETY':True,'CONSOLE':True,'ALTERNATE':False,'DATE':'AMERICAN','CENTURY':False,'DECIMALS':2,'DELETED':False,'EXACT':False,'UNIQUE':False,'SOFTSEEK':False}
        self.plain,self.encoding=plain,encoding
        self.max_steps,self.max_depth=max_steps,max_depth
        self.steps=0; self.calls=[]; self.procedure_program=None
        self.screen_row=self.screen_col=0; self.screen=[[' ']*80 for _ in range(25)]
        self.gets=[]; self.last_key=0; self.alternate=None
        self.compiled={}; self._syncing=set(); self.warnings=[]
        self.on_error=''; self.handling_error=False; self.last_error=None
        self._functions=functions(self)

    def path(self,name,suffix='.sqlite'):
        name=str(name).strip()
        if name.startswith(('"',"'",'[')):
            from .syntax import lex
            tokens=lex(name)
            if tokens[0].kind!='string' or tokens[1].kind!='end': raise XBaseError('Nome de arquivo inválido.')
            name=tokens[0].value
        name=name.replace('\\','/')
        if Path(name).suffix.lower()=='.dbf': name=str(Path(name).with_suffix('.sqlite'))
        p=super().path(name,suffix)
        if not p.exists() and p.parent.exists():
            matches=[f for f in p.parent.iterdir() if f.name.casefold()==p.name.casefold()]
            if len(matches)==1: p=matches[0].resolve()
        if not p.is_relative_to(self.cwd): raise XBaseError('Caminho fora do diretório de trabalho.')
        return p

    def close(self):
        super().close()
        if self.alternate: self.alternate.close(); self.alternate=None

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
        raise XBaseError('Área/alias desconhecido: '+name)

    def record_count(self): return self.state['db'].execute('SELECT COUNT(*) FROM records').fetchone()[0]
    def eof(self): return self.state['pointer']>self.record_count() or self.record_count()==0
    def bof(self): return self.state.get('bof',False) or self.record_count()==0

    def typed(self,row):
        row=dict(row)
        for f in self.fields():
            if f.name not in row: continue
            if f.type=='D': row[f.name]=dt.date.fromisoformat(row[f.name]) if row[f.name] else EMPTY_DATE
            elif f.type=='L': row[f.name]=bool(row[f.name])
            elif f.type=='N' and f.decimals==0: row[f.name]=int(row[f.name])
            elif f.type=='C': row[f.name]=row[f.name].ljust(f.length)
        return row

    def current(self):
        self.sync_relations()
        r=self.state['db'].execute('SELECT * FROM records WHERE _recno=?',(self.state['pointer'],)).fetchone()
        return self.typed(r) if r else {}

    def rows(self,visible=True):
        s=self.state
        rows=[self.typed(r) for r in s['db'].execute('SELECT * FROM records ORDER BY _recno')]
        if s['order']:
            rows.sort(key=lambda r:(self.expr(s['order'],r),r['_recno']))
            if s.get('unique_order'):
                unique=[]; seen=set()
                for r in rows:
                    key=self.expr(s['order'],r)
                    if key not in seen: unique.append(r); seen.add(key)
                rows=unique
        if visible:
            rows=[r for r in rows if (not self.deleted or not r['_deleted']) and (not s['filter'] or self.expr(s['filter'],r))]
        return rows

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
        except KeyError: raise XBaseError('Campo/variável desconhecido: '+name)

    def blank_value(self,f): return EMPTY_DATE if f.type=='D' else False if f.type=='L' else 0 if f.type=='N' else ' '*f.length if f.type=='C' else ''

    def type_code(self,value):
        return 'L' if isinstance(value,bool) else 'D' if isinstance(value,dt.date) else 'N' if isinstance(value,(int,float)) else 'C' if isinstance(value,str) else 'U'

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
                if ch in "'\"[": quote=']' if ch=='[' else ch
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
        if isinstance(value,bool): return '.T.' if value else '.F.'
        if isinstance(value,dt.date): return dtoc(self,value)
        if isinstance(value,float): return f'{value:.{self.settings["DECIMALS"]}f}'
        return str(value)

    def emit(self,text='',newline=True):
        text=str(text)
        if self.alternate and self.settings['ALTERNATE']:
            self.alternate.write(text+('\n' if newline else '')); self.alternate.flush()
        if self.settings['CONSOLE']:
            if self.output is print: print(text,end='\n' if newline else '',flush=True)
            else: self.output(text)

    def show(self,rows,expressions=''):
        es=split(expressions) if expressions else [f.name for f in self.fields()]
        self.emit('RECNO DEL | '+' | '.join(es))
        for r in rows: self.emit(f"{r['_recno']:5} {'*' if r['_deleted'] else ' '}   | "+' | '.join(self.format(self.expr(e,r)) for e in es))
        return rows

    def move(self,recno,bof=False):
        self.state['pointer']=recno; self.state['bof']=bof; self.sync_relations()

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
        rows=self.rows(); ids=[r['_recno'] for r in rows]; pointer=self.state['pointer']
        start=ids.index(pointer) if pointer in ids else len(ids)
        implicit_all=default_all or bool(c.get('FOR'))
        if scope=='ALL' or scope is None and implicit_all and not c.get('WHILE'): selected=rows
        elif scope=='NEXT': selected=rows[start:start+amount]
        elif scope=='RECORD': selected=[r for r in rows if r['_recno']==amount]
        elif scope=='REST' or c.get('WHILE'): selected=rows[start:]
        else: selected=[r for r in rows if r['_recno']==pointer]
        result=[]
        for r in selected:
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
        name,options=clauses(tail,{'ALIAS','INDEX','EXCLUSIVE','SHARED'})
        if not name: return super().execute('USE')
        if options.get('EXCLUSIVE') or options.get('SHARED'): raise XBaseError('EXCLUSIVE/SHARED não recebem argumento.')
        if 'SHARED' in options: raise XBaseError('USE SHARED requer travamento de registros dBASE não implementado.')
        p=self.path(name)
        alias=options.get('ALIAS',p.stem).upper()
        if not re.fullmatch(r'[A-Z_][A-Z_0-9]*',alias): raise XBaseError('Alias inválido: '+alias)
        if any(n!=self.area and s['alias'].upper()==alias for n,s in self.areas.items()): raise XBaseError('Alias já aberto: '+alias)
        super().execute('USE "'+str(p)+'" ALIAS '+alias)
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
        rows=self.rows()
        if tail.upper() in ('TOP','BOTTOM'):
            self.move(rows[0 if tail.upper()=='TOP' else -1]['_recno'] if rows else self.record_count()+1)
        else:
            n=int(self.expr(tail))
            if not 1<=n<=self.record_count(): raise XBaseError('Número de registro fora do banco.')
            self.move(n)

    def skip(self,tail):
        n=int(self.expr(tail or '1')); rows=self.rows(); ids=[r['_recno'] for r in rows]; p=self.state['pointer']
        if n==0: self.move(p,self.state.get('bof',False)); return
        if p in ids: i=ids.index(p)
        elif p>self.record_count(): i=len(ids)
        else:
            # Ponteiro pode estar em registro filtrado; usa a posição na ordem completa.
            full=[r['_recno'] for r in self.rows(False)]
            if p in full:
                at=full.index(p); i=sum(full.index(rid)<at for rid in ids)-(1 if n>0 else 0)
            else: i=-1
        i+=n
        if i<0: self.move(ids[0] if ids else 1,True)
        elif i>=len(ids): self.move(self.record_count()+1)
        else: self.move(ids[i])

    def index_name(self,name): return Path(str(name).strip().strip("\"'")).stem.upper()

    def set_indexes(self,text):
        names=[self.index_name(n) for n in split(text) if n]
        available={r[0]:(r[1],r[2]) for r in self.state['db'].execute('SELECT name,expression,unique_key FROM _indexes')}
        for name in names:
            if name not in available: raise XBaseError('Índice não encontrado neste SQLite: '+name)
        self.state['indexes']=names
        self.state['order_name']=names[0] if names else ''
        self.state['order']=available[names[0]][0] if names else ''
        self.state['unique_order']=bool(available[names[0]][1]) if names else False
        self.go('TOP')

    def seek(self,value):
        if not self.state['order']: raise XBaseError('SEEK exige índice ativo.')
        rows=self.rows(); exp=self.state['order']; found=None
        for row in rows:
            key=self.expr(exp,row)
            if (isinstance(key,str) and isinstance(value,str) and (key.rstrip()==value.rstrip() if self.exact else key.startswith(value))) or not isinstance(key,str) and key==value:
                found=row; break
        self.state['found']=bool(found)
        if found: self.move(found['_recno'])
        elif self.settings['SOFTSEEK']:
            following=next((r for r in rows if self.expr(exp,r)>=value),None); self.move(following['_recno'] if following else self.record_count()+1)
        else: self.move(self.record_count()+1)
        self.variables['FOUND']=bool(found)
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
        picture=str(picture)
        flags=''; template=picture
        if picture.startswith('@'):
            flags,_,template=picture.partition(' ')
        if isinstance(value,dt.date): return dtoc(self,value)
        if isinstance(value,bool): return ('Y' if value else 'N') if 'Y' in template else ('.T.' if value else '.F.')
        if isinstance(value,(int,float)) and any(c in template for c in '9#'):
            width=len(template); decimals=len(template.rsplit('.',1)[1]) if '.' in template else 0
            text=f'{value:,.{decimals}f}' if ',' in template else f'{value:.{decimals}f}'
            return text.rjust(width) if len(text)<=width else '*'*width
        text=self.format(value)
        if '!' in flags or '!' in template: text=text.upper()
        if template and all(c in 'X!A9' for c in template): text=text[:len(template)].ljust(len(template))
        return text

    def at(self,tail):
        coords,main=clauses(tail,{'SAY','GET','CLEAR','TO'})
        opts={k:v for k,v in main.items() if k not in ('SAY','GET')}
        if 'SAY' in main:
            expression,say_opts=clauses(main['SAY'],{'PICTURE','USING','FUNCTION','COLOR'})
            opts['SAY']=expression
            if 'PICTURE' in say_opts: opts['SAY_PICTURE']=say_opts['PICTURE']
            if 'USING' in say_opts: opts['SAY_PICTURE']=say_opts['USING']
            if 'FUNCTION' in say_opts: opts['SAY_PICTURE']='"@'+str(self.expr(say_opts['FUNCTION']))+'"'
            if 'COLOR' in say_opts: opts['COLOR']=say_opts['COLOR']
        if 'GET' in main:
            target,get_opts=clauses(main['GET'],{'PICTURE','RANGE','VALID','WHEN','COLOR','FUNCTION'})
            opts['GET']=target; opts.update(get_opts)
        pair=split(coords)
        if len(pair)!=2: raise XBaseError('@ exige linha,coluna.')
        row,col=(int(self.expr(v)) for v in pair)
        if not 0<=row<25 or not 0<=col<80: raise XBaseError('Coordenada fora da tela 25x80.')
        self.screen_row,self.screen_col=row,col
        if 'VALID' in opts or 'WHEN' in opts: raise XBaseError('VALID/WHEN em GET são de outros dialetos e não estão implementados.')
        if 'COLOR' in opts: raise XBaseError('COLOR na cláusula @ não está implementado; use SET COLOR TO.')
        if 'TO' in opts:
            end=split(opts['TO'])
            if len(end)!=2: raise XBaseError('@ TO exige linha,coluna final.')
            r2,c2=(int(self.expr(v)) for v in end)
            if not row<=r2<25 or not col<=c2<80: raise XBaseError('Retângulo fora da tela.')
            for r in range(row,r2+1):
                for c in range(col,c2+1):
                    self.screen[r][c]=' ' if 'CLEAR' in opts else '+' if r in (row,r2) and c in (col,c2) else '-' if r in (row,r2) else '|' if c in (col,c2) else self.screen[r][c]
            if not self.plain: self.render_screen()
            return
        if not opts or 'CLEAR' in opts:
            self.screen[row][col:]=[' ']*(80-col)
            if not self.plain: self.emit(f'\033[{row+1};{col+1}H\033[K',False)
        if 'SAY' in opts:
            value=self.expr(opts['SAY']); text=self.picture(value,self.expr(opts['SAY_PICTURE'])) if 'SAY_PICTURE' in opts else self.format(value)
            self.screen[row][col:col+min(len(text),80-col)]=list(text[:80-col]); self.screen_col=min(79,col+len(text))
            self.emit((f'\033[{row+1};{col+1}H' if not self.plain else '')+text,self.plain and 'GET' not in opts)
        if 'GET' in opts:
            target=opts['GET'].strip()
            if not re.fullmatch(r'(?:(?:[A-Za-z_][A-Za-z_0-9]*)(?:->|\.))?[A-Za-z_][A-Za-z_0-9]*',target): raise XBaseError('GET exige campo ou variável simples.')
            self.expr(target)  # GET requer variável já inicializada.
            self.gets.append({'target':target,'picture':self.expr(opts['PICTURE']) if 'PICTURE' in opts else ('@'+str(self.expr(opts['FUNCTION'])) if 'FUNCTION' in opts else ''),'range':opts.get('RANGE',''),'row':row,'col':self.screen_col})
            self.draw_get(self.gets[-1])

    def render_screen(self): self.emit('\033[H'+'\n'.join(''.join(r) for r in self.screen),False)

    def assign_target(self,target,value):
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
            with self.state['db']: self.state['db'].execute(f'UPDATE records SET "{name}"=? WHERE _recno=?',(self.coerce(fs[name],value),self.state['pointer']))
        finally: self.area=old

    def require_field_type(self,f,value):
        code=self.type_code(value)
        if code != ('C' if f.type=='M' else f.type): raise XBaseError('Tipo incompatível em '+f.name+': esperado '+f.type+', recebido '+code)

    def get_mask(self,item):
        from .forms import PictureMask
        value=self.expr(item['target']); width=None
        match=re.fullmatch(r'(?:(\w+)(?:->|\.))?(\w+)',item['target'])
        old=self.area
        try:
            if match[1] and match[1].upper() not in ('M','MEMVAR'): self.area=self.area_number(match[1])
            if self.area in self.areas and (not match[1] or match[1].upper() not in ('M','MEMVAR')):
                field=next((f for f in self.fields() if f.name==match[2].upper()),None)
                if field: width=field.length if field.type!='D' else None
        finally: self.area=old
        return PictureMask(value,item['picture'],self.format,width)

    def draw_get(self,item,text=None,cursor=None):
        mask=self.get_mask(item)
        text=mask.initial() if text is None else text
        row,col=item['row'],item['col']
        display=':'+text+':'
        visible=display[:max(0,80-col)]
        self.screen[row][col:col+len(visible)]=list(visible)
        if not self.plain:
            self.emit(f'\033[{row+1};{col+1}H'+visible,False)
            if cursor is not None: self.emit(f'\033[{row+1};{min(80,col+cursor+2)}H',False)
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

    def read_gets(self):
        from .forms import FieldEditor, terminal_keys, normalize_key
        if not self.gets: raise XBaseError('READ exige ao menos um GET pendente.')
        gets=self.gets; self.gets=[]
        interactive=self.key_reader is not None or self.input is input and sys.stdin.isatty() and not self.plain
        if not interactive:
            for item in gets:
                mask=self.get_mask(item)
                while True:
                    raw=self.input(item['target']+' :'+mask.initial()+': ')
                    if raw=='': break
                    try:
                        text=mask.input_text(raw)
                        value=self.get_value(item,mask,text)
                        self.assign_target(item['target'],value); self.draw_get(item,self.get_mask(item).initial()); break
                    except (ValueError,TypeError) as exc: self.emit('Erro: '+str(exc))
            self.last_key=13; return
        def edit(read_key):
            index=0
            while index<len(gets):
                item=gets[index]; mask=self.get_mask(item); editor=FieldEditor(mask,self.settings['CONFIRM'])
                while True:
                    self.draw_get(item,editor.text,editor.position)
                    key=read_key()
                    if len(key)==1: key=normalize_key(key)
                    action=editor.event(key)
                    if action=='cancel': self.last_key=27; return
                    if action=='invalid': self.emit('\a',False); continue
                    if action not in ('next','previous'): continue
                    try:
                        if editor.changed: self.assign_target(item['target'],self.get_value(item,mask,editor.text))
                    except (ValueError,TypeError): self.emit('\a',False); continue
                    self.draw_get(item,self.get_mask(item).initial(),None)
                    self.last_key=13 if key=='ENTER' else 9 if key=='TAB' else 0
                    index=max(0,index-1) if action=='previous' else index+1
                    break
        if self.key_reader is not None: edit(self.key_reader)
        else:
            with terminal_keys() as read_key: edit(read_key)

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

    def new_table(self,name,fields,records=()):
        """Cria cópia sem trocar a área selecionada ou perder a conexão do chamador."""
        p=self.path(name)
        if p.exists(): raise XBaseError('Destino já existe: '+p.name)
        old_area=self.area
        temporary=next((i for i in range(11,100) if i not in self.areas),99)
        self.area=temporary
        try:
            super().create(str(p),[Field(**vars(f)) for f in fields])
            for r in records: self.append({f.name:r[f.name] for f in fields})
        except Exception:
            if temporary in self.areas: self.areas.pop(temporary)['db'].close()
            p.unlink(missing_ok=True)
            raise
        finally:
            if temporary in self.areas: self.areas.pop(temporary)['db'].close()
            self.area=old_area
        return p

    def append_many(self,records):
        fs=self.fields()
        data=[[self.coerce(f,r.get(f.name,self.blank_value(f))) for f in fs] for r in records]
        if not data: return
        sql='INSERT INTO records ('+','.join('"'+f.name+'"' for f in fs)+') VALUES ('+','.join('?' for _ in fs)+')'
        with self.state['db']:
            for values in data: cur=self.state['db'].execute(sql,values)
        self.move(cur.lastrowid)

    def check(self,name):
        from .compatibility import inspect_program
        return inspect_program(self,self.read_program(name))

    def execute(self,line):
        line=uncomment(str(line)).strip()
        if not line: return
        line=self.expand(line)
        # Atribuição é distinta de comparação em expressões.
        m=re.fullmatch(r'((?:M->|M\.)?[A-Za-z_][A-Za-z_0-9]*)\s*(?::=|=)\s*(.+)',line,re.I|re.S)
        if m:
            name=re.sub(r'^M(?:->|\.)','',m[1],flags=re.I)
            self.variables[name]=self.expr(m[2]); return
        cmd,tail=command_parts(line)
        if cmd in ('?','??'):
            values=[self.format(self.expr(e)) for e in split(tail)] if tail else ['']
            self.emit(' '.join(values),cmd=='?'); return
        if cmd=='???': raise XBaseError('??? exige impressora física; não implementado.')
        if cmd=='@': return self.at(tail)
        if cmd=='QUIT': self.running=False; self.close(); return
        if cmd=='CANCEL': raise CancelSignal()
        if cmd=='ON':
            key,_,handler=tail.partition(' ')
            if key.upper()!='ERROR': raise XBaseError('ON implementado apenas para ERROR.')
            self.on_error=handler.strip(); return
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
            if len(names)!=len(call['args']): raise XBaseError('Número de PARAMETERS difere de DO ... WITH.')
            for name,cell in zip(names,call['args']):
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name): raise XBaseError('Nome de parâmetro inválido.')
                self.variables.bind(name,cell)
            call['parameters']=True; return
        if cmd in ('PRIVATE','PUBLIC'):
            names=self.variables.names(tail)
            if cmd=='PRIVATE': self.variables.private(names)
            else: self.variables.declare_public(names)
            return
        if cmd=='STORE':
            expression,opts=clauses(tail,{'TO'})
            if 'TO' not in opts: raise XBaseError('STORE expressão TO variáveis')
            value=self.expr(expression)
            for name in self.variables.names(opts['TO']): self.variables[name]=value
            return
        if cmd=='RELEASE':
            for name in self.variables.names(tail):
                try: del self.variables[name]
                except KeyError: pass
            return
        if cmd=='SET': return self.set_command(tail)
        if cmd=='CLEAR':
            if not tail or tail.upper()=='SCREEN':
                self.screen=[[' ']*80 for _ in range(25)]; self.screen_row=self.screen_col=0
                if not self.plain: self.emit('\033[2J\033[H',False)
            elif tail.upper()=='GETS': self.gets=[]
            elif tail.upper()=='MEMORY': self.variables.clear()
            elif tail.upper()=='ALL':
                for s in self.areas.values(): s['db'].close()
                self.areas.clear(); self.variables.clear(); self.gets=[]; self.procedure_program=None
            else: raise XBaseError('CLEAR suportado: SCREEN, GETS, MEMORY, ALL.')
            return
        if cmd=='CLOSE':
            if tail.upper() in ('ALL','DATABASES'):
                for s in self.areas.values(): s['db'].close()
                self.areas.clear()
                if tail.upper()=='ALL': self.procedure_program=None; self.gets=[]
            elif tail.upper()=='PROCEDURE': self.procedure_program=None
            elif tail.upper()=='INDEX': self.set_indexes('')
            elif not tail: super().execute('USE')
            else: raise XBaseError('CLOSE suportado: ALL, DATABASES, PROCEDURE, INDEX.')
            return
        if cmd=='READ':
            if tail: raise XBaseError('READ não aceita opções nesta implementação.')
            return self.read_gets()
        if cmd=='CREATE':
            name,opts=clauses(tail,{'FROM'})
            if 'FROM' in opts:
                source=self.path(opts['FROM']); db=sqlite3.connect(source)
                try:
                    db.row_factory=sqlite3.Row; records=[dict(r) for r in db.execute('SELECT * FROM records ORDER BY _recno')]
                    fs=[Field(str(r['FIELD_NAME']).strip(),str(r['FIELD_TYPE']).strip(),int(r['FIELD_LEN']),int(r['FIELD_DEC'])) for r in records]
                finally: db.close()
                return self.create(name,fs)
            return super().execute('CREATE '+tail)
        if cmd in ('LIST','DISPLAY','BROWSE'):
            kind=tail.upper()
            if kind=='FILES': return self.execute('DIR')
            if kind=='STRUCTURE': self.emit('\n'.join(f'{f.name} {f.type} {f.length} {f.decimals}' for f in self.fields())); return
            if kind=='MEMORY': self.emit('\n'.join(f'{k:<12} ({self.type_code(v)}) {self.format(v)}' for k,v in self.variables.items())); return
            if kind=='STATUS':
                self.emit(json.dumps({'area':self.area,'settings':self.settings,'areas':{n:{k:str(v) for k,v in s.items() if k!='db'} for n,s in self.areas.items()}},indent=2)); return
            head,opts=clauses(tail,{'OFF','TO'})
            if opts.get('OFF'): raise XBaseError('OFF não recebe argumento.')
            if 'TO' in opts: raise XBaseError('LIST/DISPLAY TO: use SET ALTERNATE TO/ON para saída em arquivo.')
            rows,ex=self.scope(head,cmd in ('LIST','BROWSE')); result=self.show(rows,ex)
            self.scope_end(head,rows,cmd in ('LIST','BROWSE')); return result
        if cmd=='APPEND':
            if tail.upper()=='BLANK': self.append(); self.state['bof']=False; self.sync_relations(); return
            name,opts=clauses(tail,{'FROM','FOR','DELIMITED','SDF'})
            if 'FROM' in opts:
                source=opts['FROM']
                if 'SDF' in opts: raise XBaseError('APPEND FROM SDF não implementado.')
                p=self.path(source,'.csv' if 'DELIMITED' in opts or Path(source).suffix.lower()=='.csv' else '.sqlite')
                records=[]
                if p.suffix.lower()=='.csv' or 'DELIMITED' in opts:
                    import csv
                    with p.open(newline='',encoding='utf-8-sig') as f: records=list(csv.DictReader(f))
                else:
                    db=sqlite3.connect(p); db.row_factory=sqlite3.Row
                    try: records=[dict(r) for r in db.execute('SELECT * FROM records ORDER BY _recno')]
                    finally: db.close()
                fs=self.fields(); typed=[]
                for r in records:
                    if r.get('_deleted'): continue
                    values={f.name:self.coerce(f,r.get(f.name,self.blank_value(f))) for f in fs}
                    if not opts.get('FOR') or self.expr(opts['FOR'],self.typed({'_recno':0,'_deleted':0,**values})): typed.append(values)
                self.append_many(typed); return
            return super().execute('APPEND')
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
                        fs={f.name:f for f in self.fields()}; name=name.upper()
                        if name not in fs: raise XBaseError('Campo desconhecido: '+target)
                        if not self.current(): raise XBaseError('Destino sem registro atual: '+target)
                        self.require_field_type(fs[name],value)
                        plans.append((self.area,name,self.coerce(fs[name],value),self.state['pointer']))
                    finally: self.area=old
                for area,name,value,recno in plans:
                    db=self.areas[area]['db']
                    with db: db.execute('UPDATE records SET "'+name+'"=? WHERE _recno=?',(value,recno))
                return
            fs={f.name:f for f in self.fields()}; updates=[]
            for r in rows:
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
            with self.state['db']:
                for r,values in updates:
                    sql='UPDATE records SET '+','.join('"'+name+'"=?' for name in values)+' WHERE _recno=?'
                    self.state['db'].execute(sql,[*values.values(),r['_recno']])
            self.scope_end(tail,rows); return
        if cmd in ('DELETE','RECALL') and not tail.upper().startswith('FILE '):
            rows,extra=self.scope(tail)
            if extra: raise XBaseError('Escopo inválido: '+extra)
            with self.state['db']: self.state['db'].executemany('UPDATE records SET _deleted=? WHERE _recno=?',[(cmd=='DELETE',r['_recno']) for r in rows])
            self.scope_end(tail,rows); return
        if cmd=='PACK':
            super().execute('PACK'); self.state['bof']=False; return
        if cmd=='ZAP':
            if self.settings['SAFETY'] and self.input('Apagar todos os registros? Digite SIM: ')!='SIM': return
            with self.state['db']: self.state['db'].execute('DELETE FROM records')
            self.move(1); return
        if cmd in ('EDIT','CHANGE'):
            if tail: self.go(tail)
            row=self.current()
            if not row: raise XBaseError('Sem registro atual.')
            values={}
            for f in self.fields():
                raw=self.input(f'{f.name} [{self.format(row[f.name]).rstrip()}]: ')
                if raw: values[f.name]=self.coerce(f,raw)
            if values:
                with self.state['db']: self.state['db'].execute('UPDATE records SET '+','.join('"'+k+'"=?' for k in values)+' WHERE _recno=?',[*values.values(),row['_recno']])
            return
        if cmd in ('LOCATE','CONTINUE'):
            if cmd=='LOCATE': self.state['locate_tail']=tail
            if 'locate_tail' not in self.state: raise XBaseError('CONTINUE exige LOCATE anterior.')
            original=self.state['locate_tail']
            rows,extra=self.scope(original,True)
            if extra: raise XBaseError('LOCATE exige FOR condição.')
            ids=[r['_recno'] for r in self.rows()]
            if cmd=='CONTINUE':
                p=self.state['pointer']; start=ids.index(p)+1 if p in ids else len(ids)
                allowed=set(ids[start:]); rows=[r for r in rows if r['_recno'] in allowed]
            found=rows[0] if rows else None
            self.move(found['_recno'] if found else self.record_count()+1); self.state['found']=bool(found)
            self.variables['FOUND']=bool(found)
            if self.settings['TALK']: self.emit('Encontrado.' if found else 'Não encontrado.')
            return bool(found)
        if cmd in ('SEEK','FIND'):
            return self.seek(self.expr(tail) if cmd=='SEEK' else tail.strip("\"'"))
        if cmd in ('COUNT','SUM','AVERAGE'):
            expression,opts=clauses(tail,{'TO'})
            rows,ex=self.scope(expression,True)
            if cmd=='COUNT' and ex: raise XBaseError('COUNT não aceita lista de campos.')
            values=[len(rows)] if cmd=='COUNT' else [sum(self.expr(e,r) for r in rows)/(len(rows) or 1) if cmd=='AVERAGE' else sum(self.expr(e,r) for r in rows) for e in split(ex)]
            if 'TO' in opts:
                names=self.variables.names(opts['TO'])
                if len(names)!=len(values): raise XBaseError('Número de variáveis TO difere das expressões.')
                for name,value in zip(names,values): self.variables[name]=value
            self.last_count=len(rows)
            if self.settings['TALK']: self.emit(' '.join(self.format(v) for v in values))
            self.scope_end(expression,rows,True); return values[0] if len(values)==1 else values
        if cmd=='INDEX':
            head,opts=clauses(tail,{'ON','TO','UNIQUE'})
            if head or 'ON' not in opts or 'TO' not in opts: raise XBaseError('INDEX ON expressão TO nome [UNIQUE]')
            name=self.index_name(opts['TO'])
            if not re.fullmatch(r'[A-Z_][A-Z_0-9]*',name): raise XBaseError('Nome de índice inválido.')
            for row in self.rows(False): self.expr(opts['ON'],row)
            with self.state['db']:
                self.state['db'].execute('INSERT OR REPLACE INTO _indexes (name,expression,unique_key) VALUES (?,?,?)',(name,opts['ON'],int('UNIQUE' in opts or self.settings['UNIQUE'])))
                self.state['db'].execute('DROP INDEX IF EXISTS "idx_'+name+'"')
                if opts['ON'].upper() in {f.name for f in self.fields()}:
                    self.state['db'].execute('CREATE INDEX IF NOT EXISTS "idx_'+name+'" ON records ("'+opts['ON'].upper()+'")')
            self.state['indexes']=[name]; self.state['order_name']=name; self.state['order']=opts['ON']; self.state['unique_order']='UNIQUE' in opts or self.settings['UNIQUE']; self.go('TOP'); return
        if cmd=='REINDEX': self.rows(False); return
        if cmd=='COPY': return self.copy_command(tail)
        if cmd=='SORT':
            _,opts=clauses(tail,{'TO','ON','FOR','WHILE'})
            if 'TO' not in opts or 'ON' not in opts: raise XBaseError('SORT TO nome ON campos [FOR condição]')
            filter_text=' '.join(k+' '+v for k,v in opts.items() if k in ('FOR','WHILE'))
            rows,_=self.scope(filter_text,True)
            for key in reversed(split(opts['ON'])):
                m=re.fullmatch(r'(\w+)(?:/(A|D|C))?',key,re.I)
                if not m: raise XBaseError('SORT suporta campo[/A|/D|/C].')
                rows.sort(key=lambda r:self.expr(m[1],r).upper() if m[2] and m[2].upper()=='C' else self.expr(m[1],r),reverse=bool(m[2] and m[2].upper()=='D'))
            return self.new_table(opts['TO'],self.fields(),rows)
        if cmd=='TOTAL':
            _,opts=clauses(tail,{'ON','TO','FIELDS'})
            if not all(k in opts for k in ('ON','TO','FIELDS')): raise XBaseError('TOTAL ON chave TO nome FIELDS campos')
            fields={f.name:f for f in self.fields()}; totals=[n.upper() for n in split(opts['FIELDS'])]
            if any(n not in fields or fields[n].type!='N' for n in totals): raise XBaseError('TOTAL exige campos numéricos.')
            groups={}
            for row in self.rows():
                key=self.expr(opts['ON'],row)
                if key not in groups: groups[key]=dict(row)
                else:
                    for name in totals: groups[key][name]+=row[name]
            return self.new_table(opts['TO'],self.fields(),groups.values())
        if cmd in ('SAVE','RESTORE'):
            stripped=re.sub(r'^(TO|FROM)\s+','',tail,flags=re.I)
            name,opts=clauses(stripped,{'ADDITIVE','ALL'})
            p=self.path(name,'.json')
            if cmd=='SAVE':
                names=self.variables.names('ALL '+opts['ALL']) if 'ALL' in opts else list(self.variables)
                payload={k:{'type':self.type_code(self.variables[k]),'value':self.variables[k].isoformat() if isinstance(self.variables[k],dt.date) else self.variables[k]} for k in names}
                p.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
            else:
                data=json.loads(p.read_text(encoding='utf-8'))
                values={k:dt.date.fromisoformat(v['value']) if isinstance(v,dict) and v.get('type')=='D' else v['value'] if isinstance(v,dict) and 'type' in v else v for k,v in data.items()}
                if 'ADDITIVE' not in opts: self.variables.clear()
                self.variables.update(values)
            return
        if cmd in ('ACCEPT','INPUT'):
            prompt,opts=clauses(tail,{'TO'})
            if 'TO' not in opts: raise XBaseError(cmd+' "texto" TO variável')
            value=self.input(self.format(self.expr(prompt)) if prompt else '')
            parsed=self.expr(value) if cmd=='INPUT' else value
            if cmd=='INPUT' and (not isinstance(parsed,(int,float)) or isinstance(parsed,bool)): raise XBaseError('INPUT exige valor numérico.')
            self.variables[opts['TO']]=parsed; return
        if cmd=='WAIT':
            prompt,opts=clauses(tail,{'TO'})
            self.emit(self.format(self.expr(prompt)) if prompt else 'Pressione uma tecla...',False)
            key=self.inkey(0)
            if 'TO' in opts: self.variables[opts['TO']]=chr(key) if key else ''
            return
        if cmd in ('DIR','DIRECTORY'):
            pattern=tail.strip() or '*.sqlite'
            self.emit('\n'.join(p.name for p in self.cwd.glob(pattern) if p.is_file())); return
        if cmd in ('ERASE','RENAME') or cmd=='DELETE' and tail.upper().startswith('FILE '):
            return self.file_command(cmd,tail)
        if cmd in ('IF','DO','ELSE','ENDIF','CASE','OTHERWISE','ENDCASE','ENDDO','TEXT','ENDTEXT','PROCEDURE','FUNCTION'):
            raise XBaseError('Estrutura requer execução de arquivo PRG: '+cmd)
        if cmd=='JOIN': return self.join_command(tail)
        if cmd=='UPDATE': return self.update_command(tail)
        if cmd=='EJECT': self.emit('\f'); return
        raise XBaseError('Comando não suportado: '+cmd+'. Consulte HELP/COMPATIBILITY.md.')

    def set_command(self,tail):
        key,_,value=tail.partition(' '); key=key.upper(); value=value.strip()
        if key=='ALTERNATE' and re.match(r'^TO(?:\s|$)',value,re.I):
            dest=re.sub(r'^TO(?:\s+|$)','',value,flags=re.I).strip()
            name,options=clauses(dest,{'ADDITIVE'})
            if self.alternate: self.alternate.close(); self.alternate=None
            if name:
                p=self.path(name,'.txt')
                if p.exists() and self.settings['SAFETY'] and 'ADDITIVE' not in options: raise XBaseError('Arquivo de saída existe; use ADDITIVE ou SET SAFETY OFF.')
                self.alternate=p.open('a' if 'ADDITIVE' in options else 'w',encoding='utf-8')
            else: self.settings['ALTERNATE']=False
            return
        value=re.sub(r'^TO(?:\s+|$)','',value,flags=re.I).strip()
        if key in ('CONFIRM','DELETED','EXACT','TALK','SAFETY','CONSOLE','ALTERNATE','UNIQUE','SOFTSEEK','CENTURY'):
            if value.upper() not in ('ON','OFF'): raise XBaseError('SET '+key+' exige ON/OFF.')
            self.settings[key]=value.upper()=='ON'
            if key in ('DELETED','EXACT'): setattr(self,key.lower(),self.settings[key])
            if key=='ALTERNATE' and self.settings[key] and not self.alternate: raise XBaseError('SET ALTERNATE TO arquivo antes de ON.')
            return
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
            else: name=self.index_name(value)
            r=self.state['db'].execute('SELECT expression,unique_key FROM _indexes WHERE name=?',(name,)).fetchone()
            if not r: raise XBaseError('Índice desconhecido: '+name)
            if name not in names: names.append(name)
            self.state['order']=r[0]; self.state['order_name']=name; self.state['unique_order']=bool(r[1]); self.go('TOP'); return
        if key=='PROCEDURE': self.procedure_program=self.read_program(value) if value else None; return
        if key=='RELATION':
            if not value: self.state['relations']=[]; return
            name,opts=clauses(value,{'INTO'})
            if 'INTO' not in opts: raise XBaseError('SET RELATION TO expressão INTO alias')
            child=self.area_number(opts['INTO'])
            if child==self.area: raise XBaseError('Relação circular.')
            def reaches(area,target,seen):
                if area==target: return True
                if area in seen: return False
                seen.add(area)
                return any(reaches(n,target,seen) for _,n in self.areas.get(area,{}).get('relations',[]))
            if reaches(child,self.area,set()): raise XBaseError('Relação circular.')
            self.state['relations']=[(name,child)]; self.sync_relations(); return
        if key=='DATE':
            if value.upper() not in ('AMERICAN','USA','BRITISH','FRENCH','GERMAN','ITALIAN','ANSI','JAPAN'): raise XBaseError('Formato de data não suportado.')
            self.settings['DATE']=value.upper(); return
        if key=='DECIMALS':
            n=int(self.expr(value))
            if not 0<=n<=20: raise XBaseError('DECIMALS entre 0 e 20.')
            self.settings['DECIMALS']=n; return
        if key=='COLOR':
            # Configuração armazenada e exposta no STATUS; renderização monocromática.
            self.settings['COLOR']=value; return
        raise XBaseError('SET não implementado: '+key+' '+value)

    def copy_command(self,tail):
        if tail.upper().startswith('FILE '):
            source,opts=clauses(tail[5:],{'TO'})
            if 'TO' not in opts: raise XBaseError('COPY FILE origem TO destino')
            import shutil
            p=self.path(source,''); dest=self.path(opts['TO'],'')
            if dest.exists(): raise XBaseError('Destino já existe.')
            if any(s['path']==p for s in self.areas.values()): raise XBaseError('Feche o banco antes de COPY FILE; prefira COPY TO.')
            shutil.copyfile(p,dest); return dest
        structure=tail.upper().startswith('STRUCTURE ')
        text=tail[10:] if structure else tail
        _,opts=clauses(text,{'TO','FIELDS','STRUCTURE','DELIMITED','SDF','FOR','WHILE','ALL','NEXT','RECORD','REST'})
        if 'TO' not in opts: raise XBaseError('COPY [STRUCTURE] TO nome')
        fs=self.fields()
        if 'FIELDS' in opts:
            names=[n.upper() for n in split(opts['FIELDS'])]; by_name={f.name:f for f in fs}
            if any(n not in by_name for n in names): raise XBaseError('COPY FIELDS contém campo desconhecido.')
            fs=[by_name[n] for n in names]
        if opts.get('STRUCTURE','').upper()=='EXTENDED':
            fields=[Field('FIELD_NAME','C',10),Field('FIELD_TYPE','C',1),Field('FIELD_LEN','N',3),Field('FIELD_DEC','N',3)]
            return self.new_table(opts['TO'],fields,[{'FIELD_NAME':f.name,'FIELD_TYPE':f.type,'FIELD_LEN':f.length,'FIELD_DEC':f.decimals} for f in fs])
        if 'SDF' in opts: raise XBaseError('COPY SDF não implementado.')
        filter_text=' '.join(k+(' '+v if v else '') for k,v in opts.items() if k in ('FOR','WHILE','ALL','NEXT','RECORD','REST'))
        rows=[] if structure else self.scope(filter_text,True)[0]
        if 'DELIMITED' in opts:
            if opts['DELIMITED']: raise XBaseError('DELIMITED usa CSV com separador vírgula; opções adicionais não implementadas.')
            import csv
            p=self.path(opts['TO'],'.csv')
            if p.exists() and self.settings['SAFETY']: raise XBaseError('Destino existente. SET SAFETY OFF para sobrescrever CSV.')
            with p.open('w',newline='',encoding='utf-8') as file:
                writer=csv.DictWriter(file,fieldnames=[f.name for f in fs]); writer.writeheader()
                writer.writerows({f.name:(r[f.name].isoformat() if isinstance(r[f.name],dt.date) and r[f.name]!=EMPTY_DATE else '' if r[f.name]==EMPTY_DATE else 'T' if r[f.name] is True else 'F' if r[f.name] is False else r[f.name].rstrip() if f.type=='C' else r[f.name]) for f in fs} for r in rows)
            return p
        return self.new_table(opts['TO'],fs,rows)

    def file_command(self,cmd,tail):
        if cmd=='DELETE': tail=tail[5:]
        source,opts=clauses(tail,{'TO'})
        p=self.path(source,'')
        if any(s['path']==p for s in self.areas.values()): raise XBaseError('Feche o banco antes de alterar o arquivo.')
        if cmd=='RENAME':
            if 'TO' not in opts: raise XBaseError('RENAME origem TO destino')
            dest=self.path(opts['TO'],'')
            if dest.exists(): raise XBaseError('Destino já existe.')
            p.rename(dest); return
        if self.settings['SAFETY'] and self.input('Apagar '+p.name+'? Digite SIM: ')!='SIM': return
        p.unlink()

    def join_command(self,tail):
        head,opts=clauses(tail,{'WITH','TO','FOR','FIELDS'})
        if head or not all(k in opts for k in ('WITH','TO','FOR')): raise XBaseError('JOIN WITH alias TO nome FOR condição [FIELDS campos]')
        parent=self.area; child=self.area_number(opts['WITH'])
        if child==parent or child not in self.areas: raise XBaseError('JOIN exige outra área aberta.')
        parent_fields=self.fields(); parent_rows=self.rows()
        self.area=child
        try: child_fields=self.fields(); child_rows=self.rows()
        finally: self.area=parent
        specs=[]
        if opts.get('FIELDS'):
            for expression in split(opts['FIELDS']):
                m=re.fullmatch(r'(?:(\w+)->)?(\w+)',expression)
                if not m: raise XBaseError('JOIN FIELDS exige campo ou alias->campo.')
                area=self.area_number(m[1]) if m[1] else parent; fieldname=m[2].upper()
                if area not in (parent,child): raise XBaseError('JOIN FIELDS referencia uma terceira área.')
                field=next((f for f in (parent_fields if area==parent else child_fields) if f.name==fieldname),None)
                if not field or field.type=='M': raise XBaseError('JOIN: campo desconhecido ou memo não permitido.')
                specs.append((area,field))
        else: specs=[(parent,f) for f in parent_fields if f.type!='M']+[(child,f) for f in child_fields if f.type!='M']
        fields=[]; used=set(); output_specs=[]
        for area,f in specs:
            name=f.name
            n=2
            while name in used: name=f.name[:26]+'_'+str(n); n+=1
            used.add(name); fields.append(Field(name,f.type,f.length,f.decimals)); output_specs.append((area,f.name,name))
        if len(parent_rows)*len(child_rows)>self.max_steps: raise XBaseError('JOIN excede limite de combinações; ajuste --max-steps.')
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
        return self.new_table(opts['TO'],fields,result)

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


HELP='''dBASE SQLite PLUS 2.1
CREATE / CREATE FROM / USE [ALIAS] [INDEX] / SELECT 0|A..J|1..10|alias
APPEND BLANK / APPEND FROM / REPLACE / LIST / DISPLAY / BROWSE / EDIT
GO TOP|BOTTOM|n / SKIP / LOCATE FOR / CONTINUE / SEEK / FOUND()
DELETE / RECALL / PACK / ZAP / SET FILTER / SET DELETED
COUNT / SUM / AVERAGE / COPY TO / COPY STRUCTURE / SORT / TOTAL
INDEX ON ... TO / SET INDEX TO / SET ORDER TO / REINDEX / SET RELATION TO
STORE ... TO / atribuição = / PUBLIC / PRIVATE / RELEASE / SAVE / RESTORE
DO programa WITH ... / SET PROCEDURE TO / PARAMETERS / RETURN
IF/ELSE/ENDIF / DO CASE/CASE/OTHERWISE/ENDCASE / DO WHILE/LOOP/EXIT/ENDDO
@ linha,coluna SAY ... GET ... PICTURE ... RANGE ... / READ / WAIT / TEXT
? / ?? / ACCEPT / INPUT / macros &nome / campos alias->campo / variáveis M->nome
SET TALK/SAFETY/EXACT/DATE/CENTURY/DECIMALS/ALTERNATE/CONSOLE
CLEAR / CLOSE / DIR / ERASE / RENAME / COPY FILE / HELP / CANCEL / QUIT
Consulte COMPATIBILITY.md para diferenças de SQLite, telas e dialetos.
CLI: python main.py --cwd data --cmd programa.prg --plain
Auditoria sem executar: python main.py --cwd data --check programa.prg'''

