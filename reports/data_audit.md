# Auditoria dos dados

## Escopo e convenções

- **Fato observado** é resultado calculado diretamente dos CSVs.
- **Inferência** é uma interpretação compatível com a estrutura observada, ainda sem documentação semântica suficiente.
- **Decisão metodológica** é uma regra humana revisável para a análise posterior.
- **Limitação** identifica algo que os arquivos não permitem concluir com segurança.

Os CSVs originais em `data/` não foram modificados. A evidência detalhada e o schema completo são reproduzidos por `scripts/audit_data.py`. O dicionário técnico de todas as colunas está em `reports/generated/data_dictionary.csv`.

## Visão geral

| Arquivo | Linhas | Colunas | Unidade de observação constatada | Período observado |
|---|---:|---:|---|---|
| `Details_Itapema.csv` | 4.441 | 35 | Um registro por `airbnb_listing_id`; snapshot de atributos do anúncio | Capturado em 13/01/2025, entre 01:54 e 03:01 |
| `Hosts_ids_Itapema.csv` | 4.440 | 11 | Atributos do anfitrião repetidos durante a captura dos listings; não é uma dimensão única por host | Capturado em 13/01/2025, entre 01:54 e 03:01 |
| `Mesh_Ids_Data_Itapema.csv` | 4.441 | 8 | Uma localização por `airbnb_listing_id` | `aquisition_date` entre 25/10/2021 e 04/05/2026, em 99 datas |
| `Price_AV_Itapema.csv` | 118.839 | 4 | Um preço por listing, data de estadia e dia de captura | Estadias de 06/01/2025 a 20/04/2025; capturas em 06/01, 07/01 e 20/01/2025 |
| `VivaReal_Itapema.csv` | 8.329 | 22 | Um anúncio de venda por linha, com duplicações | Snapshot em 11/01/2025 |

`aquisition_date` é a grafia presente nos arquivos. O relatório preserva esse nome, embora a palavra em inglês esteja grafada incorretamente.

## `Details_Itapema.csv`

### Schema e identificadores

- **Fato:** `airbnb_listing_id` é completo e único: 4.441 IDs para 4.441 linhas.
- **Fato:** `owner_id` é completo, mas não único: 3.057 anfitriões; 509 aparecem em mais de um listing; máximo de 112 listings para um anfitrião.
- **Fato:** não existem linhas exatamente duplicadas.
- **Fato:** `latitude` e `longitude` valem zero em todas as 4.441 linhas. São placeholders e não podem ser usados para localização.
- **Decisão metodológica:** usar coordenadas exclusivamente de `Mesh`.

### Categorias principais

| Campo | Principais valores observados |
|---|---|
| `listing_type` | apartamento 3.710 (83,5%); casa 443 (10,0%); outros 245 (5,5%); hotel 43 (1,0%) |
| `number_of_bedrooms` | 3 quartos 1.922 (43,3%); 2 quartos 1.482 (33,4%); 1 quarto 549 (12,4%); 0 quarto 56 (1,3%); 4 quartos 371 (8,4%) |
| `number_of_guests` | mediana 6; p95 10; máximo 16 |
| `number_of_reviews` | mediana 2; 1.540 anúncios sem reviews; máximo 504 |

### Ausências e valores suspeitos

- `space`: 2.527 ausências (56,9%).
- `check_in`: 446 ausências (10,0%); `check_out`: 842 (19,0%).
- `can_instant_book` e `is_professional`: 355 ausências cada (8,0%).
- `is_new_listing`: 874 ausências (19,7%).
- `min_nights`: zero em 100% das linhas; não contém variação analítica útil e pode representar falha de captura.
- `star_rating`, `guest_satisfaction_overall` e avaliações detalhadas usam zero nos anúncios sem reviews. Esses zeros devem ser tratados como “não avaliados”, não como nota real zero.
- `picture_count` é zero em 1.729 anúncios; falta validar se zero significa ausência de fotos ou falha de captura.
- `cleaning_fee` é zero em 939 anúncios; não é possível distinguir gratuitamente de ausente codificado como zero.
- Há 56 imóveis com zero quartos, candidatos a studio, mas essa equivalência precisa ser validada por texto/tipologia.
- Há seis registros acima de dez quartos, incluindo máximos de 16 quartos, 19 banheiros e 50 camas; exigem inspeção antes de modelagem.

