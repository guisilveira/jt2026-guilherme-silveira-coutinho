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
11. A comparação principal continuará dando peso igual a cada listing. A
    concentração será diagnosticada por `owner_id` com duas sensibilidades:
    mediana dos preços típicos de cada anfitrião, dando peso igual aos hosts, e
    retirada do anfitrião com mais listings. Empates no maior número de listings
    serão testados separadamente, sem escolha arbitrária de um ID.
12. A incerteza será mostrada por bootstrap de listings e por bootstrap agrupado
    por `owner_id`. Na versão agrupada, o anfitrião é reamostrado e todos os seus
    listings permanecem juntos; assim, anúncios do mesmo operador não são
    tratados como observações totalmente independentes. Nos contrastes entre
    dois segmentos, a união dos anfitriões é reamostrada uma vez por réplica, de
    modo que um host presente nos dois segmentos se mova conjuntamente.
13. Diferenças entre segmentos terão duas leituras separadas: tamanho do efeito
    em reais e percentual, e evidência estatística. A evidência será chamada de
    **inconclusiva** quando o intervalo agrupado da diferença incluir zero. Uma
    diferença estatisticamente sustentada não será chamada automaticamente de
    economicamente relevante; esse limite depende da futura análise de aquisição
    e retorno.
14. As diferenças entre regras de preço serão decompostas na ordem: método de
    preço → conjunto de datas → conjunto de listings. Os valores são mudanças
    incrementais condicionais a essa sequência, não três causas independentes.
    Por usar medianas, outra ordem pode atribuir valores diferentes às etapas; a
    soma deve reconciliar com a mudança total antes do arredondamento.
15. No ciclo 2, os contrastes previamente definidos da tese serão as comparações
    principais. Demais combinações de bairro, tipologia e quartos serão
    exploratórias e não sustentarão sozinhas uma conclusão geral.
16. A evidência entre segmentos terá somente duas classes: **diferença
    estatisticamente sustentada**, quando o intervalo de 95% do bootstrap
    agrupado por `owner_id` excluir zero, e **evidência inconclusiva**, quando o
    intervalo incluir zero. A diferença em reais e percentual será sempre
    reportada, sem limiar de relevância econômica nesta etapa.
17. Uma afirmação geral sobre localização exigirá pelo menos dois perfis
    equivalentes com 30 ou mais listings em cada bairro e direção coerente nos
    contrastes de preço total. Para chamar a vantagem de sustentada, os
    intervalos agrupados desses contrastes também deverão excluir zero na mesma
    direção. Sem isso, a conclusão permanecerá condicionada ao perfil.
18. O ajuste de calendário do ciclo 2 reutilizará a função do ciclo 1: o
    universo será limitado a apartamentos e casas antes de calcular a mediana
    diária e a escala de referência. Um check comparará, por segmento, as
    medianas ajustadas com `reports/generated/airbnb_price_calendar.csv`.

## Pré-registro da tese operacional dos compactos — ciclo 2

A tese será julgada em dois componentes separados, antes de observar os
resultados do ciclo:

1. **Vantagem de localização:** Centro · apartamento · 1 quarto contra o mesmo
   perfil em outros bairros. Evidência favorável exige diferença positiva no
   preço anunciado total com intervalo agrupado excluindo zero e direção que
   não se inverta na mediana entre capturas nem nas duas sensibilidades de
   preços suspeitos. Contrastes sem 30 listings nos dois lados serão
   exploratórios e não bastarão para declarar o componente sustentado.
2. **Vantagem do compacto:** Centro · apartamento · 1 quarto contra apartamentos
   maiores no Centro. O julgamento priorizará preço anunciado por hóspede
   comportado e preço anunciado por quarto; não será exigido que o compacto tenha
   preço total superior. Para cada perfil maior principal, evidência favorável
   exige ao menos uma dessas duas métricas com diferença positiva sustentada,
   nenhuma com diferença contrária sustentada e direção robusta nas
   sensibilidades principais. O componente só será favorável se essa condição
   valer para todos os perfis maiores principais disponíveis; resultado favorável
   em apenas parte deles será inconclusivo. Se as métricas divergirem, o conflito
   será exposto sem escolher a mais favorável.

A classificação conjunta será:

- **sustentada operacionalmente:** os dois componentes têm evidência favorável
  e robusta;
- **parcialmente sustentada:** somente um componente tem evidência favorável;
- **não sustentada:** há evidência robusta contrária nos dois componentes;
- **inconclusiva:** os dados não sustentam claramente nenhuma das três posições
  anteriores.

Essa classificação é apenas operacional. No componente compacto, "favorável"
significa somente maior densidade de preço anunciado por capacidade declarada.
Preço por hóspede e por quarto não demonstra demanda, ocupação, receita,
retorno ou eficiência por área ou capital. A divisão por quarto pode favorecer
mecanicamente imóveis menores. A classificação não considera aquisição.

## Regras prévias para capacidade — ciclo 2

As flags abaixo serão calculadas em `Details`, antes do cruzamento com preços:

1. `number_of_guests` ausente, não conversível, não finito, zero ou negativo é
   inválido para preço por hóspede, mas o listing permanece no preço total.
2. Capacidade positiva não inteira será marcada como suspeita e preservada.
3. Capacidade positiva acima da cerca externa de Tukey (`p75 + 3 × IQR`) de
   seu perfil `tipologia × quartos`, calculada somente em perfis com pelo menos
   30 capacidades positivas válidas, será marcada como suspeita. Nos demais
   perfis será usada a cerca externa global. A regra usa somente capacidade e
   perfil, sem observar preço.
