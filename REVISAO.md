# Revisão funcional 2.2: dBASE II do MSX e dBASE III PLUS sobre SQLite

Esta revisão compara o interpretador com as fontes abaixo, aula por aula, e registra o que foi corrigido, o que foi acrescentado para portar sistemas e o que continua pendente. O banco continua sendo SQLite: DBF, NDX, MEM e FRM legados são lidos e convertidos, nunca gravados no lugar.

## Fontes consultadas

- Curso MarMSX de dBASE II programável: [índice](https://marmsx.msxall.com/cursos/dbase_prog/index.php), aulas 1 a 5 e [funções PLUS](https://marmsx.msxall.com/cursos/dbase_prog/dbase_plus.html).
- Curso MarMSX de dBASE II interativo: [índice](https://marmsx.msxall.com/cursos/dbase/index.php), aulas 1 a 12, inclusive o formato DBF do dBASE II.
- *The dBASE Language Handbook*, David M. Kalman, 1989 (já usado nas versões anteriores; ver SOURCE_NOTES.md).
- Layout do FRM binário do dBASE III/Clipper descrito em [wiki.audean.com/xb](https://wiki.audean.com/xb/start).

Os exemplos do curso viraram testes em `tests/test_msx_course.py`, com os mesmos dados (alunos e notasmat) e os mesmos resultados esperados.

## 1. Linguagem e programas (curso programável)

| Recurso do curso | Antes | Agora |
| :--- | :--- | :--- |
| Arquivos `.CMD`/`.PRG`, `DO módulo`, `RETURN`, `CANCEL` | OK | OK |
| `@ y,x SAY ... USING` | `USING` só funcionava com gabarito numérico; `"12-10-2024" USING "XX/XX/XXXX"` não trocava os separadores | Gabarito posicional: literais ocupam a posição (dBASE II/III); `@R` insere literais; `@E @B @Z @( @C @X @!`, `$` e `*` |
| `?`, `??`, `@ y,x` sozinho para posicionar | OK | Números saem alinhados à direita (10 posições ou a largura do campo), como no curso (`? SALARIO` → `      7000`) |
| `REMARK` | Ausente | Implementado |
| `TEXT ... ENDTEXT` / `TEXTEND` | Só ENDTEXT | Ambos |
| `SET FORMAT TO PRINTER/SCREEN` | Ausente | Implementado: `@ SAY` vai para o arquivo da impressora com saltos de linha e de página |
| `NOTE`, `*` | OK | OK |
| `ERASE` (limpar tela) | Erro: tratado como apagar arquivo | `ERASE` sem argumento limpa a tela; com argumento apaga arquivo |
| `GET`/`READ`/`PICTURE`/`SET CONFIRM`/`CLEAR GETS` | OK | Ver seção 3 |
| `INPUT`/`ACCEPT` | OK | No dialeto `DBASE2` a mensagem ganha dois-pontos (`Nome:`), como no MSX |
| `RELEASE ALL LIKE/EXCEPT`, `SAVE`/`RESTORE`, `DISPLAY MEMORY` | OK | `RESTORE` também lê `.MEM` binário do dBASE III PLUS |
| `IF`, `DO CASE`, `DO WHILE`, `LOOP` | OK | OK; extensões `ELSEIF`, `SCAN/ENDSCAN`, `FOR/NEXT` |
| `do while .not. eof` (sem parênteses) | Erro: variável desconhecida | `EOF`, `BOF`, `DELETED`, `RECNO`, `DATE`, `TIME`, `FOUND`, `RECCOUNT` aceitos sem parênteses |
| `!(nome)` (maiúsculas), `$(s,i,n)`, `@(a,b)`, `#` (registro), `*` (apagado), `RANK()` | `!(x)` era negação, os demais eram erro | Implementados. `!(lógico)` continua negação |
| `store # to regpos` / `if # <> regpos` | Erro | OK (`#` binário continua "diferente") |
| `TYPE(variável)` | Avaliava o conteúdo como expressão | Dialeto `DBASE2`: tipo do valor; `DBASE3`: expressão em texto |
| Módulos `insere.cmd`, `altera.cmd`, `proc.cmd`, `mostra.cmd` | Falhavam em `#`, `!()` e `eof` | Rodam; ver testes |
| Comandos `PLUS` (CDATE, DDATE, ADATE, TDATE, CHANGE, FORMAT, LZERO, MOD11, CGC, CPF, CODE) | Ausentes | Implementados, inclusive a senha sem eco de `PLUS CODE` |

## 2. Comandos interativos (curso interativo)

| Recurso do curso | Antes | Agora |
| :--- | :--- | :--- |
| `CREATE` com estrutura `MATRICULA,N,4` | Só `MATRICULA N 4`; vírgulas davam erro | Diálogo numerado `001`, vírgulas ou espaços; L e D sem largura assumem 1 e 8 |
| `DISPLAY STRUCTURE` | Lista simples | Formato dBASE com registros, data e total da largura |
| `MODIFY STRUCTURE` | Ausente | Implementado, interativo ou `MODIFY STRUCTURE (campos...)`; **preserva os dados por nome de campo** (o dBASE II apagava tudo) e deixa cópia `_bak.sqlite` |
| `COPY STRUCTURE TO`, `APPEND FROM` | OK | OK |
| `APPEND` (tela de inclusão) | Perguntas linha a linha | Tela `Registro 00001` com um GET por campo; Enter no primeiro campo vazio encerra; `SET CARRY` |
| `INSERT [BEFORE] [BLANK]` | Ausente | Implementado, renumerando os registros seguintes |
| `SET CARRY`, `SET COLON` | Ausentes | Implementados |
| Número no prompt (`. 2`), `GO RECORD 5` | Erro | Equivalem a `GO` |
| `EDIT n` com Ctrl+D/S/E/X/C/R/G/Y/V/U/Q/W | Perguntas linha a linha | Tela de registro com teclas do dBASE II/III; PgUp/Ctrl+R e PgDn trocam de registro; Ctrl+U marca/desmarca exclusão; Ctrl+W grava; Ctrl+Q abandona. Ctrl+C continua interrompendo o programa, em vez de avançar registro |
| `CHANGE [escopo] FIELD lista [FOR]` | Igual a EDIT, sem FIELD | Escopo, `FIELD/FIELDS` e `FOR/WHILE` |
| `REPLACE [escopo] ... FOR` | OK | Mais rápido em laços (ver seção 5) |
| `DELETE`/`RECALL`/`PACK`/`SET DELETED` | OK | Saída do `DISPLAY` com `*` como no curso |
| `DISPLAY ... OFF`, campos e expressões | Formato `RECNO DEL \|` e `OFF` sem efeito | Formato do dBASE: `00001   8361 Pablo...` no dialeto `DBASE2`; cabeçalho `Record#` no `DBASE3`; `OFF` remove o número; `TO PRINT`, `TO FILE` |
| `COUNT`, `SUM`, `LOCATE`, `CONTINUE` | OK | Mensagens `Contagem =00004`/`Registro :00009` com TALK; LOCATE para no primeiro encontrado em vez de avaliar a tabela toda |
| `DISPLAY FILES` | Só nomes | Nome, registros e data, `LIKE` |
| `INDEX ON ... TO`, `FIND`, `USE ... INDEX`, `REINDEX` | OK | Busca binária; `SET INDEX TO arquivo` lê a chave de um `.NDX` (dBASE III) ou `.NTX` (Clipper) existente |
| `SORT ON campo TO arq [ASCENDING/DESCENDING]` | Só `/A /D` | Ambas as sintaxes |
| `TOTAL ON ... TO ... FIELD ... [FOR]` | Exigia FIELDS, sem FOR | `FIELD`/`FIELDS` opcionais, `FOR/WHILE`; o campo de destino é alargado se a soma não couber |
| `SELECT PRIMARY/SECONDARY`, `P.campo`/`S.campo` | `P.`/`S.` eram erro | Implementados |
| `SET LINKAGE ON` | Ausente | Implementado |
| `JOIN TO ... FOR p.x=s.x [FIELD ...]` | Exigia `WITH` | Sem `WITH` junta primária e secundária; `FIELD` aceito |
| `CLEAR` fecha bancos e variáveis (dBASE II) | Limpava a tela | Dialeto `DBASE2`; no `DBASE3` continua limpando a tela |
| `REPORT FORM` com diálogo | Ausente | Implementado (seção 4) |
| `USE b:venda`, `DELETE FILE alunos` | Unidade e extensão eram erro | Unidade ignorada; `DELETE FILE` sem extensão apaga o banco |
| Arquivos `.DBF` do dBASE II (cabeçalho de 521 bytes) | Não eram lidos | Importados no primeiro `USE` |
| Base grande (aula 12, 5.045 registros) | Laços `SKIP`/`REPLACE` eram quadráticos | Cache de navegação; 5.000 inclusões + varredura em ~2 s |

## 3. Formulários

| Recurso | Antes | Agora |
| :--- | :--- | :--- |
| GET com delimitadores `:` | OK | `SET DELIMITERS ON/OFF`, `SET DELIMITERS TO "[]"`, `SET COLON`; sem delimitador o GET aparece em vídeo reverso (`SET INTENSITY`) |
| Gabarito padrão de campo N com decimais | `#` sem ponto decimal | `9999.99` conforme largura/decimais do campo |
| Símbolos de PICTURE | 9 # X A ! L Y | Também `N`, `$`, `*`, `@A` |
| Teclas | Setas, Ctrl+S/D, Home/End | Também Ctrl+E/X (campo anterior/seguinte), Ctrl+G, Ctrl+Y (apaga campo), Ctrl+V/Insert (inserção), Ctrl+W, Ctrl+Q, PgUp/PgDn |
| `VALID`, `WHEN`, `ERROR`, `MESSAGE` em GET | Rejeitados | Implementados (extensão dBASE IV/Clipper); valor recusado por VALID é restaurado |
| `COLOR` em `@` e `SET COLOR` | `@ ... COLOR` rejeitado | Aceitos; a tela continua monocromática |
| `READ SAVE` | Ausente | Implementado |
| `SET FORMAT TO arquivo.fmt`, `CLOSE FORMAT` | Ausente | Formatos de tela legados (texto com @ SAY/GET) usados por READ, APPEND, EDIT, CHANGE e INSERT |
| `@ l,c TO l2,c2 [DOUBLE/PANEL]` | Moldura `+-\|` | Moldura com caracteres de caixa simples/dupla |
| `@ l,c CLEAR [TO ...]` | Só a linha | Até o canto inferior direito, ou a janela |
| `@ ... PROMPT` / `MENU TO` | Ausente | Menu de barras (extensão Clipper), setas, Enter, Esc e letra inicial |
| `SAVE SCREEN`/`RESTORE SCREEN` | Ausente | Extensão Clipper |
| `SET DEVICE TO PRINT`, `SET PRINT`, `SET PRINTER TO`, `???`, `EJECT`, `SET MARGIN` | Ausente | Impressora emulada em arquivo texto (`impressora.txt` por padrão) |

## 4. Relatórios

`REPORT FORM nome [escopo] [FOR] [WHILE] [TO PRINT|TO FILE arq] [PLAIN] [HEADING exp] [NOEJECT] [SUMMARY]`:

- Lê o `.FRM` binário do dBASE III PLUS/Clipper (1990 bytes): título, colunas, cabeçalhos, totais, grupo, largura, linhas e margens.
- `CREATE REPORT`/`MODIFY REPORT` fazem o diálogo do dBASE II mostrado no curso (margem, linhas, cabeçalho, espaço duplo, totais, subtotal, colunas) e gravam o formulário em JSON com extensão `.frm`. Um FRM binário modificado é preservado como `.fr3`.
- No dialeto `DBASE2`, `REPORT FORM` de um arquivo inexistente abre o diálogo, como no MSX.

## 5. Para portar sistemas

- **Dados legados**: `USE clientes` converte `clientes.dbf` (dBASE II, III, IV, FoxPro, com memo DBT/FPT) para `clientes.sqlite` no primeiro uso. Também `IMPORT FROM arq.dbf [TO nome]`, `APPEND FROM arq.dbf` e `python main.py --import-dbf arq.dbf`. Registros apagados são preservados com a marca. Nomes como `NOTA:1` viram `NOTA_1`. Codificação CP850 por padrão (`--encoding` muda).
- **Exportação**: `COPY TO arq.dbf` (ou `TYPE DBF`), `SDF`, `DELIMITED [WITH c|BLANK]` no formato do dBASE e CSV com cabeçalho (`.csv` ou `TYPE CSV`).
- **SETs de inicialização**: `SET BELL/ESCAPE/STATUS/SCOREBOARD/ECHO/STEP/MENU/HELP/...` não interrompem mais o programa; ficam registrados em `DISPLAY STATUS`. `SET PATH`/`SET DEFAULT` procuram arquivos em subpastas de `--cwd`.
- **Multiusuário**: `USE ... SHARED`, `RLOCK()`, `FLOCK()`, `LOCK()` e `UNLOCK` são aceitos; cada comando é uma transação SQLite.
- **Funções adicionadas**: RANK, STRZERO, PADL/PADR/PADC, ISDIGIT, ISBLANK, CEILING, FLOOR, SIGN, PI, RAND, GETENV, DMY, MDY, MEMLINES, MLINE, RAT, OCCURS, PROPER, PROW, PCOL, SOUNDEX, DIFFERENCE, LIKE, HEADER, NETWORK, ISCOLOR, FKMAX, FKLABEL.
- **Desempenho**: registros ficam em cache por área e são atualizados no lugar em `REPLACE`, `APPEND BLANK`, `DELETE` e `GET`; `SEEK` faz busca binária; SQLite opera em WAL com `synchronous=NORMAL`.
- **Relações**: `LIST`, `COUNT`, `SUM`, `REPLACE` e `REPORT` reposicionam o ponteiro a cada registro, então `filho->campo` acompanha o pai. Antes o filho ficava parado no registro inicial. `SET RELATION` aceita várias relações separadas por vírgula.
- **Dialeto**: `--dialect dbase2` ou `SET DIALECT TO DBASE2` ativa as diferenças do dBASE II (CLEAR, ACCEPT/INPUT com dois-pontos, TYPE por valor, LIST sem cabeçalho e com número `00001`, REPORT FORM com diálogo).

## 5a. Etiquetas, arrays, BROWSE e monitor de fósforo

- **LABEL FORM** `nome [escopo] [FOR] [WHILE] [SAMPLE] [TO PRINT|TO FILE arq]`: lê o `.LBL` binário do dBASE III PLUS (1034 bytes) e o JSON gravado por `CREATE LABEL`/`MODIFY LABEL`, que perguntam largura, altura, margem, linhas e espaços entre etiquetas, etiquetas por linha e o conteúdo de cada linha. Itens separados por vírgula são aparados e unidos por espaço (`CIDADE, "-", UF`) e linhas vazias sobem, como no dBASE III.
- **Arrays** (dBASE IV, Clipper e FoxPro): `DECLARE a[10]`, `DIMENSION m(2,3)`, `PUBLIC`/`PRIVATE`/`LOCAL` com dimensões e `LOCAL x := valor`; acesso `a[i]`, `m[i,j]`, `m[i][j]` e `a(i)`; literais `{1, "a", {2,3}}`; atribuição por `=`, `STORE ... TO a[i]` e `@ ... GET a[i]`; funções ALEN, AFILL, ASCAN, ASORT, AINS, ADEL, ASIZE, AADD, ACOPY, ACLONE, AFIELDS e ARRAY; `COPY TO ARRAY`, `APPEND FROM ARRAY`, `SCATTER`/`GATHER` (FoxPro); SAVE/RESTORE e DISPLAY MEMORY mostram arrays. `TYPE()` devolve `A`. `{10/10/26}` continua sendo data (dBASE IV); `[texto]` continua sendo texto quando o colchete não está colado a um nome.
- **BROWSE** em grade: setas, Tab, PgUp/PgDn, Home/End; Enter ou digitação editam a célula com a máscara do campo; seta para baixo na última linha inclui registro (descartado se ficar vazio); Ctrl+U marca exclusão; Esc ou Ctrl+W saem. Cláusulas FIELDS, FREEZE, WIDTH, NOAPPEND, NOEDIT, NODELETE e NOCLEAR. Com `--plain` ou entrada redirecionada continua listando.
- **Monitor**: `--monitor verde` (padrão quando a CLI roda num terminal sem `--plain`), `ambar`, `branco`, `cores` (W/N do dBASE III) ou `nenhum`; dentro do programa, `SET MONITOR TO VERDE|AMBAR|BRANCO|CORES|NENHUM`. O texto sai em fósforo sobre fundo preto e GETs/menus/célula do BROWSE em vídeo reverso. `SET COLOR TO padrão,realçado[,borda]` agora colore de fato, com os códigos do dBASE (`W+/B`, `N/W`, `GR*`, `U`, `I`, `X`).

## 6. Mudanças de comportamento ao atualizar da 2.1

1. `?`, `SAY` sem PICTURE, `LIST` e `DISPLAY MEMORY` alinham números à direita. Programas que concatenam com `STR()`/`LTRIM()` não mudam.
2. Com `SET TALK ON` (padrão), `STORE`/`=` ecoam o valor e `REPLACE`, `DELETE`, `COPY`, `INDEX` etc. informam a quantidade de registros, como o dBASE. Use `SET TALK OFF` nos programas.
3. `COPY TO x DELIMITED` grava `x.txt` no formato do dBASE (texto entre aspas, sem cabeçalho). Para CSV com cabeçalho use `COPY TO x.csv` ou `TYPE CSV`.
4. `COPY`, `SORT`, `TOTAL` e `JOIN` sobrescrevem um destino existente: perguntam com `SET SAFETY ON` e sobrescrevem com OFF. Antes davam erro.
5. `SEEK`/`LOCATE` não criam mais a variável de memória `FOUND`. `FOUND()` e `FOUND` sem parênteses continuam funcionando.
6. `PARAMETERS` com mais nomes do que argumentos inicializa os restantes com `.F.` (dBASE IV/Clipper).
7. `APPEND` e `EDIT` usam a tela de GETs; com `--plain` ou entrada redirecionada continuam lendo uma linha por campo.
8. Os bancos passam a usar `journal_mode=WAL`; enquanto um banco está aberto existem os arquivos `-wal`/`-shm` ao lado dele.
9. No terminal, a CLI abre em fósforo verde; use `--monitor nenhum` para as cores do seu terminal. `BROWSE` deixou de ser listagem no terminal interativo.
10. `nome[` colado passa a ser índice de array: escreva `? [texto]` ou `x = [texto]` com espaço ou operador antes do colchete, como no Clipper.

## 7. Pendências conhecidas

- Edição de memo em GET e no BROWSE (o memo aparece como `memo`/`MEMO` e é protegido); `EDIT`↔`BROWSE` com F2 do dBASE III.
- Índices `.MDX`/`.CDX` e o NDX/FRM/MEM do dBASE II: só a chave de `.NDX`/`.NTX` é lida; recrie os demais com `INDEX ON`.
- `ON KEY`/`ON ESCAPE` são aceitos sem disparo. Cores dependem de um terminal com ANSI e cor de 24 bits (Windows Terminal, console do Windows 10/11, terminais Linux/macOS).
- Precisão: o dBASE II exibe `(bim1+bim2+bim3+bim4)/4` com as casas dos operandos (7.7); aqui a divisão usa `SET DECIMALS` (7.75). Campos numéricos vazios aparecem como 0, não como espaços.
- `PLUS CGC` usa a regra atual de CNPJ (inclusive alfanumérico). O exemplo do curso (`18782203000128`), baseado na regra anterior a 1993, não é aceito por ela; a regra antiga não está documentada no curso.
- `INPUT` exige número, como diz o curso; o dBASE III aceita qualquer tipo de expressão.
- Acentos do MSX: textos `.CMD` acentuados do MSX usam o mapa de caracteres do MSX brasileiro; converta com o MarMSX Text Tools ou informe `--encoding`.
- `MODIFY STRUCTURE` associa campos pelo nome; um campo renomeado começa vazio.
- O editor por tecla foi testado com teclas injetadas e em pseudo-terminal Linux; falta teste manual em console Windows.

## 8. Validação

`python -m pytest -q tests`: 159 testes passaram, 1 ignorado (pseudo-terminal POSIX no Windows), Python 3.14.3, Windows 11. Detalhes em VALIDATION.md.
