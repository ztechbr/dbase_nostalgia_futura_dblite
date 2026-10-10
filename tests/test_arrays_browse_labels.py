"""Arrays, BROWSE em grade, LABEL FORM e cores de monitor."""
import datetime as dt
import struct
import tempfile
import unittest
from pathlib import Path
from dbase2py import DBaseEngine
from dbase2py.colors import attribute, monitor_scheme
from dbase2py.syntax import XBaseError


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.out=[]
        self.e=DBaseEngine(self.root,self.out.append,plain=True); self.e.execute('SET TALK OFF')
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def table(self):
        self.e.execute('CREATE cli (NOME C 12, IDADE N 3, CIDADE C 10, UF C 2, OBS M 10)')
        for row in [('Ana Silva',30,'Santos','SP'),('Bia',40,'Rio','RJ'),('Caio',25,'BH','MG')]:
            self.e.append(dict(zip(['NOME','IDADE','CIDADE','UF'],row)))
        self.e.execute('GO TOP')
    def keys(self,values):
        iterator=iter(values); self.e.key_reader=lambda:next(iterator)
    def program(self,code):
        (self.root/'p.prg').write_text(code,encoding='utf-8'); self.e.execute('DO p')


class Arrays(Base):
    def test_declare_dimension_literals(self):
        for c in ['DECLARE A[3], M[2,3]','A[1]=10','STORE "x" TO A[2], B','M[2,3]=5','DIMENSION F(2)','F(1)=7','L={1,"a",{2,3}}','D={10/10/26}','E={ / / }']: self.e.execute(c)
        values=[self.e.expr(x) for x in ['A[1]','A[2]','A[3]','M[2,3]','M[2][3]','F(1)','L[3][2]','TYPE("L")','D','EMPTY(E)','B','ALEN(M)','ALEN(M,2)']]
        self.assertEqual(values,[10,'x',False,5,5,7,3,'A',dt.date(1926,10,10),True,'x',2,3])
        with self.assertRaisesRegex(XBaseError,'fora dos limites'): self.e.expr('A[4]')
        self.assertEqual(self.e.expr('[texto]'),'texto'); self.assertEqual(self.e.expr('A[1] + LEN([ab])'),12)
    def test_array_functions(self):
        self.e.execute('DECLARE A[5]'); self.e.execute('X=AFILL(A,0)')
        for i,v in enumerate([5,3,9,1,7],1): self.e.execute(f'A[{i}]={v}')
        self.e.execute('X=ASORT(A)'); self.assertEqual(list(self.e.expr('A')),[1,3,5,7,9])
        self.assertEqual(self.e.expr('ASCAN(A,7)'),4); self.assertEqual(self.e.expr('ASCAN(A,8)'),0)
        self.e.execute('X=AINS(A,2)'); self.assertEqual(list(self.e.expr('A')),[1,False,3,5,7])
        self.e.execute('X=ADEL(A,1)'); self.assertEqual(list(self.e.expr('A')),[False,3,5,7,False])
        self.e.execute('X=ASIZE(A,2)'); self.e.execute('X=AADD(A,"z")'); self.assertEqual(list(self.e.expr('A')),[False,3,'z'])
        self.e.execute('C=ACLONE(A)'); self.e.execute('C[3]="w"'); self.assertEqual(self.e.expr('A[3]'),'z')
        self.e.execute('DECLARE N[2]'); self.e.execute('X=ACOPY(C,N,2)'); self.assertEqual(list(self.e.expr('N')),[3,'w'])
        self.e.execute('S={"PEDRO","ANA"}'); self.assertEqual(self.e.expr('ASCAN(S,"AN")'),2)
    def test_table_and_memory(self):
        self.table(); self.e.execute('DECLARE NOMES[1]'); self.assertEqual(self.e.expr('AFIELDS(NOMES)'),5); self.assertEqual(self.e.expr('NOMES[2]'),'IDADE')
        self.e.execute('COPY TO ARRAY T FIELDS NOME,IDADE FOR IDADE>=30'); self.assertEqual((self.e.expr('ALEN(T)'),self.e.expr('T[2,2]')),(2,40))
        self.e.execute('APPEND FROM ARRAY T'); self.assertEqual(self.e.expr('RECCOUNT()'),5); self.assertEqual(self.e.expr('TRIM(NOME)'),'Bia')
        self.e.execute('GO 1'); self.e.execute('SCATTER MEMVAR'); self.assertEqual(self.e.expr('M->IDADE'),30)
        self.e.execute('M->IDADE=31'); self.e.execute('GATHER MEMVAR FIELDS IDADE'); self.assertEqual(self.e.expr('IDADE'),31)
        self.e.execute('SCATTER TO R'); self.e.execute('R[1]="Ana S."'); self.e.execute('GATHER FROM R'); self.assertEqual(self.e.expr('TRIM(NOME)'),'Ana S.')
        self.e.execute('SAVE TO mem ALL LIKE T'); self.e.execute('RELEASE ALL'); self.e.execute('RESTORE FROM mem'); self.assertEqual(self.e.expr('T[1,1]'),'Ana Silva   ')
        self.e.execute('DISPLAY MEMORY'); self.assertIn('T            (A) [2]\n  [1] (A) [2]',self.out[-1])
    def test_get_element_and_program_scope(self):
        self.e.execute('DECLARE G[2]'); self.e.execute('G[1]=5'); self.e.input=lambda _:'42'
        self.e.execute('@ 1,1 GET G[1]'); self.e.execute('READ'); self.assertEqual(self.e.expr('G[1]'),42)
        self.program('PUBLIC TOTAL\nLOCAL V[3], K := 0\nFOR K = 1 TO 3\n  V[K] = K * 10\nNEXT\nTOTAL = V[1] + V[2] + V[3]\n')
        self.assertEqual(self.e.expr('TOTAL'),60); self.assertIsNone(self.e.array_variable('V'))
        report=self.e.check('p'); self.assertEqual(report['status'],'needs_runtime_validation')


