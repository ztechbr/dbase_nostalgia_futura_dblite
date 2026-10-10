"""Funções usuais dBASE III PLUS e extensões explicitadas no manual."""
import datetime as dt
import math
import re
import time
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from .syntax import XBaseError

EMPTY_DATE=dt.date.min


def xround(number,decimals=0):
    if abs(int(decimals))>20: raise XBaseError('Casas decimais fora do limite.')
    return float(Decimal(str(number)).quantize(Decimal('1').scaleb(-int(decimals)),rounding=ROUND_HALF_UP))


def val(text):
    m=re.match(r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))',str(text))
    return float(m[1]) if m else 0


def str_value(number,width=10,decimals=0):
    width,decimals=int(width),int(decimals)
    if not 1<=width<=10000 or not 0<=decimals<=20: raise XBaseError('STR: largura/casas inválidas.')
    s=f'{xround(number,decimals):.{decimals}f}'
    return '*'*width if len(s)>width else s.rjust(width)


def ctod(engine,text):
    text=str(text).strip()
    if not text or all(c in ' /.-' for c in text): return EMPTY_DATE
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text): return dt.date.fromisoformat(text)
    parts=re.split(r'[/.-]',text)
    if len(parts)!=3: raise XBaseError('CTOD: data inválida.')
    names=engine.date_order(); values=dict(zip(names,map(int,parts))); year=values['Y']
    if year<100: year+=1900  # dBASE III PLUS assume século XX para anos de dois dígitos.
    return dt.date(year,values['M'],values['D'])


def dtoc(engine,date,sortable=False):
    if not isinstance(date,dt.date): raise XBaseError('DTOC exige data.')
    if date==EMPTY_DATE: return ' '*8 if sortable else '  /  /  '
    if sortable: return date.strftime('%Y%m%d')
    values={'D':f'{date.day:02}','M':f'{date.month:02}','Y':f'{date.year:04}' if engine.settings['CENTURY'] else f'{date.year%100:02}'}
    sep=engine.date_separator()
    return sep.join(values[k] for k in engine.date_order())


