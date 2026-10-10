# dBASE SQLite, console de comandos em Python

Ambiente de terminal inspirado no dBASE II/III para criar seus próprios bancos, definir campos e manipular registros com comandos xBase. Cada banco é um arquivo SQLite real, sem DBF e sem dependências externas. Python 3.10 ou superior. Windows, Linux e macOS.

## Iniciar

Extraia o ZIP. No Windows, abra `iniciar.bat`, ou execute no terminal:

```bash
python main.py --cwd ./data
```

O ponto `.` é o prompt do ambiente. Digite os comandos sem esse ponto. `HELP` exibe a referência; `QUIT` encerra. As alterações são persistidas imediatamente em transações SQLite, sem exigir SAVE. `SAVE` salva apenas variáveis de memória.

## Criar seu próprio banco

```text
CREATE clientes
```

Informe cada campo na forma `NOME TIPO TAMANHO DECIMAIS`. Linha vazia conclui:

```text
NOME C 40
IDADE N 3
SALDO N 12 2
ATIVO L 1
NASCIMENTO D 10
```

Ou crie em uma única linha, extensão deste ambiente:

```text
CREATE clientes (NOME C 40, IDADE N 3, SALDO N 12 2, ATIVO L 1)
APPEND BLANK
REPLACE NOME WITH 'BODEZARONI', IDADE WITH 52, SALDO WITH 1500.50, ATIVO WITH .T.
DISPLAY
DISPLAY STRUCTURE
USE
USE clientes
LIST ALL
```

`CREATE` abre o banco criado. Não sobrescreve arquivos existentes. `USE clientes` abre `clientes.sqlite`. Cada arquivo contém uma tabela de registros e tabelas internas de metadados. Você pode criar quantos arquivos precisar. Este formato não abre bancos SQLite arbitrários que não possuam esses metadados.

## Tipos

| Tipo | Uso | Armazenamento |
| :--- | :--- | :--- |
| C | Texto com limite de caracteres | TEXT |
| N | Número com largura e casas decimais | REAL |
| L | Lógico `.T.` ou `.F.` | INTEGER 1/0 |
| D | Data ISO `AAAA-MM-DD`, ou vazia | TEXT |
| M | Texto livre, sem limite do campo C | TEXT |

Números usam ponto decimal. N usa ponto flutuante e arredondamento, portanto não é indicado para cálculos financeiros que exijam representação decimal exata. Campos C não recebem preenchimento com espaços. Datas usam ISO, diferente da apresentação original. Campos não informados recebem texto vazio ou zero. Valores que excedam a largura são rejeitados.

## Comandos de uso diário

| Comando | Comportamento |
| :--- | :--- |
| `USE nome`, `USE` | Abre banco ou fecha área atual |
| `CREATE nome` | Definição interativa dos campos |
| `APPEND`, `APPEND BLANK` | Formulário sequencial ou registro vazio |
| `EDIT`, `CHANGE`, `EDIT 2` | Edita campos, Enter mantém valor |
| `DISPLAY` | Exibe registro atual |
| `LIST`, `LIST ALL`, `BROWSE` | Lista registros visíveis |
| `LIST NOME, IDADE ALL FOR IDADE >= 18` | Projeta campos e filtra |
| `DISPLAY NEXT 3` | Exibe a partir da posição atual |
| `GO TOP`, `GO BOTTOM`, `GO 2`, `SKIP -1` | Navega pelo banco |
| `REPLACE SALDO WITH SALDO * 1.05 ALL` | Atualiza registros |
| `DELETE ALL FOR IDADE < 18` | Marca exclusão lógica |
| `RECALL ALL` | Desmarca exclusão nos registros visíveis |
| `SET DELETED ON`, `SET DELETED OFF` | Oculta ou mostra excluídos |
| `PACK` | Remove excluídos e renumera registros |
| `ZAP` | Apaga todos os registros após confirmação SIM |
| `SET FILTER TO IDADE >= 18`, `SET FILTER TO` | Ativa ou remove filtro |
| `LOCATE FOR NOME = 'ANA'`, `CONTINUE` | Busca sequencial |
| `COUNT FOR ATIVO = .T.` | Conta registros visíveis |
| `SUM SALDO TO TOTAL` | Soma e salva em variável |
| `INDEX ON NOME TO nomes` | Define ordenação persistente |
| `SET ORDER TO nomes`, `SET ORDER TO` | Ativa ou desativa ordenação |
| `SEEK 'ANA'`, `FIND ANA` | Busca igualdade na chave do índice |
| `SELECT PRIMARY`, `SELECT SECONDARY`, `SELECT 3` | Seleciona área independente |
| `DISPLAY FILES`, `DISPLAY STATUS`, `DISPLAY MEMORY` | Inspeciona ambiente |
| `COPY TO clientes DELIMITED` | Exporta CSV UTF-8 |
| `APPEND FROM clientes.csv` | Importa CSV, cabeçalhos iguais aos campos |
| `STORE 10 TO X`, `? X + 2`, `RELEASE ALL` | Variáveis e expressões |
| `SAVE TO memoria`, `RESTORE FROM memoria` | Variáveis em JSON |
| `ACCEPT 'Nome: ' TO N`, `INPUT 'Valor: ' TO V` | Entrada de texto ou expressão |
| `DO programa.prg` | Executa script PRG ou CMD |
| `CLEAR`, `HELP`, `QUIT` | Terminal, ajuda e saída |

