"""Exemplos do curso MarMSX de dBASE II (interativo e programável) e recursos para portar sistemas."""
import datetime as dt
import json
import sqlite3
import struct
import tempfile
import time
import unittest
from pathlib import Path
from dbase2py import DBaseEngine
from dbase2py.syntax import XBaseError

ALUNOS=[(8361,'Pablo Goncalves',11,'M',5),(4321,'Ana Maria Silva',11,'F',5),(5543,'Waldir Moraes',12,'M',6),(8437,'Alvaro Schwarz',12,'M',5),
    (7193,'Beatriz Saraiva',13,'F',6),(3398,'Mauro Pontes',11,'M',5),(9001,'Pedro Tavares',13,'M',6),(6567,'Suely Albuquerque',12,'F',6),
    (6201,'Pedro Borges',11,'M',5),(7766,'Paula Tavares',13,'F',6)]
NOTAS=[(8361,8.0,7.5,8.0,7.5),(4321,6.0,5.5,8.0,7.0),(5543,7.0,7.7,6.0,7.0),(8437,8.5,9.0,9.5,9.0),(7193,10.0,10.0,9.7,9.9),
    (3398,8.0,7.0,7.5,9.0),(9001,5.5,4.0,7.0,7.0),(6567,7.5,9.0,8.0,7.0),(6201,7.0,8.0,7.0,7.0),(7766,8.0,8.5,7.0,7.0)]


class Course(unittest.TestCase):
    dialect='DBASE2'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.out=[]
        self.e=DBaseEngine(self.root,self.out.append,plain=True,dialect=self.dialect)
        self.e.execute('SET TALK OFF')
        self.e.execute('CREATE alunos (MATRICULA N 4, NOME C 30, IDADE N 2, SEXO C 1, SERIE N 1)')
        for row in ALUNOS: self.e.append(dict(zip(['MATRICULA','NOME','IDADE','SEXO','SERIE'],row)))
        self.e.execute('CREATE notasmat (MATRICULA N 4, BIM1 N 4 1, BIM2 N 4 1, BIM3 N 4 1, BIM4 N 4 1)')
        for row in NOTAS: self.e.append(dict(zip(['MATRICULA','BIM1','BIM2','BIM3','BIM4'],row)))
        self.e.execute('USE alunos'); self.out.clear()
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def run_prg(self,name,code,inputs=()):
        (self.root/(name+'.cmd')).write_text(code,encoding='utf-8')
        answers=iter(inputs); self.e.input=lambda _:next(answers)
        self.out.clear(); self.e.execute('DO '+name)
        return self.out


