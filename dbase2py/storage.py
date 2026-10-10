"""Terminal xBase com persistência SQLite; sem eval ou execução de SQL do usuário."""
import ast
import csv
import datetime as dt
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Field:
    name: str
    type: str = 'C'
    length: int = 30
    decimals: int = 0


def split(text):
    """Separa vírgulas fora de strings e parênteses."""
    result, start, depth, quote = [], 0, 0, None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote: quote = None
        elif ch in "\"'": quote = ch
        elif ch == '(': depth += 1
        elif ch == ')': depth -= 1
        elif ch == ',' and depth == 0:
            result.append(text[start:i].strip()); start = i + 1
    result.append(text[start:].strip())
    return result


class DBaseEngine:
    def __init__(self, cwd='.', output=print, input_fn=input):
        self.cwd = Path(cwd).resolve(); self.cwd.mkdir(parents=True, exist_ok=True)
        self.output, self.input = output, input_fn
        self.areas, self.area, self.variables = {}, 1, {}
        self.deleted, self.exact, self.running = False, False, True
        self.last_count = 0

    def path(self, name, suffix='.sqlite'):
        name = name.strip().strip("\"'")
        p = Path(name)
        if not p.suffix: p = p.with_suffix(suffix)
        p = (self.cwd / p).resolve()
        if not p.is_relative_to(self.cwd): raise ValueError('Caminho fora do diretório de trabalho.')
        return p

    @property
    def state(self):
        if self.area not in self.areas: raise ValueError('Nenhum banco aberto. USE nome.')
        return self.areas[self.area]

    def close(self):
        for s in self.areas.values(): s['db'].close()
        self.areas.clear()

    def fields(self): return [Field(**f) for f in json.loads(self.state['db'].execute('SELECT definition FROM _schema').fetchone()[0])]

    def rows(self, visible=True):
        s = self.state
        rows = [dict(r) for r in s['db'].execute('SELECT * FROM records ORDER BY _recno')]
        if visible:
            rows = [r for r in rows if (not self.deleted or not r['_deleted']) and (not s['filter'] or self.expr(s['filter'], r))]
        if s['order']: rows.sort(key=lambda r: self.expr(s['order'], r))
        return rows

    def current(self):
        return next((r for r in self.rows(False) if r['_recno'] == self.state['pointer']), {})

    def expr(self, text, row=None):
        row = self.current() if row is None and self.area in self.areas else (row or {})
        # Reescreve apenas tokens fora de literais.
        parts = re.split(r"('(?:[^']|'')*'|\"[^\"]*\")", text.strip())
        for i in range(0, len(parts), 2):
            t = parts[i]
            for old, new in [('.AND.', ' and '), ('.OR.', ' or '), ('.NOT.', ' not '), ('.T.', 'True'), ('.F.', 'False')]:
                t = re.sub(re.escape(old), new, t, flags=re.I)
            t = t.replace('<>', '!=').replace('#', '!=')
            t = re.sub(r'(?<![<>=!])=(?!=)', '==', t)
            parts[i] = t
        tree = ast.parse(''.join(parts).strip(), mode='eval')
        env = {**self.variables, **{k.upper(): v for k, v in row.items()}}
        funcs = {'LEN': len, 'TRIM': lambda x: str(x).strip(), 'UPPER': lambda x: str(x).upper(), 'LOWER': lambda x: str(x).lower(), 'INT': int, 'VAL': float, 'STR': str, 'ABS': abs, 'ROUND': round, 'CHR': chr, 'AT': lambda a,b: str(b).find(str(a))+1, 'DATE': lambda: dt.date.today().isoformat(), 'RECNO': lambda: row.get('_recno', self.state['pointer']), 'RECCOUNT': lambda: len(self.rows(False)), 'DELETED': lambda: bool(row.get('_deleted', 0)), 'EOF': lambda: self.state['pointer'] > len(self.rows(False)), 'BOF': lambda: self.state['pointer'] < 1}
        def visit(n):
            if isinstance(n, ast.Constant): return n.value
            if isinstance(n, ast.Name):
                if n.id.upper() not in env: raise ValueError('Campo/variável desconhecido: '+n.id)
                return env[n.id.upper()]
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id.upper() in funcs and not n.keywords:
                return funcs[n.func.id.upper()](*[visit(a) for a in n.args])
            if isinstance(n, ast.UnaryOp):
                v=visit(n.operand)
                if isinstance(n.op, ast.Not): return not v
                if isinstance(n.op, ast.USub): return -v
                if isinstance(n.op, ast.UAdd): return +v
            if isinstance(n, ast.BoolOp):
                if isinstance(n.op, ast.And): return all(visit(v) for v in n.values)
                return any(visit(v) for v in n.values)
            if isinstance(n, ast.BinOp):
                a,b=visit(n.left),visit(n.right)
                if isinstance(n.op, ast.Add): return a+b
                if isinstance(n.op, ast.Sub): return a-b
                if isinstance(n.op, ast.Mult): return a*b
                if isinstance(n.op, ast.Div): return a/b
                if isinstance(n.op, ast.Mod): return a%b
            if isinstance(n, ast.Compare):
                a=visit(n.left)
                for op, rhs in zip(n.ops,n.comparators):
                    b=visit(rhs)
                    if isinstance(op, ast.Eq): ok = (a == b if self.exact or not isinstance(a,str) or not isinstance(b,str) else a.startswith(b))
                    elif isinstance(op, ast.NotEq): ok=a!=b
                    elif isinstance(op, ast.Lt): ok=a<b
                    elif isinstance(op, ast.LtE): ok=a<=b
                    elif isinstance(op, ast.Gt): ok=a>b
                    elif isinstance(op, ast.GtE): ok=a>=b
                    else: raise ValueError('Operador não suportado.')
                    if not ok: return False
                    a=b
                return True
            raise ValueError('Expressão não suportada.')
        return visit(tree.body)

    def create(self, name, fields):
        p=self.path(name)
        if p.exists(): raise ValueError('Banco já existe: '+p.name)
        names=set()
        for f in fields:
            f.name=f.name.upper(); f.type=f.type.upper()
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,29}',f.name) or f.name in names: raise ValueError('Nome de campo inválido/duplicado.')
            if f.type not in 'CNLDM' or f.length<1 or f.decimals<0 or f.decimals>=f.length: raise ValueError('Definição de campo inválida.')
            names.add(f.name)
        if not fields: raise ValueError('Defina ao menos um campo.')
        db=sqlite3.connect(p)
        try:
            with db:
                db.execute('CREATE TABLE _schema (definition TEXT NOT NULL)')
                db.execute('INSERT INTO _schema VALUES (?)',(json.dumps([vars(f) for f in fields]),))
                db.execute('CREATE TABLE records (_recno INTEGER PRIMARY KEY, _deleted INTEGER NOT NULL DEFAULT 0, '+','.join('"'+f.name+'" '+({'N':'REAL','L':'INTEGER'}.get(f.type,'TEXT'))+' NOT NULL' for f in fields)+')')
                db.execute('CREATE TABLE _indexes (name TEXT PRIMARY KEY, expression TEXT NOT NULL)')
        finally: db.close()
        self.execute('USE "'+str(p)+'"')
        return p

    def coerce(self, f, v):
        if f.type=='N':
            v=round(float(v),f.decimals)
            if len(f'{v:.{f.decimals}f}')>f.length: raise ValueError('Número excede largura: '+f.name)
            return int(v) if not f.decimals else v
        if f.type=='L':
            if isinstance(v,str):
                if v.upper() not in ('T','F','.T.','.F.','TRUE','FALSE','1','0'): raise ValueError('Valor lógico inválido.')
                return int(v.upper() in ('T','.T.','TRUE','1'))
            return int(bool(v))
        if f.type=='D': return dt.date.fromisoformat(str(v)).isoformat() if v else ''
        v=str(v)
        if f.type=='C' and len(v)>f.length: raise ValueError('Texto excede largura: '+f.name)
        return v

    def append(self, values=None):
        fs=self.fields(); values=values or {}
        vals=[self.coerce(f, values.get(f.name, 0 if f.type in 'NL' else '')) for f in fs]
        db=self.state['db']
        with db:
            cur=db.execute('INSERT INTO records ('+','.join('"'+f.name+'"' for f in fs)+') VALUES ('+','.join('?' for _ in fs)+')', vals)
        self.state['pointer']=cur.lastrowid

    def scope(self, tail, default_all=False):
        m=re.search(r'\s+FOR\s+', ' '+tail, re.I)
        condition=''
        if m:
            padded=' '+tail; condition=padded[m.end():]; tail=padded[:m.start()].strip()
        rows=self.rows()
        if re.search(r'\bALL\b',tail,re.I) or (default_all and not re.search(r'\b(NEXT|REST)\b',tail,re.I)): selected=rows
        elif re.search(r'\bNEXT\s+(\d+)',tail,re.I):
            n=int(re.search(r'\bNEXT\s+(\d+)',tail,re.I)[1]); ids=[r['_recno'] for r in rows]; pos=ids.index(self.state['pointer']) if self.state['pointer'] in ids else len(ids); selected=rows[pos:pos+n]
        elif re.search(r'\bREST\b',tail,re.I): selected=[r for r in rows if r['_recno']>=self.state['pointer']]
        else: selected=[r for r in rows if r['_recno']==self.state['pointer']]
        if condition: selected=[r for r in selected if self.expr(condition,r)]
        fields=re.sub(r'\b(ALL|REST|NEXT\s+\d+)\b','',tail,flags=re.I).strip()
        return selected,fields

    def show(self, rows, expressions=''):
        es=split(expressions) if expressions else [f.name for f in self.fields()]
        self.output('RECNO DEL | '+' | '.join(es))
        for r in rows: self.output(f"{r['_recno']:5} {'*' if r['_deleted'] else ' '}   | "+' | '.join(str(self.expr(e,r)) for e in es))
        return rows

    def execute(self, line):
        line=line.strip()
        if not line or line.startswith('*') or line.startswith('&&'): return
        cmd,_,tail=line.partition(' '); cmd=cmd.upper(); tail=tail.strip()
        if cmd in ('QUIT','EXIT'): self.running=False; self.close(); return
        if cmd=='HELP': self.output(HELP); return
        if cmd=='?': v=self.expr(tail); self.output(str(v)); return v
        if cmd=='SELECT': self.area={'PRIMARY':1,'SECONDARY':2}.get(tail.upper(),int(tail) if tail.isdigit() else 0); return
        if cmd=='USE':
            if not tail:
                if self.area in self.areas: self.areas.pop(self.area)['db'].close()
                return
            parts=re.split(r'\s+ALIAS\s+',tail,flags=re.I); p=self.path(parts[0])
            if not p.exists(): raise ValueError('Banco não encontrado: '+p.name)
            db=sqlite3.connect(p); db.row_factory=sqlite3.Row
            try: db.execute('SELECT definition FROM _schema').fetchone()
            except sqlite3.Error: db.close(); raise ValueError('SQLite sem estrutura dBASE SQLite.')
            if self.area in self.areas: self.areas[self.area]['db'].close()
            self.areas[self.area]={'db':db,'path':p,'pointer':1,'filter':'','order':'','alias':parts[-1] if len(parts)>1 else p.stem}
            return
        if cmd=='CREATE':
            m=re.fullmatch(r'(.+?)\s*\((.*)\)',tail)
            fs=[]
            if m:
                name=m[1]
                for item in split(m[2]):
                    t=item.split(); fs.append(Field(t[0],t[1],int(t[2]) if len(t)>2 else 30,int(t[3]) if len(t)>3 else 0))
            else:
                name=tail or self.input('Nome do banco: ')
                # Diálogo do dBASE II: "MATRICULA,N,4"; espaços também separam.
                self.output('Entre com a estrutura do registro: nome do campo, tipo, tamanho, casas decimais. Linha vazia termina.')
                while True:
                    t=self.input(f'{len(fs)+1:03}     ').replace(',',' ').split()
                    if not t: break
                    if len(t)<2: raise ValueError('Campo: NOME,TIPO,TAMANHO,DECIMAIS')
                    fs.append(Field(t[0],t[1],int(t[2]) if len(t)>2 else {'L':1,'D':8,'M':10}.get(t[1].upper(),30),int(t[3]) if len(t)>3 else 0))
            return self.create(name,fs)
        if cmd in ('LIST','DISPLAY') and tail.upper()=='FILES' or cmd=='DIR':
            self.output('\n'.join(p.name for p in self.cwd.glob('*.sqlite'))); return
        if cmd in ('LIST','DISPLAY') and tail.upper()=='STRUCTURE':
            self.output('\n'.join(f'{f.name} {f.type} {f.length} {f.decimals}' for f in self.fields())); return
        if cmd in ('LIST','DISPLAY') and tail.upper() in ('MEMORY','STATUS'):
            self.output(str(self.variables if tail.upper()=='MEMORY' else {i:{k:str(v) for k,v in s.items() if k!='db'} for i,s in self.areas.items()})); return
        if cmd in ('LIST','DISPLAY','BROWSE'):
            rows,fs=self.scope(tail,cmd in ('LIST','BROWSE')); return self.show(rows,fs)
        if cmd in ('GO','GOTO'):
            rows=self.rows()
            self.state['pointer']=(rows[0]['_recno'] if rows else 1) if tail.upper()=='TOP' else (rows[-1]['_recno'] if rows else 1) if tail.upper()=='BOTTOM' else int(self.expr(tail)); return
        if cmd=='SKIP':
            rows=self.rows(); ids=[r['_recno'] for r in rows]; p=self.state['pointer']; n=int(self.expr(tail or '1'))
            i=ids.index(p) if p in ids else len(ids) if p>0 else -1; i+=n
            self.state['pointer']=ids[i] if 0<=i<len(ids) else 0 if i<0 else len(self.rows(False))+1; return
        if cmd=='APPEND':
            if tail.upper()=='BLANK': self.append(); return
            if tail.upper().startswith('FROM '):
                p=self.path(tail[5:],'.csv')
                with p.open(newline='',encoding='utf-8-sig') as file:
                    data=list(csv.DictReader(file))
                fs=self.fields()
                data=[{f.name:self.coerce(f,r.get(f.name,'')) for f in fs} for r in data]
                db=self.state['db']
                with db:
                    for r in data:
                        cur=db.execute('INSERT INTO records ('+','.join('"'+f.name+'"' for f in fs)+') VALUES ('+','.join('?' for _ in fs)+')',[r[f.name] for f in fs])
                if data: self.state['pointer']=cur.lastrowid
                return
            while True:
                vals={}
                for f in self.fields(): vals[f.name]=self.input(f'{f.name} ({f.type}): ')
                self.append(vals)
                if self.input('Outro registro? (S/N): ').upper()!='S': break
            return
        if cmd=='REPLACE':
            m=re.search(r'\s+(ALL|REST|NEXT\s+\d+|FOR)\b',tail,re.I)
            assignments=tail[:m.start()] if m else tail; scope=tail[m.start():].strip() if m else ''
            rows,_=self.scope(scope); fs={f.name:f for f in self.fields()}; updates=[]
            for r in rows:
                vals={}
                for a in split(assignments):
                    pair=re.split(r'\s+WITH\s+',a,flags=re.I)
                    if len(pair)!=2 or pair[0].upper() not in fs: raise ValueError('Use REPLACE campo WITH expressão.')
                    f=fs[pair[0].upper()]; vals[f.name]=self.coerce(f,self.expr(pair[1],r))
                updates.append((r,vals))
            with self.state['db']:
                for r,vals in updates: self.state['db'].execute('UPDATE records SET '+','.join('"'+k+'"=?' for k in vals)+' WHERE _recno=?',[*vals.values(),r['_recno']])
            return
        if cmd in ('EDIT','CHANGE'):
            if tail: self.execute('GO '+tail)
            r=self.current()
            if not r: raise ValueError('Sem registro atual.')
            vals={}
            for f in self.fields():
                v=self.input(f'{f.name} [{r[f.name]}]: ')
                if v: vals[f.name]=self.coerce(f,v)
            if vals:
                with self.state['db']: self.state['db'].execute('UPDATE records SET '+','.join('"'+k+'"=?' for k in vals)+' WHERE _recno=?',[*vals.values(),r['_recno']])
            return
        if cmd in ('DELETE','RECALL'):
            rows,_=self.scope(tail)
            with self.state['db']: self.state['db'].executemany('UPDATE records SET _deleted=? WHERE _recno=?',[(int(cmd=='DELETE'),r['_recno']) for r in rows])
            return
        if cmd=='PACK':
            db=self.state['db']
            with db:
                db.execute('DELETE FROM records WHERE _deleted=1')
                ids=[r[0] for r in db.execute('SELECT _recno FROM records ORDER BY _recno')]
                for i,rid in enumerate(ids,1): db.execute('UPDATE records SET _recno=? WHERE _recno=?',(-i,rid))
                db.execute('UPDATE records SET _recno=-_recno')
            self.execute('GO TOP'); return
        if cmd=='ZAP':
            if self.input('Apagar todos os registros? Digite SIM: ')!='SIM': return
            with self.state['db']: self.state['db'].execute('DELETE FROM records')
            self.state['pointer']=1; return
        if cmd=='SET':
            key,_,value=tail.partition(' '); key=key.upper()
            if key in ('DELETED','EXACT'): setattr(self,key.lower(),value.upper()=='ON'); return
            if key=='FILTER': self.state['filter']=re.sub(r'^TO\s*','',value,flags=re.I); return
            if key=='ORDER':
                name=re.sub(r'^TO\s*','',value,flags=re.I).strip()
                r=self.state['db'].execute('SELECT expression FROM _indexes WHERE name=?',(name.upper(),)).fetchone() if name else None
                if name and not r: raise ValueError('Índice não encontrado.')
                self.state['order']=r[0] if r else ''; self.execute('GO TOP'); return
            raise ValueError('SET suportados: DELETED, EXACT, FILTER TO, ORDER TO.')
        if cmd in ('LOCATE','CONTINUE','SEEK','FIND'):
            s=self.state
            if cmd=='LOCATE': s['locate']=re.sub(r'^FOR\s+','',tail,flags=re.I)
            if cmd in ('SEEK','FIND'):
                if not s['order']: raise ValueError('Crie/ative um índice.')
                value=self.expr(tail) if cmd=='SEEK' else tail.strip("\"'")
                match=lambda r:self.expr(s['order'],r)==value
            else: match=lambda r:self.expr(s.get('locate','False'),r)
            rows=self.rows(); ids=[r['_recno'] for r in rows]; start=ids.index(s['pointer'])+1 if cmd=='CONTINUE' and s['pointer'] in ids else 0
            found=next((r for r in rows[start:] if match(r)),None)
            s['pointer']=found['_recno'] if found else len(self.rows(False))+1
            self.variables['FOUND']=bool(found); self.output('Encontrado.' if found else 'Não encontrado.'); return bool(found)
        if cmd in ('COUNT','SUM'):
            dest=None
            m=re.search(r'\s+TO\s+(\w+)\s*$',tail,re.I)
            if m: dest=m[1].upper(); tail=tail[:m.start()]
            rows,ex=self.scope(tail,True)
            value=len(rows) if cmd=='COUNT' else sum(self.expr(ex,r) for r in rows)
            if dest: self.variables[dest]=value
            self.last_count=len(rows); self.output(str(value)); return value
        if cmd=='INDEX':
            m=re.fullmatch(r'ON\s+(.+?)\s+TO\s+(\w+)',tail,re.I)
            if not m: raise ValueError('INDEX ON expressão TO nome')
            for r in self.rows(False): self.expr(m[1],r)
            with self.state['db']: self.state['db'].execute('INSERT OR REPLACE INTO _indexes VALUES (?,?)',(m[2].upper(),m[1]))
            if m[1].upper() in {f.name for f in self.fields()}:
                with self.state['db']: self.state['db'].execute('CREATE INDEX IF NOT EXISTS "idx_'+m[2].upper()+'" ON records ("'+m[1].upper()+'")')
            self.state['order']=m[1]; self.execute('GO TOP'); return
        if cmd=='REINDEX': self.rows(); return
        if cmd=='STORE':
            m=re.fullmatch(r'(.+)\s+TO\s+(\w+)',tail,re.I)
            if not m: raise ValueError('STORE expressão TO variável')
            self.variables[m[2].upper()]=self.expr(m[1]); return
        if cmd=='RELEASE':
            if tail.upper()=='ALL': self.variables.clear()
            else:
                for name in split(tail): self.variables.pop(name.upper(),None)
            return
        if cmd in ('SAVE','RESTORE'):
            name=re.sub(r'^(TO|FROM)\s+','',tail,flags=re.I); p=self.path(name,'.json')
            if cmd=='SAVE': p.write_text(json.dumps(self.variables),encoding='utf-8')
            else: self.variables.update(json.loads(p.read_text(encoding='utf-8')))
            return
        if cmd=='COPY':
            m=re.fullmatch(r'TO\s+(.+?)\s+DELIMITED',tail,re.I)
            if not m: raise ValueError('COPY TO arquivo DELIMITED (CSV)')
            with self.path(m[1],'.csv').open('w',newline='',encoding='utf-8') as file:
                fs=[f.name for f in self.fields()]; writer=csv.DictWriter(file,fieldnames=fs); writer.writeheader(); writer.writerows({k:r[k] for k in fs} for r in self.rows())
            return
        if cmd=='DO': return self.run_file(tail)
        if cmd in ('ACCEPT','INPUT'):
            m=re.fullmatch(r'(.+?)\s+TO\s+(\w+)',tail,re.I)
            if not m: raise ValueError('ACCEPT/INPUT "pergunta" TO variável')
            value=self.input(str(self.expr(m[1]))); self.variables[m[2].upper()]=self.expr(value) if cmd=='INPUT' else value; return
        if cmd=='CLEAR': self.output('\033[2J\033[H'); return
        raise ValueError('Comando não suportado: '+cmd+'. Digite HELP.')

    def run_file(self,name,depth=0):
        if depth>20: raise ValueError('Limite de recursão.')
        p=self.path(name,'.prg')
        if not p.exists() and p.suffix=='.prg': p=p.with_suffix('.cmd')
        lines=p.read_text(encoding='utf-8-sig').splitlines(); steps=0
        def block(start,end):
            nonlocal steps
            i=start
            while i<end and self.running:
                steps+=1
                if steps>100000: raise ValueError('Limite de execução do script.')
                line=lines[i].strip(); upper=line.upper()
                if upper.startswith('IF ') or upper.startswith('DO WHILE '):
                    is_loop=upper.startswith('DO WHILE '); nesting=1; j=i+1; other=None
                    while j<end:
                        u=lines[j].strip().upper()
                        if u.startswith('IF ') or u.startswith('DO WHILE '): nesting+=1
                        if u in ('ENDIF','ENDDO'): nesting-=1
                        if nesting==0: break
                        if nesting==1 and u=='ELSE': other=j
                        j+=1
                    if j==end: raise ValueError('Bloco sem ENDIF/ENDDO.')
                    condition=line[9:] if is_loop else line[3:]
                    if is_loop:
                        while self.expr(condition) and self.running:
                            steps+=1
                            if steps>100000: raise ValueError('Limite de execução do script.')
                            block(i+1,j)
                    elif self.expr(condition): block(i+1,other if other is not None else j)
                    elif other is not None: block(other+1,j)
                    i=j+1; continue
                if upper.startswith('DO ') and not upper.startswith('DO WHILE '): self.run_file(line[3:],depth+1)
                else: self.execute(line)
                i+=1
        block(0,len(lines))


