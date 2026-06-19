# LexTimeline — Painel de Tramitação Legislativa

Aplicativo Streamlit para gerar timeline visual proporcional da tramitação de Projetos de Lei da Câmara dos Deputados, usando metodologia estrita baseada na seção **Tramitação** da ficha oficial da proposição.

## Versão 3.1

Esta versão elimina a dependência obrigatória da API dos Dados Abertos para localizar o PL. O app prioriza a ficha oficial da Câmara (`proposicoesWeb/fichadetramitacao`) e usa:

1. URL direta da ficha, quando fornecida pelo usuário;
2. `idProposicao`, quando fornecido pelo usuário;
3. cache interno para os PLs usados na demonstração do projeto;
4. busca pública no portal da Câmara como tentativa auxiliar para localizar a ficha.

A análise da tramitação é sempre feita sobre a seção oficial **Tramitação** da ficha da Câmara.

## Metodologia

O aplicativo considera apenas marcos de efetiva tramitação por órgão. Registros acessórios de MESA e CCP são excluídos, salvo a etapa inicial de apresentação do projeto.

A timeline gerada contém:

- tabela de marcos considerados;
- barra horizontal contínua e espessa;
- cores fixas por órgão;
- siglas inclinadas acima da barra;
- datas inclinadas abaixo da barra;
- legenda de cores;
- nota metodológica.

## Arquivos

- `app.py`: aplicação principal;
- `requirements.txt`: dependências;
- `README.md`: documentação.

## Publicação no Streamlit

No Streamlit Community Cloud, configure:

- Repository: `GPE-CD/LexTimeline`
- Branch: `main`
- Main file path: `app.py`

Depois clique em **Deploy** ou, se estiver atualizando versão, em **Reboot app**.

## Exemplos de entrada

```text
PL 5875/2013
PL 5688/2023
```

Também é possível colar diretamente a URL da ficha oficial da Câmara ou informar o `idProposicao`.


## Ajuste v3.1

Correção da função de interpretação de entrada (`PL número/ano`, URL da ficha ou `idProposicao`), mantendo a análise baseada na ficha oficial da Câmara.
