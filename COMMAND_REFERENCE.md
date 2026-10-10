# Referência rápida de comandos

Sintaxe efetivamente implementada. O guia detalhado de limites está em COMPATIBILITY.md. Nomes de arquivos sem aspas devem ser simples; use aspas para espaços. Nomes de arquivos e campos são diferentes de expressões: USE recebe um nome, enquanto SEEK recebe uma expressão.

## Banco, campos e navegação

```text
CREATE nome
CREATE nome (CODIGO N 5, NOME C 30, SALDO N 12 2, ATIVO L 1, DATA D 8)
CREATE novo FROM estrutura_estendida
USE nome
USE clientes.dbf INDEX clientes_cod,clientes_nome ALIAS cadastro
USE nome EXCLUSIVE
USE
SELECT A
SELECT 2
SELECT cadastro
SELECT 0
GO TOP
GO BOTTOM
GO 10
SKIP
SKIP -1
? RECNO(), RECCOUNT(), EOF(), BOF()
LIST STRUCTURE
DISPLAY STATUS
```

Cada área tem ponteiro, filtro, índices abertos, índice controlador e FOUND próprios. EXACT e DELETED são globais. Fechar uma área não apaga o arquivo. SELECT 0 escolhe uma área livre, ou 1 se todas estiverem abertas.

## Incluir e alterar

```text
APPEND BLANK
APPEND
REPLACE NOME WITH 'ANA', SALDO WITH 100, ATIVO WITH .T., DATA WITH DATE()
REPLACE ALL SALDO WITH SALDO * 1.10 FOR ATIVO
REPLACE NEXT 3 SALDO WITH 0
REPLACE RECORD 2 NOME WITH 'BRUNO'
REPLACE SALDO WITH 0 WHILE SALDO < 100
REPLACE cadastro->SALDO WITH 250
EDIT
EDIT 2
CHANGE
```

REPLACE exige tipo compatível. Campos C são preenchidos com espaços e truncados. Valores numéricos que excedam a largura geram erro. Destinos qualificados em outra área são limitados a um registro por comando. Para percorrer registros ligados, use DO WHILE, SET RELATION e REPLACE de um registro.

## Listar, filtrar, buscar e agregar

```text
DISPLAY
DISPLAY NOME,SALDO
DISPLAY NEXT 3
LIST ALL
LIST ALL NOME,SALDO FOR ATIVO
LIST NOME,SALDO REST WHILE SALDO > 0
SET FILTER TO CIDADE = 'SAO PAULO'
SET FILTER TO
LOCATE FOR NOME = 'ANA'
CONTINUE
IF FOUND()
  DISPLAY
ENDIF
COUNT FOR ATIVO TO QUANTIDADE
SUM SALDO TO TOTAL
SUM SALDO,IDADE TO TOTAL_SALDO,TOTAL_IDADE
AVERAGE SALDO TO MEDIA
```

IF/ENDIF neste exemplo precisa estar em PRG. Sem escopo, LIST/COUNT/SUM/AVERAGE usam todos os registros visíveis. DISPLAY/REPLACE/DELETE/RECALL afetam o atual; FOR sem outro limite passa a todos; WHILE começa do atual. A posição final em escopos limitados não é certificada contra o dBASE original.

## Excluir

```text
DELETE
DELETE ALL FOR .NOT. ATIVO
SET DELETED ON
LIST ALL
SET DELETED OFF
RECALL ALL
PACK
SET SAFETY OFF
ZAP
SET SAFETY ON
```

DELETE marca; RECALL desmarca; PACK remove permanentemente e renumera; ZAP remove tudo. SAFETY ON exige confirmação SIM para ZAP/ERASE/DELETE FILE. Quando DELETED ON oculta os registros, use OFF para torná-los acessíveis a RECALL.

## Índices e relações

