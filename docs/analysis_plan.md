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

## Ciclo 2 — perfil, localização e tese operacional

### Pergunta e hipóteses pré-registradas

**Pergunta:** quais perfis e localizações apresentam maior preço anunciado ao
comparar imóveis semelhantes, e apartamentos de um quarto no Centro possuem
vantagem operacional sustentada?

- **Hipótese principal:** Centro · apartamento · 1 quarto tem vantagem de
  localização sobre o mesmo perfil em outros bairros e vantagem de compacto
  sobre apartamentos maiores do Centro nas métricas por capacidade.
- **Hipóteses concorrentes:** outro bairro supera o Centro no mesmo perfil;
  imóveis maiores igualam ou superam o compacto também por hóspede ou quarto;
  ou as diferenças são inconclusivas após considerar anfitrião e sensibilidades.

### Análise mínima

1. auditar `number_of_guests` e quartos antes de cruzar capacidade com preço;
2. calcular por listing preço anunciado total, por hóspede comportado e por
   quarto, sem razão de medianas;
3. comparar quartos dentro do mesmo bairro e tipologia;
4. comparar bairros dentro do mesmo perfil exato;
5. tratar como principais somente os contrastes pré-definidos da tese;
6. reportar `n` de listings, `n` de hosts, mediana, p25/p75, diferença em reais
   e percentual e intervalo agrupado por `owner_id`;
7. testar mediana entre capturas, duas sensibilidades de preço suspeito,
   calendário e concentração por anfitrião;
8. preservar capacidades positivas suspeitas no headline e retirá-las somente
   na sensibilidade pré-definida;
9. impedir afirmação geral de bairro sem dois perfis equivalentes principais e
   direção coerente;
10. registrar a limitação de que `listing_type` é tipologia do imóvel, não tipo
    de anúncio.

### Critério de decisão

- intervalo agrupado exclui zero: diferença estatisticamente sustentada;
- intervalo agrupado inclui zero: evidência inconclusiva;
- tamanho da diferença será mostrado em reais e percentual, sem classificação
  de relevância econômica;
- suporte principal exige 30 listings por lado; 10–29 é exploratório e abaixo
  de 10 é insuficiente;
- a tese será classificada conforme os dois componentes e as quatro categorias
  pré-registradas em `docs/methodology.md`.

### Escopo e ponto de parada

Somente `Details`, `Mesh`, `Price_AV` e artefatos derivados do ciclo 1. Não usar
VivaReal, não estimar ocupação, receita ou retorno, não construir dashboard e não
emitir recomendação final de compra. Parar após o relatório do ciclo 2.

### Resultado do ciclo e correção de calendário

- os 20 checks de integridade foram aprovados e os 777 listings do headline
  reconciliaram com o ciclo 1;
- a correção passou a reutilizar a função de calendário do ciclo 1, filtrando
  o universo residencial antes da mediana diária. As medianas ajustadas
  reconciliaram nos 45 segmentos, com diferença máxima abaixo de `1e-10`;
- todas as 4.441 capacidades são positivas, finitas e conversíveis; 24 foram
  sinalizadas previamente como suspeitas por cerca externa ou incoerência com
  quartos e permaneceram no resultado principal;
- Meia Praia · apartamento · 4 quartos tem o maior preço total mediano entre os
  segmentos principais (R$ 899). Contra o perfil controlado de 3 quartos no
  mesmo bairro, a diferença é R$ 249 (38,3%) e o intervalo agrupado exclui zero;
- Centro · apartamento · 1 quarto lidera preço por hóspede comportado
  (R$ 136,50) e preço por quarto (R$ 450) entre os segmentos principais;
- contra Centro/2 quartos, as diferenças do compacto são R$ 35,69 por hóspede
  (35,4%) e R$ 150 por quarto (50,0%); contra Centro/3 quartos, R$ 37,73
  (38,2%) e R$ 228,67 (103,3%). Os quatro intervalos agrupados excluem zero e o
  sinal permanece nas sensibilidades;
- o preço total do compacto é inferior: R$ 150 abaixo de Centro/2 quartos, com
  evidência inconclusiva, e R$ 214 abaixo de Centro/3 quartos, com diferença
  sustentada;
- a comparação Centro/1 quarto versus Meia Praia/1 quarto é apenas
  exploratória (`n=75` versus `n=16`), tem diferença total de R$ 10 (2,3%),
  intervalo de R$ -82 a R$ 100 e inverte para R$ -11,93 (-2,6%) no ajuste de
  calendário corrigido;
- nenhum par de bairros apresentou dois perfis equivalentes principais com
  diferenças sustentadas na mesma direção. A localização deve ser respondida
  de forma condicionada ao perfil;
- zero quarto permaneceu separado; o maior segmento teve apenas sete listings,
  abaixo do suporte exploratório, e não foi chamado de studio;
- a tese foi classificada como **parcialmente sustentada operacionalmente**:
  componente de localização inconclusivo e componente compacto favorável
  apenas em densidade de preço anunciado por capacidade declarada. Preço por
  hóspede e por quarto não demonstra demanda, ocupação, receita, retorno ou
  eficiência por área/capital; a razão por quarto pode favorecer mecanicamente
  imóveis menores.

**Ponto de parada:** ciclo operacional concluído. A classificação ainda deve
ser confrontada com preço de aquisição e cenários econômicos; não constitui
recomendação de compra.

## Ciclo 3 — mercado de compra e estimativa simples de retorno

### Pergunta e análise mínima

**Pergunta:** quais segmentos principais preservam melhor relação entre preço
Airbnb anunciado e preço VivaReal pedido quando o custo de aquisição entra na
comparação?

