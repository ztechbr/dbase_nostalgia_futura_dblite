"""Cenários semânticos independentes baseados nos comandos do handbook."""
import datetime as dt
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from dbase2py import DBaseEngine
from dbase2py.syntax import XBaseError


class PlusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.output=[]; self.e=DBaseEngine(self.root,self.output.append,plain=True)
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def program(self,name,code):
        (self.root/(name+'.prg')).write_text(code,encoding='utf-8')
    def table(self):
        self.e.execute('CREATE pessoas (NOME C 12, IDADE N 3, VALOR N 9 2, ATIVO L 1, DATA D 10)')
        for name,age in [('ANA',20),('BOB',40),('CARLA',50)]:
            self.e.execute('APPEND BLANK'); self.e.execute(f"REPLACE NOME WITH '{name}', IDADE WITH {age}, VALOR WITH 10.50, ATIVO WITH .T.")
        self.e.execute('GO TOP')
    def test_pratt_precedence(self):
        self.assertEqual(self.e.expr('2 + 3 * 4 ^ 2'),50)
        self.assertEqual(self.e.expr('-2^2'),-4)
        self.assertTrue(self.e.expr('.NOT. 1 = 2 .AND. 2 < 3'))
        self.assertTrue(self.e.expr("'A' $ 'ABC'"))
    def test_strings(self):
        self.assertEqual(self.e.expr("'O''BRIEN'"),"O'BRIEN")
        self.assertEqual(self.e.expr('[a "b" c]'),'a "b" c')
        self.assertEqual(self.e.expr("'A  ' - 'B'"),'AB  ')
        self.assertEqual(self.e.expr("'A  ' + 'B'"),'A  B')
    def test_exact(self):
        self.assertTrue(self.e.expr("'JOHNSON ' = 'JOHN'"))
        self.e.execute('SET EXACT ON')
        self.assertFalse(self.e.expr("'JOHNSON ' = 'JOHN'"))
        self.assertTrue(self.e.expr("'JOHNSON ' = 'JOHNSON'"))
        self.assertFalse(self.e.expr("'JOHNSON ' == 'JOHNSON'"))
    def test_shortcircuit(self):
        self.assertFalse(self.e.expr('.F. .AND. 1 / 0 > 1'))
        self.assertTrue(self.e.expr('.T. .OR. UNKNOWN = 1'))
    def test_type(self):
        self.assertEqual(self.e.expr("TYPE('MISSING')"),'U')
        self.e.execute('X = 12'); self.assertEqual(self.e.expr("TYPE('X')"),'N')
    def test_strings_functions(self):
        for exp,want in [("SUBSTR('ABCDE',2,2)",'BC'),("RIGHT('ABCDE',2)",'DE'),("AT('BC','ABCDE')",2),("TRIM(' A  ')",' A'),("STR(12.5,7,2)",'  12.50'),("STR(1234,3)",'***'),("VAL('  -12.5USD')",-12.5),("ROUND(-1.25,1)",-1.3)]:
            self.assertEqual(self.e.expr(exp),want,exp)
    def test_dates(self):
        self.e.execute('SET DATE BRITISH'); self.e.execute('SET CENTURY ON')
        self.e.execute("D = CTOD('31/12/2025')")
        self.assertEqual(self.e.expr('D + 1'),dt.date(2026,1,1))
        self.assertEqual(self.e.expr('DTOC(D)'),'31/12/2025')
        self.assertEqual(self.e.expr('DTOS(D)'),'20251231')
        self.assertEqual(self.e.expr("D - CTOD('30/12/2025')"),1)
    def test_date_fields_roundtrip(self):
        self.table(); self.e.execute("REPLACE DATA WITH CTOD('10/10/26')")
        self.e.execute('USE'); self.e.execute('USE pessoas')
        self.assertEqual(self.e.current()['DATA'],dt.date(1926,10,10))
        self.assertEqual(self.e.expr("TYPE('DATA')"),'D')
    def test_alias_collision(self):
        self.table(); self.e.execute('SELECT B'); self.e.execute('CREATE outras (NOME C 12)')
        self.e.execute('APPEND BLANK'); self.e.execute("REPLACE NOME WITH 'OUTRO'")
        self.assertEqual(self.e.expr('TRIM(pessoas->NOME)'),'ANA')
        self.e.execute("NOME = 'MEMORIA'")
        self.assertEqual(self.e.expr('TRIM(NOME)'),'OUTRO')
        self.assertEqual(self.e.expr('M->NOME'),'MEMORIA')
        self.assertEqual(self.e.expr('SELECT("pessoas")'),1)
    def test_eof_bof(self):
        self.table(); self.e.execute('SKIP -1'); self.assertTrue(self.e.expr('BOF()'))
        self.assertEqual(self.e.expr('RECNO()'),1)
        self.e.execute('SKIP'); self.assertFalse(self.e.expr('BOF()'))
        self.e.execute('GO BOTTOM'); self.e.execute('SKIP')
        self.assertTrue(self.e.expr('EOF()')); self.assertEqual(self.e.expr('IDADE'),0)
        self.assertEqual(self.e.expr('NOME'),' '*12)
    def test_empty_database(self):
        self.e.execute('CREATE vazio (N C 5)')
        self.assertTrue(self.e.expr('EOF()')); self.assertTrue(self.e.expr('BOF()'))
        self.assertEqual(self.e.expr('RECCOUNT()'),0)
    def test_abbreviations_comments(self):
        self.table(); self.e.execute("REPL NOME WITH '&& FOR ALL' && comentário")
        self.e.execute('DISP'); self.assertIn('&& FOR ALL','\n'.join(self.output))
    def test_for_implicit_all(self):
        self.table(); self.e.execute('REPLACE IDADE WITH IDADE + 1 FOR IDADE >= 40')
        self.assertEqual([r['IDADE'] for r in self.e.rows()],[20,41,51])
    def test_while_scope(self):
        self.table(); self.e.execute('REPLACE ALL VALOR WITH 99 WHILE IDADE < 50')
        self.assertEqual([r['VALOR'] for r in self.e.rows()],[99,99,10.5])
    def test_scope_next_sorted(self):
        self.table(); self.e.execute('INDEX ON -IDADE TO idade')
        rows=self.e.execute('LIST NEXT 2 NOME')
        self.assertEqual([r['IDADE'] for r in rows],[50,40])
    def test_scope_record(self):
        self.table(); self.e.execute('REPLACE RECORD 2 VALOR WITH 22')
        self.assertEqual([r['VALOR'] for r in self.e.rows()],[10.5,22,10.5])
    def test_sums(self):
        self.table(); self.e.execute('SET TALK OFF')
        self.e.execute('SUM ALL IDADE, VALOR TO S1,S2')
        self.assertEqual(self.e.expr('S1'),110); self.assertEqual(self.e.expr('S2'),31.5)
        self.e.execute('COUNT FOR IDADE >= 40 TO N'); self.assertEqual(self.e.expr('N'),2)
        self.assertEqual(self.e.execute('AVERAGE IDADE'),110/3)
    def test_seek_prefix(self):
        self.table(); self.e.execute('INDEX ON NOME TO nomes.ndx'); self.e.execute("SEEK 'CA'")
        self.assertTrue(self.e.expr('FOUND()')); self.assertEqual(self.e.expr('RECNO()'),3)
        self.e.execute("SEEK 'XX'"); self.assertFalse(self.e.expr('FOUND()')); self.assertTrue(self.e.expr('EOF()'))
    def test_use_indexes(self):
        self.table(); self.e.execute('INDEX ON NOME TO nomes'); self.e.execute('INDEX ON IDADE TO idades')
        self.e.execute('USE'); self.e.execute('USE pessoas.dbf INDEX nomes,idades ALIAS clientes')
        self.assertEqual(self.e.expr('ALIAS()'),'CLIENTES')
        self.e.execute('SET ORDER TO 2'); self.e.execute('SEEK 40'); self.assertTrue(self.e.expr('FOUND()'))
    def test_unique_persistent(self):
        self.table(); self.e.execute('APPEND BLANK'); self.e.execute("REPLACE NOME WITH 'ANA'")
        self.e.execute('INDEX ON NOME TO nomes UNIQUE'); self.assertEqual(len(self.e.rows()),3)
        self.e.execute('USE'); self.e.execute('USE pessoas INDEX nomes'); self.assertEqual(len(self.e.rows()),3)
        self.assertEqual(self.e.expr('RECCOUNT()'),4)
    def test_relation(self):
        self.table(); self.e.execute('SELECT B'); self.e.execute('CREATE detalhes (IDADE N 3, NOTA C 10)')
        self.e.execute('APPEND BLANK'); self.e.execute("REPLACE IDADE WITH 40, NOTA WITH 'MATCH'")
        self.e.execute('INDEX ON IDADE TO idades'); self.e.execute('SELECT A')
        self.e.execute('SET RELATION TO IDADE INTO detalhes'); self.e.execute('GO 2')
        self.assertEqual(self.e.expr('TRIM(detalhes->NOTA)'),'MATCH')
        self.e.execute('GO 1'); self.assertTrue(self.e.expr('EOF("detalhes")'))
    def test_private_public(self):
        self.e.execute("X = 'original'")
        self.program('sub',"PRIVATE X\nX = 'interno'\nPUBLIC RESULT\nRESULT = X\nRETURN\n")
        self.e.run_file('sub')
        self.assertEqual(self.e.expr('X'),'original'); self.assertEqual(self.e.expr('RESULT'),'interno')
    def test_by_reference(self):
        self.program('sub','PARAMETERS P\nP = P + 5\nRETURN\n')
        self.e.execute('X = 10'); self.e.execute('DO sub WITH X'); self.assertEqual(self.e.expr('X'),15)
        self.e.execute('DO sub WITH (X)'); self.assertEqual(self.e.expr('X'),15)
    def test_field_by_value(self):
        self.table(); self.program('sub','PARAMETERS P\nP = 999\nRETURN\n')
        self.e.execute('DO sub WITH IDADE'); self.assertEqual(self.e.expr('IDADE'),20)
    def test_procedure_file(self):
        self.program('lib','PROCEDURE ADDVAL\nPARAMETERS P\nP=P+1\nRETURN\n')
        self.e.execute('SET PROCEDURE TO lib'); self.e.execute('X=1'); self.e.execute('DO addval WITH X')
        self.assertEqual(self.e.expr('X'),2)
    def test_function_extension(self):
        self.program('lib','FUNCTION DOBRO\nPARAMETERS P\nRETURN P*2\n')
        self.e.execute('SET PROCEDURE TO lib'); self.assertEqual(self.e.expr('DOBRO(3)'),6)
    def test_case_loop_exit(self):
        self.program('test','PUBLIC RESULT\nI=0\nRESULT=0\nDO WHILE .T.\nI=I+1\nDO CASE\nCASE I=1\nLOOP\nCASE I=4\nEXIT\nOTHERWISE\nRESULT=RESULT+I\nENDCASE\nENDDO\nRETURN\nRESULT=999\n')
        self.e.run_file('test'); self.assertEqual(self.e.expr('RESULT'),5)
    def test_text_and_continuation(self):
        self.program('test',"PUBLIC RESULT\nRESULT = 1 + ; && continuar\n  2\nTEXT\n* literal\nIF sem comando\n\nENDTEXT\n")
        self.e.run_file('test'); self.assertEqual(self.e.expr('RESULT'),3)
        self.assertIn('* literal\nIF sem comando\n','\n'.join(self.output))
    def test_cp850(self):
        (self.root/'dos.prg').write_bytes("? 'Ação'\r\n".encode('cp850'))
        self.e.run_file('dos'); self.assertIn('Ação',self.output)
    def test_macros(self):
        self.table(); self.e.execute("MCMD='REPLACE IDADE WITH 33'"); self.e.execute('&MCMD')
        self.assertEqual(self.e.expr('IDADE'),33)
        self.e.execute("MFIELD='NOME'"); self.assertEqual(self.e.expr('TRIM(&MFIELD)'),'ANA')
        self.assertEqual(self.e.expr("'&MFIELD'"),'&MFIELD')
    def test_loop_macro_snapshot(self):
        self.program('test',"PUBLIC RESULT\nRESULT=0\nCOND='RESULT < 2'\nDO WHILE &COND\nRESULT=RESULT+1\nCOND='.F.'\nENDDO\n")
        self.e.run_file('test'); self.assertEqual(self.e.expr('RESULT'),2)
    def test_read(self):
        self.e.execute("NAME=SPACE(8)"); self.e.execute('VALUE=0')
        self.e.execute('@ 1,2 SAY "Name" GET NAME PICTURE "!"')
        self.e.execute('@ 2,2 GET VALUE RANGE 1,5')
        answers=iter(['ana','9','3']); self.e.input=lambda _:next(answers)
        self.e.execute('READ'); self.assertEqual(self.e.expr('NAME'),'ANA     '); self.assertEqual(self.e.expr('VALUE'),3)
    def test_read_field(self):
        self.table(); self.e.execute('@ 1,1 GET NOME'); self.e.input=lambda _:'DAN'
        self.e.execute('READ'); self.assertEqual(self.e.expr('TRIM(NOME)'),'DAN')
    def test_output_file(self):
        self.e.execute('SET ALTERNATE TO report'); self.e.execute('SET ALTERNATE ON'); self.e.execute('SET CONSOLE OFF')
        self.e.execute("? 'HELLO'"); self.e.execute("?? 'WORLD'"); self.e.execute('SET ALTERNATE TO')
        self.assertEqual((self.root/'report.txt').read_text(),'HELLO\nWORLD')
    def test_copy_structure_and_from(self):
        self.table(); self.e.execute('COPY STRUCTURE TO vazio FIELDS NOME,IDADE')
        self.assertEqual(self.e.expr('ALIAS()'),'PESSOAS')
        self.e.execute('COPY TO defin STRUCTURE EXTENDED'); self.e.execute('CREATE nova FROM defin')
        self.assertEqual([f.name for f in self.e.fields()],['NOME','IDADE','VALOR','ATIVO','DATA'])
    def test_copy_append_sqlite(self):
        self.table(); self.e.execute('COPY TO selecionados FOR IDADE >= 40')
        self.e.execute('APPEND FROM selecionados'); self.assertEqual(self.e.expr('RECCOUNT()'),5)
    def test_sort_total(self):
        self.table(); self.e.execute('SORT TO ordenado ON IDADE/D'); self.e.execute('USE ordenado')
        self.assertEqual(self.e.expr('IDADE'),50)
        self.e.execute('TOTAL ON ATIVO TO agrupado FIELDS VALOR'); self.e.execute('USE agrupado')
        self.assertEqual(self.e.expr('RECCOUNT()'),1); self.assertEqual(self.e.expr('VALOR'),31.5)
    def test_csv_dates(self):
        self.table(); self.e.execute("REPLACE DATA WITH DATE()"); self.e.execute('COPY TO export DELIMITED')
        self.e.execute('APPEND FROM export DELIMITED'); self.assertEqual(self.e.expr('RECCOUNT()'),6)
        self.e.execute('GO 4'); self.assertEqual(self.e.expr('DATA'),dt.date.today())
        self.e.execute('COPY TO export TYPE CSV'); self.e.execute('APPEND FROM export.csv'); self.assertEqual(self.e.expr('RECCOUNT()'),12)
        self.e.execute('GO 7'); self.assertEqual(self.e.expr('DATA'),dt.date.today())
    def test_memory_date(self):
        self.e.execute('D=DATE()'); self.e.execute('SAVE TO mem'); self.e.execute('RELEASE ALL'); self.e.execute('RESTORE FROM mem')
        self.assertEqual(self.e.expr('D'),dt.date.today())
    def test_source_diagnostic(self):
        self.program('bad',"X=1\n? MISSING\n")
        with self.assertRaisesRegex(XBaseError,r'bad.prg:2:'): self.e.run_file('bad')
    def test_compile_errors(self):
        self.program('bad','IF .T.\n? 1\nENDDO\n')
        with self.assertRaises(XBaseError): self.e.run_file('bad')
    def test_global_step_limit(self):
        self.e.max_steps=30
        self.program('infinite','DO WHILE .T.\nENDDO\n')
        with self.assertRaisesRegex(XBaseError,'Limite global'): self.e.run_file('infinite')
    def test_cancel_nested(self):
        self.program('main','PUBLIC X\nX=1\nDO sub\nX=3\n'); self.program('sub','CANCEL\n')
        self.e.run_file('main'); self.assertEqual(self.e.expr('X'),1)
    def test_private_released_after_error(self):
        self.program('bad','PRIVATE X\nX=1\n? MISSING\n')
        self.e.execute('X=99')
        with self.assertRaises(XBaseError): self.e.run_file('bad')
        self.assertEqual(self.e.expr('X'),99); self.assertEqual(len(self.e.calls),0)
    def test_static_check_no_side_effects(self):
        self.program('check','CREATE test (N C 5)\nRUN DIR\n')
        report=self.e.check('check')
        self.assertEqual(report['status'],'unsupported'); self.assertFalse((self.root/'test.sqlite').exists())
    def test_static_function_check(self):
        self.program('check','? UNKNOWNFUNC(1)\n')
        self.assertEqual(self.e.check('check')['status'],'unsupported')
    def test_dangerous_expression_rejected(self):
        for exp in ["__import__('os')",'M.__class__','[x for x in y]','(1).__class__']:
            with self.subTest(exp=exp):
                # A string entre colchetes é literal xBase, sem execução Python.
                if exp.startswith('['): self.assertEqual(self.e.expr(exp),'x for x in y')
                else:
                    with self.assertRaises(XBaseError): self.e.expr(exp)
    def test_sql_injection_rejected(self):
        with self.assertRaises(ValueError): self.e.execute('CREATE bad (A;DROP C 5)')
        self.assertFalse((self.root/'bad.sqlite').exists())
    def test_case_insensitive_paths(self):
        self.table(); self.e.execute('USE'); self.e.execute('USE PESSOAS.DBF')
        self.assertEqual(self.e.expr('RECCOUNT()'),3)
    def test_zap_safety_off(self):
        self.table(); self.e.execute('SET SAFETY OFF'); self.e.execute('ZAP'); self.assertTrue(self.e.expr('EOF()'))