Sem ALL/NEXT/REST, DISPLAY, REPLACE, DELETE e RECALL afetam apenas o registro atual. LIST, COUNT e SUM usam todos os registros visíveis por padrão. Com DELETED ON, use DELETED OFF antes de RECALL para tornar os excluídos acessíveis. Filtros continuam aplicados a RECALL. PACK ignora filtro e remove todos os registros marcados no banco aberto.

As áreas possuem conexão, ponteiro, filtro e ordem independentes. Variáveis, SET DELETED e SET EXACT são globais. ALIAS pode identificar uma área no STATUS; referências `alias->campo` não foram implementadas.

## Expressões

Comparações `=`, `<>`, `#`, `<`, `<=`, `>`, `>=`; aritmética `+`, `-`, `*`, `/`, `%`; `.AND.`, `.OR.`, `.NOT.`, `.T.`, `.F.` e parênteses. Strings entre aspas simples ou duplas. Use a outra espécie de aspas quando o texto contiver uma delas. Não há suporte a aspas escapadas em todas as posições do parser de comandos.

Funções: LEN, TRIM, UPPER, LOWER, INT, VAL, STR, ABS, ROUND, CHR, AT, DATE, RECNO, RECCOUNT, DELETED, EOF e BOF. STR converte para texto, sem argumentos de largura. `FOUND` é uma variável booleana atualizada por LOCATE/CONTINUE/SEEK/FIND. `SET EXACT OFF` permite comparação por prefixo em `=` para textos; ON exige igualdade. SEEK/FIND exigem igualdade integral da chave.

O interpretador usa AST com lista permitida, sem `eval`, acesso a atributos ou chamadas Python arbitrárias. Os valores SQL são parametrizados. Caminhos de bancos, scripts e exportações ficam restritos a `--cwd`. Não há SQL livre no console.

## Scripts e lote

```bash
python main.py --cwd ./data -c "USE clientes" -c "LIST ALL"
```

Para executar o exemplo completo em uma pasta vazia:

Como scripts ficam restritos a `--cwd`, copie primeiro `examples/demo.prg` para `demo_data` e execute:

```bash
python main.py --cwd ./demo_data --cmd demo.prg
```

O demo cria clientes.sqlite, inclui registros, navega, filtra, indexa e exporta CSV. Não execute novamente no mesmo diretório sem escolher outro nome de banco.

Scripts suportam comentários iniciados por `*` ou `&&`, comandos em uma linha, IF/ELSE/ENDIF aninhados, DO WHILE/ENDDO e DO de outros scripts. Há limite de 100.000 passos por script e profundidade de chamadas 20. Erros interrompem execução; comandos anteriores já confirmados permanecem gravados. Não há transação envolvendo um script inteiro.

## SQLite e arquitetura

`dbase2py/engine.py` contém o parser de comandos, expressão segura, gerenciamento de áreas e persistência; `cli.py` contém o terminal. `_schema` guarda tipos, larguras e casas decimais; `records` guarda campos, `_recno` e `_deleted`; `_indexes` guarda as expressões de ordenação.

Índices de campo simples também criam um índice SQLite nativo. Ordenação e busca do console são avaliadas em Python, inclusive índices de expressão; não reproduzem NDX e não oferecem o desempenho de consultas SQL diretas para grandes volumes. REINDEX recalcula a visão corrente, pois não há arquivo externo de índice a reconstruir. CSV importa somente campos definidos, sem exclusão lógica ou índices. Não faça alterações diretas nas tabelas internas sem preservar a consistência do formato.

Os comandos REPLACE validam todos os valores antes de gravar. APPEND FROM valida o lote e o insere em uma transação. O console é destinado a uso local; não implementa travamento de registros ou compartilhamento concorrente compatível com dBASE III.

## Compatibilidade e origem

O ZIP recebido contém somente main.py, README.md e ORIGINAL_DISK_ANALYSIS.md. O módulo dbase2py citado pelo README não foi incluído. Esta versão implementa um motor novo com base na interface documentada. A pasta `original` preserva os três arquivos recebidos para rastreabilidade. As alegações do README original sobre o motor ausente não representam funcionalidades verificadas no anexo.

É uma implementação de um subconjunto do comportamento xBase, não uma reprodução integral do dBASE II/III. Não inclui DBF, NDX, MEM binário, JOIN, TOTAL, UPDATE, SORT, INSERT, REPORT FORM, formulários de tela @ SAY/GET/READ, DO CASE, TEXT, macros &, funções de usuário nem compatibilidade integral com programas legados. BROWSE é uma listagem textual; EDIT é um formulário sequencial. Um comando desconhecido gera erro explícito.

## Validação

```bash
python -m unittest discover -s tests -v
```

A suíte verifica criação interativa, persistência SQLite, campos, navegação, exclusão e PACK, filtros, buscas, índices persistentes, validação de atualizações, CSV, variáveis, scripts, áreas e rejeição de expressões/caminhos indevidos. Não requer pytest.

Referências para estudo: https://www.sqlite.org/lang.html e https://docs.python.org/3/library/sqlite3.html. São referências gerais, não evidência de compatibilidade integral com xBase.