```text
INDEX ON CODIGO TO clientes_cod
INDEX ON UPPER(NOME) TO clientes_nome
INDEX ON CIDADE TO cidades UNIQUE
SET INDEX TO clientes_cod,clientes_nome
SET ORDER TO 2
SEEK 'ANA'
? FOUND()
FIND ANA
SET EXACT ON
SEEK 'ANA'
SET EXACT OFF
SET ORDER TO 0
REINDEX
SELECT A
SET RELATION TO CODIGO INTO pedidos
GO TOP
? pedidos->VALOR
SET RELATION TO
```

O nome depois de TO é uma chave de metadados dentro do banco, não um arquivo NDX. SET INDEX TO com um `.NDX` (dBASE III) ou `.NTX` (Clipper) existente na pasta lê a expressão-chave do cabeçalho e registra o índice no banco. UNIQUE filtra repetições da visão ordenada, sem impedir APPEND de chaves iguais. SEEK/FIND são sensíveis a maiúsculas. SET SOFTSEEK ON é extensão e pode posicionar na próxima chave maior.

## Copiar, importar e combinar

```text
COPY STRUCTURE TO clientes_vazio
COPY STRUCTURE TO clientes_curto FIELDS CODIGO,NOME
COPY TO estrutura STRUCTURE EXTENDED
CREATE outro FROM estrutura
COPY TO copia FOR ATIVO
COPY TO clientes_exportados DELIMITED
COPY TO clientes_planilha.csv
COPY TO clientes_fixos SDF
COPY TO clientes_legado.dbf
APPEND FROM copia
APPEND FROM clientes_exportados DELIMITED
APPEND FROM clientes_planilha.csv
APPEND FROM clientes_fixos SDF
APPEND FROM antigo.dbf
IMPORT FROM antigo.dbf TO convertido
SORT TO ordenado ON NOME/A,SALDO/D
SORT ON NOME TO por_nome DESCENDING
TOTAL ON CIDADE TO totais FIELDS SALDO
JOIN WITH pedidos TO combinado FOR CODIGO = pedidos->CODIGO FIELDS NOME,pedidos->VALOR
UPDATE ON CODIGO FROM movimentos REPLACE SALDO WITH SALDO + movimentos->VALOR RANDOM
```

COPY/SORT/TOTAL/JOIN sobre destino existente perguntam com SET SAFETY ON e sobrescrevem com OFF. DELIMITED usa o formato do dBASE em `.txt`: texto entre aspas, números sem espaços, datas AAAAMMDD, lógicos T/F, sem cabeçalho; `WITH c` troca as aspas e `WITH BLANK` separa por espaço. SDF usa colunas de largura fixa. CSV com cabeçalho é gravado quando o destino termina em `.csv` ou com `TYPE CSV`; datas ISO. APPEND FROM SQLite/CSV/DBF relaciona campos por nome; SDF/DELIMITED, pela posição. Campos ausentes recebem valores vazios. JOIN adiciona sufixos a nomes repetidos; o destino exclui memos. UPDATE precisa de chave simples em ambos os bancos; atualiza a primeira ocorrência da chave no destino. TOTAL agrupa em memória sem exigir ordenação prévia.

## Variáveis e funções

```text
PUBLIC RESULTADO
PRIVATE TEMP
VALOR = 100
STORE 10 TO A,B
PRIVATE ALL LIKE TMP*
RELEASE ALL EXCEPT KEEP*
? LEN('ABC'), SUBSTR('ABCDE',2,2), AT('BC','ABCDE')
? TRIM('ABC   '), UPPER('Ana'), STR(12.50,10,2)
? VAL('12.50'), ROUND(1.25,1)
? TYPE('VALOR')
? M->VALOR
SAVE TO memoria
SAVE TO nomes ALL LIKE NO*
SAVE TO outras ALL EXCEPT NO*
RESTORE FROM memoria ADDITIVE
```

