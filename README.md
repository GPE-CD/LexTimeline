# LexTimeline — Painel de Tramitação Legislativa

Aplicação Streamlit para visualizar a tramitação de proposições legislativas da Câmara dos Deputados em uma barra horizontal contínua, espessa e segmentada por órgão.

## Versão 1.5

Correções principais:

- O modo demonstração não usa mais datas fictícias: passou a usar amostras reais simplificadas, com datas e órgãos reais previamente selecionados.
- O modo ao vivo foi reforçado para evitar falhas em proposições como `PL 2630/2020`.
- A consulta de tramitações passou a tentar primeiro o endpoint sem parâmetros, evitando erro HTTP 400 causado por parâmetros rejeitados pela API.
- Se o endpoint de tramitações falhar, o app tenta extrair data e órgão da ficha pública HTML da Câmara dos Deputados.
- O aplicativo permanece sem pasta `data/`, para facilitar upload manual no GitHub.

## Arquivos

- `app.py`: aplicação principal.
- `requirements.txt`: dependências do Streamlit Cloud.
- `README.md`: este arquivo.

## Deploy no Streamlit Community Cloud

1. Suba `app.py`, `requirements.txt` e `README.md` para o repositório `GPE-CD/LexTimeline`.
2. No Streamlit Community Cloud, selecione o repositório.
3. Use `app.py` como arquivo principal.
4. Clique em deploy ou reinicie o app já existente.

## Uso

No modo ao vivo, informe proposições no formato:

```text
PL 2630/2020
PL 5688/2023
PL 5875/2013
```

O modo demonstração usa amostras reais simplificadas apenas para estabilidade visual em apresentação pública. Para análise completa e atualizada, use o modo ao vivo.
