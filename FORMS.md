# Formulários, GET e READ, versão 2.2

Esta atualização implementa o comportamento de entrada descrito pelo usuário para dBASE II e o integra ao interpretador PRG/SQLite. O editor é nativo no terminal moderno; não emula MSX/DOS.

## SAY, USING e GET

```text
STORE 40 TO TEMP
@ 0,0 SAY "O valor da temperatura é: " GET TEMP
```

GET exibe imediatamente o valor entre dois-pontos. Não exige SAY:

```text
@ 1,0 GET TEMP
```

SAY aceita USING e PICTURE para apresentação:

```text
@ 2,0 SAY TEMP USING "999.99"
```

Quando SAY e GET compartilham a linha, cada um pode ter seu próprio gabarito:

```text
@ 3,0 SAY 40 USING "999.99" GET TEMP PICTURE "999.99"
```

Os comandos @ são executados separadamente, uma linha de PRG por comando. O ponto do prompt não deve ser colocado no arquivo.

## Máscaras de entrada

```text
STORE SPACE(10) TO DATA
@ 0,0 SAY "Data " GET DATA PICTURE "99/99/9999"
READ
```

GET apresenta `Data :  /  /    :`. No terminal interativo, digite `01022024`: o cursor salta as barras e a variável DATA recebe `01/02/2024`. Também são aceitos os separadores digitados explicitamente. Neste exemplo DATA é texto; a máscara não verifica se a data existe no calendário. Use uma variável ou campo de tipo D para validar a data.

| Símbolo | Entrada/saída |
| :--- | :--- |
| 9 e # | Dígitos ASCII; número aceita sinal na primeira posição |
| X | Caractere imprimível, incluindo texto e pontuação |
| !, @! | Converte para maiúsculas |
| A | Letras |
| L, Y | Lógico, T/F ou Y/N |
| /, -, vírgula | Separador fixo que o editor salta |
| ponto | Separador decimal fixo |

O campo de texto sem máscara usa a largura atual da variável ou a largura declarada do campo SQLite. Campos numéricos usam largura do campo ou dez posições por padrão; os decimais podem ser especificados explicitamente em PICTURE. Campos D usam o formato de SET DATE e SET CENTURY.

A máscara fica na tela e controla a entrada: não é apenas formatação posterior. Valores numéricos são convertidos para número antes da gravação. `@R` em texto remove os separadores da variável, uma extensão disponível. Máscaras históricas adicionais não presentes nesta lista continuam fora da cobertura.

## Vários campos e confirmação

```text
STORE SPACE(15) TO NOME
STORE SPACE(10) TO DATA
@ 0,0 SAY "Nome " GET NOME PICTURE "XXXXXXXXXXXXXXX"
@ 1,0 SAY "Data " GET DATA PICTURE "99/99/9999"
READ
```

READ consome os GETs na ordem de declaração. Cada valor é confirmado e gravado ao sair do campo, tanto para variáveis quanto para campos do registro SQLite.

- SET CONFIRM OFF, padrão: o último caractere editável avança automaticamente.
- SET CONFIRM ON: RETURN/Enter confirma mesmo quando a máscara está completa.
- Enter em um campo sem alteração mantém seu valor.
- Tab/baixo avançam; cima/Shift+Tab voltam ao campo anterior.
- Esquerda/Control+S e direita/Control+D deslocam o cursor, pulando separadores.
- Home/End levam ao começo/fim do campo.
- Backspace e Delete apagam posições editáveis.
- Esc abandona o campo atual sem gravar sua alteração; campos anteriores já confirmados permanecem gravados.
- Control+C interrompe a entrada e restaura o modo do terminal.

O primeiro caractere imprimível inicia um novo valor no campo. Se mover o cursor antes de digitar, você edita o conteúdo existente. O modo padrão é de sobrescrita; Insert ou Control+V alternam para inserção. Letras recusadas por uma posição numérica produzem um aviso sonoro; RANGE inválido mantém o foco para correção.

READ sem GET pendente gera erro. CLEAR GETS descarta a fila, mantendo o desenho na tela:

```text
STORE SPACE(15) TO NOME
@ 0,0 SAY "Nome " GET NOME
CLEAR GETS
STORE SPACE(10) TO DATA
@ 1,0 SAY "Data " GET DATA PICTURE "99/99/9999"
READ
```

Somente DATA fica editável neste exemplo.

## Registro de uma tabela

```text
USE alunos
GO 1
@ 0,0 SAY "Nome " GET NOME
READ
```

Após a confirmação, o campo do registro é atualizado em SQLite. Não é necessário executar REPLACE ou SAVE. O destino também pode ser qualificado com alias->campo ou M->variavel.

