# Artefatos de auditoria e análise

Prepare o ambiente conforme a seção **Ambiente e execução reproduzível** do
`README.md` principal. As versões registradas em `requirements.txt` são
`pandas==2.2.3` e `numpy==2.3.5`; a execução de referência usou Python 3.12.13.

Execute a auditoria a partir da raiz do repositório:

```bash
python scripts/audit_data.py
```

O script lê os cinco CSVs de `data/` sem modificá-los e recria:

- `generated/audit_summary.json`: evidência detalhada da auditoria;
- `generated/data_dictionary.csv`: schema técnico, tipos, ausências, cardinalidade e exemplos;
- `generated/relationships.csv`: métricas resumidas dos relacionamentos documentados.

Os relatórios interpretativos são:

- `data_audit.md`: fatos observados, problemas de qualidade e semântica econômica;
- `relationships.md`: grafo validado e catálogo de relações adicionais.

## Primeira execução de preços do Airbnb

Execute a partir da raiz:

```bash
python scripts/analyze_airbnb_prices.py
```

O script usa somente `Details_Itapema.csv`, `Mesh_Ids_Data_Itapema.csv` e
`Price_AV_Itapema.csv`. Ele não modifica os arquivos originais e recria:

- `../data/processed/airbnb_listing_prices.csv`: preço típico por listing,
  método e tratamento de outlier;
- `generated/airbnb_price_cohorts.csv`: resumo técnico dos segmentos de imóveis;
- `generated/airbnb_price_coverage.csv`: cobertura por bairro, tipo, quartos e
  segmento;
- `generated/airbnb_price_calendar.csv`: comparabilidade das datas de estadia;
- `generated/airbnb_price_checks.csv`: testes de integridade;
- `generated/airbnb_price_transformations.csv`: contagens antes/depois e função
  responsável;
- `generated/airbnb_price_decomposition.csv`: ponte incremental entre regra de
  preço, datas e amostra, com reconciliação antes do arredondamento;
- `generated/airbnb_price_capture_changes.csv`: variação entre capturas nos
  mesmos pares listing–data;
- `generated/airbnb_price_host_concentration.csv`: concentração e sensibilidades
  por anfitrião nos segmentos principais;
- `generated/airbnb_price_pairwise_differences.csv`: diferenças em R$ e %, com
  bootstrap por listing e agrupado por `owner_id`;
- `generated/airbnb_price_summary.json`: métricas que sustentam o relatório.

O relatório interpretativo é `airbnb_price_analysis.md`.

## Ciclo 2 — perfis, localização e tese operacional

Execute depois do ciclo 1:

```bash
python scripts/analyze_airbnb_profiles.py
```

O script usa `Details`, `Mesh`, `Price_AV` e
`../data/processed/airbnb_listing_prices.csv`. Não usa VivaReal e recria:

- `../data/processed/airbnb_listing_profile_metrics.csv`: preço total, por
  hóspede comportado e por quarto no grain listing–método–tratamento;
- `generated/airbnb_profile_segments.csv`: medianas, p25/p75, amostra,
  anfitriões, incerteza agrupada e sensibilidades por segmento;
- `generated/airbnb_profile_contrasts.csv`: contrastes controlados no headline,
  com os pares pré-definidos da tese identificados separadamente;
- `generated/airbnb_profile_robustness.csv`: cada leitura de método, outlier,
  calendário, capacidade e concentração por anfitrião;
- `generated/airbnb_location_profile_matrix.csv`: comparações de bairros
  somente dentro de perfis equivalentes com suporte principal;
- `generated/airbnb_capacity_quality.csv`: auditoria e tratamento dos campos de
  capacidade e quartos;
- `generated/airbnb_profile_checks.csv`: checks explícitos de integridade;
- `generated/airbnb_profile_transformations.csv`: contagens e funções das
  transformações;
- `generated/airbnb_profile_summary.json`: resumo auditável dos resultados;
- `figures/airbnb_*.svg`: quatro gráficos estáticos do ciclo.

O relatório interpretativo é `airbnb_profile_location_analysis.md`.

O check de calendário exige o mesmo universo residencial e as mesmas medianas
ajustadas de `generated/airbnb_price_calendar.csv`; por isso o ciclo 1 deve ser
executado antes do ciclo 2.

## Ciclo 3 — mercado de compra e retorno em cenários

Execute depois dos ciclos 1 e 2:

```bash
python scripts/analyze_investment_returns.py
```

O script deduplica o VivaReal em uma tabela derivada, mantém somente o escopo
residencial para a análise principal e liga as plataformas apenas por segmento.
Ele recria:

- `../data/processed/vivareal_residential_listings.csv`: anúncios residenciais
  deduplicados, valores originais e flags de qualidade;
- `generated/vivareal_quality.csv`: contagens de deduplicação, escopo,
  normalização e anomalias;
- `generated/vivareal_segments.csv`: preço pedido, área, condomínio, IPTU e
  concentração por anunciante em cada segmento;
- `generated/airbnb_vivareal_segments.csv`: cobertura e suporte da ligação
  agregada, incluindo segmentos exclusivos de cada plataforma;
- `generated/investment_scenarios.csv`: nove testes de estresse por segmento;
- `generated/investment_robustness.csv`: sensibilidades univariadas de preço
  Airbnb, preço de compra e condomínio no cenário intermediário ilustrativo;
- `generated/investment_checks.csv`: validações críticas da execução;
- `generated/investment_summary.json`: resumo auditável da recomendação
  provisória.

O relatório interpretativo é `investment_return_analysis.md`. Os valores são
`gross yield proxy` e `yield após condomínio observado`, não retorno líquido ou
receita realizada.
