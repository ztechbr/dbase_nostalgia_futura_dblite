"""Máscaras de entrada e editor de campos para terminais modernos."""
import datetime as dt
import sys
from contextlib import contextmanager
from .syntax import XBaseError


class PictureMask:
    def __init__(self,value,picture='',format_value=str,width=None):
        self.value=value
        self.numeric=isinstance(value,(int,float)) and not isinstance(value,bool)
        self.date=isinstance(value,dt.date)
        self.flags=''
        self.template=str(picture)
        if self.template=='!': self.template='@!'
        if self.template.startswith('@'):
            self.flags,_,self.template=self.template.partition(' ')
        if not self.template:
            if self.date: self.template=''.join('9' if c.isdigit() else c for c in format_value(dt.date(2001,1,1)))
            elif self.numeric: self.template='#'*(width or 10)
            elif isinstance(value,bool): self.template='L'
            else: self.template='X'*(width or max(1,len(str(value))))
        if len(self.template)>4096: raise XBaseError('PICTURE excede 4096 caracteres.')
        self.slots=[i for i,c in enumerate(self.template) if c in 'X9#!ALY']
        if not self.slots: raise XBaseError('PICTURE precisa ter ao menos uma posição editável.')
        self.format_value=format_value

    def blank(self): return [' ' if i in self.slots else c for i,c in enumerate(self.template)]

    def accepts(self,position,ch):
        token=self.template[position]
        if ch==' ': return True
        if token in '9#': return ch.isascii() and ch.isdigit() or self.numeric and position==self.slots[0] and ch in '+-' or self.numeric and '.' not in self.template and ch=='.'
        if token=='A': return ch.isalpha()
        if token in 'LY': return ch.upper() in 'TFYNS'
        return ch.isprintable()

    def normalize(self,position,ch): return ch.upper() if '!' in self.flags or self.template[position] in '!LY' else ch

    def apply(self,text,strict=True):
        """Aceita texto com separadores ou apenas caracteres das posições editáveis."""
        result=self.blank(); pos=0; index=0
        for ch in str(text):
            if pos>=len(self.template):
                if ch!=' ': raise XBaseError('Entrada excede a máscara.')
                continue
            while pos<len(self.template) and pos not in self.slots:
                if ch==self.template[pos]: pos+=1; break
                pos+=1
            else:
                if pos>=len(self.template):
                    if ch!=' ': raise XBaseError('Entrada excede a máscara.')
                    continue
                if not self.accepts(pos,ch):
                    if strict: raise XBaseError(f'Caractere {ch!r} inválido na posição {pos+1}.')
                    continue
                result[pos]=self.normalize(pos,ch); pos+=1
        return ''.join(result)

    def input_text(self,text):
        if not self.numeric: return self.apply(text)
        if '.' not in self.template: return self.apply(text)
        try: number=float(str(text).replace(',','').strip())
        except ValueError: raise XBaseError('Número inválido.')
        decimals=len(self.template.rsplit('.',1)[1])
        formatted=f'{number:,.{decimals}f}' if ',' in self.template else f'{number:.{decimals}f}'
        if len(formatted)>len(self.template): raise XBaseError('Número excede a máscara.')
        return self.apply(formatted.rjust(len(self.template)))

    def initial(self):
        if self.numeric:
            if any(c in self.template for c in '.,'):
                decimals=len(self.template.rsplit('.',1)[1]) if '.' in self.template else 0
                text=f'{self.value:,.{decimals}f}' if ',' in self.template else f'{self.value:.{decimals}f}'
                return text.rjust(len(self.template))[-len(self.template):]
            text=self.format_value(self.value)
            # Sem gabarito decimal, exibe a representação numérica completa.
            return text.rjust(len(self.template))[-len(self.template):]
        if isinstance(self.value,bool): return ('Y' if self.value else 'N') if 'Y' in self.template else ('T' if self.value else 'F')
        if self.date: return ''.join(self.blank()) if self.value==dt.date.min else self.apply(self.format_value(self.value))
        return self.apply(str(self.value)[:len(self.template)],False)

    def decode(self,display):
        if self.numeric:
            raw=display.replace(',','').replace(' ','')
            if not raw: return 0
            return float(raw)
        if isinstance(self.value,bool):
            raw=display.strip().upper()
            if raw not in ('T','F','Y','N','S'): raise XBaseError('Valor lógico inválido.')
            return raw in ('T','Y','S')
        if '@R' in self.flags: return ''.join(display[i] for i in self.slots)
        return display


