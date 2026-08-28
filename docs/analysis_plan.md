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
- atributos ampliados de gestão profissional de H9; a concentração por
  `owner_id` já foi incorporada ao ciclo 1;
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
| H9 | Dividida: concentração por `owner_id` executada no ciclo 1; atributos ampliados do host permanecem `SHOULD` |
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

### Revisão corretiva do ciclo 1

Após a primeira leitura, o ciclo foi reaberto para separar mudanças de método,
calendário e amostra e para testar dependência de operadores. A revisão mantém a
captura de 20/01 e o peso igual por listing como decisões principais e acrescenta:

1. ponte incremental na ordem método de preço → datas → amostra, com
   reconciliação exata antes do arredondamento e aviso de dependência da ordem;
2. diagnóstico separado de mudanças entre capturas para pares listing–data
   comuns; o efeito zero do método “mais recente” nos pares de 20/01 é identidade
   por construção e não evidência de estabilidade;
3. concentração por `owner_id`, peso igual por anfitrião e retirada do maior
   anfitrião como sensibilidades;
4. bootstrap agrupado por anfitrião e contrastes pareados em reais e percentual;
5. classificação estatística inconclusiva quando o intervalo agrupado da
   diferença inclui zero, sem inferir relevância econômica.

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
  três métodos, mas a maior parte das mudanças de nível nos métodos secundários
  veio da ampliação das datas e, principalmente no topo, da mudança da amostra;
- o ajuste de calendário preservou as quatro primeiras posições e alterou apenas
  a ordem de três segmentos com medianas próximas;
- preços ≥ 10.000 não dirigiram os segmentos principais, mas a remoção integral
  de um listing alterou em 8,8% um segmento exploratório;
- a cobertura seletiva permaneceu como limitação material, especialmente pela
  sobrerrepresentação de Centro, apartamentos e imóveis de um ou dois quartos;
- Centro/apartamento/1 quarto tem 72% dos listings da captura principal sob um
  único anfitrião. Sua mediana pontual permanece R$ 450 com peso por host e sem
  esse operador, mas a dependência reduz a precisão dos contrastes agrupados;
- Centro/apartamento/2 quartos é o segmento principal com maior sensibilidade à
  concentração: o maior anfitrião reúne 20 de 59 listings (33,9%); a mediana de
  R$ 600 cai para R$ 480 com peso igual por anfitrião e para R$ 449 sem o maior
  operador. Essa dependência reforça a classificação inconclusiva dos contrastes
  envolvendo o segmento;
- somente 12 das 21 diferenças pareadas excluem zero no bootstrap por anfitrião;
  as demais nove são estatisticamente inconclusivas. Relevância econômica ainda
  não foi avaliada.

**Decisão revisada:** o bloco de preço permanece utilizável para descrever a
amostra coberta, com evidência mais forte para a liderança de Meia Praia/4
quartos sobre o segundo colocado do que para ordenar os segmentos intermediários
e inferiores. O ponto de parada foi respeitado; o próximo bloco depende de
revisão humana deste resultado.
