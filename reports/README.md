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
