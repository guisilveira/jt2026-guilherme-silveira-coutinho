# Artefatos de auditoria

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
