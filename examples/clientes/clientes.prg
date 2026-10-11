* CLIENTES.PRG - Cadastro de clientes no estilo dos sistemas dBASE
* Menu principal com @ PROMPT/MENU TO, formulario com GET/READ,
* consulta em BROWSE e relatorio. Os dados ficam em clientes.sqlite.
SET TALK OFF
SET SAFETY OFF
SET DELETED ON
SET CONFIRM ON
SET DATE BRITISH
SET CENTURY ON
SET MESSAGE TO 24

IF .NOT. FILE("clientes.sqlite")
  CREATE clientes (CODIGO N 5, NOME C 30, FONE C 15, CIDADE C 20, UF C 2, NASC D 8, LIMITE N 10 2, ATIVO L 1)
  USE
ENDIF
USE clientes
INDEX ON CODIGO TO cli_cod

PUBLIC M_CODIGO, M_NOME, M_FONE, M_CIDADE, M_UF, M_NASC, M_LIMITE, M_ATIVO
OPCAO = 1
DO WHILE .T.
  CLEAR
  @ 1,0 TO 3,79 DOUBLE
  @ 2,2 SAY "CADASTRO DE CLIENTES"
  @ 2,60 SAY DATE()
  @ 5,20 TO 16,58 DOUBLE
  @ 6,24 SAY "M E N U   P R I N C I P A L"
  @ 8,24 PROMPT "1. Incluir cliente    " MESSAGE "Cadastra um cliente novo"
  @ 9,24 PROMPT "2. Alterar cliente    " MESSAGE "Altera os dados de um cliente pelo codigo"
  @ 10,24 PROMPT "3. Excluir cliente    " MESSAGE "Marca ou desmarca um cliente para exclusao"
  @ 11,24 PROMPT "4. Consultar (BROWSE) " MESSAGE "Grade editavel: setas, Enter edita, Esc sai"
  @ 12,24 PROMPT "5. Relatorio          " MESSAGE "Lista os clientes na tela"
  @ 13,24 PROMPT "6. Compactar arquivo  " MESSAGE "Remove de vez os clientes excluidos (PACK)"
  @ 14,24 PROMPT "0. Sair               " MESSAGE "Encerra o sistema"
  @ 18,20 SAY "Clientes cadastrados: " + STR(RECCOUNT(),5)
  MENU TO OPCAO
  DO CASE
  CASE OPCAO = 1
    DO incluir
  CASE OPCAO = 2
    DO alterar
  CASE OPCAO = 3
    DO excluir
  CASE OPCAO = 4
    DO consultar
  CASE OPCAO = 5
    DO relatorio
  CASE OPCAO = 6
    DO compactar
  OTHERWISE
    EXIT
  ENDCASE
ENDDO
CLOSE DATABASES
CLEAR
? "Fim do sistema de clientes."
RETURN


PROCEDURE tela
PARAMETERS TITULO
CLEAR
@ 1,0 TO 3,79 DOUBLE
@ 2,2 SAY "CADASTRO DE CLIENTES - " + TITULO
@ 5,5 TO 17,74
@ 7,8 SAY "Codigo ......:"
@ 8,8 SAY "Nome ........:"
@ 9,8 SAY "Telefone ....:"
@ 10,8 SAY "Cidade ......:"
@ 11,8 SAY "UF ..........:"
@ 12,8 SAY "Nascimento ..:"
@ 13,8 SAY "Limite ......:"
@ 14,8 SAY "Ativo (S/N) .:"
RETURN


PROCEDURE carrega
M_CODIGO = CODIGO
M_NOME = NOME
M_FONE = FONE
M_CIDADE = CIDADE
M_UF = UF
M_NASC = NASC
M_LIMITE = LIMITE
M_ATIVO = IIF(ATIVO, "S", "N")
RETURN


PROCEDURE formulario
@ 8,23 GET M_NOME PICTURE "@!" VALID .NOT. EMPTY(M_NOME) ERROR "Informe o nome" MESSAGE "Nome completo do cliente"
@ 9,23 GET M_FONE PICTURE "(99) 99999-9999" MESSAGE "Telefone com DDD"
@ 10,23 GET M_CIDADE PICTURE "@!"
@ 11,23 GET M_UF PICTURE "!!" VALID M_UF $ "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO" ERROR "UF invalida"
@ 12,23 GET M_NASC
@ 13,23 GET M_LIMITE PICTURE "9999999.99" RANGE 0,9999999
@ 14,23 GET M_ATIVO PICTURE "!" VALID M_ATIVO $ "SN" ERROR "Responda S ou N"
READ
RETURN


