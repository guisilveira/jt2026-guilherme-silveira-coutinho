# Hipóteses e plano priorizado

## Histórico da revisão

O plano anterior tratava H1–H7 como sete análises `MUST` e usava um limiar de
reaparições para decidir se presença em `Price_AV` poderia representar
disponibilidade aparente. Essa abordagem foi revisada por decisão humana:

- estabilidade de presença não identifica reserva, bloqueio ou falha de coleta;
- o teste de presença não é um gate econômico;
- hipóteses sobrepostas foram consolidadas em quatro blocos essenciais;
- preço anunciado e ocupação assumida permanecerão explicitamente separados.

## Quatro blocos essenciais

| Bloco `MUST` | Pergunta | Análise mínima | Hipóteses incorporadas |
|---|---|---|---|
| 1 — Preço operacional e sensibilidade da amostra | Os preços anunciados permitem comparação suficientemente estável entre segmentos de imóveis? | Três regras de preço, peso igual por listing, cobertura, calendário, incerteza e duas sensibilidades de preços suspeitos | H1 reformulada; base de H2 |
| 2 — Perfil, localização e tese dos compactos | Quais perfis e bairros têm maior preço operacional em cenários comparáveis? | Segmentos por bairro × tipologia × quartos; zero e um quarto separados; contraste explícito da tese | H2 + H4 |
| 3 — Mercado de compra e gross yield | O preço de aquisição preserva ou elimina a vantagem operacional? | Segmentos agregados Airbnb–VivaReal e matriz de ocupação × sazonalidade × preço pedido | H3 + H5 + H7 |
| 4 — Características e robustez | Quais características estão associadas a preços melhores e a conclusão resiste aos controles? | Contrastes descritivos controlados, sensibilidades e síntese | H6 reformulada + parte mínima de H8 |

## Prioridades restantes

### `SHOULD`

- diagnóstico técnico de presença/ausência, sem inferir ocupação;
- regressão simples como sensibilidade dos contrastes;
- comparação entre listings com e sem preço;
- sensibilidade de host e gestão profissional de H9;
- ponderação por cobertura somente se houver suporte e pesos estáveis.

### `COULD`

- modelo preditivo interpretável;
- amenities em alta dimensionalidade;
- micro-localização de H10;
- NLP amplo;
- matching aproximado Airbnb–VivaReal;
- dashboard.

## Estado de H1–H10

| Hipótese | Estado atual |
|---|---|
| H1 | Reformulada e rebaixada: diagnóstico técnico, não disponibilidade econômica |
| H2 | Mantida e fundida com H4 |
| H3 | Mantida e fundida com H5/H7 |
| H4 | Mantida como contraste pré-especificado dentro de H2 |
| H5 | Mantida no bloco econômico |
| H6 | Reformulada: contrastes controlados são `MUST`; regressão é `SHOULD` |
| H7 | Mantida no ranking econômico |
| H8 | Dividida: parte descritiva é `MUST`; modelagem ampla é `SHOULD/COULD` |
| H9 | `SHOULD` |
| H10 | `COULD` |

## Decisões humanas pré-registradas

1. Captura principal de preço: 20/01/2025.
2. Leituras secundárias: último preço por listing–estadia e mediana entre capturas.
3. Peso igual por listing em todas as comparações entre segmentos.
4. Ocupações posteriores: 30%, 45% e 60%, sem cenário mais provável.
5. Fatores posteriores de sazonalidade: 60%, 80% e 100%, como testes de estresse.
6. Compacto principal: apartamento de um quarto; zero quarto separado; zero ou um
   apenas como leitura complementar.
7. Suporte principal: pelo menos 30 listings Airbnb com preço e, posteriormente,
   20 anúncios VivaReal. Entre 10 e 29 Airbnb e pelo menos 10 em cada base, o
   resultado será exploratório.
8. Preços ≥ 10.000 permanecerão no dado derivado com flag. Sensibilidades:
   remover somente as observações ou remover integralmente os três listings.
9. Relatórios usarão “segmentos de imóveis”; `cohort` poderá permanecer em nomes
   técnicos internos.

Estas são decisões humanas revisáveis, não propriedades observadas nos dados.

## Ciclo 1 — concluído

### Pergunta

A escolha do snapshot, a cobertura seletiva, a composição das datas de estadia
e os preços suspeitos alteram materialmente a comparação entre segmentos?

### Análise mínima

1. preparar `Details`, `Mesh` e `Price_AV` sem alterar os CSVs;
2. preservar o grain listing–estadia–dia de captura e validar unicidade;
3. calcular preço típico por listing usando captura de 20/01, último preço e
   mediana entre capturas;
4. agregar segmentos somente após produzir uma linha por listing e método;
5. mostrar mediana, p25/p75, intervalo de bootstrap e quantidade de listings;
6. comparar original, sem observações ≥ 10.000 e sem os três listings afetados;
7. medir quais segmentos perdem mais listings em 20/01;
8. comparar a composição das datas de estadia e uma sensibilidade ajustada por
   data, sem interpretar ausência como ocupação;
9. comparar listings com e sem preço por bairro, tipologia e quartos;
10. reconciliar linhas, IDs, chaves e cardinalidades em checks reproduzíveis.

### Critério para avançar

O ciclo pode avançar se:

- os checks de integridade forem aprovados;
- segmentos principais tiverem pelo menos 30 listings na captura de 20/01;
- diferenças de método, calendário ou preços suspeitos forem mensuráveis e não
  inverterem a leitura sem explicação;
- toda conclusão permanecer condicionada à população com preço.

Se algum critério falhar, a execução não será descartada: o relatório registrará
o problema, a sensibilidade tentada, a incerteza residual e se o bloqueio é local
a um segmento ou impede o bloco seguinte.

### Ponto de parada

Após o relatório de preço operacional. Não calcular retorno, não usar VivaReal,
não construir dashboard e não emitir recomendação final de compra.

### Resultado do ciclo

- todos os checks de integridade foram aprovados;
- a captura de 20/01 preservou sete segmentos com pelo menos 30 listings;
- os quatro primeiros segmentos por preço permaneceram nas mesmas posições nos
  três métodos;
- o ajuste de calendário preservou as quatro primeiras posições e alterou apenas
  a ordem de três segmentos com medianas próximas;
- preços ≥ 10.000 não dirigiram os segmentos principais, mas a remoção integral
  de um listing alterou em 8,8% um segmento exploratório;
- a cobertura seletiva permaneceu como limitação material, especialmente pela
  sobrerrepresentação de Centro, apartamentos e imóveis de um ou dois quartos.

**Decisão:** o bloco de preço pode avançar com confiança moderada no ranking dos
segmentos principais e conclusão restrita aos listings com preço. O ponto de
parada foi respeitado; o próximo bloco depende de revisão humana deste resultado.