class InteractiveCourse(Course):
    def test_display_formats(self):
        self.e.execute('DISPLAY ALL')
        self.assertEqual(self.out[0],'00001   8361 Pablo Goncalves                11 M 5')
        self.out.clear(); self.e.execute('display nome,idade for sexo="F" off')
        self.assertEqual(self.out,['Ana Maria Silva                11','Beatriz Saraiva                13','Suely Albuquerque              12','Paula Tavares                  13'])
        self.out.clear(); self.e.execute('display all $(nome, 1, 3)')
        self.assertEqual(self.out[0],'00001   Pab')
    def test_record_pointer(self):
        self.e.execute('go 4'); self.e.execute('skip 2'); self.assertEqual(self.e.expr('#'),6)
        self.e.execute('go 4'); self.e.execute('skip -1'); self.assertEqual(self.e.expr('#'),3)
        self.e.execute('2'); self.assertEqual(self.e.expr('#'),2)
        self.e.execute('go record 5'); self.assertEqual(self.e.expr('RECNO()'),5)
        self.e.execute('? #'); self.assertEqual(self.out[-1].strip(),'5')
    def test_upper_and_exact(self):
        self.assertEqual(len(self.e.execute('display for !(nome)="PEDRO BORGES"')),1)
        self.e.execute('set exact off'); self.assertEqual(len(self.e.execute('display for !(nome) = "PEDRO"')),2)
        self.e.execute('set exact on'); self.assertEqual(len(self.e.execute('display for !(nome) = "PEDRO"')),0)
        self.assertEqual(self.e.expr('$("dBASE II", 2, 4)'),'BASE'); self.assertEqual(self.e.expr('@("II","dBASE II")'),7)
        self.assertEqual(self.e.expr('!("abc")'),'ABC'); self.assertEqual(self.e.expr('RANK("A")'),65)
    def test_count_sum_locate(self):
        self.e.execute('SET TALK ON'); self.e.execute('count for sexo="F" to meninas')
        self.assertEqual(self.out[-1],'Contagem =00004'); self.assertEqual(self.e.expr('meninas'),4)
        self.assertEqual(self.e.execute('sum idade'),119); self.assertEqual(self.e.execute('sum idade for sexo="F"'),49)
        self.e.execute('locate for nome="Pedro Borges"'); self.assertEqual(self.out[-1],'Registro :00009')
        self.e.execute('locate for idade > 10 .AND. serie = 5'); self.assertEqual(self.e.expr('#'),1)
        self.e.execute('continue'); self.assertEqual(self.out[-1],'Registro :00002')
    def test_change_and_replace(self):
        self.e.execute('replace record 3 idade with 14'); self.e.execute('go 3'); self.assertEqual(self.e.expr('idade'),14)
        self.e.execute('replace serie with 7 for serie=6'); self.assertEqual(self.e.execute('count for serie=7'),5)
        self.e.input=lambda _:'Pablo G.'; self.e.execute('change record 1 field nome')
        self.e.execute('go 1'); self.assertEqual(self.e.expr('TRIM(nome)'),'Pablo G.')
    def test_delete_recall_pack(self):
        self.e.execute('delete record 1'); self.e.execute('display all'); self.assertTrue(self.out[0].startswith('00001 * '))
        self.e.execute('recall record 1'); self.e.execute('delete for idade > 12'); self.e.execute('set deleted on')
        self.assertEqual(self.e.execute('count'),7); self.e.execute('pack'); self.assertEqual(self.e.expr('RECCOUNT()'),7)
    def test_index_find_sort_total(self):
        self.e.execute('index on nome to alunos'); self.out.clear(); self.e.execute('display all')
        self.assertIn('Alvaro Schwarz',self.out[0]); self.assertTrue(self.out[0].startswith('00004'))
        self.e.execute('find Pedro'); self.assertEqual(self.e.expr('#'),9)
        self.e.execute('use alunos index alunos'); self.e.execute('find Paula'); self.assertEqual(self.e.expr('#'),10)
        self.e.execute('index on str(idade,2) + nome to aluidx'); self.e.execute('go top'); self.assertEqual(self.e.expr('TRIM(nome)'),'Ana Maria Silva')
        self.e.execute('use alunos'); self.e.execute('sort on nome to aluord'); self.e.execute('use aluord'); self.assertEqual(self.e.expr('TRIM(nome)'),'Alvaro Schwarz')
        self.e.execute('use alunos'); self.e.execute('sort on nome to alurev descending'); self.e.execute('use alurev'); self.assertEqual(self.e.expr('TRIM(nome)'),'Waldir Moraes')
        self.e.execute('use alunos'); self.e.execute('index on sexo to alugen'); self.e.execute('total on sexo to alugrp field idade')
        self.e.execute('use alugrp'); self.out.clear(); self.e.execute('display all sexo,idade')
        self.assertEqual(self.out,['00001   F 49','00002   M 70'])
    def test_join_and_linkage(self):
        self.e.execute('select primary'); self.e.execute('use alunos'); self.e.execute('select secondary'); self.e.execute('use notasmat')
        self.e.execute('join to fulltab for p.matricula=s.matricula'); self.e.execute('use fulltab')
        self.assertEqual(self.e.expr('RECCOUNT()'),10)
        self.out.clear(); self.e.execute('display all nome,(bim1+bim2+bim3+bim4)/4')
        self.assertTrue(self.out[4].startswith('00005   Beatriz Saraiva')); self.assertIn('9.90',self.out[4])
        self.e.execute('clear')  # dBASE II: fecha bancos e variáveis
        self.assertFalse(self.e.areas)
        self.e.execute('set linkage on'); self.e.execute('select primary'); self.e.execute('use alunos'); self.e.execute('select secondary'); self.e.execute('use notasmat')
        self.e.execute('select primary'); self.out.clear(); self.e.execute('display all p.nome,s.bim1')
        self.assertEqual(self.out[1],'00002   Ana Maria Silva                 6.0')
    def test_create_dialog(self):
        answers=iter(['MATRICULA,N,4','BIM1,N,4,1','']); self.e.input=lambda _:next(answers)
        self.e.execute('create notas2'); self.assertEqual([(f.name,f.type,f.length,f.decimals) for f in self.e.fields()],[('MATRICULA','N',4,0),('BIM1','N',4,1)])
    def test_structure_files_and_modify(self):
        self.e.execute('display structure'); self.assertIn('** Total **                       39',self.out[-1])
        self.e.execute('copy structure to notasnov'); self.e.execute('use notasnov')
        self.e.execute('MODIFY STRUCTURE (MATRICULA N 4, NOME C 30, IDADE N 2, SEXO C 1, SERIE N 1, MEDIA N 4 1)')
        self.e.execute('append from alunos'); self.assertEqual(self.e.expr('RECCOUNT()'),10)
        self.e.execute('replace all media with idade/2'); self.e.execute('go 1'); self.assertEqual(self.e.expr('media'),5.5)
        self.e.execute('MODIFY STRUCTURE (MATRICULA N 4, NOME C 40, MEDIA N 5 2)')
        self.assertEqual(self.e.expr('TRIM(nome)'),'Pablo Goncalves'); self.assertEqual(self.e.expr('media'),5.5); self.assertEqual(self.e.expr('LEN(nome)'),40)
        self.out.clear(); self.e.execute('display files'); self.assertTrue(any(l.startswith('alunos ') and ' 10 ' in l for l in self.out))
        self.e.execute('use'); self.e.execute('set safety off'); self.e.execute('delete file notasnov'); self.assertFalse((self.root/'notasnov.sqlite').exists())


