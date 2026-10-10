# Matriz de compatibilidade dBASE II (MSX) e dBASE III PLUS

Referências: curso MarMSX de dBASE II para MSX (interativo e programável) e *The dBASE Language Handbook*, David M. Kalman, 1989. O livro distingue os dialetos; a presença de um recurso nesta implementação não implica que ele pertença ao dBASE III PLUS. A coluna Estado descreve o comportamento implementado, não certificação pelo executável original. A comparação aula por aula está em [REVISAO.md](REVISAO.md).

O dialeto padrão é `DBASE3`. `--dialect dbase2` ou `SET DIALECT TO DBASE2` muda CLEAR, ACCEPT/INPUT, TYPE(), o formato de LIST/DISPLAY e REPORT FORM sem arquivo para o comportamento do dBASE II.

## Linguagem e execução

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| PRG e CMD | Implementado | Interpretação nativa, sem executáveis DOS/MSX-DOS |
| Comentários `*`, NOTE, `&&`, REMARK | Implementado | REMARK imprime o texto; `&&` fora de literais |
| Continuação `;` | Implementado | Ao final da linha lógica |
| Abreviações de comandos | Implementado parcialmente | Prefixos não ambíguos com pelo menos quatro caracteres; nome completo tem precedência |
| IF/ELSE/ENDIF | Implementado | ELSEIF é extensão dBASE IV/Clipper |
| DO CASE/CASE/OTHERWISE/ENDCASE | Implementado | Executa a primeira condição verdadeira |
| DO WHILE/ENDDO, LOOP, EXIT | Implementado | Macro da condição expandida uma vez ao entrar, conforme III PLUS |
| SCAN/ENDSCAN, FOR/NEXT | Extensão | dBASE IV/Clipper; LOOP e EXIT funcionam |
| RETURN, RETURN TO MASTER, CANCEL, QUIT | Implementado | |
| PROCEDURE, SET PROCEDURE TO, DO WITH, PARAMETERS | Implementado | Parâmetros a mais recebem .F. (dBASE IV/Clipper); PCOUNT() informa a quantidade |
| Passagem por referência | Implementado | Variável simples em DO WITH; campo/expressão/literal por valor |
| PUBLIC e PRIVATE | Implementado | Escopo dinâmico, ocultação, limpeza ao sair e ALL LIKE/EXCEPT |
| Atribuição `=` e STORE | Implementado | Ecoam o valor com SET TALK ON |
| Macro `&nome` / `&nome.` | Implementado parcialmente | Expansão textual fora de literais; variável precisa ser texto |
| `alias->campo`, `M->variavel`, `M.variavel`, `P.campo`, `S.campo` | Implementado | P./S. são as áreas primária e secundária do dBASE II |
| TEXT/ENDTEXT (ou TEXTEND) | Implementado | Saída literal |
| ON ERROR e RETRY | Implementado parcialmente | ERROR() usa código genérico 1; ON ESCAPE/ON KEY são aceitos sem disparo |
| FUNCTION, RETURN expressão | Extensão | Chamada por valor |
| Arrays: DECLARE, DIMENSION, LOCAL, `a[i,j]`, `a(i)`, `{...}` | Extensão | dBASE IV/Clipper/FoxPro; até 2 dimensões em DECLARE/DIMENSION, aninhamento livre em literais |
| RUN, !, CALL, LOAD | Não implementado | Nenhum shell ou binário legado é executado |

## Expressões e campos

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| C, N, L, D, M | Implementado | SQLite TEXT/REAL/INTEGER; nomes de campo até 30 caracteres são extensão |
| Operadores aritméticos, lógicos, `$`, comparações, `==` | Implementado | SET EXACT OFF compara pelo prefixo da direita; `==` é extensão |
| dBASE II: `!(texto)`, `$(texto,i,n)`, `@(a,b)`, `#`, `*` | Implementado | `!(x)` vira maiúsculas para texto e negação para lógico; `#` binário continua "diferente" |
| EOF, BOF, DATE etc. sem parênteses | Implementado | Somente quando não há campo ou variável com o nome |
| Strings `'...'`, `"..."`, `[...]` e subtração de strings | Implementado | |
| Datas e aritmética de dias, SET DATE/CENTURY | Implementado | Ano de dois dígitos no século XX |
| Exibição de números | Implementado | `?`, SAY sem PICTURE e LIST alinham à direita: 10 posições para inteiros, largura do campo para campos N |
| Números | Adaptação | SQLite REAL; o dBASE II exibe divisões com as casas dos operandos, aqui vale SET DECIMALS |
| IIF | Parcial | Ambos os resultados são avaliados |

Funções:

