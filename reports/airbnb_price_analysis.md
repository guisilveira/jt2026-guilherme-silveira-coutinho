# Primeira execução — confiabilidade dos preços anunciados do Airbnb

## Conclusão desta etapa

**A base pode avançar para a comparação de perfil e localização, mas somente com
conclusões condicionadas aos anúncios que possuem preço.** A captura de
20/01/2025 é a melhor leitura principal porque coloca os imóveis na mesma data de
referência. A mediana entre capturas funciona como segunda leitura: ela muda o
nível de preço de alguns segmentos, mas preserva os quatro primeiros do ranking.

A integridade da preparação é alta: todos os checks de chaves, cardinalidade e
reconciliação passaram. A representatividade é mais fraca: 22,5% dos 4.441
listings têm algum preço ligado e 17,5% aparecem na captura de 20/01. Essa
seleção é desigual e não pode ser corrigida com segurança pelos arquivos.

Este relatório não usa VivaReal, não estima ocupação, receita ou retorno e não
recomenda compra.

## Escopo e linguagem econômica

O enunciado informa apenas que `Price_AV` contém preço por anúncio, data de
estadia e data de captura. O arquivo não contém moeda, taxas ou status de
reserva. Por decisão humana, os valores são tratados como **preços anunciados
presumidos em reais para a data de estadia**. Não são diárias recebidas, ADR
realizado nem receita líquida; não é possível saber se incluem limpeza, impostos
ou taxas da plataforma.

Para impedir ponderação pela quantidade de linhas, o cálculo sempre segue:

```text
preços por listing e data de estadia
    → mediana por listing
    → mediana dos listings do segmento de imóveis
```

## Suporte dos três métodos

O universo da tabela abaixo é residencial — apartamentos e casas ligados a
`Details` — e a classificação usa somente o suporte do lado Airbnb.

| Método | Listings residenciais | Segmentos com preço | Principais (`n≥30`) | Exploratórios (`10≤n<30`) |
|---|---:|---:|---:|---:|
| Captura de 20/01 | 770 | 45 | 7 | 2 |
| Preço mais recente por listing–estadia | 981 | 64 | 7 | 4 |
| Mediana entre capturas | 981 | 64 | 7 | 4 |

Existem 777 listings de qualquer tipologia ligados à captura de 20/01 e 999 com
algum histórico ligado. A diferença para 770 e 981 na tabela são categorias não
residenciais, preservadas nas tabelas técnicas, mas fora do ranking principal.

## Preço anunciado na captura principal

| Segmento de imóveis | Listings | Mediana | p25–p75 | IC bootstrap 95% da mediana | Mediana de datas/listing |
|---|---:|---:|---:|---:|---:|
| Meia Praia · apartamento · 4 quartos | 43 | R$ 899 | R$ 735–1.537 | R$ 820–1.400 | 48 |
| Centro · apartamento · 3 quartos | 38 | R$ 664 | R$ 500–833 | R$ 523–800 | 57,5 |
| Meia Praia · apartamento · 3 quartos | 284 | R$ 650 | R$ 500–816 | R$ 602–700 | 54 |
| Centro · apartamento · 2 quartos | 59 | R$ 600 | R$ 399–682 | R$ 480–628 | 61 |
| Morretes · apartamento · 2 quartos | 43 | R$ 453,50 | R$ 352–554 | R$ 408–500 | 62 |
| Centro · apartamento · 1 quarto | 75 | R$ 450 | R$ 378–497 | R$ 402–471 | 67 |
| Meia Praia · apartamento · 2 quartos | 126 | R$ 448 | R$ 350–550 | R$ 400–461 | 52 |

Os intervalos de bootstrap representam somente incerteza amostral dentro dos
listings observados. Eles não corrigem cobertura seletiva, datas ausentes ou
diferenças não observadas de padrão do imóvel.

## A escolha do método muda a conclusão?

