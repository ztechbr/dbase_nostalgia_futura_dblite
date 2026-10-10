"""Cores de tela: monitores de fósforo (verde, âmbar, branco) e códigos de SET COLOR do dBASE.

Cada esquema tem a cor padrão (SAY, ?, fundo da tela) e a realçada (GET, menu,
célula do BROWSE). As sequências são ANSI; sem esquema nada é emitido.
"""
import re
from .syntax import XBaseError

RESET='\033[0m'


def rgb(fg,bg): return f'\033[0;38;2;{fg[0]};{fg[1]};{fg[2]};48;2;{bg[0]};{bg[1]};{bg[2]}m'


BLACK=(0,0,0)
PHOSPHOR={'VERDE':(51,255,102),'AMBAR':(255,176,0),'BRANCO':(225,225,215)}
MONITORS={'VERDE','FOSFORO','AMBAR','BRANCO','CORES','NENHUM'}


def monitor_scheme(name):
    """Esquema de um monitor: padrão claro sobre preto e realce em vídeo reverso."""
    name=name.upper().replace('Â','A').replace('Ó','O')
    if name not in MONITORS: raise XBaseError('SET MONITOR TO VERDE|AMBAR|BRANCO|CORES|NENHUM')
    if name=='NENHUM': return None
    if name=='CORES': return {'standard':'\033[0;37;40m','enhanced':'\033[0;30;47m','name':'CORES'}
    color=PHOSPHOR['VERDE' if name=='FOSFORO' else name]
    dim=tuple(int(c*.55) for c in color)
    return {'standard':rgb(color,BLACK),'enhanced':rgb(BLACK,color),'border':rgb(dim,BLACK),'name':name}


CODES={'N':0,'B':4,'G':2,'BG':6,'GB':6,'R':1,'RB':5,'BR':5,'GR':3,'RG':3,'W':7,'X':0,'U':4,'I':7}


def attribute(text):
    """'W+/B' -> SGR. + realça a frente, * pisca, U sublinha, I inverte, X apaga."""
    fg,_,bg=text.strip().upper().partition('/')
    def color(part):
        letters=re.sub(r'[^A-Z]','',part)
        if letters and letters not in CODES: raise XBaseError('Cor desconhecida: '+part)
        return CODES.get(letters or 'N',0),'+' in part,'*' in part,letters
    f,bright,blink,letters=color(fg or 'W')
    b,_,_,_=color(bg or 'N')
    codes=['0',str(90+f if bright else 30+f),str(40+b)]
    if blink: codes.append('5')
    if letters=='U': codes.append('4')
    if letters=='I': codes[1:3]=['30','47']
    if letters=='X': codes[1]=str(30+b)
    return '\033['+';'.join(codes)+'m'


def color_scheme(spec,base):
    """SET COLOR TO padrão[,realçado[,borda]] sobre o esquema atual."""
    parts=[p for p in spec.split(',')]
    scheme=dict(base or {'standard':'\033[0;37;40m','enhanced':'\033[0;30;47m','name':'CORES'})
    for key,part in zip(('standard','enhanced','border'),parts):
        if part.strip(): scheme[key]=attribute(part)
    scheme['name']='SET COLOR'
    return scheme