### Campos relevantes

Perfil e capacidade: `listing_type`, `number_of_bedrooms`, `number_of_bathrooms`, `number_of_beds`, `number_of_guests`. Características: `amenities`, `cleaning_fee`, `picture_count`, reserva instantânea e avaliações. Gestão: `owner_id`, `is_professional`. O campo `amenities` é texto serializado como lista e precisará de parsing determinístico.

- **Limitação:** não existe coluna explícita de Airbnb `room_type` para distinguir imóvel inteiro, quarto privativo ou quarto compartilhado. `listing_type` contém `apartamento`, `casa`, `outros` e `hotel`, portanto representa tipologia do imóvel, não comprovadamente “tipo de anúncio”.
- **Limitação:** não existe área do imóvel no Airbnb. Assim, coortes Airbnb–VivaReal não podem ser harmonizadas por m².

## `Hosts_ids_Itapema.csv`

### Granularidade

- **Fato:** existem 4.440 linhas e 3.057 `owner_id` distintos.
- **Fato:** 509 anfitriões possuem linhas repetidas; o máximo é 112 linhas para um host.
- **Evidência:** `host_snapshot_date` coincide com os timestamps de captura de `Details`. A chave composta `(owner_id, timestamp)` cobre todos os 4.441 anúncios em relacionamento N:1.
- **Inferência:** o arquivo repete atributos do host durante a captura de cada listing; as repetições não representam uma série histórica independente do anfitrião.
- **Fato:** apenas um anfitrião apresenta variação material entre as repetições, em `number_of_reviews_host` (41.261 a 41.299 durante a janela de captura). Os demais atributos são estáveis por host.

### Ausências e extremos

- `response_rate_shown` e `response_time_shown` estão ausentes em 100% das linhas; não podem ser analisados.
- `number_of_reviews_host` tem mediana 7, p95 507 e máximo 41.299. O extremo pertence a um anfitrião com muitos listings e não deve dominar modelos sem transformação robusta.
- `star_rating_host` igual a zero aparece nos mesmos casos sem reviews do host e deve ser tratado como não avaliado.

### Regra operacional

Não fazer join apenas por `owner_id` sobre o arquivo bruto: isso gera 30.822 linhas, multiplicando a base de listings por 6,94. Usar a chave composta de captura quando atributos temporais forem importantes ou reduzir deterministicamente a uma linha por `owner_id`, documentando a regra.

## `Mesh_Ids_Data_Itapema.csv`

- **Fato:** 4.441 linhas, 4.441 listings distintos, nenhuma duplicação e cobertura integral de `Details`.
- **Fato:** não há coordenadas ou bairros ausentes, mas cinco linhas contêm a string literal `none` em `suburb`.
- **Fato:** latitude varia de -27,149000 a -27,055894; longitude, de -48,661915 a -48,585948. Todas estão em limites geográficos mundiais e na caixa ampla usada apenas como teste de sanidade para Itapema.
- **Fato:** existem 3.988 pares de coordenadas para 4.441 listings; coordenadas compartilhadas podem representar edifícios com várias unidades ou arredondamento.
- **Fato:** bairros principais são Meia Praia, 2.860 (64,4%); Centro, 657 (14,8%); Morretes, 441 (9,9%).
- **Limitação:** `aquisition_date` varia de 2021 a 2026 e não está alinhada ao snapshot de janeiro de 2025. Ela não deve ser interpretada silenciosamente como data contemporânea de mercado.
- **Decisão metodológica:** bairro será a localização primária comparável com VivaReal; coordenadas servirão apenas para análises internas do Airbnb e testes de micro-localização.