| Segmento principal | 20/01 | Mais recente | Mediana das capturas | Ranks nos três métodos |
|---|---:|---:|---:|---|
| Meia Praia · apartamento · 4 quartos | R$ 899 | R$ 1.012,50 | R$ 1.075 | 1 / 1 / 1 |
| Centro · apartamento · 3 quartos | R$ 664 | R$ 790 | R$ 780 | 2 / 2 / 2 |
| Meia Praia · apartamento · 3 quartos | R$ 650 | R$ 655,25 | R$ 682,67 | 3 / 3 / 3 |
| Centro · apartamento · 2 quartos | R$ 600 | R$ 580 | R$ 600 | 4 / 4 / 4 |
| Morretes · apartamento · 2 quartos | R$ 453,50 | R$ 464 | R$ 470 | 5 / 5 / 5 |
| Centro · apartamento · 1 quarto | R$ 450 | R$ 445 | R$ 448 | 6 / 7 / 7 |
| Meia Praia · apartamento · 2 quartos | R$ 448 | R$ 450 | R$ 450 | 7 / 6 / 6 |

- A correlação de ranks entre 20/01 e cada método secundário é 0,964.
- A diferença absoluta mediana é 2,3% no método mais recente e 3,6% na mediana
  entre capturas.
- A maior diferença é 19,0% e 19,6%, respectivamente, concentrada no nível de
  preço dos segmentos do topo.
- O segmento pontualmente mais caro e as quatro primeiras posições não mudam.
- As posições 6 e 7 trocam, mas suas medianas na captura principal diferem em
  apenas R$ 2.

**Decisão metodológica:** manter 20/01 como headline, mediana entre capturas como
segunda leitura e preço mais recente como diagnóstico adicional. O ranking é
estável no topo, mas o valor absoluto não deve ser tratado como preciso, sobretudo
para Meia Praia/4 quartos.

## Preços iguais ou superiores a R$ 10 mil

| Listing | Segmento de imóveis | Linhas de preço | Linhas suspeitas | Faixa observada |
|---|---|---:|---:|---:|
| `31167122` | Meia Praia · apartamento · 2 quartos | 85 | 85 | R$ 10.000–10.000 |
| `31397917` | Meia Praia · apartamento · 1 quarto | 15 | 1 | R$ 250–29.000 |
| `40391575` | Morretes · apartamento · 2 quartos | 7 | 7 | R$ 10.000–10.000 |

### Sensibilidade 1 — remover somente os preços suspeitos

Entre os sete segmentos principais, a maior mudança na mediana foi:

- 0,39% na captura de 20/01;
- 0,65% no preço mais recente;
- 0,53% na mediana entre capturas.

### Sensibilidade 2 — remover os três listings

Nos sete segmentos principais, o impacto máximo foi igual ao da primeira
sensibilidade e nenhum ranking do topo mudou. Isso acontece porque, na captura
principal, somente o listing afetado de Morretes participa de um segmento
principal e todas as suas linhas são suspeitas; remover as linhas já elimina seu
preço típico.

Há uma diferença relevante em resultado exploratório: nos métodos secundários,
Meia Praia/apartamento/1 quarto passa de R$ 441 para R$ 480, aumento de 8,8%,
quando o listing inteiro é removido. Remover apenas a observação de R$ 29 mil não
muda a mediana do listing, que continua R$ 250. Isso demonstra por que as duas
sensibilidades devem ser preservadas.

**Conclusão:** os valores extremos não determinam os sete segmentos principais,
mas podem alterar materialmente segmentos exploratórios menores.

## Problema 1 — perda de listings ao usar somente 20/01

| Segmento de imóveis | Algum preço | Preço em 20/01 | Perda | Retenção |
|---|---:|---:|---:|---:|
| Meia Praia · apartamento · 2 quartos | 187 | 126 | 61 | 67,4% |
| Meia Praia · apartamento · 3 quartos | 327 | 284 | 43 | 86,9% |
| Meia Praia · apartamento · 4 quartos | 60 | 43 | 17 | 71,7% |
| Morretes · apartamento · 2 quartos | 51 | 43 | 8 | 84,3% |
| Casa Branca · apartamento · 2 quartos | 11 | 4 | 7 | 36,4% |
| Centro · apartamento · 3 quartos | 45 | 38 | 7 | 84,4% |
| Centro · apartamento · 2 quartos | 65 | 59 | 6 | 90,8% |
| Meia Praia · apartamento · 1 quarto | 20 | 16 | 4 | 80,0% |
| Centro · apartamento · 1 quarto | 78 | 75 | 3 | 96,2% |