```text
ABS INT ROUND MAX MIN MOD SQRT EXP LOG CEILING FLOOR SIGN PI RAND
LEN TRIM RTRIM LTRIM ALLTRIM UPPER LOWER PROPER SUBSTR LEFT RIGHT AT RAT OCCURS
SPACE REPLICATE STUFF STR STRZERO VAL CHR ASC RANK PADL PADR PADC LIKE SOUNDEX DIFFERENCE
ISALPHA ISUPPER ISLOWER ISDIGIT ISBLANK EMPTY MEMLINES MLINE
DATE CTOD DTOC DTOS DAY MONTH YEAR DOW CMONTH CDOW DMY MDY TIME SECONDS
RECNO RECCOUNT EOF BOF DELETED FOUND ALIAS SELECT USED DBF FIELD FCOUNT NDX KEY ORDER LUPDATE RECSIZE HEADER
FILE DISKSPACE GETENV OS VERSION NETWORK ISCOLOR RLOCK FLOCK LOCK
IIF TYPE TRANSFORM ROW COL PROW PCOL PCOUNT READKEY LASTKEY INKEY FKMAX FKLABEL
ALEN AFILL ASCAN ASORT AINS ADEL ASIZE AADD ACOPY ACLONE AFIELDS ARRAY
ERROR MESSAGE LINENO PROGRAM
```

Muitas são de dBASE IV/Clipper e entram como extensões de conveniência; não há modo que bloqueie extensões. TYPE recebe texto no dBASE III e valor no dialeto DBASE2. RLOCK/FLOCK/LOCK sempre retornam .T.

## Dados, áreas e índices

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| CREATE interativo (`MATRICULA,N,4`), CREATE inline, USE, SELECT | Implementado | Dez áreas A..J/1..10, PRIMARY/SECONDARY |
| MODIFY STRUCTURE | Adaptação | Preserva os dados por nome de campo (o dBASE II apagava); cópia anterior em `nome_bak.sqlite` |
| CREATE FROM, COPY STRUCTURE [EXTENDED] | Implementado | |
| COPY TO ARRAY, APPEND FROM ARRAY, SCATTER, GATHER | Extensão | dBASE IV e FoxPro |
| APPEND, APPEND BLANK, INSERT [BEFORE] [BLANK], SET CARRY | Implementado | APPEND/INSERT usam a tela de GETs ou o formato ativo |
| APPEND FROM | Implementado | SQLite, DBF, SDF, DELIMITED [WITH c/BLANK] e CSV com cabeçalho |
| REPLACE, DELETE, RECALL, PACK, ZAP | Implementado | Atualização em cache; uma transação por comando |
| ALL/REST/NEXT/RECORD, FOR, WHILE | Implementado | Posição final em escopos limitados pode diferir do runtime original |
| LIST, DISPLAY | Implementado | Formato do dBASE, OFF, TO PRINT, TO FILE, SET HEADING, SET FIELDS; DISPLAY não pausa a cada tela |
| BROWSE | Implementado | Grade editável com FIELDS, FREEZE, WIDTH, NOAPPEND, NOEDIT, NODELETE; memo protegido; listagem com --plain |
| EDIT, CHANGE | Implementado | Tela de registro, escopo, FIELDS, PgUp/PgDn |
| GO/GOTO/GO RECORD, número no prompt, SKIP, EOF/BOF | Implementado | |
| SET DELETED, SET FILTER | Implementado | |
| LOCATE/CONTINUE | Implementado | Para no primeiro registro encontrado; NEXT e WHILE respeitados |
| COUNT, SUM, AVERAGE | Implementado | SUM/AVERAGE sem campos usam todos os numéricos |
| INDEX, SET INDEX, SET ORDER, REINDEX, SEEK/FIND | Adaptação | Chave guardada no SQLite e avaliada em Python; busca binária; não produz NDX |
| `.NDX` (dBASE III) e `.NTX` (Clipper) existentes | Adaptação | SET INDEX TO lê a expressão-chave do cabeçalho e recria o índice; MDX/CDX não |
| INDEX UNIQUE | Implementado | A visão omite chaves repetidas; não impede a inclusão |
| SET RELATION, SET LINKAGE | Implementado | Várias relações por área; LIST/COUNT/REPLACE reposicionam o filho a cada registro |
| JOIN | Implementado | Sem WITH junta primária e secundária (dBASE II); FIELD/FIELDS |
| UPDATE | Parcial | ON campo simples; RANDOM na origem |
| SORT | Implementado | `ON campo TO arq [ASCENDING/DESCENDING]` (II) e `TO arq ON c1/A,c2/D` (III) |
| TOTAL | Adaptação | FIELD(S) opcional, FOR/WHILE; agrupa em memória; destino alargado se a soma não couber |
| COPY TO | Implementado | SQLite, DBF dBASE III (memo vira C 254), SDF, DELIMITED e CSV; destino existente pede confirmação com SAFETY ON |
| `.DBF` legado | Adaptação | Importado para SQLite no primeiro USE, por IMPORT FROM ou `--import-dbf`; dBASE II/III/IV/FoxPro e memo DBT/FPT |
| USE EXCLUSIVE, USE SHARED, RLOCK/FLOCK/UNLOCK | Adaptação | EXCLUSIVE trava o arquivo SQLite; SHARED e locks são aceitos sem trava por registro |

