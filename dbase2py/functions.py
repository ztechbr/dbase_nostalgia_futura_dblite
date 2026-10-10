"""Funções usuais dBASE III PLUS e extensões explicitadas no manual."""
import datetime as dt
import fnmatch
import math
import random
import re
import time
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from .syntax import XBaseError
from .memory import XArray

EMPTY_DATE=dt.date.min


class FieldInt(int):
    """Inteiro lido de campo N: conserva largura para LIST, ? e SAY, como no dBASE."""
    def __new__(cls,value,width=10,decimals=0):
        obj=int.__new__(cls,value); obj.width=width; obj.decimals=0; return obj


class FieldFloat(float):
    """Número com casas decimais lido de campo N."""
    def __new__(cls,value,width=10,decimals=2):
        obj=float.__new__(cls,value); obj.width=width; obj.decimals=decimals; return obj


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
        'VERSION':lambda:'dBASE SQLite PLUS 2.2 (Python interpreter)',
        'OS':lambda:__import__('platform').system(),
        'ROW':lambda:engine.screen_row,'COL':lambda:engine.screen_col,
        'PCOUNT':lambda:len(engine.calls[-1]['args']) if engine.calls else 0,
        'READKEY':lambda:engine.last_key,'LASTKEY':lambda:engine.last_key,
        'INKEY':lambda seconds=0:engine.inkey(seconds),
        # dBASE II: RANK(c) é o código ASCII.
        'RANK':lambda s:ord(s[0]) if s else 0,
        # Extensões de dBASE IV/Clipper usadas com frequência em sistemas portados.
        'STRZERO':lambda n,width=10,decimals=0:str_value(n,width,decimals).replace(' ','0') if n>=0 else '-'+str_value(-n,int(width)-1,decimals).replace(' ','0'),
        'PADL':lambda v,n,c=' ':pad(v,n,c,'L'),'PADR':lambda v,n,c=' ':pad(v,n,c,'R'),'PADC':lambda v,n,c=' ':pad(v,n,c,'C'),
        'ISDIGIT':lambda s:bool(s) and s[0].isdigit(),'ISBLANK':lambda v:not v.strip() if isinstance(v,str) else v==EMPTY_DATE if isinstance(v,dt.date) else not v,
        'CEILING':math.ceil,'FLOOR':math.floor,'SIGN':lambda n:(n>0)-(n<0),'PI':lambda:math.pi,
        'RAND':lambda seed=None:random.random() if seed is None or seed>=0 else random.Random(seed).random(),
        'GETENV':lambda name:__import__('os').environ.get(str(name),''),
        'DMY':lambda d:'' if d==EMPTY_DATE else f"{d.day} {CMONTHS[d.month-1]} {d.year if engine.settings['CENTURY'] else f'{d.year%100:02}'}",
        'MDY':lambda d:'' if d==EMPTY_DATE else f"{CMONTHS[d.month-1]} {d.day:02}, {d.year if engine.settings['CENTURY'] else f'{d.year%100:02}'}",
        'RLOCK':lambda *a:True,'LOCK':lambda *a:True,'FLOCK':lambda *a:True,'NETWORK':lambda:False,'ISCOLOR':lambda:False,
        'HEADER':lambda:32+32*len(engine.fields())+1,'FKMAX':lambda:10,'FKLABEL':lambda n:f'F{int(n)+1}',
        'MEMLINES':lambda s,width=50:len(mlines(s,width)),'MLINE':lambda s,n,width=50:(mlines(s,width)+['']*int(n))[int(n)-1] if int(n)>=1 else '',
        'RAT':lambda needle,haystack:haystack.rfind(needle)+1 if needle else 0,
        'OCCURS':lambda needle,haystack:haystack.count(needle) if needle else 0,
        'PROPER':lambda s:re.sub(r'[A-Za-zÀ-ÿ]+',lambda m:m[0][0].upper()+m[0][1:].lower(),s),
        'PROW':lambda:engine.printer_row,'PCOL':lambda:engine.printer_col,
        'SOUNDEX':soundex,'DIFFERENCE':lambda a,b:sum(x==y for x,y in zip(soundex(a),soundex(b))),
        'LIKE':lambda pattern,text:fnmatch.fnmatchcase(str(text),str(pattern)),
        # Arrays (dBASE IV/Clipper): alteram o array recebido, como no original.
        'ALEN':alen,'AFILL':afill,'ASCAN':lambda a,v,start=1,count=None:ascan(engine,a,v,start,count),
        'ASORT':asort,'AINS':ains,'ADEL':adel,'ASIZE':asize,'AADD':aadd,'ACOPY':acopy,'ACLONE':aclone,
        'AFIELDS':lambda *arrays:afields(engine,*arrays),'ARRAY':lambda *dims:XArray.build([int(d) for d in dims]),
    }


