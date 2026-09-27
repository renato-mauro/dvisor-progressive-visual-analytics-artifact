# Relatório do experimento de ordem física e concorrência

## Conclusão executiva

Os resultados fornecem evidência computacional favorável à hipótese de que
visualizações construídas a partir dos resultados parciais entregues pelo
DVISOR podem oferecer informação relevante antes do processamento completo.
Essa antecipação não é uma propriedade única nem independente do contexto:
ela depende da consulta, da tarefa visual e da representatividade dos
fragmentos já processados.

O encadeamento conceitual avaliado é:

`DVISOR (execução) -> resultados parciais -> camada de apresentação -> visualização parcial -> percepção -> tomada de decisão`

O experimento mede diretamente os resultados parciais e propriedades das
visualizações que podem ser construídas a partir deles. Percepção e tomada de
decisão não foram medidas diretamente. Assim, fidelidade e cobertura são
proxies computacionais da informação potencialmente disponível ao usuário.

A análise revisada de Q3 abandona a suposição de um único tempo de fidelidade
visual. Ela separa fidelidade da ordenação entre UFs visíveis, recuperação do
top-5 final e cobertura do domínio. Essa decomposição mostra que uma resposta
pode ser localmente fiel, útil para identificar categorias de maior destaque
e ainda globalmente incompleta.

## Validade da coleta

- 90 execuções medidas: 10 ordens físicas x 3 consultas x 3 quantidades de
  threads;
- uma execução por combinação e nenhum warmup;
- 90 rastros válidos, nenhum ausente e nenhum inválido;
- 810 frames de Q1, 8.100 de Q2 e 8.100 de Q3;
- frações de linhas monotônicas e final igual a 1 em todos os rastros;
- um único hash final por consulta nas 30 condições, confirmando que ordem e
  threads não alteraram a resposta final;
- sequência aleatória de execução preservada integralmente.

As novas métricas foram recalculadas offline a partir dos mesmos rastros. Não
houve repetição das consultas nem alteração da coleta.

## Definições operacionais revisadas

Todos os eventos correspondem ao primeiro limiar mantido por três frames
consecutivos.

Para Q1 e Q2 são mantidos os eventos originais:

- TNC: erro normalizado menor ou igual a 0,05;
- TVF: métrica estrutural específica da tarefa maior ou igual a 0,90;
- TSV: similaridade entre frames consecutivos maior ou igual a 0,99.

Para Q3, fidelidade passa a ser tratada como multidimensional:

- **TNC-visible**: NMAE menor ou igual a 0,05 entre as UFs já visíveis e seus
  valores finais;
- **TVF-rank**: Spearman maior ou igual a 0,90 entre as UFs já visíveis;
- **TVF-top5-80**: pelo menos quatro das cinco UFs do top-5 final recuperadas;
- **TVF-top5-100**: todas as cinco UFs do top-5 final recuperadas;
- **TCov-90**: pelo menos 90% das UFs presentes na resposta;
- **TSV**: estabilidade do ranking entre frames consecutivos maior ou igual a
  0,99.

TNC-visible, TVF-rank e os eventos de top-5 só são elegíveis depois que pelo
menos cinco UFs foram observadas. Esse suporte mínimo evita declarar
fidelidade com base em apenas duas ou três categorias. TCov-90 permanece uma
medida independente de completude e não é incorporada à definição de TVF.

## Resultados de Q1 e Q2

Os valores abaixo são as medianas das nove permutações para 1, 2 e 4 threads.
Valores menores representam maior antecipação.

| Consulta | TNC nas permutações | TVF nas permutações | TSV nas permutações | Ordem identidade: TNC / TVF / TSV |
|---|---:|---:|---:|---:|
| Q1 temporal | 18,7%-20,8% | 31,1%-32,6% | 40,5%-45,5% | 12,5% / 40,2%-45,0% / 52,3%-57,0% |
| Q2 distribuição | 4,10%-4,25% | 0,43%-0,59% | 3,45%-4,39% | 69,75%-69,76% / 9,84%-9,85% / 0,88%-1,11% |

Q2 apresenta a separação mais forte entre forma visual e exatidão numérica.
Nas permutações, TVF ocorreu tipicamente com menos de 0,6% das linhas e TNC
com cerca de 4%. A exceção foi `shuf05`, cujo TNC exigiu aproximadamente 33%.
Na ordem identidade, TNC exigiu cerca de 69,8%, embora TVF tenha ocorrido em
9,8%. Portanto, a estrutura da distribuição pode tornar-se fiel muito antes
do critério numérico mais estrito.

