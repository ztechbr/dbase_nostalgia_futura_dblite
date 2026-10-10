import argparse
import json
from .engine import DBaseEngine
from .program import ReturnSignal, LoopSignal, ExitSignal, CancelSignal, RetrySignal, ReturnMasterSignal


def main():
    p=argparse.ArgumentParser(description='dBASE SQLite PLUS 2.1: interpretador PRG/xBase com persistência SQLite')
    p.add_argument('--cwd',default='./data')
    p.add_argument('-c',action='append',default=[])
    p.add_argument('--cmd',help='PRG/CMD relativo a --cwd')
    p.add_argument('--check',help='Auditoria estática de PRG, sem executar')
    p.add_argument('--plain',action='store_true',help='Desativa ANSI e mostra SAY como linhas')
    p.add_argument('--encoding',default='auto',help='auto (UTF-8, depois CP850), cp850, cp1252, etc.')
    p.add_argument('--max-steps',type=int,default=100000)
    args=p.parse_args(); engine=DBaseEngine(args.cwd,plain=args.plain,encoding=args.encoding,max_steps=args.max_steps)
    try:
        if args.check:
            report=engine.check(args.check)
            print(json.dumps(report,ensure_ascii=False,indent=2))
            if report['status']=='unsupported': p.exit(2)
            return
        if args.cmd: engine.run_file(args.cmd)
        for command in args.c:
            if engine.running: engine.execute(command)
        if not args.c and not args.cmd:
            print('dBASE SQLite PLUS 2.1 | HELP para comandos | QUIT para sair')
            while engine.running:
                try: engine.execute(input('. '))
                except (EOFError,KeyboardInterrupt): break
                except (ReturnSignal,CancelSignal,ReturnMasterSignal): print('Execução interrompida.')
                except (LoopSignal,ExitSignal,RetrySignal): print('LOOP/EXIT requerem DO WHILE no PRG.')
                except Exception as exc: print('Erro:',exc)
    except Exception as exc: p.exit(1,'Erro: '+str(exc)+'\n')
    finally: engine.close()
