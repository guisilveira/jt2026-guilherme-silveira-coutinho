# Ciclo 4 — características associadas ao preço anunciado

## Resultado executivo

Foram analisados **668 imóveis** e **471 anfitriões** nos sete segmentos principais do Ciclo 2. Cada regressão estima separadamente a associação com `log(preço anunciado)`, controlando bairro + tipologia + quartos por efeito fixo de segmento, mas sem controlar simultaneamente as demais características. Portanto, os resultados são associações dentro de perfis comparáveis, não efeitos independentes de cada atributo.

Associações positivas sustentadas: **Anfitrião profissional, Banheiros, Taxa de limpeza positiva, Nota do anúncio avaliado**.
Associações negativas sustentadas: **Quantidade de reviews, Favorito dos hóspedes, Superhost, Presença de reviews**.
As outras 15 características permanecem inconclusivas.

Associação não é causalidade. O coeficiente de piscina, por exemplo, compara anúncios semelhantes que já diferem em piscina e em fatores não observados; não mede o efeito de instalar uma piscina.

## Associações sustentadas

| Característica | Unidade | Imóveis | Anfitriões | Direção | Efeito aproximado | IC95 inferior | IC95 superior | Sinal estável | Conclusão |
|---|---|---|---|---|---|---|---|---|---|
| Anfitrião profissional | sim vs. não | 663 | 470 | positiva | 21,0% | 9,5% | 41,4% | True | sustentada |
| Banheiros | +1 banheiro | 668 | 471 | positiva | 13,3% | 8,3% | 20,9% | True | sustentada |
| Taxa de limpeza positiva | +R$ 100 | 652 | 459 | positiva | 5,9% | 0,5% | 11,8% | True | sustentada |
| Nota do anúncio avaliado | +0,1 ponto | 654 | 467 | positiva | 2,3% | 0,2% | 7,9% | True | sustentada |
| Quantidade de reviews | dobro de reviews+1 | 668 | 471 | negativa | -6,2% | -8,7% | -4,2% | True | sustentada |
| Favorito dos hóspedes | sim vs. não | 668 | 471 | negativa | -8,6% | -14,4% | -1,7% | True | sustentada |
| Superhost | sim vs. não | 668 | 471 | negativa | -10,6% | -17,4% | -3,1% | True | sustentada |
| Presença de reviews | sim vs. não | 668 | 471 | negativa | -30,1% | -54,4% | -21,8% | True | sustentada |

## Associações inconclusivas

| Característica | Unidade | Imóveis | Anfitriões | Direção | Efeito aproximado | IC95 inferior | IC95 superior | Sinal estável | Conclusão |
|---|---|---|---|---|---|---|---|---|---|
| Piscina | presente vs. ausente | 668 | 471 | positiva | 24,9% | -6,0% | 48,2% | True | inconclusiva |
| Churrasqueira | presente vs. ausente | 668 | 471 | positiva | 8,6% | -1,4% | 18,1% | True | inconclusiva |
| Elevador | presente vs. ausente | 668 | 471 | positiva | 5,9% | -3,5% | 13,8% | True | inconclusiva |
| Acesso à praia | presente vs. ausente | 668 | 471 | positiva | 5,1% | -1,4% | 14,9% | True | inconclusiva |
| Capacidade de hóspedes | +1 hóspede | 668 | 471 | positiva | 2,3% | -0,5% | 4,8% | True | inconclusiva |
| Reserva instantânea | sim vs. não | 663 | 470 | positiva | 2,0% | -8,3% | 10,2% | False | inconclusiva |
| Quantidade de fotos positiva | +10 fotos | 560 | 455 | positiva | 1,1% | -1,0% | 4,0% | True | inconclusiva |
| Quantidade de reviews do anfitrião | dobro de reviews+1 | 668 | 471 | positiva | 0,8% | -1,9% | 1,5% | False | inconclusiva |
| Tempo como anfitrião | +1 ano | 668 | 471 | positiva | 0,4% | -1,5% | 1,9% | False | inconclusiva |
| Quantidade de comodidades | +5 comodidades | 668 | 471 | positiva | 0,3% | -1,0% | 1,7% | True | inconclusiva |
| Nota do anfitrião avaliado | +0,1 ponto | 662 | 465 | negativa | -0,3% | -3,4% | 6,0% | False | inconclusiva |
| Camas | +1 cama | 668 | 471 | negativa | -0,3% | -2,8% | 2,1% | True | inconclusiva |
| Estacionamento | presente vs. ausente | 668 | 471 | negativa | -1,1% | -15,0% | 7,1% | False | inconclusiva |
| Ar-condicionado | presente vs. ausente | 668 | 471 | negativa | -50,0% | -84,3% | 10,2% | True | inconclusiva |
| Wi-Fi | presente vs. ausente | 668 | 471 | não estimável | — | — | — | False | inconclusiva |

