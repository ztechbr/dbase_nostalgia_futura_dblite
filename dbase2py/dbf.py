"""Leitura de arquivos legados (DBF, DBT/FPT, NDX/NTX, MEM) e exportação DBF III.

Os dados são convertidos para o formato SQLite deste interpretador; os arquivos
originais nunca são alterados.
"""
import datetime as dt
import re
import struct
from pathlib import Path
from .storage import Field
from .syntax import XBaseError

EMPTY_DATE=dt.date.min


def field_name(raw,used):
    """Nome de campo válido no SQLite deste projeto (dBASE II aceita ':' em NOTA:1)."""
    name=re.sub(r'[^A-Z0-9_]','_',raw.split(b'\0',1)[0].decode('ascii','replace').strip().upper()) or 'CAMPO'
    if not name[0].isalpha(): name='F_'+name
    base,n=name[:28],2
    while name in used: name=f'{base}_{n}'; n+=1
    used.add(name); return name


def read_header(data):
    """Retorna (versão, campos [(nome, tipo, largura, decimais)], primeiro registro, tamanho, quantidade)."""
    if len(data)<32: raise XBaseError('Arquivo DBF vazio ou truncado.')
    version=data[0]; used=set(); fields=[]
    if version==0x02:
        # dBASE II (CP/M e MSX-DOS): cabeçalho fixo de 521 bytes e descritores de 16 bytes.
        count,size=struct.unpack_from('<H',data,1)[0],struct.unpack_from('<H',data,6)[0]
        for offset in range(8,8+32*16,16):
            if data[offset]==0x0D: break
            kind=chr(data[offset+11]).upper()
            fields.append((field_name(data[offset:offset+11],used),kind,data[offset+12],data[offset+15]))
        return 'dBASE II',fields,521,size,count
    count,header,size=struct.unpack_from('<IHH',data,4)
    offset=32
    while offset+32<=len(data) and data[offset]!=0x0D:
        kind=chr(data[offset+11]).upper(); length=data[offset+16]; decimals=data[offset+17]
        if kind=='C' and decimals: length+=decimals*256  # Clipper: texto com mais de 255 caracteres.
        fields.append((field_name(data[offset:offset+11],used),kind,length,decimals))
        offset+=32
    names={0x03:'dBASE III',0x83:'dBASE III + DBT',0x8B:'dBASE IV + DBT',0xF5:'FoxPro + FPT',0x30:'Visual FoxPro',0x04:'dBASE IV'}
    return names.get(version,f'DBF 0x{version:02X}'),fields,header,size,count


class MemoFile:
    def __init__(self,path):
        self.data=path.read_bytes() if path else b''
        self.fpt=bool(path) and path.suffix.lower()=='.fpt'
        if self.fpt: self.block=struct.unpack_from('>H',self.data,6)[0] or 64
        else:
            # dBASE III usa blocos fixos de 512; dBASE IV grava o tamanho no byte 20.
            self.block=512
            if len(self.data)>=22 and self.data[16]!=0x03:
                declared=struct.unpack_from('<H',self.data,20)[0]
                if declared in (64,128,256,512,1024,2048,4096,8192,16384): self.block=declared

    def read(self,number,encoding):
        if not self.data or number<=0: return ''
        start=number*self.block
        if start>=len(self.data): return ''
        if self.fpt:
            length=struct.unpack_from('>I',self.data,start+4)[0]
            return self.data[start+8:start+8+length].decode(encoding,'replace')
        if self.data[start:start+4]==b'\xff\xff\x08\x00':
            length=struct.unpack_from('<I',self.data,start+4)[0]
            return self.data[start+8:start+length].decode(encoding,'replace')
        end=self.data.find(b'\x1a',start)
        return self.data[start:end if end>=0 else len(self.data)].decode(encoding,'replace').rstrip('\x00')


def memo_path(path):
    for suffix in ('.dbt','.fpt','.DBT','.FPT'):
        candidate=path.with_suffix(suffix)
        if candidate.exists(): return candidate
    return None


def read_dbf(path,encoding='cp850'):
    """Lê um DBF e retorna (descrição, [Field], [registros com _deleted])."""
    path=Path(path); data=path.read_bytes()
    version,raw_fields,start,size,count=read_header(data)
    memo=MemoFile(memo_path(path)) if any(k in 'MGB' for _,k,_,_ in raw_fields) else None
    fields=[]; readers=[]
    for name,kind,length,decimals in raw_fields:
        if kind in ('N','F'): fields.append(Field(name,'N',max(1,min(length,20)),min(decimals,max(0,length-2)) if decimals and length>2 else 0))
        elif kind=='L': fields.append(Field(name,'L',1))
        elif kind=='D': fields.append(Field(name,'D',8))
        elif kind in ('M','G','B') and length==10: fields.append(Field(name,'M',10))
        elif kind=='I': fields.append(Field(name,'N',11))
        elif kind=='Y': fields.append(Field(name,'N',20,4))
        elif kind=='T': fields.append(Field(name,'C',19))
        else: fields.append(Field(name,'C',max(1,length)))
        readers.append((kind,length,decimals))
    records=[]
    for n in range(count):
        offset=start+n*size
        chunk=data[offset:offset+size]
        if len(chunk)<size or chunk[:1]==b'\x1a': break
        record={'_deleted':chunk[0]==0x2A}; position=1
        for field,(kind,length,decimals) in zip(fields,readers):
            raw=chunk[position:position+length]; position+=length
            record[field.name]=decode_value(field,kind,raw,decimals,memo,encoding)
        records.append(record)
    return version,fields,records