- **O que foi encontrado:** a redução não é uniforme. Meia Praia/2 quartos perde
  61 listings; Centro/1 quarto perde apenas 3. Casa Branca/2 quartos retém somente
  4 de 11 e deixa de ter suporte exploratório.
- **Pode alterar a comparação?** Sim. A captura comum favorece em suporte os
  segmentos com maior retenção, especialmente Centro/1 quarto, embora não dê
  peso adicional a esses listings no cálculo da mediana.
- **Como o efeito foi reduzido:** o método principal usa uma única captura; o
  ranking é repetido com os dois métodos de maior cobertura; quantidade e
  retenção são mostradas junto aos preços.
- **O que permanece sem solução:** não sabemos por que um listing não aparece em
  20/01 e não podemos imputar seu preço.
- **Impede avançar?** Não para os sete segmentos com `n≥30`, mas restringe a
  conclusão aos listings observados e reduz confiança em segmentos menores.

## Problema 2 — conjuntos diferentes de datas de estadia

| Segmento principal | Listings | Mediana de datas | Datas comuns a todos | Jaccard mediano | Distância do calendário geral | Rank original/ajustado |
|---|---:|---:|---:|---:|---:|---|
| Meia Praia · apartamento · 4 quartos | 43 | 48 | 0 | 0,442 | 0,061 | 1 / 1 |
| Centro · apartamento · 3 quartos | 38 | 57,5 | 0 | 0,485 | 0,082 | 2 / 2 |
| Meia Praia · apartamento · 3 quartos | 284 | 54 | 0 | 0,453 | 0,032 | 3 / 3 |
| Centro · apartamento · 2 quartos | 59 | 61 | 0 | 0,603 | 0,052 | 4 / 4 |
| Morretes · apartamento · 2 quartos | 43 | 62 | 0 | 0,570 | 0,067 | 5 / 7 |
| Centro · apartamento · 1 quarto | 75 | 67 | 5 | 0,731 | 0,049 | 6 / 5 |
| Meia Praia · apartamento · 2 quartos | 126 | 52 | 0 | 0,464 | 0,052 | 7 / 6 |

O Jaccard mede a semelhança entre os conjuntos de datas dos listings; 1 seria
igualdade total. A distância do calendário geral usa peso igual por listing; 0
seria uma composição de datas idêntica à do mercado residencial observado.

- **O que foi encontrado:** seis dos sete segmentos não têm uma única data
  presente para todos os listings. A semelhança entre listings varia de 0,442 a
  0,731. Porém, no agregado, a distância em relação ao calendário geral é baixa,
  entre 0,032 e 0,082.
- **Pode alterar a comparação?** Sim, sobretudo entre segmentos com preços muito
  próximos. Uma sensibilidade que divide cada preço pela mediana do mercado na
  mesma data preserva as quatro primeiras posições, mas reorganiza as três
  últimas.
- **Como o efeito foi reduzido:** peso igual por listing, reporte de datas por
  listing e comparação adicional ajustada pela data de estadia.
- **O que permanece sem solução:** ausência pode ser bloqueio, reserva, retirada
  ou coleta incompleta. O ajuste corrige apenas diferenças observáveis de data,
  não a seleção das noites.
- **Impede avançar?** Não para identificar os segmentos do topo; impede tratar a
  ordem entre os três segmentos de menor preço como uma diferença robusta.

## Problema 3 — listings com e sem preço são diferentes

### Bairro

| Categoria | Listings | Cobertura com algum preço | Cobertura em 20/01 | Diferença de representação: com preço − sem preço |
|---|---:|---:|---:|---:|
| Centro | 657 | 31,2% | 27,4% | +7,4 p.p. |
| Meia Praia | 2.860 | 22,1% | 16,9% | −1,5 p.p. |
| Morretes | 441 | 18,8% | 15,0% | −2,1 p.p. |
| Tabuleiro dos Oliveiras | 129 | 15,5% | 12,4% | −1,2 p.p. |

### Tipo e quartos