## INPUT e ACCEPT

```text
INPUT "Valor do produto: " TO VALOR
ACCEPT "Nome: " TO NOME
INPUT TO OUTRO_VALOR
ACCEPT TO OUTRO_NOME
```

A mensagem é opcional. INPUT exige resultado numérico, podendo receber uma expressão numérica como `100 + 50`. Texto ou lógico é rejeitado. ACCEPT preserva a linha recebida como texto. Esses comandos são entrada de linha e não usam o editor GET.

## Variáveis

```text
RELEASE NOME
RELEASE ALL
RELEASE ALL LIKE NO*
RELEASE ALL EXCEPT KEEP*
SAVE TO variav
SAVE TO nomes ALL LIKE NO*
SAVE TO outras ALL EXCEPT NO*
RESTORE FROM variav
RESTORE FROM variav ADDITIVE
DISPLAY MEMORY
```

LIKE e EXCEPT selecionam nomes com * e ?. RESTORE sem ADDITIVE apaga as variáveis atuais antes de carregar; com ADDITIVE as preserva, substituindo nomes coincidentes pelos valores do arquivo. DISPLAY MEMORY apresenta nome, tipo C/N/L/D e valor. SAVE/RESTORE continuam usando JSON tipado, não o formato MEM binário original.

## Executar os exemplos

Copie `examples/formulario.prg` para a pasta escolhida em --cwd. Não é necessário preparar bancos:

```bash
python main.py --cwd ./meus_formularios --cmd formulario.prg
```

Para testar gravação SQLite, copie também `examples/formulario_alunos.prg` para essa pasta:

```bash
python main.py --cwd ./meus_formularios --cmd formulario_alunos.prg
```

O segundo programa cria alunos.sqlite quando não existe, abre o primeiro registro e apresenta o formulário com confirmação por Enter.

## Terminal e limites

O modo por tecla é ativado quando há um terminal interativo e --plain está desativado. Windows usa msvcrt; Linux/macOS usam terminal POSIX e ANSI. Em --plain ou entrada redirecionada, há fallback de linha: as máscaras continuam validadas, mas é necessário Enter e não há salto visual/autoconfirmação durante a digitação.

A tela lógica continua 25x80. Campos maiores que o espaço disponível são desenhados com recorte; não há rolagem horizontal. Arquivos `.FMT` (texto com @ SAY/GET) são usados com SET FORMAT TO; relatórios `.FRM` estão descritos abaixo. O editor teve teste real em pseudo-terminal Linux; a implementação Windows foi incluída, mas não executada em Windows nesta entrega.

## Novidades da versão 2.2

### Teclas do editor

Além das teclas acima: Control+E/Control+X vão ao campo anterior/seguinte, Control+G apaga o caractere sob o cursor (puxando o restante), Control+Y apaga o campo, Control+V ou Insert alternam inserção, Control+W grava e sai, Control+Q abandona como Esc, PgUp/Control+R e PgDn trocam de registro em EDIT, Control+U marca ou desmarca a exclusão do registro em APPEND/EDIT. Control+C continua interrompendo o programa.

### Delimitadores e destaque

```text
SET COLON OFF                  && dBASE II: sem os dois-pontos
SET DELIMITERS TO "[]"         && dBASE III: [valor]
SET DELIMITERS TO DEFAULT
SET INTENSITY OFF              && sem vídeo reverso quando não há delimitadores
```

### Validação e campos condicionais (extensão dBASE IV/Clipper)

```text
@ 5,0 SAY "Nota " GET NOTA PICTURE "99.9" VALID NOTA <= 10 ERROR "Nota de 0 a 10"
@ 6,0 SAY "Obs  " GET OBS WHEN NOTA < 5 MESSAGE "Justifique a nota baixa"
READ
```

VALID é avaliado depois de gravar o valor; se for falso, o valor anterior é restaurado e o cursor permanece no campo. WHEN falso salta o GET. MESSAGE aparece na linha 25.

### Telas de registro: APPEND, EDIT, CHANGE e INSERT

APPEND mostra `Registro 00011` e um GET por campo. Enter no primeiro campo de um registro novo, sem digitar nada, encerra e descarta o registro vazio, como no dBASE II. SET CARRY ON copia os valores do registro anterior. EDIT n, CHANGE [escopo] FIELDS lista [FOR condição] e INSERT [BEFORE] [BLANK] usam a mesma tela.

### Formatos de tela (SET FORMAT)

```text
* cliente.fmt
@ 1,0 SAY "Codigo " GET CODIGO PICTURE "99999"
@ 2,0 SAY "Nome   " GET NOME PICTURE "@!"
```

