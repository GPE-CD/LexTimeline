# LexTimeline — Painel de Tramitação Legislativa

Aplicação Streamlit para gerar uma timeline visual proporcional da tramitação de Projetos de Lei na Câmara dos Deputados.

## Versão 2 — metodologia estrita

Esta versão abandona a reconstrução por heurística e trabalha com a página oficial de ficha de tramitação da Câmara dos Deputados.

A aplicação:

- recebe um ou vários Projetos de Lei no formato `PL número/ano`;
- localiza o `idProposicao` nos Dados Abertos da Câmara;
- abre a ficha oficial `proposicoesWeb/fichadetramitacao`;
- extrai a seção oficial **Tramitação**;
- seleciona apenas marcos de efetiva tramitação por órgão;
- exclui registros acessórios de MESA e CCP, salvo a etapa inicial de apresentação do projeto;
- gera uma tabela metodológica e uma timeline SVG com barra contínua, espessa, rótulos inclinados e datas inclinadas.

## Arquivos

- `app.py`: aplicação principal.
- `requirements.txt`: dependências para o Streamlit Community Cloud.
- `README.md`: documentação básica.

## Publicação no Streamlit Community Cloud

1. Crie ou atualize o repositório `GPE-CD/LexTimeline`.
2. Suba apenas estes três arquivos: `app.py`, `requirements.txt` e `README.md`.
3. No Streamlit Community Cloud, selecione:
   - Repository: `GPE-CD/LexTimeline`
   - Branch: `main`
   - Main file path: `app.py`
4. Clique em **Deploy**.

## Nota metodológica padrão

Critério: foram considerados apenas marcos de efetiva tramitação por órgão. Registros acessórios de MESA e CCP não foram incluídos, salvo a etapa inicial de apresentação do projeto.
