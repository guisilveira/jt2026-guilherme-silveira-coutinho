# Hackathon Jovens Talentos AI Builder 2026 — Seazone

## 👉 Leia o desafio aqui

### **[ABRIR O DESAFIO COMPLETO](https://seazone-tech.github.io/jovens-talentos-2026-hackathon-data/)**

Lá está tudo: a missão, os dados, **o que entregar**, as regras, o prazo e **como vamos avaliar**.
Leia antes de começar a mexer nos dados.

> Se o link acima não abrir, o mesmo conteúdo está no arquivo [`index.html`](index.html) deste repositório
> (baixe e abra no navegador).

---

## Primeiro passo

**Faça um _fork_ deste repositório.** É nele que você vai trabalhar e é ele que você entrega.

---

## Ambiente e execução reproduzível

A análise foi executada com **Python 3.12.13**, `pandas==2.2.3` e
`numpy==2.3.5`. Pré-requisito: Python 3.12 disponível como `python3`. Em um
ambiente novo:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/audit_data.py
python scripts/analyze_airbnb_prices.py
python scripts/analyze_airbnb_profiles.py
```

Os scripts leem os CSVs originais de `data/` e recriam somente artefatos
derivados em `data/processed/` e `reports/generated/`. Os arquivos brutos não são
alterados.

Os resultados interpretativos dos dois primeiros ciclos estão em
`reports/airbnb_price_analysis.md` e
`reports/airbnb_profile_location_analysis.md`. As tabelas reproduzíveis ficam em
`reports/generated/`.

---

## Os dados (`data/`)

Snapshot estático do mercado imobiliário de **Itapema (SC)**, com anúncios de Airbnb e de venda (VivaReal).
É a mesma base para todos os candidatos, para garantir comparação justa.

| Arquivo | O que tem | Como conecta |
|---|---|---|
| `Details_Itapema.csv` | Cada anúncio de Airbnb: título, reviews, star rating, descrição, host_id, nº de quartos, tipo de imóvel | Base principal dos listings |
| `Hosts_ids_Itapema.csv` | Dados do anfitrião: nº de reviews, anos como host, superhost, taxa de resposta | Liga com Details pelo `owner_id` |
| `Mesh_Ids_Data_Itapema.csv` | Latitude/longitude + bairro de cada anúncio | Liga por listing |
| `Price_AV_Itapema.csv` | Preço por anúncio, por data de estadia e por data de captura | Liga por listing |
| `VivaReal_Itapema.csv` | Anúncios de venda: preço, condomínio, área, vendedor | Mercado de compra |

---

## Resumo do que você entrega

1. **Este repositório, forkado e público**, com a sua análise, o `README.md` explicando como rodar,
   a pasta `ai-log/` (conversas com a IA **em texto**) e a recomendação final escrita.
2. **Vídeo de até 3 minutos** no Google Drive, com o link na primeira linha do seu README.

O detalhe de cada item, o prazo e o formulário de entrega estão no
**[desafio completo](https://seazone-tech.github.io/jovens-talentos-2026-hackathon-data/)**.

---

*Seazone — Jovens Talentos AI Builder 2026*
