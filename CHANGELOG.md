# Alterações

## 2.1

- GET exibe valor entre dois-pontos na posição da tela antes de READ.
- Editor por tecla, separadores saltados, validação de gabaritos e navegação entre GETs.
- SET CONFIRM ON/OFF, Control+S/Control+D, setas, Home/End, Backspace/Delete e Esc.
- SAY USING, SAVE ALL LIKE/EXCEPT, DISPLAY MEMORY com tipos e INPUT numérico.
- FORMS.md e dois exemplos novos de formulário, com memória e SQLite.
- Teste real em pseudo-terminal Linux, com restauração do terminal.

## 2.0

- Parser Pratt próprio para expressões, substituindo tradução para AST Python nas expressões do console.
- Compilador de blocos PRG e erros com origem/linha.
- Procedimentos, parâmetros por referência, escopo dinâmico PUBLIC/PRIVATE.
- Macros, atribuições, aliases e variáveis qualificadas.
- DO CASE, LOOP, EXIT, RETURN TO MASTER, TEXT, ON ERROR e RETRY.
- Funções de texto/número/data/ambiente ampliadas e funções de dialetos adicionais explícitas.
- Campos C preenchidos/truncados, datas tipadas e regras SET EXACT próximas da referência.
- Dez áreas, índices persistentes com UNIQUE, relações, JOIN e UPDATE.
- COPY STRUCTURE/STRUCTURE EXTENDED, CREATE FROM, SORT, TOTAL, APPEND FROM SQLite.
- SAY/GET/READ, máscaras básicas, RANGE, retângulos e saída alternada.
- Mapeamento .dbf para .sqlite e fallback CP850 para PRGs.
- Auditoria estática parcial --check e testes pela CLI.
- Documentação de compatibilidade, exemplos e referência consultada.

## 1.0

Primeiro console SQLite da conversa, com criação de campos, operações básicas, filtros e laços simples. O ZIP de origem fornecido pelo usuário incluía apenas o inicializador e dois arquivos Markdown, sem o motor mencionado em seu README.
