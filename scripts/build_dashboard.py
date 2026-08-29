#!/usr/bin/env python3
"""Gera a síntese final e o dashboard somente a partir dos artefatos aprovados."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "reports" / "generated"
DASHBOARD = ROOT / "dashboard"

RAW_FILES = (
    "Details_Itapema.csv",
    "Hosts_ids_Itapema.csv",
    "Mesh_Ids_Data_Itapema.csv",
    "Price_AV_Itapema.csv",
    "VivaReal_Itapema.csv",
)


def fail(message: str) -> None:
    raise RuntimeError(f"Falha de reconciliação: {message}")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: str | float | int | None) -> float | None:
    if value in (None, "", "nan", "NaN"):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def integer(value: str | float | int | None) -> int | None:
    parsed = number(value)
    return None if parsed is None else int(round(parsed))


def close(actual: float | None, expected: float, label: str, tolerance: float = 1e-9) -> None:
    if actual is None or not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        fail(f"{label}: obtido {actual!r}, esperado {expected!r}")


def unique(rows: list[dict[str, str]], **criteria: str) -> dict[str, str]:
    matches = [row for row in rows if all(row.get(key) == value for key, value in criteria.items())]
    if len(matches) != 1:
        fail(f"seleção {criteria} retornou {len(matches)} linhas")
    return matches[0]


def label_segment(segment_key: str) -> str:
    bairro, tipo, quartos = segment_key.split("|")
    return f"{bairro.title()} · {tipo} · {quartos}"


def format_brl(value: float) -> str:
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def build_data() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    investment_summary = read_json(GENERATED / "investment_summary.json")
    profile_summary = read_json(GENERATED / "airbnb_profile_summary.json")
    characteristics_summary = read_json(GENERATED / "airbnb_characteristics_summary.json")
    linked = read_csv(GENERATED / "airbnb_vivareal_segments.csv")
    scenarios = read_csv(GENERATED / "investment_scenarios.csv")
    robustness = read_csv(GENERATED / "investment_robustness.csv")
    profile_segments = read_csv(GENERATED / "airbnb_profile_segments.csv")
    associations = read_csv(GENERATED / "airbnb_characteristic_associations.csv")

    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, evidence: str) -> None:
        checks.append({"check": name, "status": "OK" if condition else "FALHOU", "evidence": evidence})
        if not condition:
            fail(f"check '{name}': {evidence}")

    for name, summary, expected in (
        ("Ciclo 2", profile_summary, 20),
        ("Ciclo 3", investment_summary, 18),
        ("Ciclo 4", characteristics_summary, 28),
    ):
        status = summary["checks"]
        check(
            f"Checks aprovados no {name}",
            status["all_passed"] and status["passed"] == expected and status["total"] == expected,
            f"{status['passed']}/{status['total']}",
        )

    reference_hashes = investment_summary["source_hashes"]
    actual_hashes = {name: sha256(ROOT / "data" / name) for name in RAW_FILES}
    check("Hashes dos CSVs originais preservados", actual_hashes == reference_hashes, "5 de 5 hashes reconciliados")
    check(
        "Hashes comuns entre ciclos reconciliados",
        all(reference_hashes[name] == profile_summary["source_hashes"][name] for name in profile_summary["source_hashes"]),
        "Details, Mesh e Price_AV coincidem",
    )

    main_rows = [row for row in linked if row["suporte_investimento"] == "principal"]
    check("Sete segmentos principais", len(main_rows) == 7, f"{len(main_rows)} segmentos")
    check(
        "Ligação somente agregada",
        all(row["ligacao_individual"] == "False" for row in main_rows),
        "bairro + tipo residencial + quartos",
    )

    scenario_pairs = {
        (number(row["ocupacao_assumida"]), number(row["fator_sazonalidade_assumido"])) for row in scenarios
    }
    expected_pairs = {(o, s) for o in (0.30, 0.45, 0.60) for s in (0.60, 0.80, 1.00)}
    check("Nove combinações de cenário", scenario_pairs == expected_pairs, f"{len(scenario_pairs)} combinações")

    segments: list[dict[str, Any]] = []
    for row in sorted(main_rows, key=lambda item: item["segment_key"]):
        key = row["segment_key"]
        intermediate = unique(
            scenarios,
            segment_key=key,
            ocupacao_assumida="0.45",
            fator_sazonalidade_assumido="0.8",
        )
        purchase = {
            "p25": number(row["preco_pedido_p25"]),
            "median": number(row["preco_pedido_mediano"]),
            "p75": number(row["preco_pedido_p75"]),
        }
        segment = {
            "key": key,
            "label": row["segmento_imoveis_airbnb"],
            "bairro": row["bairro"],
            "tipo": row["tipo_imovel_airbnb"],
            "quartos": integer(row["quartos_airbnb"]),
            "airbnbListings": integer(row["n_airbnb"]),
            "airbnbHosts": integer(row["n_hosts"]),
            "airbnbTypicalPrice": number(row["preco_airbnb_mediano_20_01"]),
            "vivarealListings": integer(row["n_vivareal"]),
            "purchasePrice": purchase,
            "purchasePriceWithoutSuspects": number(row["preco_pedido_mediano_sem_suspeitos"]),
            "purchaseSuspects": integer(row["n_preco_compra_suspeito"]),
            "areaMedianM2": number(row["area_util_mediana_m2"]),
            "purchasePriceMedianM2": number(row["preco_pedido_mediano_m2"]),
            "condoValid": integer(row["n_condominio_valido"]),
            "condoCoverage": number(row["cobertura_condominio_valido"]),
            "condoMonthlyMedian": number(row["condominio_mensal_mediano_valido"]),
            "condoSupport": row["suporte_condominio"],
            "intermediate": {
                "annualizedPrice": number(intermediate["preco_anualizado_no_cenario"]),
                "grossYield": number(intermediate["gross_yield_proxy"]),
                "yieldAfterObservedCondo": number(intermediate["yield_apos_condominio_observado"]),
                "rank": integer(intermediate["rank_gross_yield_principal"]),
            },
        }
        segments.append(segment)

    for row in scenarios:
        annualized = number(row["preco_anualizado_no_cenario"])
        expected_annualized = (
            number(row["preco_airbnb_mediano_20_01"])
            * number(row["fator_sazonalidade_assumido"])
            * 365
            * number(row["ocupacao_assumida"])
        )
        close(annualized, expected_annualized, "fórmula de preço anualizado")
        close(
            number(row["gross_yield_proxy"]),
            annualized / number(row["preco_pedido_mediano"]),
            "fórmula de gross yield proxy",
        )
    check("Fórmulas dos cenários reconciliadas", True, f"{len(scenarios)} linhas")

    recommended = next(segment for segment in segments if segment["key"] == "morretes|apartamento|2 quartos")
    centro_two = next(segment for segment in segments if segment["key"] == "centro|apartamento|2 quartos")
    centro_one = next(segment for segment in segments if segment["key"] == "centro|apartamento|1 quarto")
    close(recommended["airbnbTypicalPrice"], 453.5, "preço Airbnb de Morretes/2")
    close(recommended["purchasePrice"]["median"], 790000.0, "preço de compra de Morretes/2")
    close(recommended["intermediate"]["grossYield"], 0.07543025316455697, "yield de Morretes/2")
    close(recommended["intermediate"]["yieldAfterObservedCondo"], 0.07011379746835443, "yield após condomínio")
    check(
        "Amostras da recomendação reconciliadas",
        recommended["airbnbListings"] == 43 and recommended["vivarealListings"] == 1037,
        "43 Airbnb e 1.037 VivaReal",
    )

    sensitivity_rows = [
        row
        for row in robustness
        if row["segment_key"] == recommended["key"]
        and row["ocupacao_assumida"] == "0.45"
        and row["fator_sazonalidade_assumido"] == "0.8"
    ]
    wins = sum(integer(row["rank_segmentos_principais"]) == 1 for row in sensitivity_rows)
    check("Liderança em sensibilidades", len(sensitivity_rows) == 9 and wins == 8, f"{wins}/9")

    p25_yields = sorted(
        (
            segment["airbnbTypicalPrice"] * 0.8 * 365 * 0.45 / segment["purchasePrice"]["p25"],
            segment["key"],
        )
        for segment in segments
    )
    check("Inversão no p25", p25_yields[-1][1] == centro_one["key"], label_segment(p25_yields[-1][1]))

    min_yield = recommended["airbnbTypicalPrice"] * 0.60 * 365 * 0.30 / recommended["purchasePrice"]["median"]
    max_yield = recommended["airbnbTypicalPrice"] * 1.00 * 365 * 0.60 / recommended["purchasePrice"]["median"]

    top_profile = unique(
        profile_segments,
        metodo="snapshot_2025_01_20",
        tratamento_outlier="original",
        metrica="preco_total",
        tratamento_capacidade="não aplicável",
        segment_key="meia praia|apartamento|4 quartos",
    )
    compact_guest = unique(
        profile_segments,
        metodo="snapshot_2025_01_20",
        tratamento_outlier="original",
        metrica="preco_por_hospede",
        tratamento_capacidade="todas as capacidades positivas",
        segment_key="centro|apartamento|1 quarto",
    )
    compact_room = unique(
        profile_segments,
        metodo="snapshot_2025_01_20",
        tratamento_outlier="original",
        metrica="preco_por_quarto",
        tratamento_capacidade="não aplicável",
        segment_key="centro|apartamento|1 quarto",
    )
    close(number(top_profile["preco_mediano"]), 899.0, "maior preço absoluto")
    close(number(compact_guest["preco_mediano"]), 136.5, "preço por hóspede do compacto")
    close(number(compact_room["preco_mediano"]), 450.0, "preço por quarto do compacto")
    check(
        "Conclusão operacional reconciliada",
        profile_summary["results"]["thesis_operational_classification"] == "parcialmente sustentada"
        and not profile_summary["results"]["general_location_claims"],
        "localização inconclusiva; densidade por capacidade favorável",
    )

    supported = [row for row in associations if row["classificacao"] == "sustentada"]
    positive_keys = {"anfitriao_profissional", "banheiros", "taxa_limpeza", "nota_anuncio"}
    negative_keys = {"quantidade_reviews", "favorito_hospedes", "superhost", "presenca_reviews"}
    check(
        "Associações sustentadas reconciliadas",
        {row["caracteristica"] for row in supported if row["direcao"] == "positiva"} == positive_keys
        and {row["caracteristica"] for row in supported if row["direcao"] == "negativa"} == negative_keys,
        "4 positivas e 4 negativas",
    )

    def association_payload(row: dict[str, str]) -> dict[str, Any]:
        return {
            "key": row["caracteristica"],
            "label": row["caracteristica_label"],
            "unit": row["unidade_efeito"],
            "listings": integer(row["n_listings"]),
            "hosts": integer(row["n_hosts"]),
            "effect": number(row["efeito_percentual_aproximado"]),
            "ciLow": number(row["ic95_inferior_percentual"]),
            "ciHigh": number(row["ic95_superior_percentual"]),
            "direction": row["direcao"],
        }

    headline_yields = sorted(
        ((segment["intermediate"]["grossYield"], segment["key"]) for segment in segments), reverse=True
    )
    check("Líder no cenário intermediário", headline_yields[0][1] == recommended["key"], recommended["label"])

    data = {
        "meta": {
            "title": "Onde investir em Itapema?",
            "subtitle": "Preço anunciado, capital de compra e limites da evidência",
            "mainCapture": "20/01/2025",
            "currencyAssumption": "R$; unidade e taxas não são definidas explicitamente na documentação dos dados",
            "generatedFrom": [
                "reports/generated/airbnb_profile_summary.json",
                "reports/generated/airbnb_profile_segments.csv",
                "reports/generated/investment_summary.json",
                "reports/generated/airbnb_vivareal_segments.csv",
                "reports/generated/investment_scenarios.csv",
                "reports/generated/investment_robustness.csv",
                "reports/generated/airbnb_characteristics_summary.json",
                "reports/generated/airbnb_characteristic_associations.csv",
            ],
            "rawSourceHashes": actual_hashes,
        },
        "definitions": {
            "observed": "Medianas e amostras calculadas nos anúncios disponíveis.",
            "scenario": "Ocupação e sazonalidade assumidas para teste de estresse; não são previsões.",
            "decision": "Escolha humana: priorizar a relação entre preço anunciado e capital de compra.",
            "price": "Preço anunciado não é diária recebida nem receita realizada.",
            "yield": "Gross yield proxy = preço anunciado típico × sazonalidade × 365 × ocupação ÷ preço pedido mediano.",
        },
        "recommendation": {
            "segmentKey": recommended["key"],
            "statement": "Eu priorizaria um apartamento de dois quartos em Morretes, sujeito à validação do imóvel específico, do condomínio e dos custos operacionais.",
            "reason": "Melhor relação observada entre preço anunciado e capital de compra no critério principal, com liderança em 8 de 9 sensibilidades.",
            "alternatives": [centro_two["key"], centro_one["key"]],
            "robustSingleWinner": False,
            "sensitivityWins": wins,
            "sensitivityTotal": len(sensitivity_rows),
            "stressRange": {"min": min_yield, "max": max_yield},
        },
        "segments": segments,
        "scenarioControls": {
            "occupancy": [0.30, 0.45, 0.60],
            "seasonality": [0.60, 0.80, 1.00],
            "purchaseBases": [
                {"key": "p25", "label": "p25"},
                {"key": "median", "label": "Mediana"},
                {"key": "p75", "label": "p75"},
            ],
            "default": {"occupancy": 0.45, "seasonality": 0.80, "purchaseBasis": "median"},
            "note": "45% × 80% é apenas o cenário intermediário ilustrativo, nunca o mais provável.",
        },
        "profile": {
            "bestInvestment": recommended["key"],
            "highestAbsolute": {
                "key": top_profile["segment_key"],
                "label": top_profile["segmento_imoveis"],
                "price": number(top_profile["preco_mediano"]),
                "listings": integer(top_profile["n_listings"]),
                "hosts": integer(top_profile["n_hosts"]),
            },
            "highestCapacityDensity": {
                "key": compact_guest["segment_key"],
                "label": compact_guest["segmento_imoveis"],
                "pricePerGuest": number(compact_guest["preco_mediano"]),
                "pricePerRoom": number(compact_room["preco_mediano"]),
                "listings": integer(compact_guest["n_listings"]),
                "hosts": integer(compact_guest["n_hosts"]),
            },
            "listingTypeLimitation": "Não há campo confiável para distinguir imóvel inteiro, quarto privativo ou compartilhado; listing_type representa tipologia do imóvel.",
        },
        "location": {
            "conclusion": "A localização depende do perfil do imóvel; os dados não sustentam uma vantagem geral de um bairro depois de controlar minimamente o perfil.",
            "composition": "Meia Praia aparece nos maiores preços absolutos porque concentra imóveis maiores.",
            "equivalentProfiles": "As comparações diretas entre bairros para perfis equivalentes foram inconclusivas.",
        },
        "characteristics": {
            "positive": [association_payload(row) for row in supported if row["direcao"] == "positiva"],
            "negative": [association_payload(row) for row in supported if row["direcao"] == "negativa"],
            "method": "Regressões separadas de log(preço anunciado), controlando bairro, tipologia e quartos, sem controlar as demais características simultaneamente; bootstrap agrupado por anfitrião.",
            "caveat": "Associações dentro de perfis comparáveis, não efeitos independentes ou causais.",
        },
        "compactThesis": {
            "finalPosition": "Os dados não sustentam os apartamentos compactos no Centro como a principal tese de investimento.",
            "operationalStatus": profile_summary["results"]["thesis_operational_classification"],
            "economicStatus": investment_summary["results"]["compact_economic_status"],
            "evidence": [
                "Centro/1 quarto tem maior densidade de preço anunciado por hóspede comportado e por quarto.",
                "A vantagem de localização de Centro/1 quarto foi inconclusiva.",
                "No gross yield proxy central, Centro/1 quarto ficou abaixo de Centro/2 quartos.",
                "A direção se inverte em sensibilidades; com o p25 de compra, Centro/1 lidera.",
                "O yield após condomínio de Centro/1 usa apenas 10 valores válidos e é exploratório.",
            ],
        },
        "quality": {
            "limitations": [
                "Só 22,5% dos anúncios do Airbnb têm preço, com cobertura desigual por bairro e perfil.",
                "Os preços Airbnb cobrem 105 dias concentrados entre janeiro e abril; sazonalidade anual é assumida.",
                "Airbnb e VivaReal são ligados por segmento, não por imóvel individual.",
                "Preço pedido não é preço de transação; custos operacionais, IPTU, vacância e impostos não formam um retorno líquido.",
                "Condomínio observado tem cobertura desigual; no Centro/1 quarto são apenas 10 valores válidos.",
                "Os dados não identificam com segurança imóvel inteiro, quarto privativo ou compartilhado.",
            ],
            "cycleChecks": {"cycle2": 20, "cycle3": 18, "cycle4": 28},
        },
    }

    return data, checks


def render_index(data: dict[str, Any]) -> str:
    embedded = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"description\" content=\"Síntese final da análise de investimento short-stay em Itapema.\">
  <title>Onde investir em Itapema? — Seazone</title>
  <link rel=\"stylesheet\" href=\"assets/styles.css\">
</head>
<body>
  <header class=\"hero\" id=\"topo\">
    <nav class=\"nav shell\" aria-label=\"Navegação principal\">
      <a class=\"brand\" href=\"#topo\" aria-label=\"Voltar ao início\"><span class=\"brand-mark\">S</span><span>Investimento em Itapema</span></a>
      <div class=\"nav-links\"><a href=\"#ranking\">Ranking</a><a href=\"#perguntas\">Respostas</a><a href=\"#limites\">Limites</a></div>
    </nav>
    <div class=\"hero-grid shell\">
      <div class=\"hero-copy\">
        <p class=\"eyebrow decision-tag\">Decisão recomendada</p>
        <h1>Priorizar um apartamento de <em>2 quartos em Morretes</em>.</h1>
        <p class=\"hero-lead\">Melhor relação entre preço anunciado e capital de compra no critério principal — sujeita à validação do imóvel, condomínio e custos operacionais.</p>
        <div class=\"hero-actions\"><a class=\"button primary\" href=\"#ranking\">Testar cenários</a><a class=\"button ghost\" href=\"#tese\">Ver tese dos compactos</a></div>
      </div>
      <aside class=\"decision-panel\" aria-label=\"Resumo da decisão\">
        <div class=\"decision-number\"><span>7,5%</span><small>gross yield proxy</small></div>
        <dl>
          <div><dt>Preço anunciado típico</dt><dd>R$ 454</dd></div>
          <div><dt>Preço pedido mediano</dt><dd>R$ 790 mil</dd></div>
          <div><dt>Amostra</dt><dd>43 Airbnb · 1.037 VivaReal</dd></div>
          <div><dt>Robustez</dt><dd>liderou 8 de 9 sensibilidades</dd></div>
        </dl>
      </aside>
    </div>
  </header>

  <main>
    <section class=\"legend-strip\" aria-label=\"Como ler o dashboard\">
      <div class=\"shell legend-grid\">
        <div><span class=\"legend-dot observed\"></span><strong>Fato observado</strong><small>medianas e amostras nos anúncios</small></div>
        <div><span class=\"legend-dot scenario\"></span><strong>Cenário</strong><small>ocupação e sazonalidade assumidas</small></div>
        <div><span class=\"legend-dot decision\"></span><strong>Decisão humana</strong><small>critério: preço anunciado ÷ capital</small></div>
        <div><span class=\"legend-dot alert\"></span><strong>Limitação</strong><small>incerteza capaz de mudar a decisão</small></div>
      </div>
    </section>

    <section class=\"section shell\" id=\"ranking\">
      <div class=\"section-heading\">
        <div><p class=\"eyebrow\">Laboratório de cenários</p><h2>O ranking econômico responde às premissas</h2></div>
        <p>Todos os controles são testes de estresse. Nenhuma combinação é apresentada como mais provável.</p>
      </div>
      <div class=\"scenario-layout\">
        <aside class=\"controls-card\">
          <fieldset><legend>Ocupação assumida</legend><div class=\"segmented\" id=\"occupancy-controls\"></div></fieldset>
          <fieldset><legend>Preço fora do verão</legend><div class=\"segmented\" id=\"seasonality-controls\"></div></fieldset>
          <fieldset><legend>Preço pedido de compra</legend><div class=\"segmented\" id=\"purchase-controls\"></div></fieldset>
          <div class=\"scenario-result\"><span>Líder neste cenário</span><strong id=\"scenario-leader\">—</strong><b id=\"scenario-yield\">—</b></div>
          <p class=\"microcopy\" id=\"scenario-note\"></p>
        </aside>
        <div class=\"chart-card\">
          <div class=\"chart-title\"><div><h3>Ranking dos segmentos principais</h3><p>Gross yield proxy · uma observação por anúncio</p></div><span class=\"source-pill\">n Airbnb + n VivaReal</span></div>
          <div id=\"ranking-chart\" class=\"ranking-chart\" role=\"img\" aria-label=\"Ranking de gross yield proxy por segmento\"></div>
          <p class=\"chart-source\">Fonte: Ciclo 3 · captura Airbnb de 20/01 + VivaReal deduplicado · ligação agregada por bairro, tipo e quartos.</p>
        </div>
      </div>
      <div class=\"stress-card\">
        <div class=\"chart-title\"><div><h3>Nove testes de estresse para Morretes/2 quartos</h3><p>Gross yield proxy · n=43 Airbnb + 1.037 VivaReal · compra conforme controle selecionado</p></div><span class=\"scenario-pill\">cenários, não previsão</span></div>
        <div class=\"stress-grid\" id=\"stress-grid\"></div>
        <p class=\"chart-source\">Fonte: Ciclo 3 · preço Airbnb de 20/01 e preços pedidos do VivaReal no segmento.</p>
      </div>
    </section>

    <section class=\"section section-soft\" id=\"perguntas\">
      <div class=\"shell\">
        <div class=\"section-heading\"><div><p class=\"eyebrow\">Respostas do desafio</p><h2>Quatro perguntas, quatro respostas diretas</h2></div></div>

        <article class=\"answer-block\" id=\"perfil\">
          <div class=\"question-number\">01</div>
          <div class=\"answer-content\"><p class=\"eyebrow\">Qual é o melhor perfil?</p><h3>Depende da definição de “melhor”. Para investimento, Morretes/2 quartos.</h3>
            <div class=\"metric-triptych\">
              <div class=\"metric-card observed-card\"><span>Maior preço absoluto</span><strong>R$ 899</strong><p>Meia Praia · apartamento · 4 quartos</p><small>n=43 anúncios · 38 anfitriões</small></div>
              <div class=\"metric-card observed-card\"><span>Maior densidade por capacidade</span><strong>R$ 137</strong><p>Centro · apartamento · 1 quarto, por hóspede comportado</p><small>R$ 450 por quarto · n=75 · 17 anfitriões</small></div>
              <div class=\"metric-card decision-card\"><span>Melhor investimento</span><strong>7,5%</strong><p>Morretes · apartamento · 2 quartos</p><small>gross yield proxy · cenário intermediário ilustrativo</small></div>
            </div>
            <div class=\"callout alert-callout\"><strong>Tipo de anúncio sem resposta segura.</strong> Não existe campo confiável para distinguir imóvel inteiro, quarto privativo ou compartilhado. <code>listing_type</code> representa a tipologia do imóvel.</div>
          </div>
        </article>

        <article class=\"answer-block\" id=\"localizacao\">
          <div class=\"question-number\">02</div>
          <div class=\"answer-content\"><p class=\"eyebrow\">Qual é a melhor localização em preço?</p><h3>A localização depende do perfil; não há um bairro vencedor geral.</h3>
            <div class=\"location-flow\">
              <div><span class=\"step\">Composição</span><strong>Meia Praia</strong><p>Concentra imóveis maiores e aparece nos maiores preços absolutos.</p></div>
              <div class=\"flow-arrow\" aria-hidden=\"true\">→</div>
              <div><span class=\"step\">Controle mínimo</span><strong>Mesmo tipo + quartos</strong><p>Comparamos bairros apenas dentro de perfis equivalentes.</p></div>
              <div class=\"flow-arrow\" aria-hidden=\"true\">→</div>
              <div><span class=\"step\">Conclusão</span><strong>Inconclusiva</strong><p>Os intervalos agrupados não sustentam vantagem geral de localização.</p></div>
            </div>
          </div>
        </article>

        <article class=\"answer-block\" id=\"caracteristicas\">
          <div class=\"question-number\">03</div>
          <div class=\"answer-content\"><p class=\"eyebrow\">O que está associado a preços maiores?</p><h3>Quatro associações positivas sustentadas dentro de perfis comparáveis.</h3>
            <div id=\"positive-associations\" class=\"association-grid\"></div>
            <div class=\"negative-panel\"><div><span class=\"alert-kicker\">Resultados contraintuitivos</span><h4>Reviews, superhost e favorito aparecem com sinal negativo</h4><p>Podem refletir idade do anúncio, seleção, padrão do imóvel ou estratégia de preço — não uma penalidade causada por esses atributos.</p></div><div id=\"negative-associations\" class=\"negative-list\"></div></div>
            <p class=\"method-note\">Regressões separadas de log(preço anunciado), controlando bairro, tipologia e quartos, mas não as demais características simultaneamente. São associações, não efeitos causais nem instruções para modificar um imóvel. IC95 por bootstrap agrupado por anfitrião.</p>
          </div>
        </article>

        <article class=\"answer-block\" id=\"decisao\">
          <div class=\"question-number\">04</div>
          <div class=\"answer-content\"><p class=\"eyebrow\">O que comprar hoje?</p><h3>Um apartamento de dois quartos em Morretes, após validar o ativo específico.</h3>
            <div class=\"recommendation-grid\">
              <div class=\"recommendation-kpi\"><span>Preço anunciado típico</span><strong>R$ 454</strong><small>dado observado · n=43 Airbnb</small></div>
              <div class=\"recommendation-kpi\"><span>Preço pedido mediano</span><strong>R$ 790 mil</strong><small>dado observado · n=1.037 VivaReal</small></div>
              <div class=\"recommendation-kpi\"><span>Gross yield proxy</span><strong>7,5%</strong><small>45% ocupação × 80% sazonalidade</small></div>
              <div class=\"recommendation-kpi\"><span>Após condomínio observado</span><strong>7,0%</strong><small>487 valores válidos de condomínio</small></div>
              <div class=\"recommendation-kpi\"><span>Faixa de estresse</span><strong>3,8%–12,6%</strong><small>nove combinações · compra mediana</small></div>
            </div>
            <div class=\"callout uncertainty-callout\"><strong>Sem vencedor único totalmente robusto.</strong> Centro/2 e Centro/1 são alternativas; Centro/1 assume a liderança quando cada segmento usa o p25 do preço pedido.</div>
            <p class=\"method-note\">A estimativa combina imóveis diferentes do Airbnb e do VivaReal dentro do mesmo segmento. Não é retorno histórico, líquido, garantido nem avaliação de um imóvel individual.</p>
          </div>
        </article>
      </div>
    </section>

    <section class=\"section compact-section\" id=\"tese\">
      <div class=\"shell compact-grid\">
        <div><p class=\"eyebrow\">Tese dos compactos no Centro</p><h2>Um sinal operacional interessante, mas evidência econômica insuficiente.</h2><p class=\"compact-verdict\">Os dados <strong>não sustentam</strong> os apartamentos compactos no Centro como a principal tese de investimento.</p></div>
        <div class=\"evidence-stack\">
          <div class=\"evidence-item positive-evidence\"><span>01</span><p>Centro/1 quarto tem boa densidade de preço anunciado por hóspede e por quarto.</p></div>
          <div class=\"evidence-item\"><span>02</span><p>A vantagem de localização foi inconclusiva.</p></div>
          <div class=\"evidence-item\"><span>03</span><p>No gross yield central, Centro/1 ficou abaixo de Centro/2.</p></div>
          <div class=\"evidence-item\"><span>04</span><p>A direção muda nas sensibilidades; p25 de compra favorece Centro/1.</p></div>
          <div class=\"evidence-item warning-evidence\"><span>05</span><p>Yield após condomínio de Centro/1 usa só 10 valores válidos.</p></div>
        </div>
      </div>
    </section>

    <section class=\"section shell\" id=\"limites\">
      <div class=\"section-heading\"><div><p class=\"eyebrow\">Qualidade e limites</p><h2>O que ainda pode mudar a decisão</h2></div><p>Limitações não são rodapé: definem o nível de confiança da recomendação.</p></div>
      <div id=\"limitations-grid\" class=\"limitations-grid\"></div>
      <div class=\"audit-footer\"><strong>Rastreabilidade</strong><span>20/20 checks do Ciclo 2</span><span>18/18 checks do Ciclo 3</span><span>28/28 checks do Ciclo 4</span><span>5/5 hashes brutos preservados</span></div>
    </section>
  </main>

  <footer><div class=\"shell footer-grid\"><p><strong>Seazone · Jovens Talentos 2026</strong><br>Síntese baseada somente nos cinco CSVs do desafio e nos artefatos aprovados.</p><a href=\"#topo\">Voltar ao topo ↑</a></div></footer>

  <script id=\"dashboard-data\" type=\"application/json\">{embedded}</script>
  <script src=\"assets/app.js\"></script>
</body>
</html>
"""


