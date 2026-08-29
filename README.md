Vídeo de apresentação: LINK_GOOGLE_DRIVE_PENDENTE

# Onde investir em short-stay em Itapema?

## [Abrir o dashboard interativo](dashboard/index.html)

O dashboard funciona localmente, sem servidor ou internet. Ele permite testar
as combinações de ocupação, sazonalidade e preço de compra usadas na análise.

## Recomendação final

**Eu priorizaria um apartamento de dois quartos em Morretes, sujeito à
validação do imóvel específico, do condomínio e dos custos operacionais.**

Esse segmento apresentou a melhor relação entre preço anunciado e capital de
compra no critério principal:

- gross yield proxy de aproximadamente **7,5%** no cenário intermediário
  ilustrativo;
- preço pedido mediano de **R$ 790 mil**;
- liderança em **8 das 9 sensibilidades**;
- suporte de **43 anúncios do Airbnb** e **1.037 anúncios do VivaReal**.

O cenário intermediário usa **45% de ocupação** e um **fator sazonal de 80%**.
Os dois valores são premissas escolhidas para testar a decisão, não uma previsão
do desempenho futuro. O preço do Airbnb é anunciado, o preço de compra é pedido
e as plataformas foram relacionadas por bairro, tipologia e quartos — não pelo
mesmo imóvel.

### Condição importante da decisão

Não existe um vencedor totalmente robusto. **Centro/2 quartos** e **Centro/1
quarto** são alternativas. Quando usamos o p25 dos preços pedidos de cada
segmento, **Centro/1 quarto assume a liderança**. Isso torna o preço negociado e
a qualidade do ativo específico decisivos antes da compra.

## Respostas às quatro perguntas do desafio

### 1. Qual é o melhor perfil de imóvel?

Para investimento, pelo critério de preço anunciado em relação ao capital de
compra, o melhor perfil é **apartamento de dois quartos em Morretes**.

Essa resposta não deve ser confundida com outros dois resultados:

- o maior preço anunciado absoluto foi de **Meia Praia/apartamento/4 quartos**,
  com mediana de **R$ 899**;
- o maior preço anunciado por capacidade foi de
  **Centro/apartamento/1 quarto**, com **R$ 136,50 por hóspede comportado** e
  **R$ 450 por quarto**.

Os dados não distinguem com segurança imóvel inteiro, quarto privativo e quarto
compartilhado. Por isso, não há uma resposta confiável para essa dimensão de
“tipo de anúncio”.

### 2. Qual é a melhor localização em termos de preço?

**Não existe um bairro vencedor para todos os perfis.** Meia Praia aparece nos
maiores preços absolutos porque concentra imóveis maiores, mas as comparações
entre bairros para imóveis de mesmo tipo e número de quartos foram
inconclusivas. A resposta depende do perfil analisado.

### 3. Quais características estão associadas a preços anunciados maiores?

Dentro de imóveis comparáveis em bairro, tipologia e quartos, as associações
positivas sustentadas foram:

- anfitrião profissional: **+21,0%**;
- um banheiro adicional: **+13,3%**;
- taxa de limpeza positiva, por R$ 100: **+5,9%**;
- nota do anúncio avaliado, por 0,1 ponto: **+2,3%**.

Esses resultados vieram de regressões separadas e não controlam todas as
características simultaneamente. São **associações com o preço anunciado, não
causas** e não demonstram que modificar um atributo produziria o mesmo efeito.

### 4. Se a Seazone fosse investir hoje, o que deveria comprar?

**Um apartamento de dois quartos em Morretes**, seguido de due diligence do
ativo: preço negociado, regras e custo do condomínio, IPTU, manutenção, padrão
construtivo e custos da operação short-stay.

## Tese dos apartamentos compactos no Centro

**Os dados não sustentam os apartamentos compactos no Centro como a principal
tese de investimento.**

Centro/1 quarto apresentou boa densidade de preço anunciado por hóspede e por
quarto. Essa divisão, porém, não demonstrou maior demanda, ocupação, receita ou
retorno sobre o capital. A vantagem do Centro sobre outras localizações foi
inconclusiva, o resultado econômico mudou entre sensibilidades e a análise após
condomínio de Centro/1 quarto possui somente **dez valores válidos**. Existe um
sinal operacional interessante, mas ele não é suficiente para priorizar a tese
de investimento.

## Principais evidências e limitações

### Como ler o resultado econômico

O gross yield proxy relaciona o preço anunciado típico do Airbnb ao preço
pedido mediano do VivaReal:

```text
preço anualizado no cenário = preço anunciado × sazonalidade × 365 × ocupação
gross yield proxy = preço anualizado no cenário ÷ preço pedido mediano
```

Ele permite comparar segmentos sob as mesmas premissas. Não é receita
realizada, retorno líquido, previsão ou garantia de rentabilidade de um imóvel.

