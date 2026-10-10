"""Compilação de PRG em blocos e execução com diagnóstico de arquivo/linha."""
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
                if u=='ENDTEXT': in_text=False
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
            if cmd in ('ELSE','ENDIF','CASE','OTHERWISE','ENDCASE','ENDDO','ENDTEXT','ENDSCAN'):
                self.error('Terminador fora do bloco correspondente: '+cmd,line)
            if cmd in ('LOOP','EXIT') and not loops: self.error(cmd+' fora de laço.',line)
            if cmd=='IF':
                yes,j=self._block(lines,i+1,{'ELSE','ENDIF'},loops)
                no=[]
                if j>=len(lines): self.error('IF sem ENDIF.',line)
                if command_parts(lines[j].text)[0]=='ELSE':
                    no,j=self._block(lines,j+1,{'ENDIF'},loops)
                    if j>=len(lines): self.error('IF sem ENDIF.',line)
                nodes.append(Node('if',tail,line.number,branches=[(tail,yes),('',no)])); i=j+1; continue
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
                while j<len(lines) and lines[j].text.strip().upper()!='ENDTEXT': content.append(lines[j].text); j+=1
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
    elif node.kind=='while':
        # III PLUS expande a macro uma vez na entrada do DO WHILE.
        condition=engine.expand(node.text)
        while engine.expr(condition) and engine.running:
            engine.tick()
            try: execute_nodes(engine,node.children,source)
            except LoopSignal: continue
            except ExitSignal: break