TRIM remove apenas espaços à direita. Para ambos os lados, ALLTRIM está disponível como extensão. STR insere espaços à esquerda para respeitar a largura. TYPE recebe o texto da expressão e retorna C/N/L/D/U (no dialeto DBASE2 recebe o valor). SAVE grava JSON com tipos; RESTORE lê esse JSON ou um `.MEM` binário do dBASE III PLUS.

## Procedimentos e controle

```text
SET PROCEDURE TO rotinas
DO subprograma WITH VALOR, 'TEXTO', (OUTRO_VALOR)
SET PROCEDURE TO
```

Arquivo de procedimentos:

```text
PROCEDURE calcula
PARAMETERS PVALOR, PTAXA
PRIVATE TOTAL
TOTAL = PVALOR * PTAXA
PVALOR = PVALOR + TOTAL
RETURN
```

PRG com controle:

```text
I = 0
DO WHILE .T.
  I = I + 1
  DO CASE
  CASE I = 1
    LOOP
  CASE I = 5
    EXIT
  OTHERWISE
    ? I
  ENDCASE
ENDDO
RETURN
```

Comandos após RETURN não são executados. RETURN TO MASTER pode sair de subprogramas aninhados, retomando o programa principal. CANCEL interrompe a cadeia; QUIT fecha o interpretador.

Tratamento de erro:

```text
ON ERROR DO trata
* Comandos da aplicacao
ON ERROR
RETURN
PROCEDURE trata
? MESSAGE()
CANCEL
```

Dentro do handler, RETRY repete o comando com falha; RETURN continua no próximo comando. ERROR() retorna 1 para erro tratado, não o código histórico de erro dBASE. Um novo erro no próprio handler não é tratado recursivamente.

## Macros

```text
ARQUIVO = 'clientes'
USE &ARQUIVO
CAMPO = 'NOME'
? &CAMPO
COMANDO = "REPLACE NOME WITH 'ANA'"
&COMANDO
PREFIXO = 'clientes'
USE &PREFIXO..dbf
```

A primeira ocorrência de ponto termina o nome da macro. A segunda permanece como extensão. Macros são texto, não execução Python. Não se expandem dentro de literais. O limite de expansão impede recursão ilimitada.

## Datas

```text
SET DATE BRITISH
SET CENTURY ON
DATA = CTOD('10/10/2026')
? DTOC(DATA)
? DATA + 7
? DATA - CTOD('01/10/2026')
? YEAR(DATA), MONTH(DATA), DAY(DATA), DOW(DATA)
```

Anos de dois dígitos seguem a convenção histórica do século XX. Use quatro dígitos para datas de 2000 em diante. Armazenamento SQLite usa ISO; apresentação usa SET DATE. Literais `{data}` de dBASE IV não são aceitos.

## Tela e entrada

```text
CLEAR
NOME = SPACE(30)
IDADE = 0
@ 2,2 SAY 'Nome: ' GET NOME PICTURE '@!'
@ 3,2 SAY 'Idade: ' GET IDADE RANGE 0,120
READ
@ 5,2 SAY 'Saldo:'
@ 5,12 SAY 123.45 PICTURE '99999.99'
@ 7,2 TO 10,40
@ 7,2 TO 10,40 DOUBLE
@ 7,2 CLEAR TO 10,40
ACCEPT 'Cidade: ' TO CIDADE
INPUT 'Valor: ' TO VALOR
WAIT 'Pressione uma tecla' TO TECLA
```

O modelo é uma tela lógica 25x80, com coordenadas começando em zero. ANSI posiciona SAY; --plain o apresenta em linhas. READ oferece edição por tecla e navegação entre GETs em terminal interativo. SET CONFIRM OFF avança no último slot; ON exige Enter. --plain preserva entrada por linha. VALID, WHEN, @ PROMPT/MENU TO, SET FORMAT TO, APPEND/EDIT em tela e PICTURE com funções @R/@E/@B/@Z estão em FORMS.md.

## Saída em arquivo

```text
SET ALTERNATE TO relatorio
SET ALTERNATE ON
? 'RELATORIO'
? DATE()
TEXT
Texto literal que nao e interpretado como comandos.
ENDTEXT
SET ALTERNATE TO
```

