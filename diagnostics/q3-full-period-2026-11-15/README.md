# Q3 de 2012 a 2021 — teste independente

Execução única de 15 de novembro de 2026, com quatro workers. O teste foi
feito em uma cópia do coletor anterior, retirando da consulta Q3 o filtro
`WHERE year(DTNASC) = 2018`. O SQL efetivamente executado está nos
[metadados](Q3-run-001.json). O campo genérico `target_year` preserva a
configuração do coletor anterior. O período de Q3 é definido pelo SQL, que
varre os dez anos da entrada. O coletor reaproveitou um metadado de entrada
em cache, portanto o teste não obteve um novo hash do Parquet.

O [registro da execução](Q3-run-001.jsonl) contém 270 frames. O último frame
totaliza 28.789.402 linhas e 27 UFs. Em 274 pares frame–UF, a taxa parcial
difere da taxa final da mesma UF. Os agregados finais coincidem com os de Q3
nas duas fases oficiais.

Na coleta oficial, `phases/01-fixed-order/harness/queries.mjs` já contém Q3
para o período completo. As duas fases têm seus próprios registros. Este
diretório guarda a verificação adicional fora das entradas usadas para
gerar as tabelas e figuras do manuscrito.
