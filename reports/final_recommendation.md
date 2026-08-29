# Recomendação final — investimento short-stay em Itapema

## Decisão

**Eu priorizaria um apartamento de dois quartos em Morretes, sujeito à validação do imóvel específico, do condomínio e dos custos operacionais.**

“Melhor” foi definido como a melhor relação entre preço anunciado e capital necessário para compra. No cenário intermediário **ilustrativo** — ocupação assumida de 45% e fator sazonal de 80% — Morretes/2 quartos apresenta preço anunciado típico de **R$ 454**, preço pedido mediano de **R$ 790.000**, **gross yield proxy de 7,5%** e **yield após condomínio observado de 7,0%**. A faixa dos nove testes de estresse é **3,8% a 12,6%**.

**Confiança: moderada.** Morretes/2 lidera 8 das 9 sensibilidades, com 43 anúncios Airbnb e 1.037 anúncios VivaReal. Não há vencedor único totalmente robusto: Centro/1 quarto assume a liderança quando se usa o p25 do preço pedido de cada segmento. Centro/2 e Centro/1 permanecem alternativas.

## Respostas às quatro perguntas

### 1. Qual é o melhor perfil de imóvel?

- **Maior preço anunciado absoluto:** Meia Praia/apartamento/4 quartos, mediana de **R$ 899** (43 anúncios; 38 anfitriões).
- **Maior densidade de preço por capacidade declarada:** Centro/apartamento/1 quarto, **R$ 136,50 por hóspede comportado** e **R$ 450 por quarto** (75 anúncios; 17 anfitriões).
- **Melhor investimento pelo critério adotado:** Morretes/apartamento/2 quartos.

Os dados não têm um campo confiável para distinguir imóvel inteiro, quarto privativo ou compartilhado. `listing_type` representa tipologia do imóvel; portanto, a parte “tipo de anúncio” não pode ser respondida com segurança.

### 2. Qual é a melhor localização em termos de preço?

**A localização depende do perfil do imóvel.** Meia Praia aparece entre os maiores preços absolutos porque concentra imóveis maiores, mas as comparações entre bairros para perfis equivalentes foram inconclusivas. Os dados não sustentam uma vantagem geral de um bairro depois de controlar minimamente tipo e quartos.

### 3. Quais características estão associadas a preços anunciados maiores?

Em regressões **separadas** de `log(preço anunciado)`, controlando bairro, tipologia e quartos, foram sustentadas associações positivas com anfitrião profissional (**+21,0%**), banheiro adicional (**+13,3%**), taxa de limpeza positiva por R$ 100 (**+5,9%**) e nota do anúncio avaliado por 0,1 ponto (**+2,3%**).

Quantidade de reviews, favorito dos hóspedes, superhost e presença de reviews tiveram associações negativas sustentadas. São resultados contraintuitivos que podem refletir idade do anúncio, seleção, padrão do imóvel ou estratégia de preço. Nenhuma associação é causal ou representa efeito independente das demais características.

### 4. O que comprar hoje e por quê?

Um apartamento de dois quartos em Morretes, porque lidera a relação entre preço anunciado e capital no critério principal e preserva essa liderança na maior parte das sensibilidades. Antes de comprar, a Seazone deve validar o imóvel individual, o condomínio, IPTU, manutenção, impostos, padrão construtivo e a operação local.

## Ranking econômico no cenário intermediário ilustrativo

| Posição | Segmento de imóveis | n Airbnb | n VivaReal | Preço anunciado típico | Preço pedido mediano | Gross yield proxy |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Morretes · apartamento · 2 quartos | 43 | 1.037 | R$ 454 | R$ 790.000 | 7,5% |
| 2 | Centro · apartamento · 2 quartos | 59 | 89 | R$ 600 | R$ 1.150.000 | 6,9% |
| 3 | Centro · apartamento · 1 quarto | 75 | 22 | R$ 450 | R$ 890.000 | 6,6% |
| 4 | Meia Praia · apartamento · 2 quartos | 126 | 243 | R$ 448 | R$ 1.080.000 | 5,5% |
| 5 | Meia Praia · apartamento · 3 quartos | 284 | 1.697 | R$ 650 | R$ 1.885.000 | 4,5% |
| 6 | Centro · apartamento · 3 quartos | 38 | 437 | R$ 664 | R$ 2.100.000 | 4,2% |
| 7 | Meia Praia · apartamento · 4 quartos | 43 | 1.322 | R$ 899 | R$ 3.600.000 | 3,3% |

O cenário de 45% × 80% não é “mais provável”; serve apenas como leitura intermediária entre nove testes de estresse. Como ocupação e sazonalidade aplicam o mesmo multiplicador a todos os segmentos, a ordenação muda principalmente com a base de preço de compra.

## Posição sobre os apartamentos compactos no Centro

**Os dados não sustentam os apartamentos compactos no Centro como a principal tese de investimento.** Centro/1 quarto mostrou boa densidade de preço por hóspede comportado e por quarto, mas a vantagem de localização foi inconclusiva. No gross yield proxy central ficou abaixo de Centro/2, houve inversão entre sensibilidades e seu yield após condomínio se apoia em apenas 10 valores válidos. Há sinal operacional, mas evidência econômica insuficiente para priorizar a tese.

## O que os números significam — e o que não significam

- **Fato observado:** medianas de preços anunciados/pedidos e tamanhos das amostras.
- **Cenário:** ocupação de 30%, 45% ou 60% e fator sazonal de 60%, 80% ou 100%; são premissas, não previsões.
- **Decisão humana:** priorizar retorno sobre o capital e usar mediana de compra como comparação principal.
- **Limitação:** Airbnb e VivaReal foram relacionados apenas por bairro + tipo + quartos, sem correspondência de imóveis individuais.

`Preço anualizado no cenário = preço anunciado típico × fator sazonal × 365 × ocupação`

`Gross yield proxy = preço anualizado no cenário ÷ preço pedido mediano`

Essas métricas não são receita realizada, ADR realizado, retorno líquido ou rentabilidade garantida. Preço pedido não é preço transacionado; custos operacionais, IPTU, impostos, manutenção e vacância não estão integralmente incorporados.

## Condições que fariam a decisão mudar

1. O imóvel específico em Morretes exigir capital ou condomínio materialmente acima das medianas do segmento.
2. Evidência de ocupação e preços realizados mostrar sazonalidade/ocupação relativas diferentes entre segmentos.
3. Negociação de um Centro/1 quarto próximo ao p25 de compra preservar qualidade e custos comparáveis — sensibilidade na qual ele lidera.
4. Due diligence revelar restrição condominial, baixa liquidez, padrão inadequado ou custos operacionais não observados.

## Rastreabilidade

Esta síntese usa somente os artefatos aprovados dos Ciclos 1–4. A geração reconciliou **26 checks finais**, além dos 20 checks do Ciclo 2, 18 do Ciclo 3 e 28 do Ciclo 4. O dashboard permite variar as nove combinações de ocupação e sazonalidade e p25/mediana/p75 do preço de compra sem recalcular os modelos anteriores.