SET CONSOLE OFF suprime a cópia no console e mantém a saída alternada. ADDITIVE abre arquivo para anexar. `?` termina a linha; `??` não. A impressora é emulada em arquivo: SET PRINTER TO, SET PRINT ON, SET DEVICE TO PRINT, ??? e EJECT (ver FORMS.md). LIST/DISPLAY/REPORT FORM aceitam TO PRINT e TO FILE.

## Arquivos e limites de execução

```text
DIR
DIR *.prg
COPY FILE entrada.txt TO copia.txt
RENAME copia.txt TO renomeado.txt
ERASE renomeado.txt
CLEAR MEMORY
CLOSE DATABASES
CLOSE ALL
QUIT
```

Somente caminhos sob --cwd. Não apague/renomeie/copíe fisicamente um banco aberto. COPY TO é a alternativa de cópia lógica do banco aberto. O interpretador não executa RUN, shell ou código assembly.

`--max-steps 100000` controla o orçamento global de comandos e iterações da cadeia de programas. Não é um timeout de tempo de parede. Expressões, funções e operações grandes de dados podem consumir memória/tempo antes de completar um passo. A profundidade de chamadas é limitada a 64 pela API. JOIN também limita seu número de combinações ao valor de max_steps.

## dBASE II do MSX

```text
SET DIALECT TO DBASE2        && ou python main.py --dialect dbase2
SELECT PRIMARY
USE alunos
SELECT SECONDARY
USE notasmat
JOIN TO fulltab FOR P.MATRICULA = S.MATRICULA FIELD NOME,BIM1
SET LINKAGE ON
DISPLAY ALL P.NOME,S.BIM1
STORE # TO REGPOS
DISPLAY FOR !(NOME) = "PEDRO"
? $("dBASE II",2,4), @("II","dBASE II"), RANK("A")
DO WHILE .NOT. EOF
  SKIP
ENDDO
5                            && igual a GO 5
INSERT BEFORE BLANK
CHANGE NEXT 2 FIELD NOME,IDADE
REPORT FORM notas            && sem notas.frm abre o diálogo
PLUS CPF "11144477735" TO OK
ERASE                        && limpa a tela
CLEAR                        && dBASE II: fecha bancos e apaga variáveis
```

## Estrutura e editor

```text
MODIFY STRUCTURE
MODIFY STRUCTURE (CODIGO N 5, NOME C 40, EMAIL C 60)
MODIFY COMMAND principal
```

MODIFY STRUCTURE preserva os registros pelo nome do campo e guarda a versão anterior em `nome_bak.sqlite`. MODIFY COMMAND abre o editor definido em VISUAL/EDITOR ou o Bloco de Notas no Windows.

## Arrays (extensão dBASE IV/Clipper/FoxPro)

```text
DECLARE MESES[12], TAB[3,2]
DIMENSION VALORES(10)
LOCAL TOTAL := 0, ITENS[5]
MESES[1] = "Janeiro"
STORE 0 TO TAB[1,1], TAB[1,2]
VALORES(3) = 15
LISTA = {"ANA", "BIA", {1, 2}}
? LISTA[3][2], ALEN(LISTA), ASCAN(LISTA, "BIA")
X = ASORT(MESES)
COPY TO ARRAY DADOS FIELDS NOME,LIMITE FOR ATIVO
APPEND FROM ARRAY DADOS
SCATTER MEMVAR
GATHER MEMVAR
@ 5,0 GET MESES[2]
```

Índices começam em 1; acesso fora dos limites é erro. Arrays criados num programa seguem PRIVATE/PUBLIC/LOCAL como as demais variáveis. Funções que alteram o array (AFILL, ASORT, AINS, ADEL, ASIZE, AADD, ACOPY) o modificam no lugar e o devolvem, por isso podem ser usadas em `X = AFILL(A, 0)`.
