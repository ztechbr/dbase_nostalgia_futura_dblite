# Validação da versão 2.1

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
