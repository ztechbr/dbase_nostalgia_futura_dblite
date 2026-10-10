"""Parser Pratt de expressões xBase. Não executa código Python arbitrário."""
import datetime as dt
import re
from .syntax import lex, XBaseError

# Precedência: aritmética, comparação, NOT, AND, OR.
PRECEDENCE={'OR':10,'AND':20,'=':40,'==':40,'<>':40,'!=':40,'#':40,'<':40,'>':40,'<=':40,'>=':40,'$':40,'+':50,'-':50,'*':60,'/':60,'%':60,'^':70,'**':70}


class Expression:
    def __init__(self,text):
        self.text=text; self.tokens=lex(text); self.i=0
        self.tree=self.parse(0)
        if self.peek().kind!='end': raise XBaseError('Expressão contém tokens excedentes: '+str(self.peek().value))

    def peek(self): return self.tokens[self.i]
    def take(self): t=self.peek(); self.i+=1; return t
    def need(self,value):
        if self.take().value!=value: raise XBaseError('Esperado '+value+' em expressão.')

    def parse(self,min_bp):
        t=self.take()
        if t.kind in ('number','string'): left=('literal',t.value)
        elif t.kind=='bool': left=('literal',t.value in ('T','Y'))
        elif t.value=='(':
            left=self.parse(0); self.need(')')
        elif t.value=='{':
            close=next((k for k in range(self.i,len(self.tokens)) if self.tokens[k].value=='}'),None)
            raw=self.text[t.end:self.tokens[close].start] if close is not None else ''
            if close is not None and re.fullmatch(r'\s*(?:\d{1,4}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{1,4}|/\s*/|\.\s*\.|-\s*-)\s*',raw):
                # Literal de data do dBASE IV: {10/10/26}; { / / } é data vazia.
                self.i=close+1; left=('date',raw.strip())
            else:
                # Literal de array do Clipper: {1, "a", .T.}; {} é array vazio.
                items=[]
                if self.peek().value!='}':
                    while True:
                        items.append(self.parse(0))
                        if self.peek().value!=',': break
                        self.take()
                self.need('}'); left=('array',items)
        elif t.value=='!' and self.peek().value=='(':
            # dBASE II: !(texto) converte para maiúsculas; em lógico continua sendo negação.
            self.take(); left=('bang',self.parse(0)); self.need(')')
        elif t.value in ('$','@') and self.peek().value=='(':
            # dBASE II: $(texto,início,tamanho) é SUBSTR e @(procura,texto) é AT.
            self.take(); args=[self.parse(0)]
            while self.peek().value==',': self.take(); args.append(self.parse(0))
            self.need(')'); left=('call','SUBSTR' if t.value=='$' else 'AT',args)
        elif t.value=='#': left=('call','RECNO',[])
        elif t.value=='*': left=('call','DELETED',[])
        elif t.value in ('NOT','!','+','-'):
            left=('unary',t.value,self.parse(30 if t.value in ('NOT','!') else 65))
        elif t.kind=='name':
            if self.peek().value in ('->','.'):
                self.take(); name=self.take()
                if name.kind!='name': raise XBaseError('Campo/variável esperado após alias.')
                left=('qualified',t.value,name.value)
            elif self.peek().value=='(':
                self.take(); args=[]
                if self.peek().value!=')':
                    while True:
                        args.append(self.parse(0))
                        if self.peek().value!=',': break
                        self.take()
                self.need(')'); left=('call',t.value,args)
            else: left=('name',t.value)
        else: raise XBaseError('Expressão incompleta ou inválida.')
        while self.peek().value=='[':
            # Índice de array: arr[1], arr[1,2] (dBASE IV) ou arr[1][2] (Clipper).
            self.take(); indexes=[self.parse(0)]
            while self.peek().value==',': self.take(); indexes.append(self.parse(0))
            self.need(']'); left=('index',left,indexes)
        while self.peek().value in PRECEDENCE and PRECEDENCE[self.peek().value]>=min_bp:
            op=self.take().value; bp=PRECEDENCE[op]
            right=self.parse(bp if op in ('^','**') else bp+1)
            left=('binary',op,left,right)
        return left

    def evaluate(self,engine,row=None,node=None):
        def visit(n):
            kind=n[0]
            if kind=='literal': return n[1]
            if kind=='date': return engine.date_literal(n[1])
            if kind=='array': return engine.make_array([visit(item) for item in n[1]])
            if kind=='index': return engine.element(visit(n[1]),[visit(i) for i in n[2]])
            if kind=='name': return engine.resolve(n[1],row)
            if kind=='qualified': return engine.resolve(n[2],row,n[1])
            if kind=='call':
                if n[1]=='TYPE':
                    if len(n[2])!=1: raise XBaseError('TYPE exige um argumento.')
                    # dBASE II recebe o valor; dBASE III recebe a expressão como texto.
                    if engine.dbase2: return engine.type_code(visit(n[2][0]))
                    try: return engine.type_code(engine.expr(str(visit(n[2][0]))))
                    except (ValueError,KeyError): return 'U'
                args=[visit(a) for a in n[2]]
                array=engine.array_variable(n[1])
                if array is not None: return engine.element(array,args)  # FoxPro: arr(1)
                return engine.function(n[1],args,row)
            if kind=='bang':
                v=visit(n[1])
                return v.upper() if isinstance(v,str) else not v
            if kind=='unary':
                v=visit(n[2])
                if n[1] in ('NOT','!'): return not v
                return +v if n[1]=='+' else -v
            op=n[1]; a=visit(n[2])
            if op=='AND': return bool(a) and bool(visit(n[3]))
            if op=='OR': return bool(a) or bool(visit(n[3]))
            b=visit(n[3])
            if op in ('=','==','!=','<>','#'):
                if isinstance(a,str) and isinstance(b,str) and op!='==':
                    equal=a.rstrip()==b.rstrip() if engine.exact else a.startswith(b)
                else: equal=a==b
                return not equal if op in ('!=','<>','#') else equal
            if op=='$': return str(a) in str(b)
            if op=='<': return a<b
            if op=='<=': return a<=b
            if op=='>': return a>b
            if op=='>=': return a>=b
            if op=='+':
                if isinstance(a,dt.date) and isinstance(b,(int,float)): return a+dt.timedelta(days=b)
                if isinstance(b,dt.date) and isinstance(a,(int,float)): return b+dt.timedelta(days=a)
                return a+b
            if op=='-':
                if isinstance(a,str) and isinstance(b,str): return a.rstrip()+b+' '*(len(a)-len(a.rstrip()))
                if isinstance(a,dt.date): return (a-b).days if isinstance(b,dt.date) else a-dt.timedelta(days=b)
                return a-b
            if op=='*': return a*b
            if op=='/': return a/b
            if op=='%': return a%b
            if op in ('^','**'):
                if abs(b)>1000: raise XBaseError('Expoente excede limite de execução.')
                return a**b
            raise XBaseError('Operador não suportado: '+op)
        try: return visit(self.tree if node is None else node)
        except XBaseError: raise
        except (TypeError,ValueError,KeyError,ZeroDivisionError,OverflowError) as exc:
            raise XBaseError('Erro em expressão: '+str(exc)) from exc
