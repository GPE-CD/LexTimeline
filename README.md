# LexTimeline — Painel de Tramitação Legislativa

Aplicativo Streamlit para gerar timeline visual proporcional da tramitação de Projetos de Lei na Câmara dos Deputados.

## Versão 2.1

Esta versão corrige a extração da seção **Tramitação** da ficha oficial da Câmara quando o HTML chega ao Streamlit com quebras de linha diferentes. A aplicação continua usando metodologia estrita: não inventa datas, não estima períodos e não reconstrói tramitação por heurística externa.

## Metodologia

A aplicação usa a ficha oficial da Câmara (`proposicoesWeb/fichadetramitacao`) e extrai os registros da seção **Tramitação**. São considerados apenas marcos de efetiva tramitação por órgão.

Registros acessórios de **MESA** e **CCP** não são usados como segmentos próprios, salvo a etapa inicial de apresentação do projeto quando registrada na Mesa Diretora.

## Arquivos

Suba apenas estes arquivos para o repositório GitHub:

- `app.py`
- `requirements.txt`
- `README.md`

Não há necessidade de pasta `data/` nem de pasta `.streamlit/`.

## Como publicar no Streamlit Community Cloud

1. Acesse https://share.streamlit.io
2. Faça login com GitHub.
3. Escolha o repositório `GPE-CD/LexTimeline`.
4. Em **Main file path**, informe `app.py`.
5. Clique em **Deploy**.

## Exemplos de teste

- `PL 5875/2013`
- `PL 5688/2023`

## Saída visual

A aplicação gera um painel em SVG com:

- tabela dos marcos considerados;
- barra horizontal contínua, espessa e proporcional;
- rótulos dos órgãos inclinados acima da barra;
- datas inclinadas abaixo da barra;
- legenda de cores;
- nota metodológica.
