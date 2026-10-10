"""Compilação de PRG em blocos e execução com diagnóstico de arquivo/linha."""
import re
from dataclasses import dataclass, field
from .syntax import XBaseError, source_lines, command_parts


class ReturnSignal(Exception):
    def __init__(self,value=None): self.value=value
class LoopSignal(Exception): pass
class ExitSignal(Exception): pass
class CancelSignal(Exception): pass
class RetrySignal(Exception): pass
class ReturnMasterSignal(Exception): pass


@dataclass
class Node:
    kind: str
    text: str
    line: int
    children: list = field(default_factory=list)
    branches: list = field(default_factory=list)


@dataclass
class Routine:
    name: str
    source: str
    body: list
    is_function: bool = False


class Program:
    def __init__(self,path,text):
        self.source=str(path)
        self.lines=source_lines(text)
        self.routines={}
        self.main=[]
        self._compile()

    def error(self,message,line): raise XBaseError(message,self.source,line.number,line.text)

    def _compile(self):
        segments=[]; current=[]; name=None; is_function=False
        in_text=False
        for line in self.lines:
            u=line.text.strip().upper()
            if in_text:
                current.append(line)
                if u in ('ENDTEXT','TEXTEND'): in_text=False
                continue
            cmd,tail=command_parts(line.text)
            if cmd=='TEXT': in_text=True
            if cmd in ('PROCEDURE','FUNCTION'):
                segments.append((name,is_function,current)); current=[]
                name=tail.strip().upper()
                if not name or not name.replace('_','A').isalnum(): self.error('Nome de rotina inválido.',line)
                is_function=cmd=='FUNCTION'
            else: current.append(line)
        segments.append((name,is_function,current))
        for name,is_function,lines in segments:
            body,i=self._block(lines,0,set(),0)
            if i!=len(lines): self.error('Bloco excedente.',lines[i])
            if name is None: self.main=body
            else:
                if name in self.routines: raise XBaseError('Rotina duplicada: '+name,self.source)
                self.routines[name]=Routine(name,self.source,body,is_function)

    def _block(self,lines,i,stops,loops):
        nodes=[]
        while i<len(lines):
            line=lines[i]; cmd,tail=command_parts(line.text)
            if cmd in stops: return nodes,i
            if cmd in ('ELSE','ELSEIF','ENDIF','CASE','OTHERWISE','ENDCASE','ENDDO','ENDTEXT','TEXTEND','ENDSCAN','ENDFOR') or cmd=='NEXT' and not loops:
                self.error('Terminador fora do bloco correspondente: '+cmd,line)
            if cmd in ('LOOP','EXIT') and not loops: self.error(cmd+' fora de laço.',line)
            if cmd=='IF':
                # ELSEIF (extensão dBASE IV/Clipper) gera ramos avaliados em ordem, como DO CASE.
                branches=[]; condition=tail; j=i
                while True:
                    body,j=self._block(lines,j+1,{'ELSE','ELSEIF','ENDIF'},loops)
                    if j>=len(lines): self.error('IF sem ENDIF.',line)
                    branches.append((condition,body))
                    stop,condition=command_parts(lines[j].text)
                    if stop!='ELSEIF': break
                if stop=='ELSE':
                    no,j=self._block(lines,j+1,{'ENDIF'},loops)
                    if j>=len(lines): self.error('IF sem ENDIF.',line)
                else: no=[]
                if len(branches)==1: nodes.append(Node('if',tail,line.number,branches=[branches[0],('',no)]))
                else: nodes.append(Node('case','',line.number,branches=branches+([('',no)] if no else [])))
                i=j+1; continue
            if cmd=='SCAN':
                body,j=self._block(lines,i+1,{'ENDSCAN'},loops+1)
                if j>=len(lines): self.error('SCAN sem ENDSCAN.',line)
                nodes.append(Node('scan',tail,line.number,body)); i=j+1; continue
            if cmd=='FOR':
                if not re.fullmatch(r'[A-Za-z_]\w*\s*=.+\bTO\b.+',tail,re.I|re.S): self.error('FOR variável = início TO fim [STEP passo]',line)
                body,j=self._block(lines,i+1,{'NEXT','ENDFOR'},loops+1)
                if j>=len(lines): self.error('FOR sem NEXT.',line)
                nodes.append(Node('for',tail,line.number,body)); i=j+1; continue
            if cmd=='DO' and tail.upper().startswith('WHILE '):
                body,j=self._block(lines,i+1,{'ENDDO'},loops+1)
                if j>=len(lines): self.error('DO WHILE sem ENDDO.',line)
                nodes.append(Node('while',tail[6:].strip(),line.number,body)); i=j+1; continue
            if cmd=='DO' and tail.upper()=='CASE':
                j=i+1; branches=[]; otherwise=False
                while j<len(lines) and command_parts(lines[j].text)[0]!='ENDCASE':
                    c,exp=command_parts(lines[j].text)
                    if c not in ('CASE','OTHERWISE'): self.error('DO CASE exige CASE/OTHERWISE.',lines[j])
                    if otherwise: self.error('CASE após OTHERWISE.',lines[j])
                    if c=='OTHERWISE': otherwise=True; exp=''
                    body,j=self._block(lines,j+1,{'CASE','OTHERWISE','ENDCASE'},loops)
                    branches.append((exp,body))
                if j>=len(lines): self.error('DO CASE sem ENDCASE.',line)
                nodes.append(Node('case','',line.number,branches=branches)); i=j+1; continue
            if cmd=='TEXT':
                j=i+1; content=[]
                while j<len(lines) and lines[j].text.strip().upper() not in ('ENDTEXT','TEXTEND'): content.append(lines[j].text); j+=1
                if j>=len(lines): self.error('TEXT sem ENDTEXT.',line)
                nodes.append(Node('text','\n'.join(content),line.number)); i=j+1; continue
            nodes.append(Node('command',line.text,line.number)); i+=1
        return nodes,i