## Comparações depois do controle conjunto das características

O modelo conjunto usa os 668 imóveis principais e acrescenta somente os 16 imóveis de Meia Praia/1 quarto para cumprir o contraste exploratório obrigatório. Essa ampliação não entra nas regressões individuais nem transforma o segmento em principal.

| Segmento A | Segmento B | n A | n B | Diferença mediana original | Diferença ajustada | IC95 ajustado inf. | IC95 ajustado sup. | Direção mudou | Evidência ajustada |
|---|---|---|---|---|---|---|---|---|---|
| Centro · apartamento · 1 quarto | Centro · apartamento · 2 quartos | 75 | 59 | -25,0% | -20,3% | -28,9% | 11,1% | False | inconclusiva |
| Centro · apartamento · 1 quarto | Centro · apartamento · 3 quartos | 75 | 38 | -32,2% | -22,1% | -36,5% | 5,7% | False | inconclusiva |
| Centro · apartamento · 1 quarto | Meia Praia · apartamento · 1 quarto | 75 | 16 | 2,3% | -17,5% | -27,6% | 13,5% | True | inconclusiva |
| Morretes · apartamento · 2 quartos | Centro · apartamento · 2 quartos | 43 | 59 | -24,4% | -8,1% | -23,6% | 11,4% | False | inconclusiva |
| Morretes · apartamento · 2 quartos | Centro · apartamento · 1 quarto | 43 | 75 | 0,8% | 15,3% | -17,1% | 41,0% | False | inconclusiva |

O Ciclo 4 não testou novamente preço anunciado por hóspede comportado nem preço anunciado por quarto. No preço total ajustado, Centro/1 quarto continua abaixo de Centro/2 e Centro/3, mas os intervalos incluem zero; assim, não apareceu evidência para revisar a conclusão do Ciclo 2.

Este diagnóstico não invalidou a shortlist Morretes/2 quartos, Centro/2 quartos e Centro/1 quarto, mas também não a validou economicamente. A sustentação da shortlist continua vindo dos preços de compra e dos cenários do Ciclo 3.

## Qualidade, regras e sensibilidades

O join `Details.(owner_id, aquisition_date) → Hosts.(owner_id, host_snapshot_date)` é N:1 e tem 100% de cobertura. Taxa e tempo de resposta estão 100% vazios e foram excluídos. Booleanos ausentes permanecem desconhecidos; notas zero sem reviews viraram ausentes.

Comodidades específicas foram identificadas somente pelas sete expressões literais pré-definidas, após casefold e remoção de acentos. Taxa de limpeza zero e fotos zero foram preservadas com flags e excluídas somente das respectivas regressões individuais, por semântica ambígua.

A classificação exige IC95 agrupado por anfitrião excluindo zero e mesmo sinal nas seis leituras: 20/01, mediana entre capturas nos mesmos imóveis, calendário, duas sensibilidades de preços ≥ R$ 10 mil e peso igual por anfitrião.

## Limitações

- Regressões individuais não eliminam confundimento por padrão, área, vista, estado do imóvel, gestão ou seleção da amostra com preço.
- Reviews, notas, favorito e superhost podem ser consequência do tempo e desempenho do anúncio; não são necessariamente causas do preço.
- O modelo ajustado usa representações determinísticas de ausências para não reduzir a amostra, mas seus contrastes são apenas diagnóstico de direção.
- A captura permanece concentrada entre janeiro e abril, e preço anunciado não é receita realizada.
- A recomendação econômica continua dependendo do VivaReal e dos cenários do Ciclo 3.

## Checks

28 de 28 checks foram aprovados. Cada associação estimável e o modelo ajustado usaram 500 repetições de bootstrap por owner_id; Wi-Fi foi explicitamente não estimável por ausência de variação suficiente.