1. deduplicar o VivaReal por `listing_id`, interrompendo diante de divergência
   material entre duplicações;
2. preparar apenas apartamentos e casas, preservando campos originais e flags;
3. resumir preço pedido, área, condomínio, IPTU e concentração por anunciante;
4. ligar as bases somente por bairro normalizado + tipologia + quartos;
5. classificar suporte principal, exploratório e insuficiente automaticamente;
6. calcular nove testes de estresse de ocupação × sazonalidade;
7. comparar headline e sensibilidades pré-definidas sem busca exploratória;
8. testar diretamente Centro/1 quarto contra Meia Praia/1 quarto, Centro/2 e
   Centro/3 quartos;
9. recomendar um segmento apenas se a liderança persistir; caso contrário,
   manter até três alternativas.

### Critério de decisão

- liderança principal: maior gross yield proxy em 45% × 80%, com amostras
  principais e sem dependência de uma regra anômala;
- robustez: preservação da liderança nas sensibilidades de preço Airbnb, preço
  pedido e condomínio;
- compactos: Centro/1 quarto deve superar Centro/2 e Centro/3 e preservar o
  sinal; qualquer inversão torna o componente econômico inconclusivo;
- os nove testes de ocupação e sazonalidade não distinguem o ranking antes do
  condomínio, pois aplicam multiplicador comum.

### Resultado e ponto de parada

- 18 de 18 checks críticos foram aprovados;
- 8.329 linhas do VivaReal produziram 8.293 IDs únicos; as 36 duplicações não
  apresentaram divergência material após normalizar a ordem de `amenities`;
- o universo derivado contém 8.044 anúncios residenciais, 34 segmentos
  correspondentes, 11 exclusivos do Airbnb e 83 exclusivos do VivaReal;
- sete segmentos alcançaram suporte principal em ambas as plataformas;
- Morretes/apartamento/2 quartos lidera o cenário intermediário com 7,5% de
  gross yield proxy, preço Airbnb de R$ 454 e preço pedido mediano de R$ 790
  mil; a faixa dos nove testes é 3,8%–12,6%;
- a liderança não é universal: com preço de compra no p25, Centro/apartamento/1
  quarto passa à frente. A decisão provisória mantém Morretes/2 quartos,
  Centro/2 quartos e Centro/1 quarto como alternativas, sem vencedor único;
- Centro/1 quarto fica 0,21 p.p. abaixo de Centro/2 no headline e 2,49 p.p.
  acima de Centro/3; a diferença contra Centro/2 muda de sinal nas
  sensibilidades. O componente econômico dos compactos é **inconclusivo**;
- Centro versus Meia Praia/1 quarto permanece exploratório pelo suporte Airbnb
  de Meia Praia;
- condomínio válido cobre de 40,5% a 61,8% dos segmentos principais e não foi
  interpretado como custo completo. IPTU não foi descontado.

**Ponto de parada:** recomendação econômica provisória concluída. Não houve
matching individual, dashboard, Ciclo 4 ou recomendação final do hackathon.

## Ciclo 4 — características e robustez das conclusões

### Pergunta e análise mínima

**Pergunta:** quais atributos do imóvel e do anfitrião estão associados ao
preço anunciado dentro de segmentos comparáveis, e esses controles mudam as
leituras operacionais ou a shortlist econômica?

1. manter uma linha por imóvel nos sete segmentos principais do Ciclo 2;
2. ligar Hosts pela chave temporal validada e excluir campos 100% vazios;
3. construir as características e sete regras literais de comodidades antes do
   contato com os resultados;
4. estimar uma regressão por característica com controle de segmento;
5. obter IC95 com 500 bootstraps agrupados por `owner_id`;
6. exigir sinal estável nas seis sensibilidades pré-definidas;
7. executar um modelo conjunto apenas como diagnóstico das cinco comparações;
8. não substituir yields, aquisição ou cenários do Ciclo 3.

### Resultado e decisão

- 668 imóveis e 471 anfitriões compõem a análise principal; o join temporal é
  N:1, sem multiplicação e com 100% de cobertura;
- associações positivas sustentadas: anfitrião profissional (+21,0%), um
  banheiro adicional (+13,3%), R$ 100 adicionais de taxa de limpeza positiva
  (+5,9%) e 0,1 ponto adicional na nota avaliada (+2,3%);
- associações negativas sustentadas: dobro de `reviews + 1` (-6,2%), favorito
  dos hóspedes (-8,6%), superhost (-10,6%) e presença de reviews (-30,1%);
- as 15 demais características são inconclusivas; Wi-Fi não é estimável por
  falta de variação suficiente;
- as associações negativas de reviews e status do anfitrião não são tratadas
  como efeitos causais e são compatíveis com tempo de mercado, seleção e
  estratégia de preço de anúncios novos;
- todas as cinco comparações ajustadas têm IC95 incluindo zero. Centro/1 quarto
  versus Meia Praia/1 quarto muda o sinal pontual de +2,3% para -17,5%, mas o
  comparador tem somente 16 imóveis e o resultado continua exploratório e
  inconclusivo;
- Centro/1 quarto permanece abaixo de Centro/2 e Centro/3 no preço total
  ajustado, sem mudança de direção e sem separação estatística;
- Morretes/2, Centro/2 e Centro/1 continuam uma shortlist econômica defensável,
  pois os controles não produzem evidência robusta que reverta os resultados do
  Ciclo 3. Eles não transformam a shortlist em recomendação final.

**Ponto de parada:** Ciclo 4 concluído com 28/28 checks. Não houve dashboard,
Ciclo 5, commit ou recomendação final do hackathon.