```text
USE clientes
SET FORMAT TO cliente
APPEND                && usa cliente.fmt em cada registro novo
EDIT 3
READ                  && sem GETs pendentes, também usa o formato
CLOSE FORMAT
```

No dBASE II, `SET FORMAT TO PRINTER` envia os @ SAY seguintes para a impressora e `SET FORMAT TO SCREEN` volta para a tela.

### PICTURE e TRANSFORM

| Exemplo | Resultado |
| :--- | :--- |
| `@ 0,0 SAY 150.45 USING "###.#"` | `150.4` |
| `@ 0,0 SAY "12-10-2024" USING "XX/XX/XXXX"` | `12/10/2024` (literal ocupa a posição) |
| `TRANSFORM("12345678901","@R 999.999.999-99")` | `123.456.789-01` (literal inserido) |
| `TRANSFORM(1234.5,"@E 999,999.99")` | `  1.234,50` |
| `TRANSFORM(-5,"@( 999")` | `(5)` |
| `TRANSFORM(0,"@Z 999")` | três espaços |

Campos N com decimais usam o gabarito `999.99` conforme a estrutura, em vez de `######`.

### Molduras, menus e telas salvas

```text
@ 2,10 TO 10,60 DOUBLE
@ 4,12 PROMPT "1. Cadastrar" MESSAGE "Inclui alunos"
@ 5,12 PROMPT "2. Sair"
MENU TO OPCAO          && extensão Clipper: setas, Enter, Esc ou letra inicial
SAVE SCREEN TO TELA
CLEAR
RESTORE SCREEN FROM TELA
```

### Impressora

```text
SET PRINTER TO relatorio.txt
SET DEVICE TO PRINT
@ 2,5 SAY "Relatório"
EJECT
SET DEVICE TO SCREEN
SET PRINT ON
? "linha também impressa"
SET PRINT OFF
```

A impressora é um arquivo texto dentro de --cwd (`impressora.txt` por padrão). `@ SAY` com linha menor que a atual gera salto de página (form feed). `PROW()` e `PCOL()` informam a posição.

### Relatórios

```text
CREATE REPORT notas          && diálogo do dBASE II
REPORT FORM notas FOR SERIE = 6 TO PRINT
REPORT FORM vendas TO FILE vendas.txt HEADING "Dezembro" SUMMARY
```

REPORT FORM lê o FRM binário do dBASE III PLUS/Clipper e o formato JSON gravado por CREATE REPORT.

### BROWSE em grade

```text
USE clientes
BROWSE
BROWSE FIELDS CODIGO,NOME,LIMITE FREEZE LIMITE
BROWSE NOAPPEND NODELETE WIDTH 20
```

| Tecla | Ação |
| :--- | :--- |
| Setas, PgUp, PgDn | Registro anterior/seguinte, página |
| Tab, Shift+Tab, Home, End, ←, → | Campo seguinte/anterior, primeiro/último |
| Enter ou digitar | Edita a célula com a máscara do campo; Enter grava e vai ao próximo campo |
| ↓ na última linha | Inclui registro; se nada for digitado ele é descartado |
| Control+U | Marca ou desmarca a exclusão |
| Esc, Control+W | Sai, deixando o ponteiro no registro selecionado |

Campos memo aparecem como `memo` (vazio) ou `MEMO` e não são editados na grade.

### Etiquetas

```text
CREATE LABEL clientes        && largura, altura, margem, espaçamentos, etiquetas por linha e linhas
LABEL FORM clientes SAMPLE TO PRINT
LABEL FORM clientes FOR UF = "SP" TO FILE etiquetas.txt
```

Uma linha `NOME` imprime o campo; `CIDADE, "-", UF` apara e une os itens por espaço. Linhas que ficam vazias sobem. Arquivos `.LBL` do dBASE III PLUS são lidos diretamente.

### Monitor de fósforo e cores

```bash
python main.py --cwd dados                  # fósforo verde no terminal
python main.py --cwd dados --monitor ambar
python main.py --cwd dados --monitor nenhum # cores do próprio terminal
```

```text
SET MONITOR TO VERDE          && também AMBAR, BRANCO, CORES, NENHUM
SET COLOR TO W+/B,N/W         && padrão branco brilhante sobre azul, realce preto sobre branco
SET COLOR TO                  && volta ao monitor escolhido
```

O texto comum usa a cor padrão sobre fundo preto; GETs sem delimitadores, opções de menu e a célula do BROWSE usam o realce (vídeo reverso). Códigos de SET COLOR: N preto, B azul, G verde, BG ciano, R vermelho, RB magenta, GR marrom/amarelo, W branco, `+` brilhante, `*` piscante, U sublinhado, I inverso, X invisível.