def need_array(a):
    if not isinstance(a,XArray): raise XBaseError('Função de array recebeu valor que não é array.')
    return a


def span(a,start,count):
    start=max(1,int(start)); end=len(a) if count is None else min(len(a),start-1+int(count))
    return start-1,end


def alen(a,dimension=None):
    need_array(a)
    if dimension is None or int(dimension)==1: return len(a)
    if int(dimension)==2: return len(a[0]) if a and isinstance(a[0],XArray) else 0
    return sum(len(r) if isinstance(r,XArray) else 1 for r in a)


def afill(a,value,start=1,count=None):
    first,end=span(need_array(a),start,count)
    for i in range(first,end): a[i]=value
    return a


def ascan(engine,a,value,start=1,count=None):
    first,end=span(need_array(a),start,count)
    for i in range(first,end):
        item=a[i]
        if isinstance(item,str) and isinstance(value,str): found=item.rstrip()==value.rstrip() if engine.exact else item.startswith(value)
        else: found=type(item) is type(value) and item==value or isinstance(item,(int,float)) and not isinstance(item,bool) and isinstance(value,(int,float)) and not isinstance(value,bool) and item==value
        if found: return i+1
    return 0


def asort(a,start=1,count=None,descending=0):
    first,end=span(need_array(a),start,count)
    a[first:end]=sorted(a[first:end],key=lambda v:(v[0] if isinstance(v,XArray) and v else v),reverse=bool(descending))
    return a


def ains(a,position):
    need_array(a); a.insert(int(position)-1,False); a.pop(); return a


def adel(a,position):
    need_array(a); del a[int(position)-1]; a.append(False); return a


def asize(a,size):
    need_array(a); size=int(size)
    del a[size:]; a.extend([False]*(size-len(a))); return a


def aadd(a,value): need_array(a).append(value); return value


def aclone(a): return XArray(aclone(v) if isinstance(v,XArray) else v for v in need_array(a))


def acopy(source,target,start=1,count=None,target_start=1):
    first,end=span(need_array(source),start,count); position=int(target_start)-1
    for i in range(first,end):
        if position>=len(need_array(target)): break
        target[position]=source[i]; position+=1
    return target


def afields(engine,*arrays):
    """AFIELDS(nomes[,tipos,larguras,decimais]) do Clipper: preenche e devolve a quantidade de campos."""
    fields=engine.fields()
    for array,attribute in zip(arrays,('name','type','length','decimals')):
        need_array(array)[:]=[getattr(f,attribute) for f in fields]
    return len(fields)


CMONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')


def pad(value,n,char,side):
    text=value if isinstance(value,str) else str(value).strip() if not isinstance(value,dt.date) else value.isoformat()
    n=int(n); char=(char or ' ')[0]
    if len(text)>=n: return text[:n]
    return text.rjust(n,char) if side=='L' else text.ljust(n,char) if side=='R' else text.center(n,char)


def mlines(text,width):
    lines=[]
    for paragraph in str(text).replace('\r','').split('\n'):
        line=''
        for word in paragraph.split(' '):
            if line and len(line)+1+len(word)>int(width): lines.append(line); line=word
            else: line=(line+' '+word) if line else word
        lines.append(line)
    return lines


def soundex(text):
    text=re.sub(r'[^A-Z]','',str(text).upper())
    if not text: return '0000'
    codes={**dict.fromkeys('BFPV','1'),**dict.fromkeys('CGJKQSXZ','2'),**dict.fromkeys('DT','3'),'L':'4',**dict.fromkeys('MN','5'),'R':'6'}
    result=text[0]; last=codes.get(text[0],'')
    for ch in text[1:]:
        code=codes.get(ch,'')
        if code and code!=last: result+=code
        if ch not in 'HW': last=code
    return (result+'000')[:4]