Q1 é mais sensível à ordem e ao escalonamento. As medianas são semelhantes
entre 1, 2 e 4 threads, mas algumas combinações individuais apresentam
trajetórias distintas. Como Q1 possui apenas 27 fragmentos relevantes, cada
conclusão de fragmento tem influência proporcionalmente maior.

## Q3: fidelidade multidimensional

| Evento | Mediana nas permutações | Ordem identidade | Interpretação |
|---|---:|---:|---|
| TNC-visible | 1,91%-2,13% | 6,29%-6,31% | taxas das UFs visíveis próximas dos valores finais |
| TVF-rank | 1,91%-2,13% | 6,29%-6,31% | ordenação local das UFs visíveis fiel |
| TVF-top5-80 | 9,30%-9,94% | 68,26%-68,79% | quatro das cinco UFs finais identificadas |
| TVF-top5-100 | 26,69%-27,78% | 71,79%-72,68% | top-5 final integralmente identificado |
| TCov-90 | 19,74%-20,03% | 79,41%-79,44% | pelo menos 90% das UFs presentes |
| TSV | 0,95%-1,07% | 0,83%-0,93% | pouca mudança entre frames consecutivos |

TNC-visible e TVF-rank ainda coincidem aproximadamente, mas agora por uma
razão interpretável: quando o suporte mínimo de cinco UFs é alcançado, tanto
o erro numérico quanto a ordenação local já satisfazem seus limiares. Essa
coincidência não é usada como evidência suficiente de utilidade global. Os
eventos top-5 e cobertura descrevem propriedades distintas e ocorrem em
momentos substancialmente diferentes.

Nas permutações, quatro das cinco UFs mais relevantes são recuperadas após
aproximadamente 9%-10% das linhas, enquanto 90% do domínio aparece por volta
de 20%. A identificação integral do top-5 exige tipicamente 27%-28%. Portanto,
uma visualização parcial pode fornecer evidência útil para uma tarefa de
identificação das categorias de maior destaque antes de estar completa, mas
o critério mais rigoroso ainda requer uma fração maior dos dados.

## Qualidade em marcos fixos

Considerando conjuntamente as 27 execuções permutadas de cada consulta:

| Fração processada | Q1: fidelidade min./mediana | Q2: fidelidade min./mediana | Q3: Spearman min./mediana | Q3: cobertura mediana | Q3: top-5 mediano |
|---:|---:|---:|---:|---:|---:|
| >=10% | 0,115 / 0,734 | 0,960 / 0,987 | 0,963 / 0,975 | 66,7%-70,4% | 80% |
| >=25% | 0,797 / 0,901 | 0,969 / 0,990 | 0,965 / 0,984 | 96,3% | 80% |
| >=50% | 0,927 / 0,962 | 0,989 / 0,995 | 0,985 / 0,996 | 100% | 100% |

Em Q3, Spearman deve ser interpretado apenas como fidelidade entre as UFs já
presentes. A cobertura e a recuperação do top-5 impedem que uma alta
correlação local seja confundida com representatividade global.

## Por que a ordem identidade de Q3 é o resultado esperado

O arquivo original preserva a organização física temporal e, dentro dela,
por UF. Consequentemente, os quadros preliminares são construídos a partir de
um subconjunto de UFs; outras ainda não tiveram nenhum row group processado.
Essa ausência é estrutural, não um erro de estimação. Uma UF que ainda não
apareceu no fluxo não pode participar do ranking parcial nem ser recuperada
no top-5.

Por volta de 10% das linhas na ordem identidade, Spearman entre as UFs
visíveis é 1,0 e o NMAE fica entre 0,0025 e 0,0045. Entretanto, apenas 18,5%
das UFs estão presentes e nenhuma das cinco UFs do top-5 final foi recuperada.
Em 25%, a cobertura é 37,0% e o top-5 overlap é 40%; em 50%, a cobertura é
59,3% e o top-5 overlap é 60%.

A convergência tardia de TVF-top5-80, TVF-top5-100 e TCov-90 na ordem
identidade é, portanto, esperada por construção. As permutações não melhoram
a resposta final nem a exatidão do DVISOR; elas distribuem evidências sobre
mais UFs ao longo do fluxo e antecipam sua disponibilidade para a camada de
apresentação. A ordem identidade funciona como uma condição de controle que
expõe esse mecanismo.

