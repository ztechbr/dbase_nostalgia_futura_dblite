# Matriz de compatibilidade dBASE III PLUS

A referência é *The dBASE Language Handbook*, David M. Kalman, 1989. Cada verbete do livro distingue os dialetos. A presença de um recurso nesta implementação não implica que ele pertença ao dBASE III PLUS. A coluna Estado descreve o comportamento implementado, não certificação pelo executável original.

## Linguagem e execução

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| PRG e CMD | Implementado | Interpretação nativa, sem executáveis DOS |
| Comentários `*`, NOTE e `&&` | Implementado | `&&` fora de literais; texto em TEXT permanece literal |
| Continuação `;` | Implementado | Ao final da linha lógica |
| Abreviações de comandos | Implementado parcialmente | Prefixos não ambíguos com pelo menos quatro caracteres; palavras de cláusulas não são abreviadas |
| IF/ELSE/ENDIF | Implementado | Blocos aninhados, validação de terminadores |
| DO CASE/CASE/OTHERWISE/ENDCASE | Implementado | Executa a primeira condição verdadeira |
| DO WHILE/ENDDO | Implementado | Macro da condição expandida uma vez ao entrar, conforme III PLUS |
| LOOP e EXIT | Implementado | Atingem o laço mais próximo dentro do PRG |
| RETURN, RETURN TO MASTER | Implementado | RETURN simples volta ao chamador; TO MASTER retorna ao programa de nível superior |
| CANCEL e QUIT | Implementado | CANCEL encerra a cadeia; QUIT também fecha o ambiente |
| PROCEDURE, SET PROCEDURE TO, DO WITH | Implementado | Um arquivo de procedimentos ativo; chamadas a arquivos e procedimentos |
| PARAMETERS | Implementado | Primeiro comando executável quando existem argumentos; quantidade precisa coincidir |
| Passagem por referência | Implementado | Variável simples em DO WITH; campo/expressão/literal por valor |
| PUBLIC e PRIVATE | Implementado | Escopo dinâmico, ocultação, limpeza ao sair e ALL LIKE/EXCEPT |
| Atribuição `=` e STORE | Implementado | STORE permite lista de variáveis |
| Macro `&nome` / `&nome.` | Implementado parcialmente | Expansão textual fora de literais; variável precisa ser texto; limitações de expansão |
| `alias->campo`, `M->variavel`, `M.variavel` | Implementado | Campo precede variável homônima sem M-> |
| TEXT/ENDTEXT | Implementado | Saída literal no console/arquivo alternativo |
| ON ERROR e RETRY | Implementado parcialmente | Tratamento de erros em PRG, retomada ou repetição do comando; ERROR() usa código genérico 1, não os códigos originais |
| FUNCTION, RETURN expressão | Extensão | Não atribuir ao dBASE III PLUS; chamada por valor e sem parâmetros opcionais |
| FOR/NEXT, SCAN/ENDSCAN, ELSEIF, LOCAL, arrays | Não implementado | Recursos de outros dialetos também abordados no handbook |

## Expressões e campos

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| C, N, L, D, M | Implementado | SQLite TEXT/REAL/INTEGER; nomes de campo até 30 caracteres são extensão |
| Texto C | Implementado | Preenche espaços; trunca à largura em gravação |
| Tipos no REPLACE | Implementado | Verificados antes de gravação; texto numérico requer VAL, data requer CTOD |
| Operadores aritméticos e lógicos | Implementado | +, -, *, /, ^, **, %, .AND., .OR., .NOT., ! |
| Comparação =, <>, #, <, >, <=, >= | Implementado | SET EXACT OFF usa prefixo da direita; ON ignora espaços finais |
| Operador `==` | Extensão | Igualdade integral, incluindo espaços finais |
| Operador `$` | Implementado | Testa presença de substring |
| Strings simples, duplas e `[texto]` | Implementado | Aspas duplicadas dentro do literal são aceitas |
| Subtração de strings | Implementado | Remove espaços finais à esquerda e recoloca no fim |
| Datas e aritmética de dias | Implementado | Data + número; data - número; data - data em dias |
| Ano de dois dígitos | Implementado | Século XX: 26 vira 1926; use quatro dígitos para 2026 |
| SET DATE/SET CENTURY | Implementado | AMERICAN, ANSI, BRITISH, FRENCH, GERMAN, ITALIAN; USA/JAPAN são extensões |
| Data vazia | Adaptação | Internamente date.min como sentinela; exibição em branco |
| Números | Adaptação | SQLite REAL, sem garantia de decimal exato |
| IIF | Parcial | Ambos os argumentos de resultado são avaliados; sem equivalência certificada para efeitos colaterais e diferenças de avaliação |