def decode_value(field,kind,raw,decimals,memo,encoding):
    if kind=='I': return struct.unpack('<i',raw)[0]
    if kind=='Y': return struct.unpack('<q',raw)[0]/10000
    if kind=='T':
        day,ms=struct.unpack('<ii',raw)
        if not day: return ''
        moment=dt.datetime.fromordinal(day-1721425)+dt.timedelta(milliseconds=ms)
        return moment.strftime('%Y-%m-%d %H:%M:%S')
    text=raw.decode(encoding,'replace')
    if field.type=='N':
        text=text.strip().replace(',','.')
        try: return float(text) if field.decimals else int(float(text))
        except ValueError: return 0
    if field.type=='L': return text.strip().upper() in ('T','Y','S')
    if field.type=='D':
        text=text.strip()
        try: return dt.date(int(text[:4]),int(text[4:6]),int(text[6:8])) if len(text)==8 and text.isdigit() and int(text) else EMPTY_DATE
        except ValueError: return EMPTY_DATE
    if field.type=='M':
        if len(raw)==4: number=struct.unpack('<I',raw)[0]
        else:
            digits=text.strip()
            number=int(digits) if digits.isdigit() else 0
        return memo.read(number,encoding) if memo else ''
    return text.rstrip('\x00')


def index_expression(path):
    """Expressão-chave de um índice NDX (dBASE III) ou NTX (Clipper), lida do cabeçalho."""
    data=Path(path).read_bytes()[:600]
    if Path(path).suffix.lower()=='.ntx':
        expression,unique=data[22:278],len(data)>278 and data[278]==1
    else:
        expression,unique=data[24:124],len(data)>23 and data[23]==1
    text=expression.split(b'\0',1)[0].decode('cp850','replace').strip()
    if not text or not all(32<=ord(c)<127 or c.isalpha() for c in text): raise XBaseError('Cabeçalho de índice não reconhecido: '+Path(path).name)
    return text,unique


def read_mem(path,encoding='cp850'):
    """Variáveis de um arquivo MEM binário do dBASE III PLUS."""
    data=Path(path).read_bytes(); offset=0; values={}
    while offset+32<=len(data) and data[offset]!=0x1A:
        name=data[offset:offset+11].split(b'\0',1)[0].decode('ascii','replace').upper()
        kind=chr(data[offset+11]&0x7F); length=data[offset+16]; decimals=data[offset+17]
        offset+=32
        if kind=='C':
            size=length+decimals*256
            values[name]=data[offset:offset+size].split(b'\0',1)[0].decode(encoding,'replace'); offset+=size
        elif kind in ('N','D'):
            number=struct.unpack_from('<d',data,offset)[0]; offset+=8
            if kind=='N': values[name]=int(number) if number.is_integer() and not decimals else number
            else: values[name]=dt.date.fromordinal(int(number)-1721425) if number>0 else EMPTY_DATE
        elif kind=='L': values[name]=data[offset] in (1,ord('T'),ord('Y')); offset+=1
        else: raise XBaseError('Tipo de variável MEM desconhecido: '+kind)
    return values


def write_dbf(path,fields,records,encoding='cp850'):
    """Exporta para DBF dBASE III sem memo (campos M viram C 254)."""
    out=[]
    for f in fields:
        if f.type=='M': out.append((f.name,'C',254,0))
        elif f.type=='D': out.append((f.name,'D',8,0))
        elif f.type=='L': out.append((f.name,'L',1,0))
        else: out.append((f.name,f.type,min(f.length,254),f.decimals))
    for name,_,_,_ in out:
        if len(name)>10: raise XBaseError('DBF limita nomes de campo a 10 caracteres: '+name)
    size=1+sum(length for _,_,length,_ in out); today=dt.date.today()
    header=struct.pack('<BBBBIHH20x',0x03,today.year-1900,today.month,today.day,len(records),32+32*len(out)+1,size)
    for name,kind,length,decimals in out:
        header+=name.encode('ascii').ljust(11,b'\0')+kind.encode()+b'\0'*4+bytes([length,decimals])+b'\0'*14
    body=bytearray(header+b'\r')
    for record in records:
        body+=b'*' if record.get('_deleted') else b' '
        for name,kind,length,decimals in out:
            value=record.get(name)
            if kind=='N': text=(f'{value:.{decimals}f}' if decimals else str(int(value))).rjust(length)
            elif kind=='D': text=value.strftime('%Y%m%d') if isinstance(value,dt.date) and value!=EMPTY_DATE else ' '*8
            elif kind=='L': text='T' if value else 'F'
            else: text=str(value).replace('\n',' ')[:length].ljust(length)
            body+=text.encode(encoding,'replace')[:length].ljust(length,b' ')
    body+=b'\x1a'
    Path(path).write_bytes(bytes(body))
