"""Auditoria estática conservadora, sem executar comandos ou avaliar macros."""
import re
from .syntax import command_parts, XBaseError
from .expressions import Expression
from .engine import SET_STORED

SUPPORTED=set('USE CREATE SELECT LIST DISPLAY BROWSE GO GOTO SKIP APPEND INSERT REPLACE DELETE RECALL PACK ZAP SET LOCATE CONTINUE SEEK FIND COUNT SUM AVERAGE INDEX REINDEX STORE RELEASE SAVE RESTORE COPY SORT TOTAL JOIN UPDATE EDIT CHANGE ACCEPT INPUT WAIT CLEAR CLOSE ERASE RENAME DIR DIRECTORY HELP QUIT CANCEL RETURN PARAMETERS PRIVATE PUBLIC DO READ EJECT ON RETRY ? ?? ??? @ LOOP EXIT REMARK MODIFY REPORT PLUS IMPORT MENU UNLOCK RESET DECLARE DIMENSION LOCAL SCATTER GATHER LABEL'.split())
SET_KEYS=set('CONFIRM DELETED EXACT TALK SAFETY CONSOLE ALTERNATE DATE CENTURY DECIMALS UNIQUE SOFTSEEK FILTER INDEX ORDER PROCEDURE RELATION COLOR LINKAGE CARRY COLON DELIMITERS INTENSITY BELL HEADING FIXED PRINT PRINTER DEVICE FORMAT DIALECT MARGIN MESSAGE PATH DEFAULT FIELDS MONITOR'.split())|SET_STORED
# Recursos aceitos sem efeito ou com adaptação: viram aviso para revisão manual.
ADAPTED={'SET':{'ESCAPE':'SET ESCAPE é aceito sem interromper o programa.'},
    'ON':'ON ESCAPE/ON KEY são aceitos sem disparo; ON ERROR é executado.'}


def inspect_program(engine,program):
    findings=[]; commands=set(); dynamic=False
    def add(level,line,message): findings.append({'level':level,'source':program.source,'line':line,'message':message})
    def visit(nodes):
        nonlocal dynamic
        for n in nodes:
            if n.kind=='command':
                cmd,tail=command_parts(n.text); commands.add(cmd)
                if re.fullmatch(r'\d+',n.text.strip()): continue
                if cmd not in SUPPORTED and not re.fullmatch(r'(?:M->|M\.)?\w+\s*(?:\[.*\]|\(.*\))?\s*(?::=|=).*',n.text,re.I|re.S): add('error',n.line,'Comando não implementado: '+cmd)
                if cmd=='SET':
                    key=tail.partition(' ')[0].upper()
                    if key not in SET_KEYS: add('error',n.line,'SET não implementado: '+key)
                    elif key in ADAPTED['SET']: add('warning',n.line,ADAPTED['SET'][key])
                if cmd=='ON' and not tail.upper().startswith('ERROR'): add('warning',n.line,ADAPTED['ON'])
                if cmd=='REPORT': add('warning',n.line,'REPORT FORM lê FRM do dBASE III/Clipper ou o formato JSON deste projeto; confira o layout.')
                if cmd in ('DO','SET') and (cmd=='DO' or tail.upper().startswith(('PROCEDURE ','FORMAT '))): add('warning',n.line,'Dependência externa/procedimento deve ser auditada separadamente.')
                if '&' in n.text:
                    dynamic=True; add('warning',n.line,'Macro dinâmica exige validação em execução.')
                if cmd in ('CREATE','USE','COPY','APPEND'): add('info',n.line,'Bancos são SQLite; um .DBF de mesmo nome é importado no primeiro USE.')
                if cmd in ('?','??','RETURN','SEEK') and tail and '&' not in tail:
                    try:
                        from .syntax import split
                        for exp in split(tail): check_expression(exp,n.line)
                    except XBaseError as exc: add('error',n.line,exc.message)
            else:
                if n.kind in ('while','if'):
                    if '&' in n.text: dynamic=True; add('warning',n.line,'Condição usa macro dinâmica.')
                    else:
                        try: check_expression(n.text,n.line)
                        except XBaseError as exc: add('error',n.line,exc.message)
                if n.kind in ('scan','for'): add('info',n.line,(n.kind.upper())+' é extensão dBASE IV/Clipper.')
                visit(n.children)
                for condition,body in n.branches:
                    if condition and n.kind=='case' and '&' not in condition:
                        try: check_expression(condition,n.line)
                        except XBaseError as exc: add('error',n.line,exc.message)
                    visit(body)
    arrays=set()
    for line in program.lines:
        m=re.match(r'\s*(?:DIMENSION|DECLARE|DIME|DECL|PUBLIC|PRIVATE|LOCAL)\s+(.*)',line.text,re.I)
        if m: arrays.update(n.upper() for n in re.findall(r'([A-Za-z_]\w*)\s*[\[(]',m[1]))
    def check_expression(text,line):
        def walk(tree):
            if tree[0]=='call':
                if tree[1] not in engine._functions and tree[1]!='TYPE' and tree[1] not in program.routines and tree[1] not in arrays: add('error',line,'Função não implementada: '+tree[1])
                for child in tree[2]: walk(child)
            elif tree[0]=='binary': walk(tree[2]); walk(tree[3])
            elif tree[0] in ('unary','bang'): walk(tree[-1])
            elif tree[0]=='index': walk(tree[1]); [walk(i) for i in tree[2]]
            elif tree[0]=='array': [walk(i) for i in tree[1]]
        walk(Expression(text).tree)
    visit(program.main)
    for routine in program.routines.values(): visit(routine.body)
    return {'source':program.source,'status':'unsupported' if any(f['level']=='error' for f in findings) else 'needs_runtime_validation','commands':sorted(commands),'routines':sorted(program.routines),'dynamic_macros':dynamic,'findings':findings,'notice':'Auditoria estática parcial: não certifica equivalência com o runtime original nem valida todos os argumentos/cláusulas.'}
