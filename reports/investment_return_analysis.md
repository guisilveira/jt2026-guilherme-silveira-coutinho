# Ciclo 3 — mercado de compra e estimativa simples de retorno

## Decisão econômica provisória

Não há vencedor único robusto. Alternativas provisórias: **Morretes · apartamento · 2 quartos; Centro · apartamento · 2 quartos; Centro · apartamento · 1 quarto**.

No cenário intermediário meramente ilustrativo (45% de ocupação e 80% do preço observado), o líder registra **7,5% de gross yield proxy**, com preço anunciado típico de **R$ 454** e preço pedido mediano de **R$ 790.000**. A faixa nos nove testes de estresse é **3,8%–12,6%**; nenhum dos nove cenários é tratado como mais provável.

## Ranking econômico dos segmentos principais

| Segmento de imóveis | Airbnb | VivaReal | Preço Airbnb | Preço pedido | Preços compra sinalizados | Área mediana válida | Preço pedido/m² | Anunciantes | Maior anunciante | Gross yield proxy | Distância do líder | Faixa 9 cenários | Cobertura condomínio | n condomínio | Suporte condomínio | Yield após condomínio observado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Morretes · apartamento · 2 quartos | 43 | 1037 | R$ 454 | R$ 790.000 | 1 | 69 | R$ 11.551 | 121 | 19,5% | 7,5% | 0,00 p.p. | 3,8%–12,6% | 47,0% | 487 | principal | 7,0% |
| Centro · apartamento · 2 quartos | 59 | 89 | R$ 600 | R$ 1.150.000 | 0 | 86 | R$ 13.089 | 43 | 14,6% | 6,9% | 0,69 p.p. | 3,4%–11,4% | 61,8% | 55 | principal | 6,3% |
| Centro · apartamento · 1 quarto | 75 | 22 | R$ 450 | R$ 890.000 | 1 | 42 | R$ 16.250 | 16 | 13,6% | 6,6% | 0,90 p.p. | 3,3%–11,1% | 45,5% | 10 | exploratório | 6,0% |
| Meia Praia · apartamento · 2 quartos | 126 | 243 | R$ 448 | R$ 1.080.000 | 2 | 85 | R$ 13.033 | 68 | 7,8% | 5,5% | 2,09 p.p. | 2,7%–9,1% | 54,3% | 132 | principal | 4,9% |
| Meia Praia · apartamento · 3 quartos | 284 | 1697 | R$ 650 | R$ 1.885.000 | 33 | 128 | R$ 15.000 | 192 | 8,8% | 4,5% | 3,01 p.p. | 2,3%–7,6% | 47,1% | 799 | principal | 4,1% |
| Centro · apartamento · 3 quartos | 38 | 437 | R$ 664 | R$ 2.100.000 | 1 | 131 | R$ 15.789 | 119 | 7,3% | 4,2% | 3,39 p.p. | 2,1%–6,9% | 41,0% | 179 | principal | 3,8% |
| Meia Praia · apartamento · 4 quartos | 43 | 1322 | R$ 899 | R$ 3.600.000 | 21 | 188 | R$ 18.604 | 175 | 7,6% | 3,3% | 4,26 p.p. | 1,6%–5,5% | 40,5% | 536 | principal | 3,0% |

O ranking de gross yield proxy é idêntico nos nove pares ocupação × sazonalidade porque o multiplicador é comum aos segmentos. Mudanças de ranking, quando existem, vêm das sensibilidades de preço do Airbnb, preço de compra e condomínio, não da escolha entre esses nove multiplicadores.

### Liderança nas sensibilidades

| Sensibilidade | Métrica | Líder | Yield no cenário intermediário |
|---|---|---|---|
| Airbnb com ajuste de calendário aprovado | gross yield proxy | Morretes · apartamento · 2 quartos | 7,3% |
| Airbnb sem os três imóveis afetados | gross yield proxy | Morretes · apartamento · 2 quartos | 7,5% |
| Airbnb sem preços ≥ R$ 10 mil | gross yield proxy | Morretes · apartamento · 2 quartos | 7,5% |
| Após condomínio observado | yield após condomínio observado | Morretes · apartamento · 2 quartos | 7,0% |
| Compra mediana sem preços suspeitos | gross yield proxy | Morretes · apartamento · 2 quartos | 7,5% |
| Mediana Airbnb entre capturas | gross yield proxy | Morretes · apartamento · 2 quartos | 7,8% |
| Preço Airbnb 20/01 + compra mediana | gross yield proxy | Morretes · apartamento · 2 quartos | 7,5% |
| Preço de compra p25 | gross yield proxy | Centro · apartamento · 1 quarto | 9,1% |
| Preço de compra p75 | gross yield proxy | Morretes · apartamento · 2 quartos | 6,8% |

