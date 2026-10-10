* Formulario em memoria, sem necessidade de bancos de demonstracao.
CLEAR
SET CONFIRM OFF
STORE SPACE(15) TO NOME
STORE SPACE(10) TO DATA
STORE 40 TO TEMP
@ 0,0 SAY "Nome " GET NOME PICTURE "XXXXXXXXXXXXXXX"
@ 1,0 SAY "Data " GET DATA PICTURE "99/99/9999"
@ 2,0 SAY "Temperatura " GET TEMP PICTURE "999.9"
READ
@ 4,0 SAY "Nome digitado: "
@ 4,16 SAY NOME
@ 5,0 SAY "Data digitada: "
@ 5,16 SAY DATA
@ 6,0 SAY "Temperatura: "
@ 6,16 SAY TEMP USING "999.9"
SAVE TO formulario_vars ALL LIKE N*
RETURN
