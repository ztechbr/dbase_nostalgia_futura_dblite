# Validação

## Versão 2.2

Resultado: **160 testes; 159 passaram e 1 foi ignorado** (o teste de pseudo-terminal POSIX não roda no Windows). Ambiente: Python 3.14.3, Windows 11.

`tests/test_arrays_browse_labels.py` (12 testes) cobre arrays (declaração, literais, 2 dimensões, sintaxe FoxPro, funções, COPY TO ARRAY, SCATTER/GATHER, GET, SAVE/RESTORE, escopo LOCAL), LABEL FORM (diálogo, duas por linha, linhas vazias, TO FILE, LBL binário, SAMPLE), BROWSE (edição, inclusão, exclusão, descarte de linha vazia, NOAPPEND, FREEZE, NOEDIT, fallback em listagem) e cores (códigos de SET COLOR, monitores e sequências emitidas).

```bash
python -m pytest -q tests
```

`tests/test_msx_course.py` (36 testes) reproduz os exemplos do curso MarMSX com as tabelas alunos e notasmat:

- Curso interativo: DISPLAY no formato `00001`, OFF, `$()`, ponteiro `#`, número no prompt, `!()` com SET EXACT, COUNT/SUM/LOCATE/CONTINUE com as mensagens do dBASE II, REPLACE/CHANGE com escopo, DELETE/RECALL/PACK, INDEX/FIND, índice composto, SORT ascendente e descendente, TOTAL por sexo (F 49, M 70), JOIN com P./S., SET LINKAGE, CLEAR do dBASE II, CREATE com `MATRICULA,N,4`, DISPLAY STRUCTURE, MODIFY STRUCTURE preservando dados, DISPLAY FILES e DELETE FILE.
- Curso programável: SAY USING (`150.4`, `12/10/2024`), TEXT/TEXTEND, REMARK, DO CASE com `!()`, LOOP (1, 2, 4, 5), maior média (Beatriz Saraiva, 9.90), módulo de inclusão com `store # to regpos` e matrícula repetida, busca por nome com CONTINUE, SET FORMAT TO PRINTER e os comandos PLUS.
- dBASE III: cabeçalho `Record#`, SET HEADING, relação acompanhando LIST/COUNT, eco de TALK e alinhamento numérico, SCAN/FOR/ELSEIF, COPY/APPEND SDF e ida e volta por DBF.
- Formulários e relatórios: APPEND por linha e por tecla com SET CARRY, EDIT com PgDn, INSERT BEFORE BLANK, VALID/WHEN/ERROR e delimitadores, SET FORMAT TO .fmt com READ e APPEND, moldura dupla, SAVE/RESTORE SCREEN, MENU TO, funções de PICTURE, CREATE REPORT pelo diálogo, REPORT FORM com FOR/PLAIN/TO FILE e FRM binário.
- Arquivos legados: DBF do dBASE II (cabeçalho de 521 bytes, campo `NOTA:1`, registro apagado) e DBF do dBASE III com memo DBT, índice NDX e MEM binário.
- Desempenho: 5.000 APPEND BLANK/REPLACE, INDEX, varredura com REPLACE e SKIP, SEEK e SUM em cerca de 2 segundos.

Também foi executado pela CLI um menu no estilo do curso com `--dialect dbase2 --plain` (APPEND em tela e DISPLAY ALL), `--check` e `--import-dbf`.

Limites: não houve comparação com um executável dBASE II/III; o editor por tecla foi testado com teclas injetadas, sem sessão manual em console Windows.

## Versão 2.1

Resultado registrado: **112 testes, todos passaram**.

Ambiente: Python 3.12.14 / Linux. A execução original do dBASE III PLUS não esteve disponível para comparação diferencial. Windows e macOS não foram executados nesta validação.

Comando:

```bash
python -m unittest discover -s tests -v
```

O log completo está em `tests/VALIDATION_LOG.txt`.

## Cobertura funcional

- Persistência SQLite, fechamento/reabertura, criação interativa e nomes sem distinguir maiúsculas.
- Campos C preenchidos/truncados, validação de tipos e datas armazenadas/reabertas.
- Precedência, strings, comparação por prefixo, SET EXACT, espaços, curto-circuito, funções e datas.
- GO/SKIP/BOF/EOF, escopos, filtros, exclusão lógica, PACK, ZAP e agregações.
- Índices persistentes, UNIQUE, SEEK/FIND, ORDER por posição e locking SQLite EXCLUSIVE.
- Dez áreas, aliases, campo/variável homônima e SET RELATION.
- PROCEDURE, PARAMETERS por referência/valor, PRIVATE/PUBLIC e liberação do escopo inclusive em erro.
- IF, DO CASE, DO WHILE, LOOP/EXIT, RETURN, RETURN TO MASTER, CANCEL, macros e limite global de passos.
- TEXT, comentários, continuações e leitura CP850.
- SAY/GET, PICTUREs independentes para SAY/GET, RANGE, READ em variável/campo e saída alternada.
- COPY STRUCTURE/STRUCTURE EXTENDED/CREATE FROM, COPY/APPEND SQLite/CSV, SORT, TOTAL, JOIN e UPDATE.
- ON ERROR, RETRY e diagnósticos com arquivo/linha.
- Auditoria estática sem criar os bancos mencionados no código auditado.
- Expressões Python indevidas, nomes de campo inválidos e caminhos fora do diretório rejeitados.

## Testes de integração pela CLI

1. `examples/setup.py` prepara dados e PRGs numa pasta temporária.
2. `negocios.prg` roda integralmente, produz `.T.` na validação, soma final 6075 e JOIN com 3 linhas.
3. `menu.prg` recebe entradas B, BRU e X, encontra BRUNO e encerra.
4. `--check compat_auditoria.prg` identifica recursos ausentes e retorna código 2.
5. `--check menu.prg` retorna `needs_runtime_validation`.
6. Um comando desconhecido em lote retorna código 1.

## Limite da evidência

Estes resultados demonstram o comportamento nos cenários incluídos. Não demonstram compatibilidade integral com todas as aplicações dBASE III PLUS, formatos binários, impressoras ou edição de tela DOS. Não há percentual de cobertura da linguagem, benchmark de grandes volumes ou certificação de equivalência.

## Validação de formulários 2.1

Máscaras com 9/#/X e separadores, GET delimitado por dois-pontos, avanço automático, CONFIRM ON, pilha de GETs, CLEAR GETS mantendo desenho, Control+S/Control+D, setas, apagamento, Esc, campos SQLite, RANGE, SAY USING, SAVE filtrado e DISPLAY MEMORY com tipos.

O teste nativo POSIX executou a CLI em pseudo-terminal, digitou 01022024 sem Enter, confirmou 01/02/2024 e verificou a restauração dos atributos do terminal. Windows continua sem execução de teste nativo nesta entrega.