4. Em imóveis com quartos positivos, capacidade menor que o número de quartos
   será marcada como suspeita por inconsistência interna, sem exclusão do
   resultado principal.
5. O resultado principal por hóspede manterá todas as capacidades positivas,
   inclusive as suspeitas. A sensibilidade retirará todas as capacidades
   positivas sinalizadas pela regra prévia, sem seleção posterior pelo efeito.
6. Preço por quarto será calculado somente quando quartos for finito e maior que
   zero. Zero quarto permanecerá separado; não haverá imputação.

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
| Preço anunciado por hóspede comportado | Preço anunciado típico do listing dividido por `number_of_guests` positivo | Mede somente densidade sobre capacidade declarada; não mede demanda, ocupação, receita, retorno ou eficiência por área/capital |
| Preço anunciado por quarto | Preço anunciado típico do listing dividido por quartos, somente quando quartos > 0 | Pode favorecer mecanicamente imóveis menores e não mede desempenho econômico |
| ADR proxy | Estatística robusta dos preços anunciados por data de estadia no snapshot escolhido | Não é ADR realizado nem valor efetivamente recebido |
| Presença no arquivo | Existência de uma linha listing–data no dia de captura | Não será interpretada como disponibilidade, reserva ou ocupação |
| Receita bruta em cenário | `ADR proxy × noites ocupadas assumidas` | Não é receita observada; ocupação será premissa ou proxy explicitamente rotulado |
| Preço de aquisição | Distribuição de `sale_price` deduplicado no segmento VivaReal | É preço pedido, não transacionado |
| Gross yield proxy | `receita bruta anual em cenário ÷ preço de aquisição do segmento` | Numerador e denominador vêm de imóveis diferentes do mesmo segmento |
| Yield após condomínio observado | `(receita bruta em cenário − 12 × condomínio mensal válido) ÷ preço de aquisição` | Ainda não é retorno líquido; faltam custos operacionais e de compra |

## Fórmulas provisórias

```text
preco_anualizado_no_cenario = preco_anunciado_tipico × fator_sazonalidade × 365 × ocupacao_cenario

gross_yield_proxy = preco_anualizado_no_cenario / preco_pedido_mediano_segmento

yield_apos_condominio =
    (preco_anualizado_no_cenario - 12 × condominio_mensal_mediano_valido)
    / preco_pedido_mediano_segmento
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

- **Faixa de incerteza:** mediana e p25/p75 serão obrigatórios; bootstrap por
  listing e agrupado por anfitrião serão usados quando houver suporte, sem
  pretensão de corrigir viés de seleção.
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

## Decisões implementadas no Ciclo 3 — compra e retorno

As regras abaixo são **decisões metodológicas humanas**, não fatos fornecidos
pelos dados:

1. A ligação Airbnb–VivaReal é exclusivamente agregada por `bairro normalizado
   + tipo residencial + quartos`. IDs, títulos e descrições não são usados para
   correspondência individual.
2. A normalização de bairro remove caixa, espaços repetidos e acentos. Ausências
   permanecem `desconhecido`, não são ligadas entre plataformas e subdivisões
   como `Meia Praia - Frente Mar` não são fundidas.
3. O VivaReal é deduplicado por `listing_id` somente após comprovar que as 36
   duplicações não divergem além da ordem de `amenities`. Não se tenta detectar
   imóveis físicos repetidos sob IDs diferentes.
4. O universo residencial principal contém apenas apartamentos e casas.
   Terrenos, comerciais e `outros` são filtros de escopo, não erros.
5. Preços pedidos inválidos são ausentes, não finitos ou não positivos. Valores
   abaixo de R$ 100 mil ou fora da cerca externa `p25 ± 3 × IQR` do segmento
   com pelo menos 20 anúncios recebem flag e permanecem no headline; somente a
   sensibilidade os retira.
6. Área ausente/não finita, não positiva ou acima de 1.000 m² não exclui o
   anúncio da análise de preço. Ela fica fora apenas das métricas por m².
7. Condomínio ausente ou zero significa desconhecido. O yield após condomínio
   usa somente valores positivos, não suspeitos e apresenta suporte principal
   apenas com pelo menos 20 observações válidas no segmento.
8. IPTU é auditado, mas não descontado no Ciclo 3.
9. O headline usa preço Airbnb da captura de 20/01 e preço pedido mediano. Os
   nove pares de ocupação (30%, 45%, 60%) e sazonalidade (60%, 80%, 100%) são
   testes de estresse; nenhum é o mais provável. O par 45% × 80% é apenas uma
   leitura intermediária para comunicação.
10. As sensibilidades são univariadas e pré-definidas: mediana Airbnb entre
    capturas, ajuste de calendário, dois tratamentos dos preços Airbnb ≥ R$ 10
    mil, p25/p75 do preço de compra, retirada dos preços de compra suspeitos e
    condomínio observado. Não há escolha posterior da regra mais favorável.
11. Suporte principal exige 30 anúncios Airbnb com preço em 20/01 e 20 anúncios
    VivaReal deduplicados; exploratório exige ao menos 10 em cada base.
12. O componente econômico dos compactos só é favorável se Centro/apartamento/1
    quarto superar Centro/2 e Centro/3 no gross yield proxy e preservar o sinal
    nas sensibilidades. Inversão produz classificação inconclusiva.

### Interpretação econômica

`preço anualizado no cenário` é um valor construído a partir de preço anunciado
e premissas. `gross yield proxy` relaciona segmentos agregados de duas bases, não
o fluxo de caixa de um imóvel. `yield após condomínio observado` desconta apenas
um custo parcial e com cobertura seletiva. Nenhuma dessas métricas é receita
realizada, retorno líquido, ADR realizado ou rentabilidade garantida.
