# LexTimeline — Painel Inteligente de Permanência Legislativa

Aplicação web em Streamlit para visualização proporcional da tramitação de proposições legislativas da Câmara dos Deputados.

O projeto foi desenhado para demonstrar, em um produto funcional e visualmente forte, como dados públicos e engenharia de prompt podem apoiar assessorias parlamentares, servidores, gabinetes e pesquisadores no acompanhamento de proposições legislativas.

## Funcionalidade central

A visualização principal é uma barra horizontal contínua, espessa e segmentada por cores. Cada segmento corresponde ao tempo de permanência da proposição em determinado órgão interno da Câmara dos Deputados.

Características da timeline:

- barra horizontal contínua, sem espaços entre segmentos;
- espessura elevada, para funcionar como elemento visual principal;
- uma cor fixa e persistente para cada órgão;
- siglas dos órgãos posicionadas acima da barra, no início de cada segmento, inclinadas para a direita;
- datas marcantes abaixo da barra, no formato `dd/mm/aa`, também inclinadas;
- tooltip com órgão, datas, duração real e percentual do período analisado;
- modo de comparação de múltiplas proposições;
- prompt estruturado para análise no ChatGPT.

## Modos de uso

### Modo demonstração

Usa dados sintéticos salvos no repositório para garantir estabilidade em apresentações. Serve para demonstrar a interface mesmo se a API externa estiver lenta ou indisponível.

### Dados ao vivo da Câmara

Consulta os Dados Abertos da Câmara dos Deputados para buscar proposições e histórico de tramitação.

Formato de entrada:

```text
PL 1291/2025
PL 5875/2013
PL 2630/2020
```

## Estrutura dos arquivos

```text
LexTimeline/
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── demo_proposicoes.json
```

## Publicação no Streamlit Community Cloud

1. Crie o repositório `github.com/GPE-CD/LexTimeline`.
2. Faça upload destes arquivos para o repositório.
3. Acesse o Streamlit Community Cloud.
4. Faça login com a conta GitHub autorizada.
5. Selecione o repositório `GPE-CD/LexTimeline`.
6. Informe o arquivo principal: `app.py`.
7. Clique em **Deploy**.

Após a publicação, o aplicativo será acessível por URL pública do tipo:

```text
https://lextimeline.streamlit.app
```

O endereço exato dependerá da disponibilidade do subdomínio no Streamlit.

## Dependências

As dependências estão listadas em `requirements.txt`:

```text
streamlit
pandas
requests
```

## Observação sobre os dados

O modo ao vivo depende da disponibilidade da API de Dados Abertos da Câmara dos Deputados. Por isso, o aplicativo mantém modo demonstração para reduzir risco em apresentações públicas.

## Observação sobre arquivos ocultos

Esta versão não depende da pasta `.streamlit/`. As configurações principais da página são aplicadas diretamente no arquivo `app.py`, por meio de `st.set_page_config()` e de CSS incorporado. Por isso, todos os arquivos necessários podem ser enviados pelo upload comum do GitHub, sem necessidade de incluir pastas ocultas.