## Tese econômica dos compactos

O componente econômico é **inconclusivo**. A comparação de Centro/1 quarto com apartamentos maiores no Centro usa gross yield proxy; a localização Centro versus Meia Praia/1 quarto continua exploratória devido ao suporte do Airbnb em Meia Praia.

| Comparação | Centro/1 quarto | Comparador | Diferença | Faixa nas sensibilidades (p.p.) | Suporte |
|---|---|---|---|---|---|
| Centro · apartamento · 1 quarto − Meia Praia · apartamento · 1 quarto | 6,6% | 6,6% | 0,06 p.p. | -0,27 a 1,42 | exploratório |
| Centro · apartamento · 1 quarto − Centro · apartamento · 2 quartos | 6,6% | 6,9% | -0,21 p.p. | -0,36 a 0,95 | principal |
| Centro · apartamento · 1 quarto − Centro · apartamento · 3 quartos | 6,6% | 4,2% | 2,49 p.p. | 1,73 a 4,08 | principal |

O Ciclo 2 encontrou vantagem apenas na densidade de preço anunciado por capacidade declarada. Este ciclo pergunta se o menor preço pedido preserva essa direção econômica; não transforma preço por hóspede ou por quarto em demanda, ocupação ou retorno.

## Cobertura e ligação agregada

Após deduplicar 8.329 linhas em 8.293 IDs, o universo residencial contém 8044 anúncios derivados. Foram encontrados 34 segmentos correspondentes, 11 exclusivos do Airbnb e 83 exclusivos do VivaReal.

| Situação | Anúncios Airbnb | Anúncios VivaReal |
|---|---|---|
| exclusivo Airbnb | 18 | 0 |
| exclusivo VivaReal | 0 | 1889 |
| segmento correspondente | 752 | 6155 |

A ligação é exclusivamente agregada por bairro normalizado + tipo residencial + quartos. Não há correspondência entre anúncios individuais, títulos ou IDs. Bairros ausentes permanecem `desconhecido`; subdivisões não foram fundidas.

## Preparação e qualidade do VivaReal

| Categoria fora do escopo | Anúncios deduplicados | Tratamento |
|---|---|---|
| Tipo: terreno | 160 | FILTRO DE ESCOPO |
| Tipo: comercial | 79 | FILTRO DE ESCOPO |
| Tipo: outros | 10 | FILTRO DE ESCOPO |

Preços pedidos suspeitos foram preservados no resultado principal e retirados somente na sensibilidade. Áreas suspeitas ficam fora apenas das métricas por m². Condomínio ausente ou zero é desconhecido, nunca gratuito. IPTU não foi descontado.

## Limitações capazes de mudar a decisão

- O preço Airbnb é anunciado, cobre datas entre janeiro e abril e não informa ocupação observada, taxas ou valor efetivamente recebido.
- Ocupação e sazonalidade são premissas de teste de estresse; o preço anualizado no cenário não é receita realizada.
- O preço VivaReal é pedido, não transacionado, e os imóveis das duas plataformas não são os mesmos; padrão, área e capacidade podem diferir dentro do segmento.
- Gross yield proxy não inclui vacância observada, gestão, limpeza, manutenção, mobília, impostos, custos de aquisição, capex ou financiamento.
- Yield após condomínio observado usa apenas anúncios com condomínio positivo e não suspeito; cobertura seletiva pode mudar a comparação.
- IPTU foi apenas auditado e não descontado. Área existe somente no VivaReal e preço por m² é contexto, não denominador comum com o Airbnb.
- Segmentos pequenos podem aparecer como exploratórios, mas não fundamentam a recomendação principal.

## Checks

18 de 18 checks críticos foram aprovados. A execução não fez matching individual, não produziu retorno líquido e não alterou os CSVs originais.
