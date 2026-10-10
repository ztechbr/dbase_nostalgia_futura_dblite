"""Comandos PLUS do dBASE II PLUS para MSX (curso MarMSX, Casari 1989).

Datas usam o formato DDMMAA e o século XX, como no original; as respostas
são textos ("1"/"0", "00010", "140224"...).
"""
import datetime as dt
import itertools
import re
from .syntax import XBaseError, clauses


def ddmmyy(text):
    text=str(text).strip()
    if not re.fullmatch(r'\d{6}',text): return None
    try: return dt.date(1900+int(text[4:]),int(text[2:4]),int(text[:2]))
    except ValueError: return None


def as_ddmmyy(date): return f'{date.day:02}{date.month:02}{date.year%100:02}'


def digits(text): return re.sub(r'\D','',str(text))


def mod11(number):
    """Dígito verificador módulo 11 com pesos 2..9 da direita para a esquerda."""
    total=sum(int(d)*w for d,w in zip(reversed(number),itertools.cycle(range(2,10))))
    dv=total*10%11
    return 0 if dv==10 else dv


def cpf_valid(text):
    number=digits(text)[-11:]
    if len(number)!=11: return False
    for size in (9,10):
        total=sum(int(d)*w for d,w in zip(number[:size],range(size+1,1,-1)))
        dv=total*10%11%10
        if dv!=int(number[size]): return False
    return True


def cgc_valid(text):
    """CGC/CNPJ pela regra atual, inclusive o CNPJ alfanumérico (letra vale código ASCII - 48)."""
    number=re.sub(r'[^0-9A-Z]','',str(text).upper())
    if len(number)!=14 or not number[12:].isdigit(): return False
    for size,weights in ((12,[5,4,3,2,9,8,7,6,5,4,3,2]),(13,[6,5,4,3,2,9,8,7,6,5,4,3,2])):
        rest=sum((ord(d)-48)*w for d,w in zip(number,weights))%11
        if (0 if rest<2 else 11-rest)!=int(number[size]): return False
    return True


def add_days(engine,args,skip_weekend):
    if len(args)!=3: raise XBaseError('PLUS ADATE/TDATE data dias flag TO resposta')
    date=ddmmyy(args[0]); days=int(digits(args[1]) or 0)
    if not date: return '      '
    if not 0<=days<=242: raise XBaseError('PLUS ADATE aceita no máximo 242 dias.')
    if str(args[2]).strip()=='1': date=(date.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    date+=dt.timedelta(days=days)
    if skip_weekend and date.weekday()>=5: date+=dt.timedelta(days=7-date.weekday())
    return as_ddmmyy(date)


def european(number,decimals):
    whole,fraction=(number[:-decimals],number[-decimals:]) if decimals else (number,'')
    whole=whole.lstrip('0') or '0'
    grouped=''
    while len(whole)>3: grouped='.'+whole[-3:]+grouped; whole=whole[:-3]
    return whole+grouped+(','+fraction if decimals else '')


def plus_command(engine,tail):
    head,opts=clauses(tail,{'TO'})
    if 'TO' not in opts: raise XBaseError('PLUS comando argumentos TO variável')
    name,_,rest=head.partition(' '); name=name.upper()
    args=[engine.expr(a) for a in re.findall(r'"[^"]*"|\'[^\']*\'|\[[^\]]*\]|\S+',rest)]
    target=opts['TO'].strip()
    try: width=len(engine.variables[target])
    except (KeyError,TypeError): width=0
    if name=='CDATE': result='1' if args and ddmmyy(args[0]) else '0'
    elif name=='DDATE':
        if len(args)!=2: raise XBaseError('PLUS DDATE data1 data2 TO resposta')
        first,second=ddmmyy(args[0]),ddmmyy(args[1])
        result=f'{(second-first).days:05}' if first and second else '00000'
    elif name in ('ADATE','TDATE'): result=add_days(engine,args,name=='TDATE')
    elif name=='CHANGE': result=str(args[0]).translate(str.maketrans('.,',',.'))
    elif name=='FORMAT':
        if len(args)!=2: raise XBaseError('PLUS FORMAT número casas TO resposta')
        result=european(digits(args[0]) or '0',int(digits(args[1]) or 0)).rjust(width)
    elif name=='LZERO':
        text=str(args[0]); result='0'*(len(text)-len(text.lstrip(' ')))+text.lstrip(' ')
    elif name=='MOD11': result=str(mod11(digits(args[0])))
    elif name=='CPF': result='1' if cpf_valid(args[0]) else '0'
    elif name=='CGC': result='1' if cgc_valid(args[0]) else '0'
    elif name=='CODE':
        if len(args)!=2: raise XBaseError('PLUS CODE linha coluna TO senha')
        result=engine.secret(int(digits(args[0]) or 0),int(digits(args[1]) or 0),'Entre com a senha:')
    else: raise XBaseError('Comando PLUS desconhecido: '+name)
    engine.variables[target]=result
    return result
