"""Lexer xBase, utilitários de cláusulas e diagnósticos."""
import re
from dataclasses import dataclass


class XBaseError(ValueError):
    def __init__(self, message, source=None, line=None, command=None):
        self.message, self.source, self.line, self.command = message, source, line, command
        where = f'{source}:{line}: ' if source else ''
        super().__init__(where + message + (f' [{command}]' if command else ''))


@dataclass
class Token:
    kind: str
    value: object
    start: int
    end: int


def subscript(text, i):
    """[ colado a nome, ) ou ] é índice de array (arr[1]); nos demais casos abre texto [assim]."""
    return text[i] == '[' and i > 0 and (text[i-1].isalnum() or text[i-1] in '_)]')


def lex(text):
    result = []
    i = 0
    brackets = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        start = i
        if subscript(text, i):
            brackets += 1; i += 1; result.append(Token('op','[',start,i)); continue
        if ch == ']' and brackets:
            brackets -= 1; i += 1; result.append(Token('op',']',start,i)); continue
        if ch in "'\"[":
            close = ']' if ch == '[' else ch
            i += 1
            value = ''
            while i < len(text):
                if text[i] == close:
                    if close != ']' and i + 1 < len(text) and text[i+1] == close:
                        value += close; i += 2; continue
                    i += 1; break
                value += text[i]; i += 1
            else:
                raise XBaseError('Literal de texto não terminado.')
            result.append(Token('string', value, start, i)); continue
        match = re.match(r'\.(AND|OR|NOT|T|F|Y|N)\.', text[i:], re.I)
        if match:
            value = match[1].upper(); i += len(match[0])
            result.append(Token('bool' if value in ('T','F','Y','N') else 'op', value, start, i)); continue
        match = re.match(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text[i:])
        if match:
            raw = match[0]; i += len(raw)
            result.append(Token('number', float(raw) if any(c in raw for c in '.eE') else int(raw), start, i)); continue
        match = re.match(r'[A-Za-z_][A-Za-z_0-9]*', text[i:])
        if match:
            i += len(match[0]); result.append(Token('name',match[0].upper(),start,i)); continue
        pair = text[i:i+2]
        if pair in ('->','<=','>=','<>','!=','==','**',':='):
            i += 2; result.append(Token('op',pair,start,i)); continue
        if ch in '+-*/%^$=<>#!(),.;:&@{}':
            i += 1; result.append(Token('op',ch,start,i)); continue
        raise XBaseError(f'Caractere inválido em expressão: {ch!r}')
    result.append(Token('end','',len(text),len(text)))
    return result


def outside_words(text):
    """Identificadores apenas fora de strings e parênteses, com offsets."""
    # Comandos incluem caminhos não aceitos como expressões: percorremos a string.
    i, depth, quote = 0, 0, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if quote != ']' and i+1 < len(text) and text[i+1] == quote:
                    i += 2; continue
                quote = None
            i += 1; continue
        if subscript(text, i): depth += 1; i += 1; continue
        if ch in "'\"[": quote = ']' if ch == '[' else ch; i += 1; continue
        if ch in '({': depth += 1
        if ch in ')}' or ch == ']' and depth: depth -= 1
        if depth == 0 and (ch.isalpha() or ch == '_'):
            match = re.match(r'[A-Za-z_][A-Za-z_0-9]*',text[i:])
            yield match[0].upper(),i,i+len(match[0]); i += len(match[0]); continue
        i += 1


def split(text):
    pieces, start, depth, quote, i = [],0,0,None,0
    while i < len(text):
        ch=text[i]
        if quote:
            if ch==quote:
                if quote!=']' and i+1<len(text) and text[i+1]==quote: i+=2; continue
                quote=None
        elif subscript(text,i): depth+=1
        elif ch in "'\"[": quote=']' if ch=='[' else ch
        elif ch in '({': depth+=1
        elif ch in ')}' or ch==']' and depth: depth-=1
        elif ch==',' and depth==0: pieces.append(text[start:i].strip()); start=i+1
        i+=1
    pieces.append(text[start:].strip())
    return pieces


def clauses(text, keys):
    marks = [(word,start,end) for word,start,end in outside_words(text) if word in keys]
    head=text[:marks[0][1]].strip() if marks else text.strip()
    result={}
    for i,(word,start,end) in enumerate(marks):
        if word in result: raise XBaseError('Cláusula repetida: '+word)
        result[word]=text[end:marks[i+1][1] if i+1<len(marks) else len(text)].strip()
    return head,result


def uncomment(line):
    if line.lstrip().upper().startswith(('*','NOTE ')): return ''
    i,quote=0,None
    while i<len(line)-1:
        ch=line[i]
        if quote:
            if ch==quote:
                if quote!=']' and line[i+1]==quote: i+=2; continue
                quote=None
        elif ch in "'\"[" and not subscript(line,i): quote=']' if ch=='[' else ch
        elif line[i:i+2]=='&&': return line[:i].rstrip()
        i+=1
    return line.rstrip()


@dataclass
class SourceLine:
    text: str
    number: int


def source_lines(text):
    result, pending, start, in_text = [],'',0,False
    for number,raw in enumerate(text.splitlines(),1):
        if in_text:
            result.append(SourceLine(raw,number))
            if raw.strip().upper() in ('ENDTEXT','TEXTEND'): in_text=False
            continue
        line=uncomment(raw).strip()
        if not pending: start=number
        # A continuação é válida quando o último caractere externo é ponto e vírgula.
        continuation=line.endswith(';')
        if continuation: pending+=line[:-1]+' '; continue
        line=pending+line; pending=''
        if line: result.append(SourceLine(line,start))
        if line.upper()=='TEXT': in_text=True
    if pending: raise XBaseError('Continuação sem linha seguinte.',line=start)
    return result


COMMANDS = set('USE CREATE SELECT LIST DISPLAY BROWSE GO GOTO SKIP APPEND REPLACE DELETE RECALL PACK ZAP SET LOCATE CONTINUE SEEK FIND COUNT SUM AVERAGE INDEX REINDEX STORE RELEASE SAVE RESTORE COPY SORT TOTAL JOIN UPDATE EDIT CHANGE ACCEPT INPUT WAIT CLEAR CLOSE ERASE RENAME DIR DIRECTORY HELP QUIT CANCEL RETURN PARAMETERS PRIVATE PUBLIC DO IF ELSE ELSEIF ENDIF CASE OTHERWISE ENDCASE ENDDO LOOP EXIT TEXT ENDTEXT TEXTEND PROCEDURE FUNCTION READ EJECT ON RETRY REMARK INSERT MODIFY REPORT LABEL PLUS IMPORT MENU SCAN ENDSCAN ENDFOR UNLOCK RESET DECLARE DIMENSION LOCAL SCATTER GATHER'.split())
ABBREVIATIONS={}
for command in COMMANDS:
    for n in range(4,len(command)):
        prefix=command[:n]
        if prefix not in ABBREVIATIONS: ABBREVIATIONS[prefix]=command
        elif ABBREVIATIONS[prefix]!=command: ABBREVIATIONS[prefix]=None


def command_parts(line):
    if line.startswith(('???','??','?','@')):
        m=re.match(r'\?{1,3}|@',line); return m[0],line[m.end():].strip()
    m=re.match(r'([A-Za-z_][A-Za-z_0-9]*)(.*)',line,re.S)
    if not m: raise XBaseError('Comando inválido.')
    name=m[1].upper(); rest=m[2].strip()
    if name in COMMANDS: return name,rest
    return ABBREVIATIONS.get(name,name) or name,rest