def render_recommendation(data: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    recommended = next(s for s in data["segments"] if s["key"] == data["recommendation"]["segmentKey"])
    ranked = sorted(data["segments"], key=lambda s: s["intermediate"]["grossYield"], reverse=True)
    rows = "\n".join(
        f"| {i} | {s['label']} | {s['airbnbListings']} | {format_int(s['vivarealListings'])} | {format_brl(s['airbnbTypicalPrice'])} | {format_brl(s['purchasePrice']['median'])} | {format_pct(s['intermediate']['grossYield'])} |"
        for i, s in enumerate(ranked, 1)
    )
    return f"""# Recomendação final — investimento short-stay em Itapema

## Decisão

**Eu priorizaria um apartamento de dois quartos em Morretes, sujeito à validação do imóvel específico, do condomínio e dos custos operacionais.**

“Melhor” foi definido como a melhor relação entre preço anunciado e capital necessário para compra. No cenário intermediário **ilustrativo** — ocupação assumida de 45% e fator sazonal de 80% — Morretes/2 quartos apresenta preço anunciado típico de **{format_brl(recommended['airbnbTypicalPrice'])}**, preço pedido mediano de **{format_brl(recommended['purchasePrice']['median'])}**, **gross yield proxy de {format_pct(recommended['intermediate']['grossYield'])}** e **yield após condomínio observado de {format_pct(recommended['intermediate']['yieldAfterObservedCondo'])}**. A faixa dos nove testes de estresse é **{format_pct(data['recommendation']['stressRange']['min'])} a {format_pct(data['recommendation']['stressRange']['max'])}**.

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
{rows}

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

Esta síntese usa somente os artefatos aprovados dos Ciclos 1–4. A geração reconciliou **{len(checks)} checks finais**, além dos 20 checks do Ciclo 2, 18 do Ciclo 3 e 28 do Ciclo 4. O dashboard permite variar as nove combinações de ocupação e sazonalidade e p25/mediana/p75 do preço de compra sem recalcular os modelos anteriores.
"""


def render_video_script(data: dict[str, Any]) -> str:
    return """# Roteiro do vídeo — até três minutos

## Texto falado

Se a Seazone fosse investir hoje em Itapema, eu priorizaria um apartamento de dois quartos em Morretes, sujeito à validação do imóvel específico, do condomínio e dos custos operacionais.

Eu defini “melhor” como a melhor relação entre preço anunciado e capital necessário para compra, e não simplesmente o maior preço no Airbnb. Morretes, com dois quartos, apresentou preço anunciado típico de 454 reais e preço pedido mediano de 790 mil reais. No cenário intermediário ilustrativo, com 45% de ocupação e fator sazonal de 80%, o gross yield proxy foi de 7,5%. Esse segmento liderou oito das nove sensibilidades e possui suporte de 43 anúncios no Airbnb e 1.037 no VivaReal.

Esses percentuais são testes de estresse, não previsões. A análise relaciona imóveis diferentes das duas plataformas apenas por bairro, tipo e quartos. Portanto, não representa retorno histórico ou garantido de um imóvel individual.

Centro, com dois ou um quarto, continua como alternativa. Não existe vencedor totalmente robusto porque Centro com um quarto assume a liderança quando usamos o p25 dos preços pedidos.

Os dados também não sustentam os apartamentos compactos no Centro como principal tese de investimento. Eles mostraram maior densidade de preço anunciado por hóspede e por quarto, mas a vantagem de localização foi inconclusiva. No gross yield central, Centro com um quarto ficou abaixo de Centro com dois quartos, houve inversão nas sensibilidades e o resultado após condomínio usa somente dez valores válidos.

Eu trabalhei com a IA como parceira de análise, não como fonte de verdade. As decisões de negócio, critérios, cenários e limites de amostra foram escolhas humanas. A IA auditou os arquivos, validou relacionamentos, executou checks e sensibilidades e tornou o processo reproduzível. Durante as revisões, corrigimos o universo do ajuste de calendário, a leitura da concentração por anfitrião e rebaixamos conclusões que os dados não sustentavam, como a ideia de um bairro vencedor geral.

Com mais uma semana, eu buscaria dados de ocupação e preços realizados ao longo de um ano, custos operacionais completos e preços efetivamente negociados. Depois faria a due diligence de imóveis específicos da shortlist, verificando regras do condomínio, IPTU, manutenção, liquidez e padrão construtivo. Isso permitiria transformar esta recomendação por segmento em uma decisão real de aquisição.
"""


def main() -> None:
    data, checks = build_data()
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    (DASHBOARD / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    GENERATED.mkdir(parents=True, exist_ok=True)

    dashboard_json = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (DASHBOARD / "data" / "dashboard_data.json").write_text(dashboard_json, encoding="utf-8")
    html = render_index(data)
    (DASHBOARD / "index.html").write_text(html, encoding="utf-8")

    def technical_check(name: str, condition: bool, evidence: str) -> None:
        checks.append({"check": name, "status": "OK" if condition else "FALHOU", "evidence": evidence})
        if not condition:
            fail(f"check técnico '{name}': {evidence}")

    css_path = DASHBOARD / "assets" / "styles.css"
    js_path = DASHBOARD / "assets" / "app.js"
    technical_check("Assets locais presentes", css_path.exists() and js_path.exists(), "CSS e JavaScript locais")
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    technical_check("Quatro respostas no HTML", html.count('class=\"answer-block\"') == 4, "4 blocos")
    technical_check(
        "Três grupos de controles",
        all(identifier in html for identifier in ("occupancy-controls", "seasonality-controls", "purchase-controls")),
        "ocupação, sazonalidade e preço de compra",
    )
    embedded = html.split('<script id=\"dashboard-data\" type=\"application/json\">', 1)[1].split("</script>", 1)[0]
    technical_check("JSON incorporado reconciliado", json.loads(embedded) == data, "igual a dashboard_data.json")
    technical_check(
        "Funcionamento sem internet",
        not any(token in (html + css + js).lower() for token in ("http://", "https://", "fetch(", "xmlhttprequest", "cdn.")),
        "sem URL externa, CDN ou requisição de rede",
    )
    technical_check(
        "Breakpoints responsivos presentes",
        "@media (max-width: 980px)" in css and "@media (max-width: 680px)" in css,
        "desktop, tablet e celular",
    )
    dynamic_leaders = {}
    for basis in ("p25", "median", "p75"):
        values = [
            (segment["airbnbTypicalPrice"] * 0.8 * 365 * 0.45 / segment["purchasePrice"][basis], segment["key"])
            for segment in data["segments"]
        ]
        technical_check(
            f"Yields dinâmicos finitos — {basis}",
            all(math.isfinite(value) and value > 0 for value, _ in values),
            f"{len(values)} segmentos",
        )
        dynamic_leaders[basis] = max(values)[1]
    technical_check(
        "Controles reproduzem mudança de liderança",
        dynamic_leaders == {
            "p25": "centro|apartamento|1 quarto",
            "median": "morretes|apartamento|2 quartos",
            "p75": "morretes|apartamento|2 quartos",
        },
        json.dumps(dynamic_leaders, ensure_ascii=False, sort_keys=True),
    )
    technical_check(
        "Hashes brutos preservados após o build",
        {name: sha256(ROOT / "data" / name) for name in RAW_FILES} == data["meta"]["rawSourceHashes"],
        "5 de 5 hashes",
    )

    (ROOT / "reports" / "final_recommendation.md").write_text(
        render_recommendation(data, checks), encoding="utf-8"
    )
    (ROOT / "reports" / "video_script.md").write_text(render_video_script(data), encoding="utf-8")

    final_summary = {
        "recommendation": data["recommendation"],
        "compactThesis": data["compactThesis"],
        "headlineSegment": next(s for s in data["segments"] if s["key"] == data["recommendation"]["segmentKey"]),
        "locationConclusion": data["location"]["conclusion"],
        "checks": {"passed": len(checks), "total": len(checks), "allPassed": True, "items": checks},
        "sources": data["meta"]["generatedFrom"],
        "rawSourceHashes": data["meta"]["rawSourceHashes"],
    }
    (GENERATED / "final_summary.json").write_text(
        json.dumps(final_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Dashboard gerado com {len(data['segments'])} segmentos principais e {len(checks)} checks finais.")


if __name__ == "__main__":
    main()