def functions(engine):
    def area_state(area=None):
        return engine.areas.get(engine.area if area is None else engine.area_number(area))
    def with_area(method,area=None,default=0):
        s=area_state(area)
        if not s: return default
        old=engine.area; engine.area=engine.area if area is None else engine.area_number(area)
        try: return method()
        finally: engine.area=old
    def space(n):
        n=int(n)
        if not 0<=n<=1000000: raise XBaseError('Tamanho fora do limite.')
        return ' '*n
    def replicate(s,n):
        n=int(n)
        if n<0 or len(s)*n>1000000: raise XBaseError('REPLICATE excede limite.')
        return s*n
    def field(n):
        fs=engine.fields(); return fs[int(n)-1].name if 1<=int(n)<=len(fs) else ''
    def dbf(area=None):
        s=area_state(area); return str(s['path']) if s else ''
    def alias(area=None):
        s=area_state(area); return s['alias'] if s else ''
    def ndx(n=1):
        names=engine.state.get('indexes',[]); return names[int(n)-1] if 1<=int(n)<=len(names) else ''
    def key(): return engine.state['order'] if engine.area in engine.areas else ''
    return {
        'ABS':abs,'INT':lambda x:math.trunc(x),'ROUND':xround,'MAX':max,'MIN':min,
        'MOD':lambda a,b:a%b,'SQRT':math.sqrt,'EXP':math.exp,'LOG':math.log,
        'LEN':len,'TRIM':lambda s:s.rstrip(),'RTRIM':lambda s:s.rstrip(),
        'LTRIM':lambda s:s.lstrip(),'ALLTRIM':lambda s:s.strip(),
        'UPPER':lambda s:s.upper(),'LOWER':lambda s:s.lower(),
        'SUBSTR':lambda s,start,count=None:s[max(0,int(start)-1):] if count is None else s[max(0,int(start)-1):max(0,int(start)-1)+max(0,int(count))],
        'LEFT':lambda s,n:s[:max(0,int(n))],'RIGHT':lambda s,n:s[-int(n):] if int(n)>0 else '',
        'AT':lambda needle,haystack:haystack.find(needle)+1,
        'SPACE':space,'REPLICATE':replicate,'STUFF':lambda s,start,count,new:s[:int(start)-1]+new+s[int(start)-1+int(count):],
        'STR':str_value,'VAL':val,'CHR':lambda n:chr(int(n)%256),'ASC':lambda s:ord(s[0]) if s else 0,
        'ISALPHA':lambda s:bool(s) and s[0].isalpha(),'ISUPPER':lambda s:bool(s) and s[0].isupper(),'ISLOWER':lambda s:bool(s) and s[0].islower(),
        'DATE':dt.date.today,'CTOD':lambda s:ctod(engine,s),'DTOC':lambda d,flag=False:dtoc(engine,d,bool(flag)),
        'DTOS':lambda d:dtoc(engine,d,True),'DAY':lambda d:0 if d==EMPTY_DATE else d.day,
        'MONTH':lambda d:0 if d==EMPTY_DATE else d.month,'YEAR':lambda d:0 if d==EMPTY_DATE else d.year,
        'DOW':lambda d:0 if d==EMPTY_DATE else (d.weekday()+1)%7+1,
        'CMONTH':lambda d:'' if d==EMPTY_DATE else ('January','February','March','April','May','June','July','August','September','October','November','December')[d.month-1],
        'CDOW':lambda d:'' if d==EMPTY_DATE else ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')[d.weekday()],
        'TIME':lambda:dt.datetime.now().strftime('%H:%M:%S'),
        'SECONDS':lambda:(dt.datetime.now()-dt.datetime.combine(dt.date.today(),dt.time())).total_seconds(),
        'RECNO':lambda area=None:with_area(lambda:engine.state['pointer'],area),
        'RECCOUNT':lambda area=None:with_area(lambda:engine.record_count(),area),
        'EOF':lambda area=None:with_area(lambda:engine.eof(),area,False),
        'BOF':lambda area=None:with_area(lambda:engine.bof(),area,False),
        'DELETED':lambda:bool(engine.current().get('_deleted',False)),
        'FOUND':lambda area=None:with_area(lambda:engine.state.get('found',False),area,False),
        'ORDER':lambda:engine.state.get('order_name','') if engine.area in engine.areas else '',
        'EMPTY':lambda value:not value.strip() if isinstance(value,str) else value==EMPTY_DATE if isinstance(value,dt.date) else not value,
        'RECSIZE':lambda:1+sum(8 if f.type=='D' else 10 if f.type=='M' else f.length for f in engine.fields()),
        'ALIAS':alias,'SELECT':lambda name=None:engine.area if name is None else engine.area_number(name),
        'USED':lambda area=None:area_state(area) is not None,
        'DBF':dbf,'FIELD':field,'FCOUNT':lambda:len(engine.fields()),'NDX':ndx,'KEY':key,
        'LUPDATE':lambda:dt.date.fromtimestamp(engine.state['path'].stat().st_mtime),
        'FILE':lambda name:engine.path(name,'').is_file(),'DISKSPACE':lambda:__import__('shutil').disk_usage(engine.cwd).free,
        'IIF':lambda condition,yes,no:yes if condition else no,
        'TRANSFORM':lambda value,picture:engine.picture(value,picture),
        'ERROR':lambda:1 if engine.last_error else 0,
        'MESSAGE':lambda:engine.last_error.message if engine.last_error else '',
        'LINENO':lambda:engine.last_error.line or 0 if engine.last_error else 0,
        'PROGRAM':lambda:Path(engine.calls[-1]['program'].source).stem if engine.calls and engine.calls[-1]['program'] else '',
        'VERSION':lambda:'dBASE SQLite PLUS 2.1 (Python interpreter)',
        'OS':lambda:__import__('platform').system(),
        'ROW':lambda:engine.screen_row,'COL':lambda:engine.screen_col,
        'PCOUNT':lambda:len(engine.calls[-1]['args']) if engine.calls else 0,
        'READKEY':lambda:engine.last_key,'LASTKEY':lambda:engine.last_key,
        'INKEY':lambda seconds=0:engine.inkey(seconds),
    }
