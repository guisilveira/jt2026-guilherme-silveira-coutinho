# Artefatos de auditoria e análise

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

O script requer Python 3, pandas e numpy.

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
- `generated/airbnb_price_summary.json`: métricas que sustentam o relatório.

O relatório interpretativo é `airbnb_price_analysis.md`.