## `Price_AV_Itapema.csv`

### Granularidade e cobertura

- **Fato:** 118.839 linhas, 1.005 listings e nenhuma linha exatamente duplicada.
- **Fato:** a chave `(airbnb_listing_id, date, dia de aquisition_date)` é única. Timestamps diferentes no mesmo dia particionam datas de estadia, sem duplicar essa chave.
- **Fato:** há 59.040 pares listing–data de estadia; 33.588 reaparecem em mais de uma captura e 15.617 possuem mudança de preço.
- **Fato:** 999 listings ligam-se a `Details`; seis IDs existem apenas em `Price_AV`, somando 509 linhas.
- **Fato:** apenas 999 dos 4.441 anúncios de `Details` possuem preço, cobertura de 22,5%.
- **Fato:** a cobertura é desigual: apartamento 24,6%, casa 15,8%, hotel 2,3%; Centro 31,2%, Meia Praia 22,1%, Morretes 18,8%; um quarto 26,2%, dois 23,7%, três 21,0%.
- **Risco:** comparar segmentos somente na amostra com preço pode favorecer perfis e bairros com maior cobertura, inclusive Centro e apartamentos compactos.

### Estrutura temporal

| Dia de captura | Listings com registros | Horizonte máximo observado |
|---|---:|---|
| 06/01/2025 | 753 | 06/01 a 06/04 |
| 07/01/2025 | 773 | 07/01 a 07/04 |
| 20/01/2025 | 780 | 20/01 a 20/04 |

Há 628 listings presentes nos três dias, 45 em dois e 332 em apenas um. Cada listing–dia possui entre 2 e 91 datas de estadia, com mediana 54.

### Preço e disponibilidade

- **Fato:** o arquivo contém somente `airbnb_listing_id`, `date`, `price` e `aquisition_date`.
- **Fato:** não existe coluna de moeda, taxa ou status de disponibilidade.
- **Fato:** `price` varia de 63 a 29.000; mediana 607, p95 1.500 e p99 2.250.
- **Fato:** o valor 29.000 pertence a um apartamento de um quarto para três hóspedes; valores de 10.000 aparecem repetidamente em um apartamento de dois quartos. São suspeitos e podem representar erro ou preço usado para desestimular reservas.
- **Inferência:** a presença de somente parte dos 91 dias por listing–captura é compatível com o arquivo registrar datas anunciadas como disponíveis, mas isso não está explicitamente documentado.
- **Limitação:** ausência de linha pode significar reserva, bloqueio, indisponibilidade operacional ou falha de coleta. Mesmo se representar indisponibilidade, não identifica reserva paga.
- **Decisão metodológica provisória:** tratar `price` como preço anunciado associado à noite, não como diária realizada. Usar o dia de captura como snapshot. Não somar preços como receita.

## `VivaReal_Itapema.csv`

### Granularidade e categorias

- **Fato:** 8.329 linhas e 8.293 `listing_id` distintos.
- **Fato:** há 36 IDs duplicados; 35 pares são idênticos. O par restante difere somente na ordem dos itens de `amenities`, sendo semanticamente duplicado.
- **Decisão metodológica:** deduplicar por `listing_id`, preservando uma linha; normalizar listas antes de comparar conteúdo.
- **Fato:** 7.529 anúncios são apartamentos (90,4%), 547 casas, 164 terrenos, 79 comerciais e 10 outros.
- **Fato:** `property_type` é `UNIT` em 100% das linhas e não discrimina segmentos.
- **Fato:** bairros principais: Meia Praia 3.452 (41,4%), Morretes 1.777 (21,3%), Centro 1.009 (12,1%). Há 98 bairros ausentes e variações como `Meia Praia`/`Meia praia`.

### Ausências e anomalias

