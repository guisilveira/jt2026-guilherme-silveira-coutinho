# Hipóteses e plano priorizado

## Hipóteses verificáveis

### H1 — O painel permite uma proxy de disponibilidade

- **Pergunta de negócio:** é possível transformar `Price_AV` em insumo de receita sem fingir que preço anunciado é reserva?
- **Hipótese principal:** a presença de listing–data em cada captura se comporta como disponibilidade aparente; desaparecimentos aumentam perto da estadia e reaparências são raras.
- **Hipótese concorrente:** presença/ausência é instável ou reflete falhas/bloqueios, não permitindo proxy de disponibilidade.
- **Unidade:** listing × data de estadia × dia de captura.
- **População/filtros:** 628 listings presentes nos três dias; janela comum de 20/01 a 06/04; preços extremos sinalizados, não removidos no primeiro passe.
- **Métrica:** transições presente→ausente, ausente→presente, persistência, lead time e mudança de preço.
- **Arquivos/relações:** `Price_AV`; grain derivado por `capture_day`.
- **Análise mínima:** matriz de presença nas três capturas e tabela de transições por lead time.
- **Sustenta:** desaparecimento predominantemente monotônico e reaparência menor que 10% dos desaparecimentos; sensibilidade do limiar em 5% e 20%.
- **Enfraquece:** reaparências frequentes, buracos não temporais ou forte dependência do listing/captura.
- **Limitação:** mesmo uma boa proxy não distingue reserva de bloqueio e não estima receita realizada.
- **Esforço:** baixo/médio.
- **Prioridade:** `MUST` — primeiro ciclo.

### H2 — Perfil e localização alteram o preço anunciado e a receita em cenário

- **Pergunta de negócio:** quais perfis e bairros têm maior potencial operacional?
- **Hipótese principal:** existem diferenças robustas de ADR proxy e receita em cenário entre tipologia, quartos, tipo de anúncio e bairro.
- **Hipótese concorrente:** diferenças aparentes são explicadas por capacidade, cobertura desigual, outliers ou composição.
- **Unidade:** listing, após agregação temporal sem ponderar por número de linhas.
- **População/filtros:** 999 listings com `Details`, `Mesh` e preço; residenciais; exigir amostra mínima.
- **Métrica:** mediana de ADR proxy, receita bruta em cenários comuns, dispersão e n.
- **Arquivos/relações:** `Details → Mesh`, `Details → Price_AV`.
- **Análise mínima:** tabela e intervalos por bairro × tipologia × quartos; comparação com/sem outliers.
- **Sustenta:** diferenças persistentes em snapshots, estatísticas robustas e cenários.
- **Enfraquece:** ranking instável ou intervalos amplamente sobrepostos.
- **Limitação:** amostra de preços cobre 22,5% e não é aleatória; não há `room_type` explícito para responder diretamente imóvel inteiro/quarto privativo/compartilhado.
- **Esforço:** médio.
- **Prioridade:** `MUST`.

### H3 — O mercado de compra varia materialmente entre coortes comparáveis

- **Pergunta de negócio:** quanto capital cada perfil/localização exige?
- **Hipótese principal:** preço pedido e preço por m² diferem de forma material por bairro, tipologia e quartos.
- **Hipótese concorrente:** diferenças resultam de área, padrão ou anomalias dentro das coortes.
- **Unidade:** anúncio de venda deduplicado.
- **População/filtros:** residenciais; excluir comercial/terreno; regras de qualidade para preço e área; `outros` sob inspeção.
- **Métrica:** mediana, p25/p75 de preço, preço/m², condomínio e tamanho amostral.
- **Arquivos/relações:** `VivaReal`; coortes agregadas.
- **Análise mínima:** distribuição de aquisição por coorte e flags de qualidade.
- **Sustenta:** diferenças robustas a filtros e controle por área.
- **Enfraquece:** coortes pequenas ou ranking dirigido por registros anômalos.
- **Limitação:** preço pedido, sem idade, padrão construtivo, mobiliário ou transação.
- **Esforço:** baixo/médio.
- **Prioridade:** `MUST`.

