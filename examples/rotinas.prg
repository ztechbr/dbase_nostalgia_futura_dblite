* Procedimentos originais do projeto, usando sintaxe dBASE III PLUS.
PROCEDURE aumenta
PARAMETERS PVALOR, PTAXA
PRIVATE TEMP
TEMP = PVALOR * PTAXA
PVALOR = PVALOR + TEMP
RETURN

PROCEDURE registra_erro
? "Erro de interpretacao: " + MESSAGE()
CANCEL