class ProgrammableCourse(Course):
    def test_say_using_and_text(self):
        out=self.run_prg('tela','erase\n@ 0,0 say 150.45 using "###.#"\n@ 1,0 say "12-10-2024" using "XX/XX/XXXX"\nTEXT\n   1. Consultar dados\nTEXTEND\nremark *** MENU ***\nnote nao aparece\n')
        self.assertEqual(out,['150.4','12/10/2024','   1. Consultar dados','*** MENU ***'])
    def test_case_with_upper(self):
        code='accept "Estado brasileiro" to estado\ndo case\n   case !(estado) = "RIO DE JANEIRO"\n     ? "Maracana"\n   otherwise\n     ? "Nao conheco"\nendcase\n'
        self.assertEqual(self.run_prg('testcase',code,['Rio de Janeiro'])[-1],'Maracana')
        prompts=[]; self.e.input=lambda p:prompts.append(p) or 'Goias'; self.out.clear(); self.e.execute('do testcase')
        self.assertEqual(prompts,['Estado brasileiro:']); self.assertEqual(self.out[-1],'Nao conheco')
    def test_loop(self):
        code='set talk off\nstore 1 to i\ndo while i <= 5\n  if i = 3\n    store i + 1 to i\n    loop\n  endif\n  ? i\n  store i + 1 to i\nenddo\nset talk on\n'
        self.assertEqual(self.run_prg('laco',code),['         1','         2','         4','         5'])
    def test_best_average(self):
        code='''set talk off
use notasmat
store -1 to maiormedia
go top
do while .not. eof
  store (bim1 + bim2 + bim3 + bim4) / 4 to media
  if media > maiormedia
    store media to maiormedia
    store matricula to mat
  endif
  skip
enddo
use alunos
locate for matricula = mat
? "Nome: " + Nome
? "Media: " + str(maiormedia, 5, 2)
'''
        self.assertEqual(self.run_prg('media',code),['Nome: '+'Beatriz Saraiva'.ljust(30),'Media:  9.90'])
    def test_insert_module_duplicate_check(self):
        code='''set talk off
store " " to opcao
set confirm on
do while !(opcao) <> "N"
  append blank
  @ 4,0 say "Matricula " get matricula
  @ 5,0 say "Nome      " get nome
  read
  store matricula to mat
  store # to regpos
  locate for matricula = mat
  if # <> regpos
    @ 10,0 say "Matricula existente"
    delete record regpos
    pack
    go bottom
    loop
  endif
  accept "Outra entrada? ('N'=nao, 'enter'=sim)" to opcao
enddo
release all
use
'''
        out=self.run_prg('insere',code,['8361','Repetido','1234','Laura','N'])
        self.assertIn('Matricula existente',out)
        self.e.execute('use alunos'); self.assertEqual(self.e.expr('RECCOUNT()'),11)
        self.e.execute('go bottom'); self.assertEqual(self.e.expr('TRIM(nome)'),'Laura')
    def test_search_by_name(self):
        code='''set talk off
set exact off
use alunos
accept "Nome a buscar " to nombusca
locate for !(nome) = !(nombusca)
store 0 to total
do while .not. eof
  ? str(matricula, 4) + " - " + nome
  store total + 1 to total
continue
enddo
? "Total de arquivos: " + str(total, 4)
'''
        out=self.run_prg('proc',code,['paula'])
        self.assertEqual(out,['7766 - '+'Paula Tavares'.ljust(30),'Total de arquivos:    1'])
    def test_plus_commands(self):
        code='''public r1,r2,r3,r4,valeur,resp,novonum,dv,cpf,cgc
store " " to resposta
plus cdate "040224" to resposta
store resposta to r1
store "     " to resposta
plus ddate "040224" "140224" to resposta
store resposta to r2
store "      " to resposta
plus adate "040224" "010" "0" to resposta
store resposta to r3
plus tdate "070292" "001" "0" to resposta
store resposta to r4
store "            " to valeur
plus change "1,000,000.00" to valeur
store "         " to resp
plus format "1234567" "2" to resp
store "    " to novonum
plus lzero "  10" to novonum
plus mod11 "1201611227" to dv
plus cpf "11144477735" to cpf
plus cgc "11222333000181" to cgc
'''
        self.run_prg('plus',code)
        values={k:self.e.expr(k) for k in ('r1','r2','r3','r4','valeur','resp','novonum','dv','cpf','cgc')}
        self.assertEqual(values,{'r1':'1','r2':'00010','r3':'140224','r4':'100292','valeur':'1.000.000,00','resp':'12.345,67','novonum':'0010','dv':'3','cpf':'1','cgc':'1'})
        self.e.execute('plus cdate "310224" to r1'); self.assertEqual(self.e.expr('r1'),'0')
    def test_set_format_printer(self):
        self.run_prg('relat','set format to printer\n@ 2,5 say "Relatorio"\n@ 3,5 say "Linha"\neject\nset format to screen\n')
        self.assertEqual((self.root/'impressora.txt').read_text(encoding='utf-8'),'\n\n     Relatorio\n     Linha\f')