class FieldEditor:
    """Estado de edição puro. Eventos simbólicos podem ser injetados nos testes."""
    def __init__(self,mask,confirm=False,initial=None):
        self.mask=mask; self.confirm=confirm
        self.buffer=list(initial if initial is not None else mask.initial())
        self.position=mask.slots[0]; self.started=False; self.changed=False

    @property
    def text(self): return ''.join(self.buffer)

    def event(self,key):
        slots=self.mask.slots; at=slots.index(self.position)
        if key in ('ENTER','TAB','DOWN'): return 'next'
        if key in ('UP','SHIFT_TAB'): return 'previous'
        if key=='ESC': return 'cancel'
        if key=='LEFT': self.started=True; self.position=slots[max(0,at-1)]; return
        if key=='RIGHT': self.started=True; self.position=slots[min(len(slots)-1,at+1)]; return
        if key=='HOME': self.started=True; self.position=slots[0]; return
        if key=='END': self.started=True; self.position=slots[-1]; return
        if key=='BACKSPACE':
            self.position=slots[max(0,at-1)]; self.buffer[self.position]=' '; self.changed=True; self.started=True; return
        if key=='DELETE': self.buffer[self.position]=' '; self.changed=True; self.started=True; return
        if len(key)!=1: return
        if self.mask.numeric and key=='.' and '.' in self.mask.template:
            after=[s for s in slots if s>self.mask.template.index('.')]
            if after: self.position=after[0]
            return
        # Um separador digitado explicitamente é aceito e não ocupa um slot.
        if key in ',/-' and self.position>0 and self.mask.template[self.position-1]==key: return
        if not self.mask.accepts(self.position,key): return 'invalid'
        if not self.started:
            self.buffer=self.mask.blank(); self.started=True
        self.buffer[self.position]=self.mask.normalize(self.position,key); self.changed=True
        if at==len(slots)-1: return None if self.confirm else 'next'
        self.position=slots[at+1]


@contextmanager
def terminal_keys():
    """Mantém o terminal restaurável e normaliza teclas Windows/POSIX."""
    if sys.platform=='win32':
        import msvcrt
        def read():
            ch=msvcrt.getwch()
            if ch in ('\x00','\xe0'):
                return {'K':'LEFT','M':'RIGHT','H':'UP','P':'DOWN','G':'HOME','O':'END','S':'DELETE'}.get(msvcrt.getwch(),'UNKNOWN')
            return normalize_key(ch)
        yield read
    else:
        import termios,tty,select,os
        fd=sys.stdin.fileno(); previous=termios.tcgetattr(fd)
        def read():
            raw=os.read(fd,1)
            if not raw: raise EOFError()
            if raw[0]>=128:
                size=2 if raw[0]<224 else 3 if raw[0]<240 else 4
                for _ in range(size-1): raw+=os.read(fd,1)
            ch=raw.decode('utf-8',errors='replace')
            if ch=='\x1b':
                suffix=''
                while select.select([fd],[],[],.03)[0]:
                    suffix+=os.read(fd,1).decode('ascii',errors='replace')
                    if suffix[-1:].isalpha() or suffix.endswith('~'): break
                return {'[D':'LEFT','[C':'RIGHT','[A':'UP','[B':'DOWN','[H':'HOME','[F':'END','[1~':'HOME','[4~':'END','[3~':'DELETE','[Z':'SHIFT_TAB'}.get(suffix,'ESC')
            return normalize_key(ch)
        try:
            tty.setraw(fd); yield read
        finally: termios.tcsetattr(fd,termios.TCSADRAIN,previous)


def normalize_key(ch):
    if ch=='\x03': raise KeyboardInterrupt()
    return {'\r':'ENTER','\n':'ENTER','\t':'TAB','\x13':'LEFT','\x04':'RIGHT','\x08':'BACKSPACE','\x7f':'BACKSPACE','\x1b':'ESC'}.get(ch,ch)
