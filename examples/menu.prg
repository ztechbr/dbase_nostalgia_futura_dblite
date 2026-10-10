* Cadastro de consulta com menu no terminal. Digite X para encerrar.
SET TALK OFF
USE clientes INDEX clientes_nome
PRIVATE OPCAO, PESQUISA
DO WHILE .T.
  CLEAR
  @ 1,2 SAY "CADASTRO DE CLIENTES - SQLite"
  @ 3,2 SAY "L - Listar | B - Buscar | X - Sair"
  OPCAO = SPACE(1)
  @ 5,2 SAY "Opcao: " GET OPCAO PICTURE "!"
  READ
  DO CASE
  CASE OPCAO = "L"
    LIST ALL NOME,CIDADE,LIMITE
    WAIT "Pressione uma tecla para continuar"
  CASE OPCAO = "B"
    PESQUISA = SPACE(30)
    @ 7,2 SAY "Nome ou prefixo: " GET PESQUISA PICTURE "!"
    READ
    SEEK TRIM(PESQUISA)
    IF FOUND()
      DISPLAY NOME,CIDADE,LIMITE
    ELSE
      ? "Cliente nao encontrado"
    ENDIF
    WAIT "Pressione uma tecla para continuar"
  CASE OPCAO = "X"
    EXIT
  OTHERWISE
    ? "Opcao invalida"
  ENDCASE
ENDDO
USE
RETURN
