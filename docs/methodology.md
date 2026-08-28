# Decisões metodológicas provisórias

Estas decisões são humanas, revisáveis e não representam políticas declaradas da Seazone.

## Objetivo e critérios

- **Objetivo principal:** retorno sobre o capital investido em compra à vista.
- **Métrica econômica inicial:** gross yield estimado por cenário.
- **Critérios secundários:** receita absoluta, estabilidade e robustez da evidência.
- **Unidade de decisão:** coorte residencial definida por bairro, tipologia e número de quartos; não um pareamento individual Airbnb–VivaReal.

## Definições operacionais

| Termo | Definição provisória | Limitação material |
|---|---|---|
| Melhor investimento | Coorte com maior gross yield proxy que permaneça competitiva em sensibilidade, tenha amostra suficiente e não dependa de anomalias | Não incorpora valorização, liquidez ou todos os custos |
| Perfil | Tipologia residencial + número de quartos + capacidade; atributos operacionais entram como explicadores secundários | Zero quarto só será chamado studio após validação textual |
| Localização | Bairro normalizado; coordenadas apenas para análise interna do Airbnb | Bairros das duas plataformas podem usar fronteiras/nomenclaturas diferentes |
| Preço anunciado | Valor de `Price_AV.price` associado a listing, noite e captura | Moeda, taxas e natureza exata da unidade não estão codificadas |
| ADR proxy | Estatística robusta dos preços anunciados por noite no snapshot escolhido | Não é ADR realizado |
| Disponibilidade aparente | Presença de listing–data no dia de captura, caso o painel temporal sustente essa interpretação | Ausência não distingue reserva, bloqueio ou falha de coleta |
| Receita bruta em cenário | `ADR proxy × noites ocupadas assumidas` | Não é receita observada; ocupação será premissa ou proxy explicitamente rotulado |
| Preço de aquisição | Distribuição de `sale_price` deduplicado na coorte VivaReal | É preço pedido, não transacionado |
| Gross yield proxy | `receita bruta anual em cenário ÷ preço de aquisição da coorte` | Numerador e denominador vêm de imóveis diferentes da mesma coorte |
| Yield após condomínio observado | `(receita bruta em cenário − 12 × condomínio mensal válido) ÷ preço de aquisição` | Ainda não é retorno líquido; faltam custos operacionais e de compra |

## Fórmulas provisórias

```text
receita_bruta_cenario = ADR_proxy × 365 × ocupacao_cenario

gross_yield_proxy = receita_bruta_cenario / preco_aquisicao_coorte

yield_apos_condominio =
    (receita_bruta_cenario - 12 × condominio_mensal_valido)
    / preco_aquisicao_coorte
```

O headline não usará soma de preços disponíveis como receita. Cenários de ocupação e custos ausentes ficarão em parâmetros visíveis, nunca embutidos como constantes silenciosas.

## Regras de preparação já decididas

1. Preservar os CSVs originais em `data/` sem alteração.
2. Manter `Price_AV` no grain listing–data de estadia–dia de captura; agregar antes de juntar a métricas no nível do listing.
3. Ligar hosts por `(owner_id, timestamp de captura)` para evitar join N:N.
4. Usar somente coordenadas de `Mesh`.
5. Deduplicar VivaReal por `listing_id`; a única diferença não exata é ordem de amenities.
6. Excluir terreno e comercial do universo principal de compra residencial; inspecionar `outros` antes de decidir.
7. Preservar valores originais e criar flags de qualidade; não substituir outliers sem regra registrada.
8. Reportar tamanho da amostra, cobertura e dispersão junto a cada resultado.
9. Testar resultados com e sem outliers e com mais de uma regra de snapshot.
10. Não interpretar associação de características como causalidade.

## Regras ainda condicionais

- **Compacto:** candidato inicial = apartamento com zero ou um quarto. Analisar zero e um separadamente e validar studio em título/descrição.
- **Snapshot de preço:** candidato inicial = último dia de captura disponível para cada listing–data; a regra só será adotada após análise de transições do painel.
- **Preço representativo:** mediana como headline; p25/p75 e média aparada como sensibilidade.
- **Amostra mínima:** definir antes do ranking final com base na distribuição das coortes. Segmentos abaixo do limite permanecerão exploratórios.
- **Normalização de bairros:** apenas mapeamentos determinísticos e auditáveis; subdivisões ambíguas não serão fundidas silenciosamente.

## Condições que mudam o método

- Se presença em `Price_AV` não se comportar como disponibilidade aparente, usar apenas preço anunciado e cenários externos de ocupação.
- Se coortes compactas no Centro tiverem amostra insuficiente no Airbnb ou no VivaReal, ampliar a definição ou declarar a tese inconclusiva.
- Se erros de condomínio/área/preço forem concentrados em um segmento, o ranking deve ser recalculado com filtros alternativos.
- Se a cobertura de preços alterar materialmente a composição, aplicar ponderação/estratificação ou restringir a conclusão à população coberta.