### H4 — Compactos no Centro têm maior receita anunciada

- **Pergunta de negócio:** a primeira parte da tese interna é sustentada?
- **Hipótese principal:** apartamentos de zero/um quarto no Centro superam alternativas comparáveis em ADR proxy e receita em cenário.
- **Hipótese concorrente:** compactos no Centro têm receita absoluta inferior e eventual vantagem existe somente por eficiência/preço.
- **Unidade:** listing Airbnb.
- **População/filtros:** apartamentos residenciais com preço; zero e um quarto separados e combinados; Centro versus demais bairros com n suficiente.
- **Métrica:** ADR proxy, receita em cenários idênticos, dispersão e estabilidade entre capturas.
- **Arquivos/relações:** `Details → Mesh → Price_AV`.
- **Análise mínima:** contraste pré-registrado compacto/Centro versus cada alternativa relevante.
- **Sustenta:** vantagem consistente e não dependente de poucos outliers.
- **Enfraquece:** receita menor, amostra pequena ou resultado instável.
- **Limitação:** não há receita realizada; Centro tem cobertura de preço acima da média.
- **Esforço:** baixo após H1/H2.
- **Prioridade:** `MUST`.

### H5 — Compactos no Centro têm maior gross yield proxy

- **Pergunta de negócio:** a eficiência operacional compensa o preço de compra?
- **Hipótese principal:** compactos no Centro maximizam gross yield proxy entre coortes residenciais viáveis.
- **Hipótese concorrente:** preço de aquisição no Centro elimina a vantagem, ou outro bairro/perfil oferece yield maior.
- **Unidade:** coorte bairro × tipologia × quartos.
- **População/filtros:** interseção semântica de coortes Airbnb e VivaReal; amostra mínima nos dois lados.
- **Métrica:** gross yield proxy em cenários de ocupação, preço de compra p25/mediana/p75 e yield após condomínio válido.
- **Arquivos/relações:** `Details`, `Mesh`, `Price_AV` e `VivaReal`, somente por relação agregada.
- **Análise mínima:** matriz de cenários por coorte e fronteira de Pareto receita–capital–evidência.
- **Sustenta:** compacto/Centro lidera ou permanece no grupo dominante na maioria dos cenários.
- **Enfraquece:** liderança só ocorre em uma premissa extrema ou outra coorte domina.
- **Limitação:** numerador e denominador não pertencem ao mesmo imóvel; ocupação é cenário.
- **Esforço:** médio.
- **Prioridade:** `MUST`.

### H6 — A vantagem de compactos desaparece ao controlar composição

- **Pergunta de negócio:** a tese é efeito do perfil ou reflexo de localização, capacidade e tipo?
- **Hipótese principal:** a vantagem bruta diminui materialmente ao controlar bairro, hóspedes, tipologia, captura e host.
- **Hipótese concorrente:** compactos mantêm associação positiva após controles observáveis.
- **Unidade:** listing Airbnb, com métricas temporais agregadas.
- **População/filtros:** listings residenciais com preço e covariáveis completas; comparar com amostra sem imputação.
- **Métrica:** efeito associativo padronizado/contrastes ajustados; validação fora da amostra se houver modelo preditivo.
- **Arquivos/relações:** `Details → Mesh → Price_AV`, opcionalmente `Hosts` pela chave composta.
- **Análise mínima:** regressão/árvore simples com controles e diagnóstico de colinearidade; não interpretar causalmente.
- **Sustenta:** coeficiente/importance de compacto cai ou muda de sinal após controles.
- **Enfraquece:** associação permanece estável em especificações e amostras alternativas.
- **Limitação:** confundidores não observados, seleção da amostra e horizonte curto.
- **Esforço:** médio/alto.
- **Prioridade:** `MUST` para responder “características associadas”, após análises descritivas.