| Categoria | Cobertura com algum preço | Cobertura em 20/01 | Diferença de representação |
|---|---:|---:|---:|
| Apartamento | 24,6% | 19,9% | +9,9 p.p. |
| Casa | 15,8% | 7,4% | −3,8 p.p. |
| 1 quarto | 26,2% | 20,0% | +2,6 p.p. |
| 2 quartos | 23,7% | 17,7% | +2,3 p.p. |
| 3 quartos | 21,0% | 17,7% | −3,7 p.p. |
| 0 quartos | 14,3% | 12,5% | −0,6 p.p. |

- **O que foi encontrado:** Centro, apartamentos e imóveis de um ou dois quartos
  estão sobrerrepresentados entre os listings com preço. Centro/1 quarto tem
  cobertura de 67,2% em algum snapshot e 64,7% em 20/01, muito acima da base.
- **Pode alterar a comparação?** Sim. Isso aumenta o suporte estatístico desses
  segmentos e pode esconder diferenças entre os listings precificados e os não
  precificados.
- **Como o efeito foi reduzido:** cada listing recebe peso igual; rankings exigem
  suporte mínimo; cobertura e composição são reportadas; não foi feita imputação.
  Entre os nove segmentos com ao menos dez listings na captura principal, a
  correlação de Spearman entre preço e número de listings foi 0,30 e entre preço
  e cobertura foi −0,13. Não há evidência de que a mediana seja alta apenas por
  haver mais listings, mas a amostra é pequena para esse diagnóstico.
- **O que permanece sem solução:** a ausência provavelmente não é aleatória e os
  arquivos não permitem corrigir fatores não observados. Ponderação por atributos
  observáveis não resolveria esse problema com segurança.
- **Impede avançar?** Não para descrever a amostra coberta. Impede generalizar os
  resultados como retrato não enviesado de todos os anúncios de Itapema.

## Problema 4 — moeda, unidade e taxas

- **O que foi encontrado:** não existe definição de moeda ou composição de taxas
  nos CSVs, README ou enunciado. A documentação sustenta apenas que há um preço
  por listing, data de estadia e captura.
- **Pode alterar a comparação?** Se todos os registros seguirem a mesma unidade,
  a comparação relativa permanece útil. Pode alterar totalmente qualquer
  interpretação de receita ou retorno.
- **Como o efeito foi reduzido:** premissa explícita de preço anunciado presumido
  em reais e proibição de tratá-lo como valor recebido ou receita líquida.
- **O que permanece sem solução:** inclusão de limpeza, impostos, taxas da
  plataforma e descontos.
- **Impede avançar?** Não para ranking relativo de preços anunciados. Impede
  converter os valores diretamente em receita realizada e exige cenários
  conservadores na etapa econômica.

## Verificação de integridade

| Check | Resultado |
|---|---|
| IDs de `Details` e `Mesh` únicos | OK |
| Join `Details`–`Mesh` | 4.441 → 4.441, sem multiplicação |
| Grain listing–estadia–capture_day | 0 duplicações |
| Reconciliação de `Price_AV` | 118.330 linhas ligadas + 509 órfãs = 118.839 |
| Reconciliação de IDs de preço | 999 ligados + 6 órfãos = 1.005 |
| Grain listing–método–tratamento | 0 duplicações |
| Pares listing–estadia após cada método | 0 duplicações nos nove resultados |

Os 509 registros órfãos não foram descartados silenciosamente: permanecem na
reconciliação, mas não entram em segmentos porque não possuem atributos em
`Details`. Hashes SHA-256 dos três arquivos de entrada e contagens de cada
transformação foram gravados nos artefatos gerados.

## Decisão de continuidade

**O bloco de preço operacional está suficientemente íntegro para avançar, com
confiança moderada na ordenação dos segmentos principais e baixa confiança na
representatividade do mercado completo.**

Condições para o próximo bloco:

1. usar 20/01 como preço principal e mediana entre capturas como sensibilidade;
2. manter quantidade, dispersão e intervalo junto de toda comparação;
3. não promover resultados abaixo de 30 listings para conclusão principal;
4. manter as duas sensibilidades de preços suspeitos;
5. declarar que a análise representa listings com preço, não todos os anúncios;
6. tratar diferenças pequenas entre os segmentos de menor preço como empate
   metodológico, pois calendário e snapshot alteram sua ordem.

Nenhuma conclusão de investimento foi produzida nesta etapa.