### O que pode mudar a decisão

- Apenas **22,5%** dos anúncios do Airbnb possuem preço, com cobertura desigual
  entre bairros e perfis.
- Os preços disponíveis cobrem **105 dias**, concentrados entre janeiro e
  abril.
- Não existe ocupação observada; ocupação e sazonalidade foram assumidas em
  cenários.
- Airbnb e VivaReal foram ligados somente por segmento — bairro, tipologia e
  quartos — e não por imóvel individual.
- Preço pedido não é preço de transação.
- Faltam custos operacionais completos, impostos, manutenção, mobília e
  vacância para estimar retorno líquido.
- Os dados não distinguem com segurança imóvel inteiro, quarto privativo e
  compartilhado.

Essas limitações fazem da recomendação um ponto de partida para selecionar e
investigar ativos, não uma autorização automática de compra.

## Como executar e reproduzir

A execução de referência usou **Python 3.12.13**, `pandas==2.2.3` e
`numpy==2.3.5`. Com Python 3.12 disponível como `python3`:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python scripts/audit_data.py
python scripts/analyze_airbnb_prices.py
python scripts/analyze_airbnb_profiles.py
python scripts/analyze_investment_returns.py
python scripts/analyze_price_characteristics.py
python scripts/build_dashboard.py
```

Os scripts devem ser executados nessa ordem porque os ciclos posteriores
reutilizam artefatos aprovados dos anteriores. Eles leem os CSVs originais em
`data/`, preservam os arquivos brutos e recriam somente tabelas derivadas em
`data/processed/` e `reports/generated/`.

Para abrir o dashboard sem servidor:

```bash
xdg-open dashboard/index.html
```

Também é possível abrir `dashboard/index.html` diretamente pelo gerenciador de
arquivos. Os dados necessários são incorporados ao HTML durante a geração; não
há dependência de CDN ou conexão com a internet.

## Mapa dos arquivos importantes

| O que verificar | Arquivo |
|---|---|
| Dashboard e testes de cenário | [`dashboard/index.html`](dashboard/index.html) |
| Recomendação final detalhada | [`reports/final_recommendation.md`](reports/final_recommendation.md) |
| Roteiro do vídeo | [`reports/video_script.md`](reports/video_script.md) |
| Resumo final auditável | [`reports/generated/final_summary.json`](reports/generated/final_summary.json) |
| Dados usados pelo dashboard | [`dashboard/data/dashboard_data.json`](dashboard/data/dashboard_data.json) |
| Metodologia e decisões | [`docs/methodology.md`](docs/methodology.md) |
| Plano dos ciclos | [`docs/analysis_plan.md`](docs/analysis_plan.md) |
| Auditoria dos dados | [`reports/data_audit.md`](reports/data_audit.md) |
| Validação dos relacionamentos | [`reports/relationships.md`](reports/relationships.md) |
| Ciclo 1 — preços do Airbnb | [`reports/airbnb_price_analysis.md`](reports/airbnb_price_analysis.md) |
| Ciclo 2 — perfil e localização | [`reports/airbnb_profile_location_analysis.md`](reports/airbnb_profile_location_analysis.md) |
| Ciclo 3 — compra e retorno | [`reports/investment_return_analysis.md`](reports/investment_return_analysis.md) |
| Ciclo 4 — características | [`reports/airbnb_characteristics_analysis.md`](reports/airbnb_characteristics_analysis.md) |
| Tabelas reproduzíveis | [`reports/generated/`](reports/generated/) |
| Conversas completas com IA | [`ai-log/`](ai-log/) |

## Como trabalhei com IA

Usei a IA como parceira de análise e verificação, não como fonte de verdade. Eu
defini a decisão de negócio, as premissas, os cenários e os limites mínimos de
amostra. A IA ajudou a auditar os arquivos, validar relações, executar análises
de sensibilidade e transformar o processo em código reproduzível.

As conclusões foram revisadas criticamente. Durante o trabalho, corrigimos o
universo do ajuste de calendário, a leitura da concentração por anfitrião e a
linguagem das regressões. Também rebaixamos conclusões quando os dados não
sustentavam certeza — como a presença de um bairro vencedor geral e a tese dos
compactos como recomendação principal. A exportação integral desse processo
deve ser preservada em [`ai-log/`](ai-log/).

## Sobre o desafio e os dados

O enunciado oficial está em
[Jovens Talentos AI Builder 2026](https://seazone-tech.github.io/jovens-talentos-2026-hackathon-data/)
e também no [`index.html`](index.html) da raiz.

A análise usa os cinco CSVs fornecidos pelo desafio: detalhes dos anúncios do
Airbnb, anfitriões, localização, preços anunciados e anúncios de venda do
VivaReal. O VivaReal foi comparado ao Airbnb somente em segmentos agregados; não
foi feita correspondência entre imóveis individuais.