class DialectThree(Course):
    dialect='DBASE3'
    def test_list_heading_and_off(self):
        self.e.execute('LIST NEXT 1')
        self.assertEqual(self.out[0],'Record#  MATRICULA NOME                           IDADE SEXO SERIE')
        self.assertEqual(self.out[1],'      1       8361 Pablo Goncalves                   11 M        5')
        self.out.clear(); self.e.execute('SET HEADING OFF'); self.e.execute('LIST NOME OFF FOR MATRICULA=4321')
        self.assertEqual(self.out,['Ana Maria Silva'])
    def test_clear_is_screen_and_type_is_text(self):
        self.e.execute('X=1'); self.e.execute('CLEAR'); self.assertTrue(self.e.areas); self.assertEqual(self.e.expr('TYPE("X")'),'N')
    def test_relation_list_follows_parent(self):
        self.e.execute('SELECT B'); self.e.execute('USE notasmat'); self.e.execute('INDEX ON MATRICULA TO notamat'); self.e.execute('SELECT A')
        self.e.execute('SET RELATION TO MATRICULA INTO notasmat'); self.out.clear(); self.e.execute('LIST NOME,notasmat->BIM1 OFF FOR SEXO="F"')
        self.assertEqual([l.split()[-1] for l in self.out[1:]],['6.0','10.0','7.5','8.0'])
        self.assertEqual(self.e.execute('COUNT FOR notasmat->BIM1 >= 8'),5)
    def test_talk_and_numbers(self):
        self.e.execute('SET TALK ON'); self.e.execute('STORE 7000 TO SALARIO'); self.assertEqual(self.out[-1],'      7000')
        self.e.execute('SET TALK OFF'); self.e.execute('? SALARIO * 1.1'); self.assertEqual(self.out[-1],'      7700.00')
        self.e.execute('? IDADE, SERIE'); self.assertEqual(self.out[-1],'11 5')
        self.e.execute('? 10/4'); self.assertEqual(self.out[-1].strip(),'2.50')
    def test_scan_for_elseif(self):
        (self.root/'x.prg').write_text('PUBLIC T, N, C\nT=0\nSCAN FOR SEXO="F"\n  T=T+IDADE\nENDSCAN\nN=0\nFOR I=1 TO 10 STEP 3\n  N=N+I\nNEXT\nX=5\nIF X<3\n  C="A"\nELSEIF X<6\n  C="B"\nELSE\n  C="C"\nENDIF\n',encoding='utf-8')
        self.e.execute('DO x'); self.assertEqual((self.e.expr('T'),self.e.expr('N'),self.e.expr('C')),(49,22,'B'))
    def test_copy_sdf_delimited_dbf_roundtrip(self):
        self.e.execute('COPY TO saida SDF FOR SERIE=6'); line=(self.root/'saida.txt').read_text().splitlines()[0]
        self.assertEqual(line,'5543Waldir Moraes                 12M6')
        self.e.execute('COPY STRUCTURE TO vazio'); self.e.execute('USE vazio'); self.e.execute('APPEND FROM saida SDF')
        self.assertEqual(self.e.expr('RECCOUNT()'),5); self.assertEqual(self.e.expr('IDADE'),13)
        self.e.execute('USE alunos'); self.e.execute('COPY TO legado.dbf'); self.e.execute('USE')
        (self.root/'alunos.sqlite').rename(self.root/'antigo.sqlite')
        (self.root/'legado.dbf').rename(self.root/'alunos.dbf')
        self.e.execute('USE alunos'); self.assertEqual(self.e.expr('RECCOUNT()'),10); self.assertEqual(self.e.expr('TRIM(NOME)'),'Pablo Goncalves')
        self.assertTrue((self.root/'alunos.sqlite').exists())