Funções implementadas, com subconjuntos de argumentos quando indicado:

```text
ABS INT ROUND MAX MIN MOD SQRT EXP LOG
LEN TRIM RTRIM LTRIM ALLTRIM UPPER LOWER SUBSTR LEFT RIGHT AT
SPACE REPLICATE STUFF STR VAL CHR ASC ISALPHA ISUPPER ISLOWER
DATE CTOD DTOC DTOS DAY MONTH YEAR DOW CMONTH CDOW TIME SECONDS
RECNO RECCOUNT EOF BOF DELETED FOUND ALIAS SELECT USED DBF
FIELD FCOUNT NDX KEY ORDER LUPDATE RECSIZE FILE DISKSPACE
IIF TYPE TRANSFORM VERSION OS ROW COL PCOUNT READKEY LASTKEY INKEY
EMPTY ERROR MESSAGE LINENO PROGRAM
```

ALLTRIM, LEFT, RIGHT, DTOS, EMPTY, USED, PCOUNT e outras funções desta lista pertencem também, ou exclusivamente em alguns casos, a dialetos adicionais descritos no livro. Esta implementação as oferece como extensões de conveniência. Não há modo que bloqueie todas as extensões de outros dialetos.

Observações: AT aceita duas strings; SUBSTR usa posição 1; STR aceita largura e casas; TRIM remove apenas espaços finais; TYPE recebe uma expressão em texto e retorna U se não puder resolvê-la. DTOC aceita uma opção de formato ordenável como extensão. PROGRAM retorna o nome do programa atual, sem nível opcional; ERROR/MESSAGE/LINENO referem-se à última falha tratada. INKEY trata teclas simples e não reproduz códigos estendidos de teclado DOS. RECSIZE representa a largura lógica xBase, não o tamanho físico da linha SQLite.

## Dados, áreas e índices

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| CREATE interativo, USE, SELECT | Implementado | Dez áreas A..J/1..10; SELECT 0 escolhe uma área livre |
| CREATE inline | Extensão | Definição `CREATE nome (campo tipo largura...)` |
| CREATE FROM, COPY STRUCTURE, STRUCTURE EXTENDED | Implementado | Estrutura estendida também usa SQLite com FIELD_NAME/TYPE/LEN/DEC |
| APPEND BLANK e APPEND | Implementado | APPEND usa formulário sequencial no terminal |
| APPEND FROM SQLite | Implementado | Compatibiliza campos pelo nome; dados validados antes do lote |
| REPLACE | Implementado parcialmente | Atualização local de um ou múltiplos registros; alias->campo apenas em comando de um registro |
| ALL/REST/NEXT/RECORD, FOR, WHILE | Implementado parcialmente | Ordem, filtro e condições respeitados; posição final em escopos limitados pode diferir do runtime original |
| LIST, DISPLAY, BROWSE, EDIT, CHANGE | Adaptação | Listagem/formulário textual; BROWSE não é uma grade editável DOS |
| LIST/DISPLAY OFF | Parcial | Cláusula aceita; cabeçalho/RECNO da listagem continuam presentes |
| LIST/DISPLAY TO | Não implementado | Use SET ALTERNATE |
| GO/GOTO, SKIP, EOF/BOF | Implementado | BOF mantém acesso ao primeiro registro; EOF retorna valores vazios nos campos |
| DELETE, RECALL, PACK, ZAP | Implementado | Exclusão lógica; PACK remove e renumera; ZAP respeita SAFETY |
| SET DELETED e SET FILTER | Implementado | Operações usam registros visíveis; DELETED OFF antes de RECALL para expor excluídos |
| LOCATE/CONTINUE | Implementado parcialmente | Busca e FOUND; combinação de CONTINUE com escopos NEXT/WHILE não certificada |
| COUNT, SUM, AVERAGE | Implementado | TO e múltiplas expressões numéricas em SUM/AVERAGE |
| INDEX, SET INDEX, SET ORDER, REINDEX | Adaptação | Metadados persistem no SQLite; não produz NDX/MDX |
| INDEX UNIQUE | Implementado | Visão de navegação omite chaves repetidas; não impõe unicidade na inserção |
| SEEK/FIND | Implementado | Prefixo com EXACT OFF; chave completa com ON; FOUND por área |
| SET SOFTSEEK | Extensão | Pode parar na próxima chave maior |
| Índices de expressão | Adaptação | Avaliados em Python, inclusive após atualizações; sem B+tree NDX |
| SET RELATION | Parcial | Uma relação pai-filho por área; filhos encadeados; rejeita ciclos |
| JOIN | Parcial | Produto cartesiano filtrado; exclui memos; campos repetidos recebem sufixo _2 etc. |
| UPDATE | Parcial | ON campo simples; destino ordenado; RANDOM na origem; atualiza primeira chave duplicada |
| SORT | Parcial | Campos simples /A, /D e /C; destinos SQLite |
| TOTAL | Adaptação | Agrupa pela chave em memória e soma campos; não exige grupos contíguos como no fluxo legado |
| USE EXCLUSIVE | Adaptação | Usa locking_mode=EXCLUSIVE SQLite, sem simulação de locking DBF |
| USE SHARED e RLOCK/FLOCK/UNLOCK | Não implementado | Não oferece compartilhamento e locks por registro dBASE |