PROCEDURE grava
REPLACE CODIGO WITH M_CODIGO, NOME WITH M_NOME, FONE WITH M_FONE, CIDADE WITH M_CIDADE
REPLACE UF WITH M_UF, NASC WITH M_NASC, LIMITE WITH M_LIMITE, ATIVO WITH (M_ATIVO = "S")
RETURN


PROCEDURE confirma
PARAMETERS PERGUNTA, RESPOSTA
RESPOSTA = "S"
@ 19,8 SAY PERGUNTA GET RESPOSTA PICTURE "!" VALID RESPOSTA $ "SN"
READ
RETURN


PROCEDURE incluir
CONTINUA = "S"
DO WHILE CONTINUA = "S"
  DO tela WITH "INCLUSAO"
  GO BOTTOM
  IF EOF()
    M_CODIGO = 1
  ELSE
    M_CODIGO = CODIGO + 1
  ENDIF
  M_NOME = SPACE(30)
  M_FONE = SPACE(15)
  M_CIDADE = SPACE(20)
  M_UF = "SP"
  M_NASC = CTOD("")
  M_LIMITE = 0
  M_ATIVO = "S"
  @ 7,23 SAY M_CODIGO PICTURE "99999"
  DO formulario
  IF EMPTY(M_NOME)
    EXIT
  ENDIF
  RESP = "S"
  DO confirma WITH "Grava o cliente? (S/N) ", RESP
  IF RESP = "S"
    APPEND BLANK
    DO grava
    @ 21,8 SAY "Cliente " + LTRIM(STR(M_CODIGO)) + " gravado."
  ENDIF
  DO confirma WITH "Incluir outro? (S/N) ", CONTINUA
ENDDO
RETURN


PROCEDURE localiza
PARAMETERS ACHOU
ACHOU = .F.
PCODIGO = 0
@ 7,23 GET PCODIGO PICTURE "99999" MESSAGE "Codigo do cliente (0 volta ao menu)"
READ
IF PCODIGO = 0
  RETURN
ENDIF
SEEK PCODIGO
IF FOUND()
  ACHOU = .T.
  DO carrega
  @ 7,23 SAY M_CODIGO PICTURE "99999"
  @ 8,23 SAY M_NOME
  @ 9,23 SAY M_FONE
  @ 10,23 SAY M_CIDADE
  @ 11,23 SAY M_UF
  @ 12,23 SAY M_NASC
  @ 13,23 SAY M_LIMITE PICTURE "9999999.99"
  @ 14,23 SAY M_ATIVO
ELSE
  @ 19,8 SAY "Cliente nao encontrado."
  WAIT
ENDIF
RETURN


PROCEDURE alterar
ACHOU = .F.
DO tela WITH "ALTERACAO"
DO localiza WITH ACHOU
IF ACHOU
  DO formulario
  RESP = "S"
  DO confirma WITH "Grava as alteracoes? (S/N) ", RESP
  IF RESP = "S"
    DO grava
  ENDIF
ENDIF
RETURN


PROCEDURE excluir
ACHOU = .F.
DO tela WITH "EXCLUSAO"
DO localiza WITH ACHOU
IF ACHOU
  RESP = "N"
  DO confirma WITH "Exclui este cliente? (S/N) ", RESP
  IF RESP = "S"
    DELETE
    @ 21,8 SAY "Cliente excluido. Use Compactar para remove-lo de vez."
    WAIT
  ENDIF
ENDIF
RETURN


PROCEDURE consultar
CLEAR
GO TOP
BROWSE FIELDS CODIGO, NOME, FONE, CIDADE, UF, LIMITE NOAPPEND FREEZE NOME
RETURN


PROCEDURE relatorio
CLEAR
? "RELACAO DE CLIENTES", DATE()
?
? "Codigo Nome                           Cidade               UF       Limite"
? REPLICATE("-", 78)
TOTAL = 0
GO TOP
DO WHILE .NOT. EOF()
  ? STR(CODIGO,6), NOME, CIDADE, UF, TRANSFORM(LIMITE, "@E 999,999.99")
  TOTAL = TOTAL + LIMITE
  SKIP
ENDDO
? REPLICATE("-", 78)
? "Total de limites:", TRANSFORM(TOTAL, "@E 9,999,999.99")
?
WAIT
RETURN


PROCEDURE compactar
RESP = "N"
CLEAR
DO confirma WITH "Remove de vez os clientes excluidos? (S/N) ", RESP
IF RESP = "S"
  PACK
  @ 21,8 SAY "Arquivo compactado."
  WAIT
ENDIF
RETURN
