"""Cria dados SQLite de demonstração e copia os PRGs originais deste projeto."""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dbase2py import DBaseEngine, Field


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cwd',default='./demo_data')
    args=parser.parse_args()
    root=Path(args.cwd).resolve(); root.mkdir(parents=True,exist_ok=True)
    names=['clientes','pedidos','movimentos']
    if any((root/(name+'.sqlite')).exists() for name in names):
        parser.exit(1,'Os bancos de exemplo já existem. Escolha outro diretório.\n')
    engine=DBaseEngine(root,plain=True)
    try:
        engine.create('clientes',[Field('CODIGO','N',5),Field('NOME','C',30),Field('CIDADE','C',20),Field('LIMITE','N',12,2),Field('ATIVO','L',1),Field('CRIADO','D',8)])
        import datetime as dt
        for code,name,city,limit in [(1,'ANA','SAO PAULO',1000),(2,'BRUNO','RIO DE JANEIRO',2000),(3,'CARLA','SAO PAULO',3000)]:
            engine.append({'CODIGO':code,'NOME':name,'CIDADE':city,'LIMITE':limit,'ATIVO':True,'CRIADO':dt.date(2026,10,10)})
        engine.execute('INDEX ON CODIGO TO clientes_cod')
        engine.execute('INDEX ON NOME TO clientes_nome')
        engine.create('pedidos',[Field('CODIGO','N',5),Field('VALOR','N',12,2)])
        for code,value in [(1,100),(1,200),(2,150)]: engine.append({'CODIGO':code,'VALOR':value})
        engine.execute('INDEX ON CODIGO TO pedidos_cod')
        engine.create('movimentos',[Field('CODIGO','N',5),Field('VALOR','N',12,2)])
        for code,value in [(2,25),(1,50)]: engine.append({'CODIGO':code,'VALOR':value})
        for p in Path(__file__).parent.glob('*.prg'):
            if p.name=='demo.prg': continue
            shutil.copyfile(p,root/p.name)
        print('Dados e programas preparados em',root)
        print('Execute: python main.py --cwd "'+str(root)+'" --cmd negocios.prg --plain')
    finally: engine.close()

if __name__=='__main__': main()