Os bancos usam `journal_mode=WAL` e `synchronous=NORMAL`. O esquema interno (`records`, `_schema`, `_indexes`) não deve ser alterado manualmente.

## Terminal, formulários e arquivos

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| @ SAY, GET, READ, CLEAR GETS, READ SAVE | Implementado | Tela 25x80; edição por tecla em terminal interativo e uma linha por GET com --plain; ver FORMS.md |
| PICTURE/FUNCTION/USING | Implementado | 9 # X A ! N L Y $ * e literais; @R @E @B @Z @( @C @X @! @A |
| SET CONFIRM, SET COLON, SET DELIMITERS, SET INTENSITY, SET BELL | Implementado | |
| RANGE, VALID, WHEN, ERROR, MESSAGE | Implementado | VALID/WHEN/ERROR/MESSAGE são extensões dBASE IV/Clipper |
| SET FORMAT TO arquivo.fmt / PRINTER / SCREEN | Implementado | Formato usado por READ, APPEND, EDIT, CHANGE e INSERT |
| @ TO [DOUBLE/PANEL], @ CLEAR [TO] | Implementado | Caracteres de caixa Unicode |
| @ PROMPT / MENU TO, SAVE/RESTORE SCREEN | Extensão | Clipper |
| SET COLOR, SET MONITOR | Implementado | Códigos do dBASE em ANSI; monitores de fósforo verde/âmbar/branco; COLOR na cláusula @ é aceito e ignorado |
| ?, ??, ???, ACCEPT, INPUT, WAIT, INKEY | Implementado | INPUT exige número; teclas estendidas DOS não emuladas |
| SET ALTERNATE, SET PRINT, SET PRINTER TO, SET DEVICE TO PRINT, EJECT, SET MARGIN | Adaptação | Impressora emulada em arquivo texto (`impressora.txt`) |
| REPORT FORM, CREATE/MODIFY REPORT | Implementado | Lê FRM binário dBASE III/Clipper; diálogo do dBASE II grava JSON `.frm` |
| LABEL FORM, CREATE/MODIFY LABEL | Implementado | Lê LBL binário do dBASE III PLUS; diálogo grava JSON `.lbl`; SAMPLE, TO PRINT, TO FILE |
| SAVE/RESTORE | Adaptação | SAVE grava JSON tipado; RESTORE lê JSON ou MEM binário do dBASE III PLUS |
| PLUS CDATE/DDATE/ADATE/TDATE/CHANGE/FORMAT/LZERO/MOD11/CGC/CPF/CODE | Implementado | Datas DDMMAA no século XX; CGC pela regra atual de CNPJ |
| DIR, DISPLAY FILES [LIKE], ERASE, DELETE FILE, RENAME, COPY FILE | Implementado | Dentro de --cwd; unidade `B:` ignorada; ERASE sem argumento limpa a tela |
| SET PATH, SET DEFAULT | Adaptação | Subpastas de --cwd |
| MODIFY COMMAND/FILE | Adaptação | Abre o editor do sistema (VISUAL/EDITOR, Bloco de Notas no Windows) |
| SETs sem efeito (BELL, ESCAPE, STATUS, SCOREBOARD, ECHO, STEP, MENU, HELP, TYPEAHEAD...) | Adaptação | Aceitos e mostrados em DISPLAY STATUS |

## Como decidir se um programa pode rodar

1. Copie os `.PRG`/`.CMD`, `.FMT`, `.FRM`, `.DBF`/`.DBT`, `.NDX` e `.MEM` para a pasta de `--cwd`. Os DBF são convertidos no primeiro USE.
2. Execute `--check` em cada PRG e biblioteca de procedimentos e trate os erros.
3. Revise os pontos parciais desta matriz e as mudanças listadas em REVISAO.md.
4. Execute em uma cópia dos dados com entradas conhecidas e compare com a aplicação original.

Não houve teste diferencial com um executável licenciado do dBASE II ou III PLUS. Os cenários comprovados estão em [VALIDATION.md](VALIDATION.md) e em `tests/test_msx_course.py`.
