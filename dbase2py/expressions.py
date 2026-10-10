"""Parser Pratt de expressões xBase. Não executa código Python arbitrário."""
import datetime as dt
from .syntax import lex, XBaseError

# Precedência: aritmética, comparação, NOT, AND, OR.
PRECEDENCE={'OR':10,'AND':20,'=':40,'==':40,'<>':40,'!=':40,'#':40,'<':40,'>':40,'<=':40,'>=':40,'$':40,'+':50,'-':50,'*':60,'/':60,'%':60,'^':70,'**':70}


class Expression:
    def __init__(self,text):
        self.tokens=lex(text); self.i=0
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
        while self.peek().value in PRECEDENCE and PRECEDENCE[self.peek().value]>=min_bp:
            op=self.take().value; bp=PRECEDENCE[op]
            right=self.parse(bp if op in ('^','**') else bp+1)
            left=('binary',op,left,right)
        return left

    def evaluate(self,engine,row=None):
        def visit(n):
            kind=n[0]
            if kind=='literal': return n[1]
            if kind=='name': return engine.resolve(n[1],row)
            if kind=='qualified': return engine.resolve(n[2],row,n[1])
            if kind=='call':
                if n[1]=='TYPE':
                    if len(n[2])!=1: raise XBaseError('TYPE exige um argumento.')
                    try: return engine.type_code(engine.expr(str(visit(n[2][0]))))
                    except (ValueError,KeyError): return 'U'
                args=[visit(a) for a in n[2]]
                return engine.function(n[1],args,row)
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
        try: return visit(self.tree)
        except XBaseError: raise
        except (TypeError,ValueError,KeyError,ZeroDivisionError,OverflowError) as exc:
            raise XBaseError('Erro em expressão: '+str(exc)) from exc