HELP='''CREATE nome (NOME C 30, IDADE N 3, ATIVO L 1, DATA D 10)
CREATE nome                  definição interativa
USE nome [ALIAS apelido]      abre nome.sqlite; USE fecha
SELECT PRIMARY|SECONDARY|n   áreas independentes
APPEND BLANK / APPEND         inclui registro / formulário no terminal
REPLACE campo WITH expressão [, campo WITH expressão] [ALL|NEXT n|REST] [FOR condição]
LIST [campos] [ALL] [FOR condição] / DISPLAY / BROWSE (listagem)
DISPLAY STRUCTURE|STATUS|MEMORY|FILES
GO TOP|BOTTOM|n / SKIP [n] / ? RECNO() / ? EOF()
DELETE / RECALL [ALL] [FOR condição] / PACK / ZAP (confirmação)
SET DELETED ON|OFF / SET EXACT ON|OFF / SET FILTER TO [condição]
LOCATE FOR condição / CONTINUE
COUNT [FOR condição] / SUM expressão [FOR condição]
INDEX ON expressão TO nome / SET ORDER TO [nome] / SEEK expressão / FIND texto
STORE expressão TO variável / ? expressão / RELEASE ALL
SAVE TO nome / RESTORE FROM nome (JSON)
COPY TO nome DELIMITED / APPEND FROM nome.csv (CSV UTF-8)
EDIT [n] / CHANGE [n] / ACCEPT "texto" TO variável / INPUT "texto" TO variável
DO nome.prg (ou .cmd): IF/ELSE/ENDIF e DO WHILE/ENDDO
CLEAR / HELP / QUIT'''