class FormsAndReports(Course):
    dialect='DBASE3'
    def keys(self,values):
        iterator=iter(values); self.e.key_reader=lambda:next(iterator)
    def test_append_form_line_mode(self):
        answers=iter(['1111','Nova Aluna','10','F','4','']); self.e.input=lambda _:next(answers)
        self.e.execute('APPEND'); self.assertEqual(self.e.expr('RECCOUNT()'),11)
        self.e.execute('GO BOTTOM'); self.assertEqual((self.e.expr('MATRICULA'),self.e.expr('TRIM(NOME)')),(1111,'Nova Aluna'))
    def test_append_form_keys_and_carry(self):
        self.e.execute('SET CARRY ON'); self.e.execute('GO BOTTOM')
        self.keys(['CLEARFIELD']+list('2222')+['ENTER','ENTER','ENTER','ENTER','ENTER','ENTER','ENTER'])
        self.e.execute('APPEND'); self.assertEqual(self.e.expr('RECCOUNT()'),11)
        self.assertEqual((self.e.expr('MATRICULA'),self.e.expr('TRIM(NOME)')),(2222,'Paula Tavares'))
    def test_edit_navigation_and_insert(self):
        self.keys(['PGDN','ESC']); self.e.execute('EDIT 1'); self.assertEqual(self.e.expr('RECNO()'),2)
        self.e.execute('GO 2'); self.e.execute('INSERT BEFORE BLANK'); self.assertEqual(self.e.expr('RECNO()'),2)
        self.e.execute('GO 3'); self.assertEqual(self.e.expr('TRIM(NOME)'),'Ana Maria Silva'); self.assertEqual(self.e.expr('RECCOUNT()'),11)
    def test_valid_when_and_delimiters(self):
        self.e.execute('N=0'); self.e.execute('M="X"'); self.e.execute('SET DELIMITERS TO "[]"')
        self.e.execute('@ 1,0 SAY "Nota" GET N PICTURE "99" VALID N<=10 ERROR "Nota de 0 a 10"')
        self.e.execute('@ 2,0 GET M WHEN N>5'); self.assertIn('Nota[ 0]',''.join(self.e.screen[1]))
        answers=iter(['11','7','Z']); self.e.input=lambda _:next(answers); self.e.execute('READ')
        self.assertEqual((self.e.expr('N'),self.e.expr('M')),(7,'Z')); self.assertIn('Erro: Nota de 0 a 10',self.out)
    def test_format_file_and_read(self):
        (self.root/'aluno.fmt').write_text('@ 1,0 SAY "Nome " GET NOME\n@ 2,0 SAY "Idade" GET IDADE PICTURE "99"\n',encoding='utf-8')
        self.e.execute('SET FORMAT TO aluno'); self.e.execute('GO 2')
        answers=iter(['Ana M.','15']); self.e.input=lambda _:next(answers); self.e.execute('READ')
        self.assertEqual((self.e.expr('TRIM(NOME)'),self.e.expr('IDADE')),('Ana M.',15))
        answers=iter(['Novo','9','']); self.e.input=lambda _:next(answers); self.e.execute('APPEND')
        self.assertEqual(self.e.expr('RECCOUNT()'),11); self.e.execute('CLOSE FORMAT')
    def test_menu_box_screen(self):
        self.e.execute('@ 0,0 TO 3,10 DOUBLE'); self.assertEqual(''.join(self.e.screen[0][:11]),'╔'+'═'*9+'╗')
        self.e.execute('SAVE SCREEN TO TELA'); self.e.execute('CLEAR'); self.e.execute('RESTORE SCREEN FROM TELA')
        self.assertEqual(self.e.screen[3][10],'╝')
        self.e.execute('@ 5,2 PROMPT "Incluir"'); self.e.execute('@ 6,2 PROMPT "Sair"')
        self.keys(['DOWN','ENTER']); self.e.execute('MENU TO OP'); self.assertEqual(self.e.expr('OP'),2)
        self.e.execute('@ 5,2 PROMPT "Incluir"'); self.e.execute('@ 6,2 PROMPT "Sair"')
        self.e.key_reader=None; self.e.input=lambda _:'s'; self.e.execute('MENU TO OP'); self.assertEqual(self.e.expr('OP'),2)
    def test_picture_functions(self):
        for exp,want in [('TRANSFORM(1234.5,"@E 999,999.99")','  1.234,50'),('TRANSFORM("12345678901","@R 999.999.999-99")','123.456.789-01'),
            ('TRANSFORM(-5,"@( 999")','(5)'),('TRANSFORM(0,"@Z 999")','   '),('TRANSFORM(7,"@B 999")','7  ')]:
            self.assertEqual(self.e.expr(exp),want,exp)
    def test_report_dialog_and_form(self):
        answers=iter(['M=0','Y','Relacao de Notas','N','Y','','4,matricula','Mat.','N','30,nome','Aluno','2,idade','Id','Y',''])
        self.e.input=lambda _:next(answers); self.e.execute('CREATE REPORT notas')
        definition=json.loads((self.root/'notas.frm').read_text(encoding='utf-8'))
        self.assertEqual([c['expr'] for c in definition['columns']],['matricula','nome','idade'])
        self.out.clear(); self.e.execute('REPORT FORM notas FOR SEXO="F" PLAIN')
        text='\n'.join(self.out)
        self.assertIn('Relacao de Notas',text); self.assertIn('4321 Ana Maria Silva                11',text); self.assertIn('*** Total ***',text); self.assertIn('49',self.out[-1])
        self.e.execute('REPORT FORM notas TO FILE saida'); self.assertIn('Página No.',(self.root/'saida.txt').read_text(encoding='utf-8'))
    def test_binary_frm(self):
        pool=b''; lengths=[0]*55; offsets=[0]*55
        def add(i,text):
            nonlocal pool
            offsets[i]=len(pool); lengths[i]=len(text)+1; pool+=text.encode()+b'\0'
        add(0,'Alunos;por idade'); add(1,'NOME'); add(2,'Nome'); add(3,'IDADE'); add(4,'Idade')
        data=bytearray(1990); data[0:2]=b'\x02\x00'; struct.pack_into('<H',data,2,len(pool))
        struct.pack_into('<55H',data,4,*lengths); struct.pack_into('<55H',data,114,*offsets); data[224:224+len(pool)]=pool
        struct.pack_into('<HxxxcHHH',data,1664,30,b'N',0,1,2); struct.pack_into('<HxxxcHHH',data,1676,5,b'Y',0,3,4)
        struct.pack_into('<5h5H',data,1964,0,-1,-1,-1,-1,80,58,0,0,2); data[1984:1988]=b'NNN\x04'; data[1988:1990]=b'\x02\x00'
        (self.root/'idades.frm').write_bytes(bytes(data))
        self.out.clear(); self.e.execute('REPORT FORM idades')
        self.assertIn('Alunos',self.out[0]); self.assertIn('por idade',self.out[1]); self.assertIn('119',self.out[-1])


