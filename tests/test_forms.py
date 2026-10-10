import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from dbase2py import DBaseEngine
from dbase2py.forms import PictureMask,FieldEditor
from dbase2py.syntax import XBaseError


class FormTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.out=[]
        self.e=DBaseEngine(self.root,self.out.append,plain=True)
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def keys(self,values):
        iterator=iter(values); self.e.key_reader=lambda:next(iterator)
    def test_get_draws_colons(self):
        self.e.execute('STORE 40 TO TEMP'); self.e.execute('@ 0,0 SAY "Temperatura " GET TEMP')
        row=''.join(self.e.screen[0]); self.assertIn('Temperatura :',row); self.assertIn('40:',row)
    def test_date_mask_display(self):
        self.e.execute('D=SPACE(10)'); self.e.execute('@ 0,0 SAY "Data " GET D PICTURE "99/99/9999"')
        self.assertTrue(''.join(self.e.screen[0]).startswith('Data :  /  /    :'))
    def test_auto_advance_separators(self):
        self.e.execute('D=SPACE(10)'); self.e.execute('@ 0,0 GET D PICTURE "99/99/9999"')
        self.keys(list('01022024')); self.e.execute('READ'); self.assertEqual(self.e.expr('D'),'01/02/2024')
    def test_confirm_requires_enter(self):
        self.e.execute('SET CONFIRM ON'); self.e.execute('N=SPACE(2)'); self.e.execute('@ 0,0 GET N')
        self.keys(['A','B','LEFT','C','ENTER']); self.e.execute('READ'); self.assertEqual(self.e.expr('N'),'CB')
    def test_two_gets_auto(self):
        self.e.execute('N=SPACE(3)'); self.e.execute('D=SPACE(10)')
        self.e.execute('@ 0,0 GET N'); self.e.execute('@ 1,0 GET D PICTURE "99/99/9999"')
        self.keys(list('ANA01022024')); self.e.execute('READ')
        self.assertEqual(self.e.expr('N'),'ANA'); self.assertEqual(self.e.expr('D'),'01/02/2024')
    def test_clear_gets_keeps_screen(self):
        self.e.execute('N=SPACE(3)'); self.e.execute('D=SPACE(10)')
        self.e.execute('@ 0,0 SAY "Nome " GET N'); self.e.execute('CLEAR GETS'); self.e.execute('@ 1,0 GET D PICTURE "99/99/9999"')
        self.keys(list('01022024')); self.e.execute('READ')
        self.assertEqual(self.e.expr('N'),'   '); self.assertIn('Nome :',''.join(self.e.screen[0]))
    def test_read_requires_get(self):
        with self.assertRaises(XBaseError): self.e.execute('READ')
    def test_invalid_characters_ignored(self):
        self.e.execute('D=SPACE(10)'); self.e.execute('@ 0,0 GET D PICTURE "99/99/9999"')
        self.keys(['a']+list('01022024')); self.e.execute('READ'); self.assertEqual(self.e.expr('D'),'01/02/2024')
    def test_ctrl_s_d(self):
        self.e.execute('SET CONFIRM ON'); self.e.execute('N=SPACE(3)'); self.e.execute('@ 0,0 GET N')
        self.keys(['A','B','\x13','C','\x04','D','ENTER']); self.e.execute('READ'); self.assertEqual(self.e.expr('N'),'ACD')
    def test_delete_and_backspace(self):
        mask=PictureMask('     '); editor=FieldEditor(mask,True)
        for k in ['A','B','BACKSPACE','C','LEFT','DELETE']: editor.event(k)
        self.assertEqual(editor.text,'A    ')
    def test_escape_preserves_current(self):
        self.e.execute("N='ANA'"); self.e.execute('@ 0,0 GET N'); self.keys(['B','ESC']); self.e.execute('READ')
        self.assertEqual(self.e.expr('N'),'ANA'); self.assertEqual(self.e.last_key,27)
    def test_field_sqlite(self):
        self.e.execute('CREATE alunos (NOME C 15)'); self.e.execute('APPEND BLANK'); self.e.execute("REPLACE NOME WITH 'Pablo'")
        self.e.execute('@ 0,0 SAY "Nome " GET NOME'); self.keys(list('Laura')+['ENTER']); self.e.execute('READ')
        self.e.execute('USE'); self.e.execute('USE alunos'); self.assertEqual(self.e.expr('TRIM(NOME)'),'Laura')
    def test_line_mask_compact(self):
        self.e.execute('D=SPACE(10)'); self.e.execute('@ 0,0 GET D PICTURE "99/99/9999"')
        self.e.input=lambda _:'01022024'; self.e.execute('READ'); self.assertEqual(self.e.expr('D'),'01/02/2024')
    def test_mask_formatted_input(self):
        mask=PictureMask(' '*10,'99/99/9999')
        self.assertEqual(mask.apply('01/02/2024'),'01/02/2024')
    def test_numeric_mask(self):
        self.e.execute('V=0'); self.e.execute('@ 0,0 GET V PICTURE "999.99"')
        self.keys(list('15032')); self.e.execute('READ'); self.assertEqual(self.e.expr('V'),150.32)
    def test_line_numeric_mask(self):
        self.e.execute('V=0'); self.e.execute('@ 0,0 GET V PICTURE "999.99"'); self.e.input=lambda _:'150.32'
        self.e.execute('READ'); self.assertEqual(self.e.expr('V'),150.32)
    def test_say_using(self):
        self.e.execute('@ 0,0 SAY 40 USING "999.99"'); self.assertIn(' 40.00',''.join(self.e.screen[0]))
    def test_save_like(self):
        self.e.execute("NOME='MSX'"); self.e.execute("NOTA='A'"); self.e.execute('VERSAO=1.1')
        self.e.execute('SAVE TO variav ALL LIKE NO*'); self.e.execute('RELEASE ALL'); self.e.execute('RESTORE FROM variav')
        self.assertEqual(set(self.e.variables),{'NOME','NOTA'})
    def test_save_except_additive(self):
        self.e.execute('NOME="MSX"'); self.e.execute('VERSAO=1.1'); self.e.execute('SAVE TO variav ALL EXCEPT NO*')
        self.e.execute('RELEASE ALL'); self.e.execute('EXTRA=5'); self.e.execute('RESTORE FROM variav ADDITIVE')
        self.assertEqual(set(self.e.variables),{'EXTRA','VERSAO'})
    def test_display_memory_types(self):
        self.e.execute("NOME='MSX'"); self.e.execute('VERSAO=1.1'); self.e.execute('DISPLAY MEMORY')
        text='\n'.join(self.out); self.assertIn('(C)',text); self.assertIn('(N)',text)
    def test_input_accept_no_prompt(self):
        self.e.input=lambda _:'150.32'; self.e.execute('INPUT TO V'); self.assertEqual(self.e.expr('V'),150.32)
        self.e.input=lambda _:'Laura'; self.e.execute('ACCEPT TO N'); self.assertEqual(self.e.expr('N'),'Laura')

    def test_previous_field(self):
        self.e.execute('SET CONFIRM ON'); self.e.execute('A=SPACE(2)'); self.e.execute('B=SPACE(2)')
        self.e.execute('@ 0,0 GET A'); self.e.execute('@ 1,0 GET B')
        self.keys(['A','A','TAB','UP','HOME','B','ENTER','C','C','ENTER'])
        self.e.execute('READ'); self.assertEqual(self.e.expr('A'),'BA'); self.assertEqual(self.e.expr('B'),'CC')
    def test_input_rejects_text(self):
        self.e.input=lambda _:"'Laura'"
        with self.assertRaises(XBaseError): self.e.execute('INPUT TO N')
    @unittest.skipIf(__import__('sys').platform=='win32','Teste PTY POSIX')
    def test_native_terminal_and_restore(self):
        import os,pty,select,subprocess,sys,termios,time
        (self.root/'form.prg').write_text('D=SPACE(10)\n@ 0,0 GET D PICTURE "99/99/9999"\nREAD\n? D\n')
        master,slave=pty.openpty(); before=termios.tcgetattr(slave)
        process=subprocess.Popen([sys.executable,'main.py','--cwd',str(self.root),'--cmd','form.prg'],cwd=Path(__file__).parents[1],stdin=slave,stdout=slave,stderr=slave)
        captured=b''; sent=False; deadline=time.monotonic()+6
        try:
            while time.monotonic()<deadline and process.poll() is None:
                if select.select([master],[],[],.1)[0]: captured+=os.read(master,8192)
                if not sent and b'\x1b[1;2H' in captured: os.write(master,b'01022024'); sent=True
            process.wait(timeout=2)
            while select.select([master],[],[],.05)[0]: captured+=os.read(master,8192)
            self.assertEqual(process.returncode,0,captured.decode(errors='replace'))
            self.assertIn(b'01/02/2024',captured)
            self.assertEqual(termios.tcgetattr(slave),before)
        finally:
            if process.poll() is None: process.kill(); process.wait()
            os.close(master); os.close(slave)

    def test_date_field_format_german(self):
        self.e.execute('SET DATE GERMAN'); self.e.execute('SET CENTURY ON'); self.e.execute("D=CTOD('10.10.2026')")
        self.e.execute('@ 0,0 GET D'); self.keys(list('01022024')); self.e.execute('READ')
        self.assertEqual(self.e.expr('D'),dt.date(2024,2,1))

    def test_numeric_short_integer_part(self):
        self.e.execute('V=7.5'); self.e.execute('@ 0,0 GET V PICTURE "99.99"')
        self.e.input=lambda _:'9.50'; self.e.execute('READ'); self.assertEqual(self.e.expr('V'),9.5)
    def test_numeric_decimal_jump(self):
        self.e.execute('V=0'); self.e.execute('@ 0,0 GET V PICTURE "99.99"')
        self.keys(['9','.','5','0']); self.e.execute('READ'); self.assertEqual(self.e.expr('V'),9.5)
