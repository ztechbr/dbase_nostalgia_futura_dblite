import argparse
from .engine import DBaseEngine


def main():
    parser=argparse.ArgumentParser(description='dBASE SQLite, console xBase em Python')
    parser.add_argument('--cwd',default='./data')
    parser.add_argument('-c',action='append',default=[])
    parser.add_argument('--cmd')
    args=parser.parse_args(); engine=DBaseEngine(args.cwd)
    try:
        if args.cmd: engine.run_file(args.cmd)
        for command in args.c:
            if engine.running: engine.execute(command)
        if not args.c and not args.cmd:
            print('dBASE SQLite 1.0 | HELP para comandos | QUIT para sair')
            while engine.running:
                try: engine.execute(input('. '))
                except (EOFError,KeyboardInterrupt): break
                except Exception as exc: print('Erro:',exc)
    except Exception as exc:
        parser.exit(1,'Erro: '+str(exc)+'\n')
    finally: engine.close()