def execute_nodes(engine,nodes,source):
    for node in nodes:
        while engine.running:
            engine.tick()
            try:
                execute_node(engine,node,source)
                break
            except (ReturnSignal,LoopSignal,ExitSignal,CancelSignal,RetrySignal,ReturnMasterSignal): raise
            except Exception as exc:
                if isinstance(exc,XBaseError) and exc.source: error=exc
                else: error=XBaseError(exc.message if isinstance(exc,XBaseError) else str(exc),source,node.line,node.text)
                if engine.on_error and not engine.handling_error:
                    if engine.handle_error(error)=='retry': continue
                    break
                raise error from exc


def execute_node(engine,node,source):
    if node.kind=='command': engine.execute(node.text)
    elif node.kind=='text': engine.emit(node.text)
    elif node.kind=='if':
        branch=node.branches[0][1] if engine.expr(node.text) else node.branches[1][1]
        execute_nodes(engine,branch,source)
    elif node.kind=='case':
        for condition,body in node.branches:
            if not condition or engine.expr(condition): execute_nodes(engine,body,source); break
    elif node.kind=='scan': execute_scan(engine,node,source)
    elif node.kind=='for': execute_for(engine,node,source)
    elif node.kind=='while':
        # III PLUS expande a macro uma vez na entrada do DO WHILE.
        condition=engine.expand(node.text)
        while engine.expr(condition) and engine.running:
            engine.tick()
            try: execute_nodes(engine,node.children,source)
            except LoopSignal: continue
            except ExitSignal: break


def run_body(engine,node,source):
    """Executa o corpo de um laço; retorna False quando EXIT encerra o laço."""
    engine.tick()
    try: execute_nodes(engine,node.children,source)
    except LoopSignal: pass
    except ExitSignal: return False
    return True


def execute_scan(engine,node,source):
    """SCAN [escopo] [FOR] [WHILE] ... ENDSCAN (extensão dBASE IV): SKIP automático após o corpo."""
    from .syntax import clauses, outside_words
    head,c=clauses(node.text,{'FOR','WHILE'})
    words={w for w,_,_ in outside_words(head)}
    limit=int(engine.expr(head.split()[-1])) if 'NEXT' in words else None
    if not words.intersection({'REST','NEXT'}) and not c.get('WHILE'): engine.go('TOP')
    area=engine.area; visited=0
    while engine.running and not engine.eof():
        if limit is not None and visited>=limit: break
        visited+=1
        if c.get('WHILE') and not engine.expr(c['WHILE']): break
        if not c.get('FOR') or engine.expr(c['FOR']):
            if not run_body(engine,node,source): break
            engine.area=area
        engine.skip('1')


def execute_for(engine,node,source):
    """FOR variável = início TO fim [STEP passo] ... NEXT (extensão dBASE IV/Clipper)."""
    from .syntax import clauses
    head,c=clauses(node.text,{'TO','STEP'})
    name,_,start=head.partition('=')
    name=name.strip()
    engine.variables[name]=engine.expr(start)
    step=engine.expr(c['STEP']) if c.get('STEP') else 1
    if not step: raise XBaseError('STEP 0 em FOR.')
    while engine.running:
        value=engine.variables[name]; end=engine.expr(c['TO'])
        if step>0 and value>end or step<0 and value<end: break
        if not run_body(engine,node,source): break
        engine.variables[name]=engine.variables[name]+step