class LegacyFiles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.out=[]
        self.e=DBaseEngine(self.root,self.out.append,plain=True)
    def tearDown(self): self.e.close(); self.tmp.cleanup()
    def test_dbase2_dbf_import(self):
        fields=[(b'MATRICULA','N',4,0),(b'NOME','C',10,0),(b'NOTA:1','N',4,1),(b'ATIVO','L',1,0)]
        header=bytearray(521); header[0]=2; struct.pack_into('<H',header,1,2); struct.pack_into('<H',header,6,1+4+10+4+1)
        for i,(name,kind,length,dec) in enumerate(fields):
            o=8+16*i; header[o:o+len(name)]=name; header[o+11]=ord(kind); header[o+12]=length; header[o+15]=dec
        header[8+16*len(fields)]=0x0D
        body=b' 8361Pablo      8.5T'+b'*4321Ana Maria  6.0F'
        (self.root/'ALUNOS.DBF').write_bytes(bytes(header)+body+b'\x1a')
        self.e.execute('USE alunos'); self.assertEqual(self.e.expr('RECCOUNT()'),2)
        self.assertEqual([f.name for f in self.e.fields()],['MATRICULA','NOME','NOTA_1','ATIVO'])
        self.assertEqual((self.e.expr('MATRICULA'),self.e.expr('NOTA_1'),self.e.expr('ATIVO')),(8361,8.5,True))
        self.e.execute('GO 2'); self.assertTrue(self.e.expr('DELETED()'))
    def test_dbase3_dbf_memo_ndx_mem(self):
        fields=[(b'CODIGO','N',5,0),(b'NOME','C',8,0),(b'NASC','D',8,0),(b'OBS','M',10,0)]
        size=1+5+8+8+10
        header=struct.pack('<BBBBIHH20x',0x83,126,10,10,1,32+32*len(fields)+1,size)
        for name,kind,length,dec in fields: header+=name.ljust(11,b'\0')+kind.encode()+b'\0'*4+bytes([length,dec])+b'\0'*14
        record=b'    7JOSE    19800131'+b'         1'
        (self.root/'clientes.dbf').write_bytes(header+b'\r'+b' '+record+b'\x1a')
        (self.root/'clientes.dbt').write_bytes(b'\x02'+b'\0'*511+'Cliente antigo\nlinha 2'.encode('cp850')+b'\x1a\x1a')
        ndx=bytearray(512); ndx[24:24+4]=b'NOME'; (self.root/'clinome.ndx').write_bytes(bytes(ndx))
        self.e.execute('USE clientes INDEX clinome'); self.assertEqual(self.e.expr('NASC'),dt.date(1980,1,31))
        self.assertEqual(self.e.expr('OBS'),'Cliente antigo\nlinha 2'); self.assertTrue(self.e.execute('SEEK "JO"'))
        mem=b'TOTAL'.ljust(11,b'\0')+bytes([ord('N')|0x80])+b'\0'*4+bytes([10,2])+b'\0'*14+struct.pack('<d',12.5)
        mem+=b'NOMEV'.ljust(11,b'\0')+bytes([ord('C')|0x80])+b'\0'*4+bytes([4,0])+b'\0'*14+b'ABC\0'+b'\x1a'
        (self.root/'config.mem').write_bytes(mem); self.e.execute('RESTORE FROM config')
        self.assertEqual((self.e.expr('TOTAL'),self.e.expr('NOMEV')),(12.5,'ABC'))


