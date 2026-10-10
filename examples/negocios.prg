* Exemplo composto neste projeto. Nao copia trechos do handbook.
SET TALK OFF
SET CENTURY ON
SET DATE BRITISH
SET PROCEDURE TO rotinas
ON ERROR DO registra_erro
PUBLIC DEMO_OK, TOTAL_GERAL, LIMITE_NOVO, CONTADOR
DEMO_OK = .F.
CONTADOR = 0
TOTAL_GERAL = 0
USE clientes.dbf INDEX clientes_cod,clientes_nome ALIAS clientes
SELECT B
USE pedidos.dbf INDEX pedidos_cod ALIAS pedidos
SELECT clientes
GO TOP
DO WHILE .NOT. EOF()
  IF ATIVO .AND. CIDADE = "SAO PAULO"
    TOTAL_GERAL = TOTAL_GERAL + LIMITE
    CONTADOR = CONTADOR + 1
  ENDIF
  SKIP
ENDDO
? "Clientes de SP: " + LTRIM(STR(CONTADOR))
? "Limites de SP: " + LTRIM(STR(TOTAL_GERAL,12,2))
LIMITE_NOVO = 1000
DO aumenta WITH LIMITE_NOVO, 0.10
IF LIMITE_NOVO <> 1100
  ? "Falha na passagem de parametro por referencia"
  CANCEL
ENDIF
SET ORDER TO 2
SEEK "BRU"
IF FOUND()
  DISPLAY NOME, LIMITE, CRIADO
ENDIF
SET ORDER TO 1
SET RELATION TO CODIGO INTO pedidos
GO 1
IF FOUND("pedidos")
  ? "Primeiro pedido: " + STR(pedidos->VALOR,10,2)
ENDIF
JOIN WITH pedidos TO clientes_pedidos FOR CODIGO = pedidos->CODIGO ;
  FIELDS NOME,pedidos->VALOR
SET RELATION TO
SELECT C
USE movimentos ALIAS movimentos
SELECT clientes
UPDATE ON CODIGO FROM movimentos REPLACE LIMITE WITH LIMITE + movimentos->VALOR RANDOM
COPY STRUCTURE TO cadastro_vazio
COPY TO estrutura_clientes STRUCTURE EXTENDED
CREATE cadastro_novo FROM estrutura_clientes
USE clientes INDEX clientes_cod
COUNT FOR ATIVO TO CONTADOR
SUM LIMITE TO TOTAL_GERAL
COPY TO clientes_exportados DELIMITED
SET ALTERNATE TO resultado
SET ALTERNATE ON
? "Clientes: " + STR(CONTADOR,5)
? "Total atualizado: " + STR(TOTAL_GERAL,12,2)
SET ALTERNATE TO
DEMO_OK = CONTADOR = 3 .AND. TOTAL_GERAL = 6075
? "Validacao: ", DEMO_OK
ON ERROR
CLOSE ALL
RETURN
