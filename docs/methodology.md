# Decisões metodológicas

Estas decisões são humanas, revisáveis e não representam políticas declaradas da Seazone.

## Decisões humanas confirmadas

As regras abaixo foram escolhidas durante a colaboração entre a pessoa responsável
pela análise e a IA. Elas **não são fatos presentes nos CSVs**.

1. O preço operacional principal usará somente a captura de 20/01/2025.
2. A mediana entre capturas será a segunda leitura; o último preço disponível por
   listing e data de estadia será mantido como terceira comparação metodológica.
3. Cada listing terá o mesmo peso: primeiro será calculado um preço típico por
   imóvel e somente depois os imóveis serão agregados por segmento.
4. Os cenários posteriores de ocupação serão 30%, 45% e 60%.
5. Os fatores posteriores de sazonalidade serão 60%, 80% e 100% do preço
   observado entre janeiro e abril. São testes de estresse, não previsões, e
   nenhum será rotulado como o mais provável.
6. Apartamentos de um quarto serão a referência principal de compacto. Zero
   quarto será analisado separadamente e não será chamado automaticamente de
   studio; o grupo zero ou um quarto será apenas uma leitura complementar.
7. Para suporte do lado Airbnb, um segmento precisa de pelo menos 30 listings
   com preço para integrar a análise principal. Entre 10 e 29, será exploratório;
   abaixo de 10, terá evidência insuficiente. A recomendação posterior também
   exigirá pelo menos 20 anúncios do VivaReal no mesmo segmento.
8. Presença ou ausência em `Price_AV` não será usada para inferir ocupação,
   reserva ou receita. Eventual análise de transições será somente um diagnóstico
   técnico e não bloqueará a análise principal.
9. Preços iguais ou superiores a 10.000 serão preservados e sinalizados. Serão
   produzidas duas sensibilidades: remover apenas essas observações e remover
   integralmente os três listings afetados.
10. Em relatórios e tabelas para leitura será usado o termo **segmento de
    imóveis**. Nomes técnicos internos podem continuar usando `cohort`.

## Objetivo e critérios

- **Objetivo principal:** retorno sobre o capital investido em compra à vista.
- **Métrica econômica inicial:** gross yield estimado por cenário.
- **Critérios secundários:** receita absoluta, estabilidade e robustez da evidência.
- **Unidade de decisão:** segmento residencial definido por bairro, tipologia e número de quartos; não um pareamento individual Airbnb–VivaReal.

## Definições operacionais

| Termo | Definição provisória | Limitação material |
|---|---|---|
| Melhor investimento | Segmento com maior gross yield proxy que permaneça competitivo em sensibilidade, tenha amostra suficiente e não dependa de anomalias | Não incorpora valorização, liquidez ou todos os custos |
| Perfil | Tipologia residencial + número de quartos + capacidade; atributos operacionais entram como explicadores secundários | Zero quarto só será chamado studio após validação textual |
| Localização | Bairro normalizado; coordenadas apenas para análise interna do Airbnb | Bairros das duas plataformas podem usar fronteiras/nomenclaturas diferentes |
| Preço anunciado | Valor de `Price_AV.price` associado a listing, data de estadia e captura | A documentação não informa moeda nem inclusão de taxas |
| ADR proxy | Estatística robusta dos preços anunciados por data de estadia no snapshot escolhido | Não é ADR realizado nem valor efetivamente recebido |
| Presença no arquivo | Existência de uma linha listing–data no dia de captura | Não será interpretada como disponibilidade, reserva ou ocupação |
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

O headline não usará soma de preços disponíveis como receita. Cenários de
ocupação, fatores de sazonalidade e custos ausentes ficarão em parâmetros
visíveis, nunca embutidos como constantes silenciosas.

### Premissa sobre moeda e taxas

O enunciado descreve `Price_AV` somente como preço por anúncio, data de estadia e
data de captura. O arquivo não contém coluna de moeda, taxa ou composição do
valor. Por decisão metodológica, os números serão tratados como **preços
anunciados presumidos em reais para a data de estadia**, coerentes com o contexto
brasileiro do desafio. Esta premissa não demonstra que o preço inclua ou exclua
taxas, limpeza ou impostos e não autoriza chamá-lo de diária recebida, ADR
realizado ou receita líquida.

## Regras de preparação já decididas

1. Preservar os CSVs originais em `data/` sem alteração.
2. Manter `Price_AV` no grain listing–data de estadia–dia de captura; agregar antes de juntar a métricas no nível do listing.
3. Ligar hosts por `(owner_id, timestamp de captura)` para evitar join N:N.
4. Usar somente coordenadas de `Mesh`.
5. Deduplicar VivaReal por `listing_id`; a única diferença não exata é ordem de amenities.
6. Excluir terreno e comercial do universo principal de compra residencial; inspecionar `outros` antes de decidir.
7. Preservar valores originais e criar flags de qualidade; não substituir outliers sem regra registrada.
8. Reportar tamanho da amostra, cobertura e dispersão junto a cada resultado.
9. Testar resultados com as duas sensibilidades de preços ≥ 10.000 e com as três
   regras de snapshot aprovadas.
10. Não interpretar associação de características como causalidade.

## Regras ainda condicionais

- **Faixa de incerteza:** mediana e p25/p75 serão obrigatórios; bootstrap será
  usado para incerteza amostral quando houver suporte, sem pretensão de corrigir
  viés de seleção.
- **Normalização de bairros:** apenas mapeamentos determinísticos e auditáveis;
  subdivisões ambíguas não serão fundidas silenciosamente.
- **Custos e retorno:** permanecem fora do primeiro ciclo de preço operacional.

## Condições que mudam o método

- Se um segmento tiver menos de 30 listings com preço em 20/01, ele não poderá
  entrar na análise principal do lado Airbnb, ainda que métodos secundários
  forneçam amostra maior.
- Se segmentos compactos no Centro tiverem amostra insuficiente no Airbnb ou no
  VivaReal, a tese será declarada inconclusiva para aquele componente; a
  definição não será ampliada silenciosamente.
- Se preços suspeitos forem concentrados em um segmento, o ranking deverá ser
  mostrado nas três versões: original, sem observações suspeitas e sem listings
  afetados.
- Se a cobertura ou a composição das datas de estadia alterar materialmente os
  resultados, a conclusão será restringida à população coberta e acompanhada de
  uma leitura ajustada de calendário; não haverá imputação de preços ausentes.
