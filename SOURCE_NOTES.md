# Referência de interpretação

Fonte indicada pelo usuário: David M. Kalman, *The dBASE Language Handbook*, Microtrend Books, 1989.

URL: https://www.terrellamedia.com/wp-content/uploads/2022/01/dBASE-Language-Handbook-by-David-M-Kalman-Final.pdf

A fonte foi aberta como PDF e seu texto foi consultado para especificar comportamento. O PDF disponível tem 979 páginas. O livro inclui dBASE III PLUS, dBASE IV, Clipper, FoxBASE+, dBXL e Quicksilver. Não se assumiu que todas as opções descritas pertencem ao III PLUS.

## Verbetes consultados e aplicação

| Verbete no handbook | Decisão no interpretador |
| :--- | :--- |
| Operadores e SET EXACT | Comparação por prefixo em OFF; espaços finais ignorados em ON; == como extensão |
| DO WHILE/ENDDO | Aninhamento, LOOP/EXIT e expansão de macro da condição uma vez no III PLUS |
| DO CASE/CASE/ENDCASE | Primeira condição verdadeira, com OTHERWISE |
| PARAMETERS | DO WITH; variável por referência; campo/expressão por valor; quantidade coincidente |
| PRIVATE/PUBLIC | Ocultação de variáveis e restauração do chamador |
| PROCEDURE/SET PROCEDURE | Carregamento de biblioteca e pesquisa de procedimento antes do arquivo PRG |
| RETURN | Volta ao chamador, limpeza do escopo e TO MASTER |
| REPLACE | Tipo compatível, truncamento de texto e destino alias->campo |
| COUNT/SUM/AVERAGE | Escopos, FOR/WHILE e TO |
| SEEK/SET ORDER | Prefixos, FOUND, lista de índices e controle por posição |
| BOF/EOF | Primeiro registro continua acessível em BOF; sem banco retorna falso |
| COPY STRUCTURE/STRUCTURE EXTENDED/CREATE FROM | Criação de banco a partir da descrição de campos |
| JOIN | Combinações de registros, condição e referência qualificada |
| UPDATE | Chave, origem em outra área, RANDOM e primeira chave duplicada no destino |
| SET RELATION | Sincronização de ponteiro do filho pelo pai |
| CTOD/DTOC/SET DATE/SET CENTURY | Data tipada, formato selecionado e anos de dois dígitos no século XX |
| STR/VAL/TRIM/IIF | Funções de conversão e manipulação usuais |
| @ SAY/GET/PICTURE/RANGE/READ | Subconjunto de apresentação e entrada, adaptado ao terminal moderno |
| ON ERROR/RETRY | Handler de PRG e repetição limitada pelo orçamento de execução |

A matriz COMPATIBILITY.md distingue implementação, adaptação, extensão e recursos ausentes. Os cenários de teste e os exemplos são originais deste projeto; não são cópias dos exemplos do livro. O PDF permanece fora do pacote. A consulta ao handbook não substitui teste diferencial com um runtime dBASE III PLUS, que não esteve disponível nesta execução.