### H7 — Outro segmento oferece melhor retorno ou evidência mais robusta

- **Pergunta de negócio:** qual é a melhor alternativa à tese?
- **Hipótese principal:** pelo menos uma coorte supera compacto/Centro em yield proxy ou oferece resultado próximo com amostra/estabilidade melhores.
- **Hipótese concorrente:** compacto/Centro domina alternativas relevantes.
- **Unidade:** coorte harmonizada.
- **População/filtros:** coortes residenciais com suporte mínimo nos dois mercados.
- **Métrica:** yield proxy, receita, dispersão, n e cobertura; dominância de Pareto.
- **Arquivos/relações:** todos, por relações validadas/agregadas.
- **Análise mínima:** ranking com incerteza e identificação do melhor concorrente.
- **Sustenta:** alternativa domina ou empate econômico com evidência superior.
- **Enfraquece:** nenhuma alternativa permanece competitiva nos cenários.
- **Limitação:** coortes podem ocultar diferenças de área/padrão.
- **Esforço:** baixo após H5.
- **Prioridade:** `MUST`.

### H8 — Atributos do anúncio estão associados a preços/receita melhores

- **Pergunta de negócio:** quais características observáveis acompanham melhor desempenho?
- **Hipótese principal:** capacidade, avaliações, guest favorite, reserva instantânea, fotos e amenities selecionadas agregam sinal além de bairro/perfil.
- **Hipótese concorrente:** associações desaparecem após controles ou refletem tempo ativo/qualidade do host.
- **Unidade:** listing.
- **População/filtros:** amostra com preço; zeros de rating recodificados como não avaliados; amenities com suporte mínimo.
- **Métrica:** diferenças ajustadas, importância preditiva com validação e estabilidade entre especificações.
- **Arquivos/relações:** `Details`, `Mesh`, `Price_AV`, `Hosts`.
- **Análise mínima:** modelo explicativo simples e tabela de efeitos associativos; checagem de leakage e colinearidade.
- **Sustenta:** sinal consistente fora da amostra e em análise robusta.
- **Enfraquece:** instabilidade, baixo ganho preditivo ou efeito explicado por bairro/capacidade.
- **Limitação:** associação, não causalidade; muitos campos são pós-performance, como reviews.
- **Esforço:** alto.
- **Prioridade:** `SHOULD` além do conjunto mínimo de controles de H6.

### H9 — Gestão profissional/host confunde o desempenho do imóvel

- **Pergunta de negócio:** o retorno aparente pertence ao imóvel/local ou à operação do host?
- **Hipótese principal:** atributos do host e concentração de listings explicam parte relevante das diferenças.
- **Hipótese concorrente:** perfil/localização preservam associação após efeitos de host.
- **Unidade:** listing, com clusters por `owner_id`.
- **População/filtros:** listings com preço e chave composta de host.
- **Métrica:** comparação de modelos com/sem atributos ou efeitos de host; erros agrupados por host.
- **Arquivos/relações:** `Details → Hosts`, `Details → Price_AV`.
- **Análise mínima:** sensibilidade com `is_professional`, superhost, experiência e concentração.
- **Sustenta:** mudanças materiais nas estimativas de perfil/localização.
- **Enfraquece:** resultados estáveis após inclusão dos controles.
- **Limitação:** resposta do host está 100% ausente; Seazone domina extremos de reviews/listings.
- **Esforço:** médio.
- **Prioridade:** `SHOULD`.

### H10 — Micro-localização e amenities refinam a decisão