class Labels(Base):
    def test_dialog_across_and_blank_lines(self):
        self.table()
        answers=iter(['20','4','2','1','2','2','NOME','OBS','CIDADE, "-", UF','']); self.e.input=lambda _:next(answers)
        self.e.execute('CREATE LABEL etiq'); self.out.clear(); self.e.execute('LABEL FORM etiq')
        self.assertEqual(self.out[:5],['  Ana Silva             Bia','  Santos - SP           Rio - RJ','','',''])
        self.assertEqual(self.out[5:7],['  Caio','  BH - MG'])
        self.e.execute('LABEL FORM etiq FOR UF="SP" TO FILE etiquetas'); self.assertIn('Santos - SP',(self.root/'etiquetas.txt').read_text(encoding='utf-8'))
    def test_binary_lbl_and_sample(self):
        self.table()
        data=bytearray(1034); data[0]=2; data[1:9]=b'Clientes'; struct.pack_into('<6H',data,61,2,15,0,0,0,1)
        for i,t in enumerate([b'NOME',b'CIDADE']): data[73+60*i:73+60*i+len(t)]=t
        data[1033]=2; (self.root/'bin.lbl').write_bytes(bytes(data))
        self.out.clear(); self.e.execute('LABEL FORM bin SAMPLE NEXT 1')
        self.assertEqual(self.out,['XXXXXXXXXXXXXXX','XXXXXXXXXXXXXXX','Ana Silva','Santos'])


class Browse(Base):
    def snapshot(self,rows=6): return [''.join(r).rstrip() for r in self.e.screen[:rows]]
    def test_edit_append_delete(self):
        self.table(); seen=[]
        sequence=iter(['DOWN','TAB']+list('41')+['ENTER','DOWN','DOWN','HOME']+list('Davi')+['ENTER','UP','\x15','SNAP','ESC'])
        def read():
            key=next(sequence)
            if key=='SNAP': seen.extend(self.snapshot()); key=next(sequence)
            return key
        self.e.key_reader=read; self.e.execute('BROWSE FIELDS NOME,IDADE,OBS NOCLEAR')
        self.assertEqual(seen[1],'  NOME        │IDADE│OBS'); self.assertTrue(seen[5].startswith('* Caio'))
        rows=self.e.rows(False)
        self.assertEqual([(r['NOME'].strip(),r['IDADE'],r['_deleted']) for r in rows],[('Ana Silva',30,0),('Bia',41,0),('Caio',25,1),('Davi',0,0)])
        self.assertEqual(self.e.expr('RECNO()'),3)
    def test_blank_new_row_discarded_and_noappend(self):
        self.table(); self.e.execute('GO BOTTOM'); self.keys(['DOWN','UP','ESC']); self.e.execute('BROWSE')
        self.assertEqual(self.e.expr('RECCOUNT()'),3)
        self.keys(['DOWN','DOWN','ESC']); self.e.execute('BROWSE NOAPPEND'); self.assertEqual(self.e.expr('RECCOUNT()'),3)
    def test_freeze_noedit_and_memo(self):
        self.table(); self.keys(['RIGHT']+list('99')+['ENTER','ESC']); self.e.execute('BROWSE FREEZE IDADE')
        self.e.execute('GO 1'); self.assertEqual(self.e.expr('IDADE'),99)
        self.keys(['X','ESC']); self.e.execute('BROWSE NOEDIT'); self.e.execute('GO 1'); self.assertEqual(self.e.expr('TRIM(NOME)'),'Ana Silva')
    def test_plain_without_keys_lists(self):
        self.table(); self.e.execute('BROWSE FIELDS NOME'); self.assertIn('Ana Silva',self.out[1])


class Colors(unittest.TestCase):
    def test_attribute_codes(self):
        self.assertEqual(attribute('W+/B'),'\033[0;97;44m'); self.assertEqual(attribute('N/W'),'\033[0;30;47m'); self.assertEqual(attribute('GR*/N'),'\033[0;33;40;5m')
        with self.assertRaises(XBaseError): attribute('Q/N')
        self.assertIn('38;2;51;255;102',monitor_scheme('verde')['standard']); self.assertIsNone(monitor_scheme('nenhum'))
    def test_engine_uses_scheme(self):
        with tempfile.TemporaryDirectory() as folder:
            out=[]; e=DBaseEngine(folder,out.append,monitor='verde')
            try:
                e.execute('CLEAR'); self.assertTrue(out[-1].startswith('\033[0;38;2;51;255;102;48;2;0;0;0m\033[2J'))
                e.execute('SET DELIMITERS OFF'); e.execute('X="ab"'); e.execute('@ 1,1 GET X'); self.assertIn('\033[0;38;2;0;0;0;48;2;51;255;102mab',out[-1])
                e.execute('SET COLOR TO W+/B,N/W'); e.execute('@ 2,1 SAY "oi"'); self.assertIn('\033[0;97;44m',out[-1])
                e.execute('SET MONITOR TO AMBAR'); self.assertIn('38;2;255;176;0',out[-1])
                e.execute('SET MONITOR TO NENHUM'); e.execute('@ 3,1 SAY "x"'); self.assertEqual(out[-1],'\033[4;2Hx')
            finally: e.close()


if __name__=='__main__': unittest.main()
