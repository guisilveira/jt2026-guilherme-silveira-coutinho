# AGENTS.md

## Objetivo do projeto

Construir uma recomendação de investimento imobiliário para a Seazone em Itapema, sustentada pelos dados fornecidos no desafio.

A entrega deve responder às quatro perguntas oficiais e tomar posição sobre a tese de apartamentos compactos — studio ou um quarto — no Centro.

## Prioridades

Sob pressão de tempo, priorize nesta ordem:

1. Decisão de investimento acionável.
2. Sustentação nos dados.
3. Validade metodológica.
4. Estimativa de retorno defensável.
5. Comunicação e reprodutibilidade.

O dashboard é uma ferramenta de comunicação, não o objetivo principal.

## Regras de análise

- Antes de analisar, audite schemas, granularidade, período, duplicatas, valores ausentes, outliers e chaves de relacionamento.
- Nunca altere os CSVs originais.
- Preserve dados brutos em `data/raw/` e salve transformações reproduzíveis separadamente.
- Não assuma que anúncios do Airbnb e VivaReal representam os mesmos imóveis.
- Quando não houver ligação imóvel a imóvel, compare segmentos agregados e declare essa limitação.
- Defina explicitamente “melhor”, “perfil”, “localização”, “receita” e “retorno”.
- Não confunda maior receita com melhor retorno sobre o investimento.
- Não apresente associação ou importância preditiva como causalidade.
- Informe tamanho da amostra e limitações junto às conclusões relevantes.
- Separe fatos observados, inferências, hipóteses e premissas.
- Dados externos podem contextualizar, mas não substituir a evidência dos arquivos do desafio; cite a fonte e identifique-os como externos.

## Forma de trabalhar

Antes de implementar uma mudança substancial:

1. Declare a pergunta ou hipótese.
2. Explique qual análise mínima pode testá-la.
3. Informe o resultado esperado e o critério de decisão.

Depois de implementar:

1. Execute a análise.
2. Verifique os resultados e casos extremos.
3. Registre a evidência encontrada.
4. Informe o que permanece incerto.
5. Recomende a próxima ação.

Não implemente grandes blocos de análise sem checkpoints intermediários.

## Critérios mínimos de pronto

A entrega somente está pronta quando:

- responde explicitamente às quatro perguntas;
- toma posição sobre a tese dos compactos no Centro;
- recomenda o que comprar, onde, por qual faixa de preço e por quê;
- apresenta fórmula, premissas e sensibilidade da estimativa de retorno;
- permite rastrear as conclusões até dados e código;
- documenta limitações capazes de mudar a decisão;
- possui instruções de execução no `README.md`;
- possui recomendação final escrita;
- possui a sessão completa exportada em texto para `ai-log/`;
- possui vídeo acessível de até três minutos.

## Comunicação

- Comece pela decisão, depois mostre as evidências.
- Cada gráfico deve responder a uma pergunta específica.
- Use títulos que expressem a conclusão do gráfico.
- Evite precisão superior à sustentada pelos dados.
- No final, diferencie recomendação, confiança, riscos e condições que fariam a decisão mudar.

## Preservação do processo

- Não apague tentativas ou resultados apenas porque falharam.
- Não esconda sugestões incorretas da IA; registre como foram verificadas e corrigidas.
- Não trate o `ai-log/` como uma seleção dos melhores prompts: a sessão completa faz parte da avaliação.