## Efeito do número de threads

As conclusões agregadas de Q2 e Q3 são praticamente invariantes entre 1, 2 e
4 threads. Em Q3, as medianas de TVF-top5-80 variam de 9,30% a 9,94%, as de
TVF-top5-100 de 26,69% a 27,78% e as de TCov-90 de 19,74% a 20,03%.

Q1 permanece mais sensível ao escalonamento: para uma mesma ordem, a amplitude
mediana entre threads foi 4,8 pontos percentuais para TNC, 5,0 para TVF e
14,4 para TSV. As medianas sobre as nove ordens, porém, permanecem próximas.

## Consequência para outras tarefas visuais

A ordem física não deve ser interpretada apenas como uma limitação. Sua
utilidade depende da tarefa visual. Q3 exige uma comparação global entre UFs,
portanto se beneficia da diversidade antecipada produzida pelas permutações.
Uma visualização de evolução temporal, como uma Bar Chart Race, pode se
beneficiar da ordem cronológica se o DVISOR entregar primeiro resultados
suficientemente completos para os períodos iniciais.

O progresso da execução, contudo, não representa automaticamente a evolução
temporal. A camada de apresentação precisa receber snapshots temporalmente
coerentes, possivelmente aguardando que um período esteja suficientemente
completo antes de exibi-lo. Esse caso motiva, como trabalho futuro, métricas
como tempo para o primeiro período utilizável, quantidade de períodos
utilizáveis durante a execução e fidelidade do ranking dentro de cada
período.

Não existe, portanto, uma única ordem física ótima para todos os usos:
comparações globais favorecem diversidade antecipada; visualizações de
evolução podem favorecer continuidade temporal.

## Relação com a hipótese do artigo

### Evidência que fortalece

- as respostas finais são invariantes, enquanto a qualidade parcial pode ser
  quantificada continuamente;
- Q2 alcança alta fidelidade estrutural muito cedo nas permutações;
- em Q3, quatro das cinco categorias finais são tipicamente recuperadas com
  cerca de 9%-10% das linhas permutadas;
- a distinção entre ranking local, top-k e cobertura permite identificar
  quando a resposta parcial é útil para uma tarefa específica sem chamá-la de
  completa;
- em 50% dos dados, todas as tarefas e todas as condições permutadas possuem
  fidelidade estrutural superior a 0,90; Q3 também possui cobertura completa e
  top-5 completo na mediana;
- os resultados agregados de Q2/Q3 são robustos a 1, 2 e 4 threads.

### Evidência que limita

- a ordem física pode atrasar fortemente representatividade e cobertura;
- Q1 não oferece qualidade inicial uniforme em todas as ordens;
- fidelidade local e estabilidade entre frames podem ocorrer cedo mesmo com
  domínio incompleto;
- top-5 overlap representa uma tarefa decisória específica e não substitui
  outras possíveis noções de utilidade;
- uma execução por combinação caracteriza trajetórias, mas não estima
  variabilidade temporal de desempenho;
- sem testes com usuários, as métricas são proxies de utilidade visual, não
  evidência direta de percepção ou melhoria da decisão;
- como concorrentes não foram executados, o estudo não demonstra
  superioridade comparativa mensurada.

## Figuras e dados revisados

- `output/figures/q3_fidelity_events.{pdf,png}`: comparação direta de
  TVF-rank, TVF-top5-80, TVF-top5-100 e TCov-90;
- `output/figures/q3_quality_dimensions.{pdf,png}`: trajetórias separadas de
  fidelidade local, recuperação do top-5 e cobertura, com escala ampliada no
  painel de Spearman;
- `output/figures/q1_q2_order_sensitivity_events.{pdf,png}`: eventos de Q1 e
  Q2 por ordem física e número de threads;
- `output/figures/q1_q2_fidelity_trajectories.{pdf,png}`: trajetórias de
  fidelidade de Q1 e Q2;
- `output/tables/q3_event_results.csv`: eventos multidimensionais de Q3 por
  execução;
- `output/tables/order_effects.csv`, `event_summary.csv` e
  `milestone_summary.csv`: valores agregados usados neste relatório;
- `output/validation/collection_validation.json`: validação da coleta e hashes
  finais.

A antiga matriz 10 x 3 foi retirada do conjunto principal de figuras: a
escala comum ocultava as diferenças relevantes e colocava métricas com
semânticas distintas no mesmo eixo.
