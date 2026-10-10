# Formulários, GET e READ, versão 2.1

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

O primeiro caractere imprimível inicia um novo valor no campo. Se mover o cursor antes de digitar, você edita o conteúdo existente. O modo é de sobrescrita: não há inserção/deslocamento de caracteres. Letras recusadas por uma posição numérica produzem um aviso sonoro; RANGE inválido mantém o foco para correção.

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

A tela lógica continua 25x80. Campos maiores que o espaço disponível são desenhados com recorte; não há rolagem horizontal. Nenhum formulário binário FMT/FRM é importado. A aplicação precisa definir os GETs em PRG. O editor teve teste real em pseudo-terminal Linux; a implementação Windows foi incluída, mas não executada em Windows nesta entrega.