Índices são sempre recalculados pelo console em sua visão Python; as situações de NDX desatualizado do runtime original não são reproduzidas. Atualizações locais são transacionadas por comando. Não há transação distribuída: REPLACE com campos de bancos distintos confirma cada arquivo separadamente. JOIN/UPDATE restauram os ponteiros de entrada, outra adaptação que pode diferir do executável original. O esquema interno não deve ser alterado manualmente sem preservar os metadados.

## Terminal, arquivos e ambiente

| Recurso | Estado | Limites/semântica |
| :--- | :--- | :--- |
| @ SAY, GET e READ | Adaptação | Tela 25x80; edição por tecla em terminal interativo, fallback por linha com --plain; veja FORMS.md |
| PICTURE/FUNCTION | Parcial | Templates editáveis, separadores saltados, validação 9/#, X, A, !, L/Y; subconjunto de máscaras |
| SET CONFIRM, CLEAR GETS | Implementado | Confirmação por Enter ou avanço no último slot; CLEAR GETS conserva a tela |
| SAY USING | Implementado | Máscara de apresentação independente da máscara GET |
| RANGE | Implementado | Mínimo/máximo para GET; reentrada em valor inválido |
| @ TO, @ CLEAR | Parcial | Retângulo simples e limpeza de linha; sem DOUBLE/estilos históricos |
| VALID/WHEN/COLOR em @ | Não implementado | Recursos de outros dialetos são rejeitados |
| SET COLOR | Parcial | Armazena a configuração em STATUS; renderização permanece monocromática |
| ? e ?? | Implementado | Saída com/sem newline; callback de teste recebe fragmentos separados |
| ACCEPT, INPUT, WAIT, INKEY | Adaptação | Entrada moderna; teclas estendidas DOS não emuladas |
| SET ALTERNATE TO/ON/OFF | Implementado | Arquivo texto UTF-8; ADDITIVE permitido; SAFETY na sobrescrita |
| SET TALK, EXACT, DELETED, DECIMALS, SAFETY, CONSOLE | Implementado | Conjunto explicitamente suportado |
| DIR, ERASE, DELETE FILE, RENAME, COPY FILE | Parcial | Dentro de --cwd; não renomeia/apaga/copía banco aberto; sem drive DOS |
| SAVE/RESTORE | Adaptação | JSON tipado; SAVE ALL LIKE/EXCEPT; RESTORE ADDITIVE; não lê MEM binário |
| COPY/APPEND DELIMITED | Adaptação | CSV UTF-8 com cabeçalho; não reproduz DELIMITED histórico sem cabeçalho |
| SDF, DBF, DBT, NDX, MDX, FRM, LBL, MEM binários | Não implementado | Formatos legados requerem conversão/implementação adicional |
| REPORT FORM, LABEL FORM, SET FORMAT | Não implementado | Relatórios/formulários podem ser reescritos em PRG com SAY/GET e saída em arquivo |
| SET DEFAULT/PATH/FIELDS/CATALOG/DEVICE/PRINTER | Não implementado | Ajuste layout/caminhos; impressora física não emulada |
| RUN, !, CALL, LOAD, comandos DOS/assembly | Não implementado | Nenhum shell ou binário legado é executado |
| SAVE/RESTORE SCREEN, menus/windows dBASE IV | Não implementado | Extensões não necessárias ao núcleo III PLUS |

## Como decidir se um programa pode rodar

1. Prepare bancos SQLite com campos compatíveis; arquivos DBF não são importados automaticamente.
2. Execute --check em cada PRG e biblioteca de procedimentos.
3. Corrija os erros indicados e revise os pontos parciais desta matriz.
4. Execute em uma cópia de dados, com saídas e entradas de teste conhecidas.
5. Compare valores gravados, fluxo de telas e resultados com a aplicação original quando tiver seu runtime disponível.

O resultado desta entrega comprova os cenários testados em [VALIDATION.md](VALIDATION.md). Não houve teste diferencial com um executável licenciado do dBASE III PLUS nem teste de uma aplicação legada externa fornecida pelo usuário. Consequentemente, não há percentual de compatibilidade declarado.