if __name__=='__main__': unittest.main()

class AdditionalTests(unittest.TestCase):
    setUp = PlusTests.setUp
    tearDown = PlusTests.tearDown
    table = PlusTests.table
    program = PlusTests.program
    def test_replace_truncates(self):
        self.e.execute('CREATE curto (NOME C 3)'); self.e.execute('APPEND BLANK')
        self.e.execute("REPLACE NOME WITH 'ABCDE'"); self.assertEqual(self.e.expr('NOME'),'ABC')
    def test_replace_type_validation(self):
        self.table()
        for command in ["REPLACE IDADE WITH '33'",'REPLACE NOME WITH 1',"REPLACE DATA WITH '2026-01-01'",'REPLACE ATIVO WITH 1']:
            with self.subTest(command=command):
                with self.assertRaises(XBaseError): self.e.execute(command)
    def test_replace_alias(self):
        self.table(); self.e.execute('SELECT B'); self.e.execute('CREATE other (VALOR N 9 2)'); self.e.execute('APPEND BLANK')
        self.e.execute('REPLACE pessoas->VALOR WITH 42.25'); self.assertEqual(self.e.expr('pessoas->VALOR'),42.25)
    def test_expression_recno_in_scope(self):
        self.table(); self.assertEqual(self.e.execute('COUNT FOR RECNO() >= 2'),2)
    def test_dates_two_digits_historical(self):
        self.assertEqual(self.e.expr("CTOD('01/02/26')"),dt.date(1926,1,2))
    def test_no_db_eof_false(self):
        self.assertFalse(self.e.expr('EOF()')); self.assertFalse(self.e.expr('BOF()'))

    def test_join(self):
        self.table(); self.e.execute('SELECT B'); self.e.execute('CREATE details (IDADE N 3, NOTA C 8)')
        self.e.execute('APPEND BLANK'); self.e.execute("REPLACE IDADE WITH 40, NOTA WITH 'MATCH'")
        self.e.execute('SELECT A'); self.e.execute('JOIN WITH details TO merged FOR IDADE = details->IDADE FIELDS NOME, details->NOTA')
        self.e.execute('USE merged'); self.assertEqual(self.e.expr('RECCOUNT()'),1)
        self.assertEqual(self.e.expr('TRIM(NOTA)'),'MATCH')
    def test_update(self):
        self.table(); self.e.execute('INDEX ON IDADE TO idades'); self.e.execute('SELECT B')
        self.e.execute('CREATE trans (IDADE N 3, VALOR N 9 2)'); self.e.execute('APPEND BLANK')
        self.e.execute('REPLACE IDADE WITH 40, VALOR WITH 5'); self.e.execute('SELECT A')
        self.e.execute('UPDATE ON IDADE FROM trans REPLACE VALOR WITH VALOR + trans->VALOR RANDOM')
        self.e.execute('GO 2'); self.assertEqual(self.e.expr('VALOR'),15.5)

    def test_on_error_resume(self):
        self.program('main','PUBLIC RESULT\nRESULT=0\nON ERROR DO handler\n? MISSING\nRESULT=RESULT+1\nON ERROR\nPROCEDURE handler\nRESULT=RESULT+10\nRETURN\n')
        self.e.run_file('main'); self.assertEqual(self.e.expr('RESULT'),11)
        self.assertIn('MISSING',self.e.expr('MESSAGE()'))
    def test_retry(self):
        self.program('main','PUBLIC RESULT\nON ERROR DO handler\nRESULT=MISSING\nON ERROR\nPROCEDURE handler\nPUBLIC MISSING\nMISSING=99\nRETRY\n')
        self.e.run_file('main'); self.assertEqual(self.e.expr('RESULT'),99)
    def test_return_master(self):
        self.program('main','PUBLIC RESULT\nRESULT=1\nDO sub\nRESULT=RESULT+1\n')
        self.program('sub','DO deep\nRESULT=99\n')
        self.program('deep','RETURN TO MASTER\n')
        self.e.run_file('main'); self.assertEqual(self.e.expr('RESULT'),2)

    def test_blank_text_comparison(self):
        self.assertFalse(self.e.expr("'ANA' = ' '"))
        self.assertTrue(self.e.expr("SPACE(5) = ' '"))
    def test_blank_seek(self):
        self.table(); self.e.execute('INDEX ON NOME TO names'); self.e.execute("SEEK ' '")
        self.assertFalse(self.e.expr('FOUND()'))
    def test_order_name(self):
        self.table(); self.e.execute('INDEX ON NOME TO n1'); self.e.execute('INDEX ON NOME TO n2')
        self.e.execute('SET INDEX TO n1,n2'); self.e.execute('SET ORDER TO 2')
        self.assertEqual(self.e.expr('ORDER()'),'N2')
    def test_exclusive_sqlite_lock(self):
        self.table(); self.e.execute('USE pessoas EXCLUSIVE')
        db=sqlite3.connect(self.root/'pessoas.sqlite',timeout=.01)
        try:
            with self.assertRaises(sqlite3.OperationalError): db.execute('SELECT * FROM records').fetchall()
        finally: db.close()

    def test_say_and_get_separate_pictures(self):
        self.e.execute('N=0')
        self.e.execute('@ 1,1 SAY 10 PICTURE "999.99" GET N PICTURE "999"')
        self.e.input=lambda _:'12'; self.e.execute('READ'); self.assertEqual(self.e.expr('N'),12)
        self.assertIn(' 10.00','\n'.join(self.output))
