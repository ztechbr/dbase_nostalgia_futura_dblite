# Alterações

## 2.2

- Revisão completa contra o curso MarMSX de dBASE II (interativo e programável); ver REVISAO.md.
- Sintaxe do dBASE II: `!()`, `$()`, `@()`, `#`, `*`, RANK, EOF/BOF/DATE sem parênteses, P./S., SET LINKAGE, número no prompt, GO RECORD, REMARK, TEXTEND, ERASE, INSERT, SET CARRY/COLON, JOIN sem WITH, SORT ASCENDING/DESCENDING, TOTAL FIELD/FOR, CHANGE FIELD, DELETE FILE sem extensão, unidade `B:`.
- Dialeto DBASE2 (`--dialect dbase2`/`SET DIALECT`): CLEAR, ACCEPT/INPUT com dois-pontos, TYPE por valor, LIST no formato `00001`.
- Comandos PLUS do dBASE II PLUS para MSX.
- Formulários: APPEND/EDIT/CHANGE/INSERT em tela, SET FORMAT TO .fmt, VALID/WHEN/ERROR/MESSAGE, READ SAVE, delimitadores, modo inserção, teclas Ctrl do dBASE, @ TO DOUBLE, @ PROMPT/MENU TO, SAVE/RESTORE SCREEN, PICTURE com @R @E @B @Z @( @C @X e literais posicionais.
- Impressora emulada: SET PRINT/PRINTER/DEVICE, ???, EJECT, SET FORMAT TO PRINTER, LIST/REPORT TO PRINT.
- REPORT FORM (FRM binário do dBASE III/Clipper ou JSON) e CREATE/MODIFY REPORT com o diálogo do dBASE II.
- Dados legados: DBF dBASE II/III/IV/FoxPro com memo importado no primeiro USE, IMPORT FROM, --import-dbf, NDX/NTX, MEM binário; COPY TO DBF/SDF/DELIMITED/CSV e APPEND FROM correspondentes.
- MODIFY STRUCTURE preservando dados e MODIFY COMMAND.
- Desempenho: cache de navegação, SEEK binário, escopos preguiçosos, SQLite em WAL; laços de 5.000 registros em segundos.
- LIST/COUNT/REPLACE/REPORT reposicionam relações a cada registro (antes o filho ficava parado).
- LIST/DISPLAY e `?` no formato do dBASE; SET TALK ecoa STORE e contagens; SET HEADING, SET FIELDS, LIST TO PRINT/FILE.
- SCAN/ENDSCAN, FOR/NEXT, ELSEIF, PARAMETERS opcionais e cerca de 30 funções de dBASE IV/Clipper.
- SETs de inicialização (BELL, ESCAPE, STATUS...) aceitos; SET PATH/DEFAULT; USE SHARED e RLOCK/FLOCK.
- 36 testes novos em tests/test_msx_course.py com os exemplos do curso.
- LABEL FORM/CREATE LABEL/MODIFY LABEL com LBL binário do dBASE III PLUS.
- Arrays (DECLARE, DIMENSION, LOCAL, literais, funções A*, COPY TO ARRAY, APPEND FROM ARRAY, SCATTER/GATHER).
- BROWSE em grade editável.
- Monitores de fósforo verde/âmbar/branco (`--monitor`, `SET MONITOR`) e SET COLOR com cores reais.
- Saída redirecionada em UTF-8 e ANSI ativado no console do Windows.

## 2.1

- GET exibe valor entre dois-pontos na posição da tela antes de READ.
- Editor por tecla, separadores saltados, validação de gabaritos e navegação entre GETs.
- SET CONFIRM ON/OFF, Control+S/Control+D, setas, Home/End, Backspace/Delete e Esc.
- SAY USING, SAVE ALL LIKE/EXCEPT, DISPLAY MEMORY com tipos e INPUT numérico.
- FORMS.md e dois exemplos novos de formulário, com memória e SQLite.
- Teste real em pseudo-terminal Linux, com restauração do terminal.

## 2.0

- Parser Pratt próprio para expressões, substituindo tradução para AST Python nas expressões do console.
- Compilador de blocos PRG e erros com origem/linha.
- Procedimentos, parâmetros por referência, escopo dinâmico PUBLIC/PRIVATE.
- Macros, atribuições, aliases e variáveis qualificadas.
- DO CASE, LOOP, EXIT, RETURN TO MASTER, TEXT, ON ERROR e RETRY.
- Funções de texto/número/data/ambiente ampliadas e funções de dialetos adicionais explícitas.
- Campos C preenchidos/truncados, datas tipadas e regras SET EXACT próximas da referência.
- Dez áreas, índices persistentes com UNIQUE, relações, JOIN e UPDATE.
- COPY STRUCTURE/STRUCTURE EXTENDED, CREATE FROM, SORT, TOTAL, APPEND FROM SQLite.
- SAY/GET/READ, máscaras básicas, RANGE, retângulos e saída alternada.
- Mapeamento .dbf para .sqlite e fallback CP850 para PRGs.
- Auditoria estática parcial --check e testes pela CLI.
- Documentação de compatibilidade, exemplos e referência consultada.

## 1.0

Primeiro console SQLite da conversa, com criação de campos, operações básicas, filtros e laços simples. O ZIP de origem fornecido pelo usuário incluía apenas o inicializador e dois arquivos Markdown, sem o motor mencionado em seu README.
