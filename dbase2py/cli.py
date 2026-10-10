import argparse
import json
import sys
from .engine import DBaseEngine
from .program import ReturnSignal, LoopSignal, ExitSignal, CancelSignal, RetrySignal, ReturnMasterSignal


def prepare_terminal():
    """Ativa sequências ANSI no console do Windows e evita erro de codificação em saída redirecionada."""
    try: sys.stdout.reconfigure(errors='replace') if sys.stdout.isatty() else sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    except (AttributeError,ValueError): pass
    if sys.platform=='win32' and sys.stdout.isatty():
        import ctypes
        kernel=ctypes.windll.kernel32; handle=kernel.GetStdHandle(-11); mode=ctypes.c_uint32()
        if kernel.GetConsoleMode(handle,ctypes.byref(mode)): kernel.SetConsoleMode(handle,mode.value|0x0004)


def main():
    p=argparse.ArgumentParser(description='dBASE SQLite PLUS 2.2: interpretador PRG/xBase com persistência SQLite')
    p.add_argument('--cwd',default='./data')
    p.add_argument('-c',action='append',default=[])
    p.add_argument('--cmd',help='PRG/CMD relativo a --cwd')
    p.add_argument('--check',help='Auditoria estática de PRG, sem executar')
    p.add_argument('--plain',action='store_true',help='Desativa ANSI e mostra SAY como linhas')
    p.add_argument('--encoding',default='auto',help='auto (UTF-8, depois CP850), cp850, cp1252, etc.')
    p.add_argument('--max-steps',type=int,default=100000)
    p.add_argument('--dialect',default='dbase3',choices=['dbase2','dbase3'],help='dbase2: CLEAR/ACCEPT/TYPE/LIST como no dBASE II do MSX')
    p.add_argument('--import-dbf',metavar='ARQUIVO',action='append',default=[],help='Converte DBF (dBASE II/III/IV, FoxPro) em SQLite e sai')
    p.add_argument('--monitor',choices=['verde','ambar','branco','cores','nenhum'],help='Cores da tela: fósforo verde (padrão no terminal), âmbar, branco, cores do dBASE III ou nenhum')
    args=p.parse_args(); prepare_terminal()
    monitor=args.monitor or ('verde' if sys.stdout.isatty() and not args.plain and not args.check else 'nenhum')
    engine=DBaseEngine(args.cwd,plain=args.plain,encoding=args.encoding,max_steps=args.max_steps,dialect=args.dialect,monitor=monitor)
    try:
        if args.check:
            report=engine.check(args.check)
            print(json.dumps(report,ensure_ascii=False,indent=2))
            if report['status']=='unsupported': p.exit(2)
            return
        for name in args.import_dbf: engine.execute('IMPORT FROM "'+name+'"')
        if args.import_dbf and not args.cmd and not args.c: return
        if engine.scheme and not args.plain: engine.clear_screen()
        if args.cmd: engine.run_file(args.cmd)
        for command in args.c:
            if engine.running: engine.execute(command)
        if not args.c and not args.cmd:
            engine.emit('dBASE SQLite PLUS 2.2 | HELP para comandos | QUIT para sair')
            while engine.running:
                try: engine.execute(input('. '))
                except (EOFError,KeyboardInterrupt): break
                except (ReturnSignal,CancelSignal,ReturnMasterSignal): print('Execução interrompida.')
                except (LoopSignal,ExitSignal,RetrySignal): print('LOOP/EXIT requerem DO WHILE no PRG.')
                except Exception as exc: print('Erro:',exc)
    except Exception as exc: p.exit(1,'Erro: '+str(exc)+'\n')
    finally: engine.close()
