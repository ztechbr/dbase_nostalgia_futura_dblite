"""Auditoria estática conservadora, sem executar comandos ou avaliar macros."""
import re
from .syntax import command_parts, XBaseError
from .expressions import Expression

SUPPORTED=set('USE CREATE SELECT LIST DISPLAY BROWSE GO GOTO SKIP APPEND REPLACE DELETE RECALL PACK ZAP SET LOCATE CONTINUE SEEK FIND COUNT SUM AVERAGE INDEX REINDEX STORE RELEASE SAVE RESTORE COPY SORT TOTAL JOIN UPDATE EDIT CHANGE ACCEPT INPUT WAIT CLEAR CLOSE ERASE RENAME DIR DIRECTORY HELP QUIT CANCEL RETURN PARAMETERS PRIVATE PUBLIC DO READ EJECT ON RETRY ? ?? @ LOOP EXIT'.split())
SET_KEYS=set('CONFIRM DELETED EXACT TALK SAFETY CONSOLE ALTERNATE DATE CENTURY DECIMALS UNIQUE SOFTSEEK FILTER INDEX ORDER PROCEDURE RELATION COLOR'.split())


def inspect_program(engine,program):
    findings=[]; commands=set(); dynamic=False
    def add(level,line,message): findings.append({'level':level,'source':program.source,'line':line,'message':message})
    def visit(nodes):
        nonlocal dynamic
        for n in nodes:
            if n.kind=='command':
                cmd,tail=command_parts(n.text); commands.add(cmd)
                if cmd not in SUPPORTED and not re.fullmatch(r'(?:M->|M\.)?\w+\s*(?::=|=).*',n.text,re.I): add('error',n.line,'Comando não implementado: '+cmd)
                if cmd=='SET' and tail.partition(' ')[0].upper() not in SET_KEYS: add('error',n.line,'SET não implementado: '+tail.partition(' ')[0])
                if cmd=='@' and re.search(r'\b(VALID|WHEN|COLOR)\b',tail,re.I): add('error',n.line,'Opção de @ não implementada; verificar dialeto.')
                if cmd in ('DO','SET') and (cmd=='DO' or tail.upper().startswith('PROCEDURE ')): add('warning',n.line,'Dependência externa/procedimento deve ser auditada separadamente.')
                if '&' in n.text:
                    dynamic=True; add('warning',n.line,'Macro dinâmica exige validação em execução.')
                if cmd in ('CREATE','USE','COPY','APPEND'): add('info',n.line,'Arquivos de dados usam formato SQLite; DBF não é lido.')
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
                visit(n.children)
                for condition,body in n.branches:
                    if condition and n.kind=='case' and '&' not in condition:
                        try: check_expression(condition,n.line)
                        except XBaseError as exc: add('error',n.line,exc.message)
                    visit(body)
    def check_expression(text,line):
        def walk(tree):
            if tree[0]=='call':
                if tree[1] not in engine._functions and tree[1]!='TYPE' and tree[1] not in program.routines: add('error',line,'Função não implementada: '+tree[1])
                for child in tree[2]: walk(child)
            elif tree[0]=='binary': walk(tree[2]); walk(tree[3])
            elif tree[0]=='unary': walk(tree[2])
        walk(Expression(text).tree)
    visit(program.main)
    for routine in program.routines.values(): visit(routine.body)
    return {'source':program.source,'status':'unsupported' if any(f['level']=='error' for f in findings) else 'needs_runtime_validation','commands':sorted(commands),'routines':sorted(program.routines),'dynamic_macros':dynamic,'findings':findings,'notice':'Auditoria estática parcial: não certifica equivalência com o runtime original nem valida todos os argumentos/cláusulas.'}