class Performance(unittest.TestCase):
    def test_loop_over_5000_records(self):
        with tempfile.TemporaryDirectory() as folder:
            e=DBaseEngine(folder,lambda _:None,plain=True,max_steps=10**7)
            try:
                e.execute('SET TALK OFF'); e.execute('CREATE venda (NOTA C 6, QTD N 4, PRECO N 6 2, TOTAL N 10 2)')
                start=time.monotonic()
                (Path(folder)/'carga.prg').write_text('I=1\nDO WHILE I<=5000\nAPPEND BLANK\nREPLACE NOTA WITH STR(536365+I%40,6), QTD WITH I%7+1, PRECO WITH 2.55\nI=I+1\nENDDO\n',encoding='utf-8')
                e.execute('DO carga'); e.execute('INDEX ON NOTA TO vnota')
                (Path(folder)/'soma.prg').write_text('PUBLIC S\nS=0\nGO TOP\nDO WHILE .NOT. EOF()\nREPLACE TOTAL WITH QTD*PRECO\nS=S+TOTAL\nSKIP\nENDDO\n',encoding='utf-8')
                e.execute('DO soma'); e.execute('SEEK "536370"')
                self.assertTrue(e.expr('FOUND()')); self.assertEqual(e.expr('RECCOUNT()'),5000)
                self.assertAlmostEqual(e.expr('S'),e.execute('SUM QTD*PRECO'),places=2)
                self.assertLess(time.monotonic()-start,30)
            finally: e.close()


if __name__=='__main__': unittest.main()
