import sqlite3
import tempfile
import unittest
from pathlib import Path
from dbase2py import DBaseEngine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.out=[]; self.e=DBaseEngine(self.root,self.out.append)
        self.e.execute('CREATE pessoas (NOME C 20, IDADE N 3, SALDO N 10 2, ATIVO L 1)')
        for name,age in [('ANA',30),('BOB',40),('CAIO',50)]:
            self.e.execute('APPEND BLANK'); self.e.execute(f"REPLACE NOME WITH '{name}', IDADE WITH {age}, SALDO WITH 10.25, ATIVO WITH .T.")
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def test_persistence(self):
        self.e.execute('USE'); self.e.execute('USE pessoas')
        self.assertEqual(self.e.execute('COUNT'),3)
        db=sqlite3.connect(self.root/'pessoas.sqlite')
        self.assertEqual(db.execute('SELECT NOME FROM records WHERE _recno=1').fetchone()[0].rstrip(),'ANA'); db.close()
    def test_navigation(self):
        self.e.execute('GO TOP'); self.assertEqual(self.e.expr('RECNO()'),1)
        self.e.execute('SKIP 3'); self.assertTrue(self.e.expr('EOF()'))
        self.e.execute('SKIP -1'); self.assertEqual(self.e.current()['NOME'].rstrip(),'CAIO')
        self.e.execute('GO BOTTOM'); self.e.execute('SKIP -3'); self.assertTrue(self.e.expr('BOF()'))
    def test_delete_pack(self):
        self.e.execute('GO 2'); self.e.execute('DELETE'); self.e.execute('SET DELETED ON')
        self.assertEqual(self.e.execute('COUNT'),2)
        self.e.execute('SET DELETED OFF'); self.e.execute('RECALL'); self.assertEqual(self.e.execute('COUNT'),3)
        self.e.execute('DELETE'); self.e.execute('PACK')
        self.assertEqual([r['_recno'] for r in self.e.rows()],[1,2])
        self.assertEqual(self.e.rows()[1]['NOME'].rstrip(),'CAIO')
    def test_filter_locate(self):
        self.e.execute('SET FILTER TO IDADE >= 40 .AND. ATIVO = .T.')
        self.assertEqual(self.e.execute('COUNT'),2)
        self.assertTrue(self.e.execute('LOCATE FOR IDADE >= 40'))
        self.assertEqual(self.e.current()['NOME'].rstrip(),'BOB')
        self.assertTrue(self.e.execute('CONTINUE')); self.assertEqual(self.e.current()['NOME'].rstrip(),'CAIO')
        self.assertFalse(self.e.execute('CONTINUE'))
    def test_index(self):
        self.e.execute('INDEX ON NOME TO nomes'); self.assertTrue(self.e.execute("SEEK 'BOB'"))
        self.e.execute('USE'); self.e.execute('USE pessoas'); self.e.execute('SET ORDER TO nomes')
        self.assertTrue(self.e.execute('FIND CAIO'))
    def test_replace_atomic(self):
        before=self.e.rows()
        with self.assertRaises(ValueError): self.e.execute("REPLACE NOME WITH 'OK', IDADE WITH 99999 ALL")
        self.assertEqual(before,self.e.rows())
        self.e.execute('REPLACE IDADE WITH IDADE + 1 ALL FOR IDADE >= 40')
        self.assertEqual([r['IDADE'] for r in self.e.rows()],[30,41,51])
    def test_scopes(self):
        self.e.execute('GO TOP'); self.assertEqual(len(self.e.execute('DISPLAY NEXT 2')),2)
        self.assertEqual(len(self.e.execute('DISPLAY')),1)
    def test_csv(self):
        self.e.execute('COPY TO dados DELIMITED'); self.e.execute('APPEND FROM dados DELIMITED')
        self.assertEqual(self.e.execute('COUNT'),6)
        self.assertEqual((self.root/'dados.txt').read_text().splitlines()[0],'"ANA",30,10.25,T')
        self.e.execute('COPY TO dados.csv'); self.e.execute('APPEND FROM dados.csv')
        self.assertEqual(self.e.execute('COUNT'),12)
    def test_memory(self):
        self.e.execute('STORE 123 TO X'); self.e.execute('SAVE TO vars'); self.e.execute('RELEASE ALL'); self.e.execute('RESTORE FROM vars')
        self.assertEqual(self.e.expr('X'),123)
    def test_scripts(self):
        (self.root/'test.prg').write_text('PUBLIC X\nSTORE 0 TO X\nGO TOP\nDO WHILE .NOT. EOF()\nIF IDADE >= 40\nSTORE X + 1 TO X\nELSE\nSTORE X TO X\nENDIF\nSKIP\nENDDO\n')
        self.e.execute('DO test'); self.assertEqual(self.e.expr('X'),2)
    def test_safety(self):
        with self.assertRaises(ValueError): self.e.execute('CREATE ../escape (N C 5)')
        with self.assertRaises(ValueError): self.e.expr("__import__('os')")
        with self.assertRaises(ValueError): self.e.execute('CREATE pessoas (N C 5)')
    def test_areas(self):
        self.e.execute('SELECT SECONDARY'); self.e.execute('CREATE outras (N C 5)'); self.e.execute('APPEND BLANK')
        self.assertEqual(self.e.execute('COUNT'),1)
        self.e.execute('SELECT PRIMARY'); self.assertEqual(self.e.execute('COUNT'),3)
    def test_interactive_create(self):
        answers=iter(['TITULO C 10','VALOR N 6 2',''])
        self.e.input=lambda _:next(answers)
        self.e.execute('CREATE novo'); self.assertEqual(len(self.e.fields()),2)
    def test_string_literals(self):
        self.assertEqual(self.e.expr("'A=B .AND. C'"),'A=B .AND. C')

if __name__=='__main__': unittest.main()
