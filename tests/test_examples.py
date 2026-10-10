import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ExampleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.data=Path(self.tmp.name)
        self.run_command('examples/setup.py','--cwd',str(self.data))
    def tearDown(self): self.tmp.cleanup()
    def run_command(self,*args,input=None,returncode=0):
        r=subprocess.run([sys.executable,*args],cwd=ROOT,input=input,capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,returncode,r.stdout+'\n'+r.stderr)
        return r
    def test_business_end_to_end(self):
        r=self.run_command('main.py','--cwd',str(self.data),'--cmd','negocios.prg','--plain')
        self.assertIn('Validacao:  .T.',r.stdout)
        db=sqlite3.connect(self.data/'clientes.sqlite')
        self.assertEqual(db.execute('SELECT SUM(LIMITE) FROM records').fetchone()[0],6075); db.close()
        db=sqlite3.connect(self.data/'clientes_pedidos.sqlite')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],3); db.close()
        self.assertIn('6075.00',(self.data/'resultado.txt').read_text())
    def test_menu_keyboard_script(self):
        r=self.run_command('main.py','--cwd',str(self.data),'--cmd','menu.prg','--plain',input='B\nBRU\n\nX\n')
        self.assertIn('BRUNO',r.stdout)
    def test_check_rejects_unsupported(self):
        r=self.run_command('main.py','--cwd',str(self.data),'--check','compat_auditoria.prg',returncode=2)
        report=json.loads(r.stdout); self.assertEqual(report['status'],'unsupported')
    def test_check_supported(self):
        r=self.run_command('main.py','--cwd',str(self.data),'--check','menu.prg')
        self.assertEqual(json.loads(r.stdout)['status'],'needs_runtime_validation')
    def test_runtime_error_nonzero(self):
        r=self.run_command('main.py','--cwd',str(self.data),'-c','REPORT FORM old',returncode=1)
        self.assertIn('REPORT',r.stderr)

if __name__=='__main__': unittest.main()