- `monthly_condo_fee`: 2.490 ausências (29,9%) e 2.364 zeros. O zero pode ser real ou ausência codificada.
- `yearly_iptu`: 2.714 ausências (32,6%) e 2.231 zeros.
- `rental_price` e `rental_period`: preenchidos em somente duas linhas; são irrelevantes para a compra na quase totalidade da base.
- `sale_price`: mediana 1.750.000; mínimo 10.000 e máximo 44.000.000. Os dois valores abaixo de 100.000 são semanticamente suspeitos para os imóveis descritos.
- `monthly_condo_fee` é igual ao preço de venda em cinco registros; há valores de até 3.150.000. Isso indica erro de extração/campo.
- `yearly_iptu` é igual ao preço de venda em um registro e chega a 2.800.000.
- Há 33 apartamentos com área acima de 1.000 m²; exemplos como 4.448 provavelmente perderam separador decimal. Terrenos muito grandes são plausíveis, mas não comparáveis a residenciais de short-stay.
- Há onze áreas iguais a zero.

### Regra operacional

Restringir a análise de compra a imóveis residenciais comparáveis; deduplicar IDs; validar ou remover anomalias por regras explícitas; apresentar resultados com e sem registros afetados. Preço de venda é preço pedido, não transacionado.

## O que é economicamente estimável

| Métrica | Classificação | Fundamentação |
|---|---|---|
| Preço pedido de aquisição | Estimável diretamente | `VivaReal.sale_price`, após deduplicação e filtros de qualidade; não equivale a preço transacionado. |
| Condomínio anunciado | Estimável diretamente, com cobertura parcial | Campo explícito, mas 29,9% ausente, muitos zeros ambíguos e erros claros de extração. |
| IPTU anunciado | Estimável diretamente, com cobertura parcial | Campo explícito, mas 32,6% ausente e contém anomalias. |
| Preço anunciado por data de estadia | Estimável diretamente | `Price_AV.price`; moeda, taxas e natureza “por noite” não são codificadas explicitamente. |
| ADR realizado | Estimável apenas como proxy | O preço é anunciado, não há valor de reserva concluída. |
| Disponibilidade aparente | Estimável apenas como proxy | Pode ser derivada da presença da data no snapshot, mas ausência não tem status explícito. |
| Ocupação | Não estimável com segurança | Não é possível distinguir reserva, bloqueio e falha de coleta. |
| Receita realizada | Não estimável com segurança | Não há reservas, noites vendidas ou pagamentos. |
| Receita bruta potencial em cenário | Estimável apenas como proxy | Requer preço anunciado e premissa explícita de ocupação. |
| Gross yield por coorte | Estimável apenas como proxy | Combina receita em cenário do Airbnb com preço pedido mediano de uma coorte do VivaReal; não são os mesmos imóveis. |
| Retorno após condomínio observado | Estimável apenas como proxy | Pode subtrair condomínio anual válido, mas continuam ausentes ocupação e demais custos. |
| Retorno líquido, cash-on-cash ou IRR | Não estimável com segurança | Faltam receita realizada, custos operacionais completos, capex, impostos de compra, valorização, venda e horizonte. |
| Estabilidade de receita anual | Não estimável com segurança | O horizonte de estadia cobre apenas 105 dias e não representa um ano completo. |

## Principais riscos para a decisão

1. A amostra de preços cobre somente 22,5% dos listings e não é uniforme entre segmentos.
2. Não há ocupação ou reserva observada; receita e yield dependerão de cenários.
3. Airbnb e VivaReal só podem ser relacionados por coortes, não imóvel a imóvel.
4. A base não traz `room_type` do Airbnb nem área do listing, reduzindo a comparabilidade de perfil.
5. O horizonte de preços é curto e concentrado no verão/início de outono.
6. Preços e custos possuem outliers compatíveis com erros ou estratégias de bloqueio.
7. Preço de venda é pedido, não transação; custos de aquisição e operação estão incompletos.
