# dBASE SQLite PLUS 2.1

Interpretador Python para executar programas PRG escritos com um conjunto ampliado de comandos dBASE III PLUS, mantendo os dados em SQLite. Inclui console, procedimentos, variáveis com escopo, parâmetros por referência, macros, expressões xBase, operações entre áreas e entrada/saída no terminal.

Esta versão amplia a implementação SQLite 2.0 entregue anteriormente. Não é o executável original, não emula MS-DOS e não oferece compatibilidade integral com qualquer aplicação dBASE III PLUS. A cobertura e as diferenças estão em [COMPATIBILITY.md](COMPATIBILITY.md). O parser rejeita comandos desconhecidos explicitamente.

Referência utilizada: David M. Kalman, *The dBASE Language Handbook*, 1989, no [PDF indicado](https://www.terrellamedia.com/wp-content/uploads/2022/01/dBASE-Language-Handbook-by-David-M-Kalman-Final.pdf). O livro trata vários dialetos. Recursos de Clipper/FoxBASE/dBASE IV que também foram incluídos são identificados como extensões. O PDF e os exemplos do livro não são redistribuídos neste pacote; os exemplos PRG aqui foram escritos para este projeto.

## Requisitos e início

Python 3.10 ou superior, sem pacotes externos. Windows, Linux e macOS. Testes executados em Python 3.12/Linux. O inicializador Windows foi incluído, mas não foi validado em uma máquina Windows nesta execução.

Extraia o ZIP e abra um terminal na pasta que contém `main.py`:

```bash
python main.py --cwd ./data
```

No Windows, também pode abrir `iniciar.bat`. Digite HELP para a referência de comandos e QUIT para sair. O ponto é o prompt e não faz parte do comando.

## Formulários da versão 2.1

GET exibe o valor entre dois-pontos, READ edita campos com máscaras e salta separadores. SET CONFIRM ON exige Enter; OFF permite avanço automático. Inclui Control+S/Control+D, navegação entre campos, SAY USING e SAVE ALL LIKE/EXCEPT. Veja [FORMS.md](FORMS.md) e os exemplos `formulario.prg` e `formulario_alunos.prg`.

## Seu próprio banco SQLite

```text
CREATE clientes
```

Informe os campos como `NOME TIPO LARGURA DECIMAIS`; uma linha vazia conclui:

```text
CODIGO N 5
NOME C 30
SALDO N 12 2
ATIVO L 1
CRIADO D 8
```

Ou use a extensão de criação em uma linha:

```text
CREATE clientes (CODIGO N 5, NOME C 30, SALDO N 12 2, ATIVO L 1, CRIADO D 8)
APPEND BLANK
REPLACE CODIGO WITH 1, NOME WITH 'ANA', SALDO WITH 1500.50, ATIVO WITH .T., CRIADO WITH DATE()
DISPLAY
DISPLAY STRUCTURE
USE
USE clientes
LIST ALL
```

Cada banco é um arquivo `nome.sqlite`, com uma tabela de registros e tabelas internas de metadados. CREATE abre o banco criado. Comandos de escrita persistem os dados imediatamente. SAVE salva variáveis de memória, não registros.

## Executar seu PRG

Coloque seus `.PRG` e suas dependências dentro do diretório escolhido em `--cwd`, junto com os bancos no formato desta implementação:

```bash
python main.py --cwd ./meu_sistema --cmd principal.prg
```

Para terminais sem ANSI ou para observar SAYs como linhas:

```bash
python main.py --cwd ./meu_sistema --cmd principal.prg --plain
```

Arquivos legados: UTF-8 é tentado primeiro; CP850 é o fallback. Se o programa usa outra codificação:

```bash
python main.py --cwd ./meu_sistema --cmd principal.prg --encoding cp1252
```

No console:

```text
SET PROCEDURE TO rotinas
DO principal
```

Nomes de arquivos são procurados sem distinguir maiúsculas/minúsculas quando há uma correspondência única. Os caminhos são restritos ao diretório `--cwd`; diretórios/drive letters DOS, SET DEFAULT e SET PATH não estão implementados. Adapte os caminhos legados ou organize os arquivos nesse diretório.

## Auditoria antes da execução

```bash
python main.py --cwd ./meu_sistema --check principal.prg
```

A auditoria compila os blocos e identifica parte dos comandos, configurações SET e funções não implementadas. Não executa o PRG. Retorna JSON e código de saída 2 quando detecta recurso não suportado. Quando não encontra erro, o status continua `needs_runtime_validation`: cláusulas, macros, procedimentos externos, tipos e comportamento de negócio ainda exigem execução e testes. Não certifica compatibilidade. Dependências DO e SET PROCEDURE precisam ser auditadas separadamente.

Erros em execução informam arquivo, linha e comando. Código de saída 1 indica falha; 0 indica término sem erro não tratado. CANCEL termina a cadeia de programas e pode produzir saída 0, assim como um ON ERROR que trate a falha.

## Demonstração completa

Prepare os dados e copie os programas de exemplo para uma pasta nova:

```bash
python examples/setup.py --cwd ./demo_data
python main.py --cwd ./demo_data --cmd negocios.prg --plain
```

O programa usa sintaxe dBASE III PLUS para percorrer clientes, chamar um procedimento com parâmetro por referência, buscar por índice, sincronizar uma relação, executar JOIN, atualizar limites com UPDATE, copiar a estrutura, usar CREATE FROM e gerar CSV/arquivo de saída.

Resultados esperados:

- 2 clientes de São Paulo, com limites originais somando 4000.
- O procedimento aumenta uma variável do chamador de 1000 para 1100.
- JOIN produz 3 registros de cliente/pedido.
- UPDATE altera os limites e a soma final chega a 6075.
- A linha final mostra `Validacao: .T.`.

O demo gera destinos novos. Execute novamente em outro diretório, pois CREATE/COPY de bancos não sobrescrevem arquivos existentes.

Menu interativo de consulta:

```bash
python main.py --cwd ./demo_data --cmd menu.prg
```

Escolha L para listar, B para buscar ou X para sair. A busca aceita um prefixo do nome. READ agora oferece edição por tecla e máscaras no terminal interativo; --plain mantém entrada por linha. Consulte [FORMS.md](FORMS.md).

## Procedimentos e parâmetros

Arquivo `rotinas.prg`:

```text
PROCEDURE aumenta
PARAMETERS PVALOR, PTAXA
PRIVATE TEMP
TEMP = PVALOR * PTAXA
PVALOR = PVALOR + TEMP
RETURN
```

Chamador:

```text
SET PROCEDURE TO rotinas
VALOR = 1000
DO aumenta WITH VALOR, 0.10
? VALOR
```

VALOR vira 1100. Uma variável simples passada em DO WITH é uma referência à variável do chamador. Campo, literal ou expressão é passado por valor. `(VALOR)` força uma expressão passada por valor. PARAMETERS deve ser o primeiro comando executável quando existem argumentos; as quantidades precisam coincidir.

PRIVATE oculta variáveis homônimas do chamador até terminar o procedimento. PUBLIC mantém uma variável disponível depois da chamada. Variáveis novas criadas num programa são liberadas quando ele termina. As variáveis existentes de um chamador permanecem acessíveis por escopo dinâmico.

## Comandos e expressões

Consulte [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) para exemplos de sintaxe e [COMPATIBILITY.md](COMPATIBILITY.md) antes de adaptar programas existentes.

Destaques: IF/ELSE/ENDIF, DO CASE, DO WHILE, LOOP, EXIT, RETURN, RETURN TO MASTER, DO WITH, PROCEDURE, PARAMETERS, PUBLIC, PRIVATE, macros `&nome`, referências `alias->campo` e `M->variavel`, TEXT/ENDTEXT, @ SAY/GET, PICTURE/RANGE, READ, ON ERROR e RETRY.

REPLACE valida os tipos: C/M recebem texto, N recebe número, L recebe lógico e D recebe data. Use CTOD para transformar texto em data. Campos C são preenchidos com espaços e truncados à largura, como no comportamento documentado no handbook. SET EXACT OFF compara o texto da direita como prefixo, preservando espaços; ON ignora espaços finais na igualdade. `==` é uma extensão que exige igualdade integral, incluindo espaços finais.

## SQLite e migração

`USE clientes.dbf` é traduzido para `clientes.sqlite`, permitindo manter esse nome nos PRGs. FILE, CREATE e comandos de arquivos também traduzem a extensão .dbf para .sqlite. Isso não importa nem lê DBF binário. Um DBF original não deve ser renomeado para SQLite: ele precisa de conversão externa para o formato de metadados deste projeto. NDX/MDX/DBT/FRM/MEM binários não são lidos.

Bancos SQLite criados pela versão 1.0 podem ser abertos pela 2.0. Ao abrir, é adicionada uma coluna de metadados de índices quando necessário. A 2.0 não foi projetada para permitir que a versão 1.0 volte a escrever nesses índices depois da atualização. Faça uma cópia se precisar manter ambas.

O banco usa `records`, `_schema` e `_indexes`; a exclusão lógica fica em `_deleted`. Os índices pertencem ao próprio SQLite, sem arquivo NDX. Chaves de campo simples também criam índices SQLite nativos, mas ordenação, filtragem e busca no console são avaliadas em Python. JOIN pode percorrer todas as combinações de registros. Este interpretador é indicado para estudos, aplicações locais pequenas e adaptação de lógica, não para grandes volumes ou equivalência de desempenho com o runtime original.

Numéricos são armazenados em REAL e podem ter aproximação de ponto flutuante. ROUND usa arredondamento decimal half-up na etapa de formatação/validação, mas isso não muda a representação do armazenamento para decimal exato. Não há atomicidade de PRG inteiro nem transação distribuída entre arquivos. Operações entre múltiplos bancos precisam de validação de negócio.

## API Python

```python
from dbase2py import DBaseEngine, Field

engine = DBaseEngine('./dados', plain=True)
try:
    engine.create('pessoas', [Field('NOME', 'C', 30), Field('IDADE', 'N', 3)])
    engine.append({'NOME': 'ANA', 'IDADE': 30})
    engine.execute('GO TOP')
    engine.execute('DISPLAY')
finally:
    engine.close()
```

## Validação e arquitetura

```bash
python -m unittest discover -s tests -v
```

A suíte cobre persistência, expressões, datas, escopo, parâmetros por referência, comandos de dados, índices, relações, arquivos, leitura de teclado, auditoria e execução dos exemplos pela CLI. Veja [VALIDATION.md](VALIDATION.md) para o resultado registrado nesta entrega.

Arquivos principais:

- `dbase2py/syntax.py`: lexer, cláusulas, comentários e abreviações.
- `dbase2py/expressions.py`: parser Pratt de expressões xBase.
- `dbase2py/program.py`: compilação e execução dos blocos PRG.
- `dbase2py/memory.py`: variáveis, escopo dinâmico e referências.
- `dbase2py/forms.py`: máscaras, editor de campos e teclado por plataforma.
- `dbase2py/functions.py`: funções de texto, número, data e ambiente.
- `dbase2py/engine.py`: comando, tela, índices e operações de dados.
- `dbase2py/storage.py`: camada de persistência e funcionalidades herdadas da 1.0.
- `dbase2py/compatibility.py`: auditoria estática parcial.
- `dbase2py/cli.py`: terminal e execução em lote.

O ZIP original recebido não incluía o módulo dbase2py citado em seu README. A pasta `original` preserva os três arquivos recebidos; suas alegações sobre um motor ausente não foram usadas como evidência de funcionalidades existentes. A implementação nova foi construída nesta conversa.