- **Pergunta de negócio:** há sinal adicional dentro dos bairros e perfis líderes?
- **Hipótese principal:** proximidade geográfica e conjuntos de amenities diferenciam preço anunciado dentro da coorte.
- **Hipótese concorrente:** o ganho é pequeno, instável ou não transportável ao mercado de compra.
- **Unidade:** listing Airbnb.
- **População/filtros:** somente coortes líderes com n suficiente.
- **Métrica:** gradientes espaciais e efeitos associativos de amenities frequentes.
- **Arquivos/relações:** `Mesh`, `Details`, `Price_AV`.
- **Análise mínima:** mapa/efeitos locais apenas se alterar a decisão.
- **Sustenta:** melhoria robusta e interpretável dentro da coorte.
- **Enfraquece:** efeito frágil ou sem equivalente observável no VivaReal.
- **Limitação:** VivaReal não tem coordenadas; não permite matching individual.
- **Esforço:** alto.
- **Prioridade:** `COULD`.

## Priorização consolidada

| Prioridade | Análises | Motivo |
|---|---|---|
| `MUST` | H1–H7 | Determinam validade da proxy, respondem perfil/localização, incorporam aquisição, testam a tese e procuram alternativa |
| `SHOULD` | H8–H9 | Aumentam robustez das associações e separam imóvel de qualidade de gestão |
| `COULD` | H10; matching manual exploratório; NLP amplo de descrições | Alto esforço ou baixa capacidade de mudar uma decisão em um dia |

Matching aproximado Airbnb–VivaReal não será executado na análise principal.

## Ciclos de trabalho

| Ciclo | Hipótese → análise mínima | Evidência gerada | Decisão ao final |
|---|---|---|---|
| 0 — concluído | Integridade e relações → auditoria e joins | Schema, granularidade, cobertura, riscos e métricas possíveis | Grafo validado; receita real não observável |
| 1 | H1 → painel comum de três capturas | Transições de presença e preços por lead time | Usar disponibilidade aparente ou abandonar essa proxy |
| 2 | H2/H4 → métricas no nível do listing e contrastes de perfil/local | Receita em cenário, dispersão, n e cobertura | Manter/revisar definição de perfil e candidatos |
| 3 | H3/H5/H7 → coortes VivaReal e yield em cenários | Preço de compra, condomínio válido, Pareto e tese versus alternativas | Selecionar shortlist econômica e posição provisória sobre a tese |
| 4 | H6/H8/H9 → controles, robustez e sensibilidade | Associações ajustadas e condições de mudança | Confirmar, reduzir confiança ou abandonar shortlist |
| 5 | Síntese e comunicação | Recomendação rastreável, README e roteiro do vídeo | Entrega final; dashboard somente se ainda agregar clareza |

## Primeiro ciclo recomendado — e único autorizado a seguir após revisão

**Pergunta:** a presença de uma diária em `Price_AV` pode ser usada, com baixa confiança, como proxy de disponibilidade aparente?

**Análise mínima:**

1. restringir aos 628 listings presentes nas três datas de captura;
2. usar a janela comum de estadia de 20/01 a 06/04/2025;
3. construir a matriz listing × estadia × captura, marcando apenas presença/ausência de linha;
4. medir presente→ausente, ausente→presente, persistência e mudança de preço por lead time;
5. repetir com todos os listings elegíveis em cada par de capturas para avaliar viés do painel balanceado;
6. manter os preços extremos sinalizados e executar uma versão robusta sem os casos suspeitos.

**Critério de decisão pré-registrado:** se reaparências forem inferiores a 10% dos desaparecimentos, com conclusão estável nos limiares de 5% e 20%, e desaparecimentos crescerem à medida que a estadia se aproxima, aceitar presença como **proxy de disponibilidade aparente**, nunca como reserva. Caso contrário, abandonar essa proxy e estimar receita somente por cenários explícitos de ocupação aplicados ao preço anunciado.

**Resultado esperado:** uma decisão binária sobre o uso da proxy, a regra de snapshot e a população válida para o ciclo 2. Nenhuma recomendação de imóvel será emitida nesse ciclo.
