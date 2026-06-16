# LexTimeline — Painel de Tramitação Legislativa
# Aplicação Streamlit para visualização proporcional da tramitação de proposições
# da Câmara dos Deputados, com base nos Dados Abertos.

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import streamlit.components.v1 as components

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
TODAY = date.today()
APP_DIR = Path(__file__).parent
DEMO_PATH = APP_DIR / "data" / "demo_proposicoes.json"

# Dados de demonstração embutidos no próprio app.
# Amostras reais simplificadas: os marcos abaixo foram selecionados de páginas públicas
# de tramitação da Câmara/Congresso. Não pretendem reproduzir todos os atos, mas usam
# datas e órgãos reais para demonstrar a visualização sem depender de consulta externa.
DEMO_DATA = {
  "observacao": "Amostras reais simplificadas, usadas para demonstração visual com datas e órgãos reais. Para análise completa, use Dados ao vivo da Câmara.",
  "proposicoes": [
    {
      "codigo": "PL 2630/2020",
      "id_proposicao": 2256735,
      "ementa": "Institui a Lei Brasileira de Liberdade, Responsabilidade e Transparência na Internet.",
      "situacao": "Pronta para pauta no Plenário",
      "orgao_atual": "PLEN",
      "ultima_movimentacao": "2023-04-25",
      "fim_periodo": "2026-06-16",
      "fonte": "Modo demonstração: amostra real simplificada da Câmara/Congresso",
      "eventos": [
        {
          "data": "2020-07-03",
          "orgao": "MESA",
          "descricao": "Recebimento do Ofício nº 591/20 do Senado Federal, encaminhando o projeto à revisão da Câmara."
        },
        {
          "data": "2020-07-03",
          "orgao": "PLEN",
          "descricao": "Apresentação do Projeto de Lei n. 2630/2020 no Plenário."
        },
        {
          "data": "2023-04-12",
          "orgao": "MESA",
          "descricao": "Apresentação de requerimento de constituição de Comissão Especial."
        },
        {
          "data": "2023-04-25",
          "orgao": "PLEN",
          "descricao": "Atos de Plenário, incluindo designação de relator e aprovação de urgência."
        }
      ]
    },
    {
      "codigo": "PL 5688/2023",
      "id_proposicao": 2406422,
      "ementa": "Institui a Política Nacional de Enfrentamento da Infecção por Papilomavírus Humano.",
      "situacao": "Transformado em norma jurídica, com veto parcial",
      "orgao_atual": "PLEN",
      "ultima_movimentacao": "2025-02-12",
      "fim_periodo": "2025-02-12",
      "fonte": "Modo demonstração: amostra real simplificada da Câmara/Congresso",
      "eventos": [
        {
          "data": "2023-11-23",
          "orgao": "MESA",
          "descricao": "Apresentação do PL n. 5688/2023."
        },
        {
          "data": "2024-11-19",
          "orgao": "CSAUDE",
          "descricao": "Registro de atividade na Comissão de Saúde relacionada à apreciação da matéria."
        },
        {
          "data": "2025-02-11",
          "orgao": "PLEN",
          "descricao": "Parecer proferido em Plenário em nome de comissões."
        }
      ]
    },
    {
      "codigo": "PL 5875/2013",
      "id_proposicao": 582806,
      "ementa": "Altera a Lei nº 8.080, de 1990, para dispor sobre informações do cartão de identificação do usuário do SUS e temas correlatos.",
      "situacao": "Em tramitação na Câmara dos Deputados",
      "orgao_atual": "CSAUDE",
      "ultima_movimentacao": "2026-05-26",
      "fim_periodo": "2026-06-16",
      "fonte": "Modo demonstração: amostra real simplificada da Câmara/Congresso",
      "eventos": [
        {
          "data": "2013-07-02",
          "orgao": "MESA",
          "descricao": "Apresentação na Câmara dos Deputados, oriundo do Senado Federal."
        },
        {
          "data": "2023-03-28",
          "orgao": "MESA",
          "descricao": "Revisão de despacho para incluir CCTI, CSAUDE, CFT e CCJC."
        },
        {
          "data": "2023-11-30",
          "orgao": "CSAUDE",
          "descricao": "Registro de relatoria na Comissão de Saúde em proposição apensada ao bloco do PL 5875/2013."
        },
        {
          "data": "2024-12-19",
          "orgao": "CSAUDE",
          "descricao": "Recomendação do Conselho Nacional de Saúde menciona necessidade de aprofundamento dos debates sobre o PL 5875/2013."
        },
        {
          "data": "2026-05-26",
          "orgao": "CSAUDE",
          "descricao": "Audiência pública na Comissão de Saúde para debater o substitutivo ao PL 5875/2013."
        }
      ]
    }
  ]
}

# Identificadores conhecidos, usados apenas como fallback quando a busca principal por API falhar.
# Isso ajuda em proposições frequentemente usadas na demonstração e evita quebra por oscilações do endpoint de busca.
KNOWN_PROPOSITION_IDS = {
    ("PL", 2630, 2020): 2256735,
    ("PL", 5688, 2023): 2406422,
    ("PL", 5875, 2013): 582806,
    ("PL", 1291, 2025): 2490661,
}

KNOWN_PROPOSITION_METADATA = {
    2256735: {
        "ementa": "Institui a Lei Brasileira de Liberdade, Responsabilidade e Transparência na Internet.",
        "situacao": "Pronta para Pauta no Plenário",
        "orgao_atual": "PLEN",
        "dataApresentacao": "2020-07-03",
    },
    2406422: {
        "ementa": "Institui a Política Nacional de Enfrentamento da Infecção por Papilomavírus Humano.",
        "situacao": "Transformado em Norma Jurídica",
        "orgao_atual": "PLEN",
        "dataApresentacao": "2023-11-23",
    },
    582806: {
        "ementa": "Altera a Lei nº 8.080, de 1990, para dispor sobre informações do cartão de identificação do usuário do SUS.",
        "situacao": "Em tramitação",
        "orgao_atual": "CSAUDE",
        "dataApresentacao": "2013-07-02",
    },
    2490661: {
        "ementa": "Proposição legislativa em tramitação na Câmara dos Deputados.",
        "situacao": "Em tramitação",
        "orgao_atual": "CSAUDE",
        "dataApresentacao": "2025-03-25",
    },
}

# Paleta fixa dos órgãos mais comuns. As cores são preservadas em todos os usos.
ORG_COLORS: Dict[str, str] = {
    "MESA": "#1F4E79",
    "PLEN": "#B03A2E",
    "CCJC": "#6C3483",
    "CFT": "#1E8449",
    "CSAUDE": "#2874A6",
    "CSSF": "#2874A6",
    "CE": "#D35400",
    "CDE": "#B7950B",
    "CAPADR": "#229954",
    "CSPCCO": "#566573",
    "CTRAB": "#935116",
    "CASP": "#2E86C1",
    "CCTI": "#17A589",
    "CMULHER": "#C0398A",
    "CCTCI": "#17A589",
    "CDC": "#7D6608",
    "CDU": "#5D6D7E",
    "CINDRE": "#BA4A00",
    "CMADS": "#117A65",
    "CPD": "#7E5109",
    "CREDN": "#1A5276",
    "CULTURA": "#AF7AC5",
    "ESPORTE": "#CA6F1E",
    "LEGIS": "#626567",
    "OUTRO": "#7F8C8D",
    "ND": "#7F8C8D",
}

ORG_NAMES: Dict[str, str] = {
    "MESA": "Mesa Diretora",
    "PLEN": "Plenário",
    "CCJC": "Comissão de Constituição e Justiça e de Cidadania",
    "CFT": "Comissão de Finanças e Tributação",
    "CSAUDE": "Comissão de Saúde",
    "CSSF": "Comissão de Seguridade Social e Família / Comissão de Saúde",
    "CE": "Comissão de Educação",
    "CDE": "Comissão de Desenvolvimento Econômico",
    "CAPADR": "Comissão de Agricultura, Pecuária, Abastecimento e Desenvolvimento Rural",
    "CSPCCO": "Comissão de Segurança Pública e Combate ao Crime Organizado",
    "CTRAB": "Comissão de Trabalho",
    "CASP": "Comissão de Administração e Serviço Público",
    "CCTI": "Comissão de Ciência, Tecnologia e Inovação",
    "CMULHER": "Comissão de Defesa dos Direitos da Mulher",
    "CCTCI": "Comissão de Ciência e Tecnologia, Comunicação e Informática",
    "CDC": "Comissão de Defesa do Consumidor",
    "CDU": "Comissão de Desenvolvimento Urbano",
    "CINDRE": "Comissão de Integração Nacional e Desenvolvimento Regional",
    "CMADS": "Comissão de Meio Ambiente e Desenvolvimento Sustentável",
    "CPD": "Comissão de Defesa dos Direitos das Pessoas com Deficiência",
    "CREDN": "Comissão de Relações Exteriores e de Defesa Nacional",
    "CULTURA": "Comissão de Cultura",
    "ESPORTE": "Comissão do Esporte",
    "LEGIS": "Legislação Participativa",
    "OUTRO": "Outro órgão",
    "ND": "Órgão não identificado",
}


@dataclass
class Period:
    orgao: str
    nome_orgao: str
    inicio: date
    fim: date
    dias: int
    cor: str
    inicio_pct: float = 0.0
    largura_pct: float = 0.0
    visual_inicio_pct: float = 0.0
    visual_largura_pct: float = 0.0
    descricao_inicio: str = ""


@dataclass
class PropositionTimeline:
    codigo: str
    id_proposicao: Optional[int]
    ementa: str
    situacao: str
    orgao_atual: str
    ultima_movimentacao: Optional[date]
    periodos: List[Period]
    fonte: str
    alerta: str = ""


def normalize_org(sigla: Optional[str]) -> str:
    if not sigla:
        return "ND"
    sigla = str(sigla).upper().strip()
    sigla = sigla.replace("-", "").replace(" ", "")
    return sigla or "ND"


def deterministic_color(sigla: str) -> str:
    """Gera cor estável para órgão não previsto no dicionário fixo."""
    sigla = normalize_org(sigla)
    if sigla in ORG_COLORS:
        return ORG_COLORS[sigla]
    digest = hashlib.md5(sigla.encode("utf-8")).hexdigest()
    hue = int(digest[:2], 16) % 360
    # HSL com saturação e luminosidade moderadas para evitar cores excessivamente claras.
    return f"hsl({hue}, 55%, 43%)"


def org_name(sigla: str) -> str:
    sigla = normalize_org(sigla)
    return ORG_NAMES.get(sigla, f"Órgão {sigla}")


def parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    value = str(value).strip()
    if not value:
        return None
    try:
        # Ex.: 2025-02-03T14:30:00 ou 2025-02-03
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def fmt_date_br(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%y") if d else "—"


def parse_proposition_inputs(raw: str) -> List[Tuple[str, int, int]]:
    """Aceita entradas como 'PL 1291/2025', uma por linha, vírgula ou ponto e vírgula."""
    if not raw:
        return []
    candidates = re.split(r"[\n;,]+", raw)
    parsed: List[Tuple[str, int, int]] = []
    seen = set()
    for item in candidates:
        item = item.strip()
        if not item:
            continue
        match = re.search(r"([A-Za-zÀ-ÿ]{1,12})\s*[- ]?\s*(\d{1,6})\s*/\s*(\d{4})", item)
        if not match:
            continue
        sigla, numero, ano = match.group(1).upper(), int(match.group(2)), int(match.group(3))
        key = (sigla, numero, ano)
        if key not in seen:
            parsed.append(key)
            seen.add(key)
    return parsed


def first_nonempty(*values: Any) -> Optional[Any]:
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def extract_org_sigla(record: Dict[str, Any]) -> str:
    """Extrai a sigla do órgão em diferentes formatos possíveis do retorno da API."""
    direct = first_nonempty(
        record.get("siglaOrgao"),
        record.get("siglaOrgaoAtual"),
        record.get("sigla"),
        record.get("orgao"),
        record.get("nomeOrgao"),
    )
    if isinstance(direct, dict):
        direct = first_nonempty(direct.get("sigla"), direct.get("siglaOrgao"), direct.get("nome"))
    if direct:
        text = str(direct).strip()
        # Alguns retornos podem trazer algo como "Comissão de Saúde (CSAUDE)".
        m = re.search(r"\(([A-Z0-9]{2,12})\)", text)
        if m:
            return normalize_org(m.group(1))
        return normalize_org(text)
    return "ND"


def extract_event_description(record: Dict[str, Any]) -> str:
    return str(first_nonempty(
        record.get("descricaoTramitacao"),
        record.get("despacho"),
        record.get("descricaoSituacao"),
        record.get("regime"),
        "Movimentação registrada"
    ))


def get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Faz requisição JSON com mensagens de erro compreensíveis para o usuário final."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "LexTimeline/1.5 (visualizacao legislativa; dados abertos)",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("A consulta aos Dados Abertos excedeu o tempo limite. Tente novamente ou use o modo demonstração.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Falha de conexão com os Dados Abertos: {exc}") from exc

    if resp.status_code >= 400:
        detalhe = resp.text[:300].replace("\n", " ")
        raise RuntimeError(f"A API da Câmara retornou erro HTTP {resp.status_code}. Detalhe: {detalhe}")

    try:
        payload = resp.json()
    except ValueError as exc:
        detalhe = resp.text[:300].replace("\n", " ")
        raise RuntimeError(f"A API não retornou JSON válido. Detalhe: {detalhe}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("A API retornou uma estrutura inesperada, diferente de objeto JSON.")
    return payload


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_all(endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Busca endpoint paginado dos Dados Abertos da Câmara, tolerando pequenas variações no retorno."""
    url = f"{BASE_URL}{endpoint}"
    params = dict(params or {})
    params.setdefault("itens", 100)
    dados: List[Dict[str, Any]] = []
    visited = set()
    for _ in range(50):
        key = (url, tuple(sorted((params or {}).items())))
        if key in visited:
            break
        visited.add(key)
        payload = get_json(url, params=params)
        page_data = payload.get("dados", [])
        if isinstance(page_data, dict):
            page_data = [page_data]
        if not isinstance(page_data, list):
            raise RuntimeError("A API retornou o campo 'dados' em formato inesperado.")
        dados.extend([x for x in page_data if isinstance(x, dict)])
        next_url = None
        for link in payload.get("links", []) or []:
            if isinstance(link, dict) and link.get("rel") == "next":
                next_url = link.get("href")
                break
        if not next_url:
            break
        url = next_url
        params = None
    return dados


@st.cache_data(ttl=60 * 60, show_spinner=False)
def find_proposition(sigla: str, numero: int, ano: int) -> Optional[Dict[str, Any]]:
    """Localiza a proposição por API; em caso de falha, usa fallback para exemplos conhecidos."""
    params = {
        "siglaTipo": sigla,
        "numero": numero,
        "ano": ano,
        "ordem": "ASC",
        "ordenarPor": "id",
        "itens": 100,
    }
    erros: List[str] = []
    dados: List[Dict[str, Any]] = []
    try:
        dados = fetch_all("/proposicoes", params)
    except Exception as exc:
        erros.append(str(exc))

    if not dados:
        try:
            # Segunda tentativa mais ampla, útil quando a API oscila com filtros combinados.
            dados = fetch_all("/proposicoes", {"numero": numero, "ano": ano, "itens": 100})
        except Exception as exc:
            erros.append(str(exc))

    if dados:
        # Preferência por correspondência exata.
        for item in dados:
            try:
                if (
                    str(item.get("siglaTipo", "")).upper() == sigla
                    and int(item.get("numero", -1)) == numero
                    and int(item.get("ano", -1)) == ano
                ):
                    return item
            except Exception:
                continue
        # Se a API retornar apenas uma proposição, usa-a; se retornar muitas, evita falso positivo.
        if len(dados) == 1:
            return dados[0]

    key = (sigla, numero, ano)
    if key in KNOWN_PROPOSITION_IDS:
        prop_id = KNOWN_PROPOSITION_IDS[key]
        meta = KNOWN_PROPOSITION_METADATA.get(prop_id, {})
        return {
            "id": prop_id,
            "siglaTipo": sigla,
            "numero": numero,
            "ano": ano,
            "ementa": meta.get("ementa", "Ementa não informada"),
            "dataApresentacao": meta.get("dataApresentacao"),
            "_fallback": "Identificador conhecido usado porque a busca por API não retornou resultado confiável.",
        }

    if erros:
        raise RuntimeError("Falha ao localizar a proposição na API. " + " | ".join(erros[:2]))
    return None


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_proposition_detail(prop_id: int) -> Dict[str, Any]:
    try:
        payload = get_json(f"{BASE_URL}/proposicoes/{prop_id}")
        dados = payload.get("dados", {})
        if isinstance(dados, dict):
            return dados
    except Exception:
        pass
    # Fallback mínimo para exemplos conhecidos. Para proposições desconhecidas,
    # retorna objeto vazio e o app tenta seguir com os dados básicos disponíveis.
    return KNOWN_PROPOSITION_METADATA.get(prop_id, {})


def _extract_dados_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    page_data = payload.get("dados", [])
    if isinstance(page_data, dict):
        page_data = [page_data]
    if not isinstance(page_data, list):
        return []
    return [x for x in page_data if isinstance(x, dict)]


def fetch_tramitacoes_api_sem_paginacao(prop_id: int) -> List[Dict[str, Any]]:
    """Consulta o endpoint de tramitações sem forçar parâmetros potencialmente rejeitados."""
    url = f"{BASE_URL}/proposicoes/{prop_id}/tramitacoes"
    tentativas = [None, {"ordem": "ASC"}, {"itens": 100}, {"ordem": "ASC", "itens": 100}]
    erros: List[str] = []
    for params in tentativas:
        try:
            payload = get_json(url, params=params)
            dados = _extract_dados_from_payload(payload)
            if dados:
                return dados
        except Exception as exc:
            erros.append(f"params={params or '{}'}: {exc}")
    raise RuntimeError("Endpoint /tramitacoes não retornou dados aproveitáveis. " + " | ".join(erros[:3]))


def scrape_ficha_tramitacao(prop_id: int) -> List[Dict[str, Any]]:
    """Fallback: extrai data e órgão da ficha pública de tramitação HTML."""
    url = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={prop_id}"
    headers = {
        "User-Agent": "LexTimeline/1.5 (fallback html; dados públicos)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Não foi possível consultar a ficha pública de tramitação: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    eventos: List[Dict[str, Any]] = []
    date_re = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    org_re = re.compile(r"\(\s*([A-Z0-9]{2,15})\s*\)")

    for i, line in enumerate(lines):
        if not date_re.match(line):
            continue
        data = parse_date(line)
        if not data:
            continue
        sigla = None
        descricao = "Movimentação extraída da ficha pública de tramitação."
        for j in range(i + 1, min(i + 8, len(lines))):
            m = org_re.search(lines[j])
            if m:
                sigla = normalize_org(m.group(1))
                # Primeira linha subsequente mais longa tende a ser a ação.
                for k in range(j + 1, min(j + 8, len(lines))):
                    if len(lines[k]) > 20 and not date_re.match(lines[k]) and "Inteiro teor" not in lines[k]:
                        descricao = lines[k]
                        break
                break
        if sigla:
            eventos.append({
                "dataHora": data.isoformat(),
                "siglaOrgao": sigla,
                "descricaoTramitacao": descricao,
                "sequencia": len(eventos),
                "fonteFallback": "ficha pública HTML",
            })

    if not eventos:
        raise RuntimeError("A ficha pública foi acessada, mas não foi possível extrair eventos com data e órgão.")

    # Remove duplicatas exatas comuns na página pública.
    dedup: List[Dict[str, Any]] = []
    seen = set()
    for ev in eventos:
        key = (ev.get("dataHora"), ev.get("siglaOrgao"), ev.get("descricaoTramitacao"))
        if key not in seen:
            dedup.append(ev)
            seen.add(key)
    return dedup


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_tramitacoes(prop_id: int) -> List[Dict[str, Any]]:
    """
    Busca tramitações de forma resiliente.

    A versão anterior ainda podia falhar em proposições como PL 2630/2020
    quando o endpoint rejeitava parâmetros de paginação/ordenação. Agora a
    primeira tentativa é sem parâmetros; se a API falhar, o app usa a ficha
    pública HTML da Câmara como fallback.
    """
    erros: List[str] = []
    try:
        dados = fetch_tramitacoes_api_sem_paginacao(prop_id)
        dados = [x for x in dados if isinstance(x, dict)]
        if dados:
            dados.sort(
                key=lambda t: parse_date(t.get("dataHora") or t.get("data") or t.get("dataApresentacao"))
                or date.min
            )
            return dados
    except Exception as exc:
        erros.append(f"API: {exc}")

    try:
        dados = scrape_ficha_tramitacao(prop_id)
        dados.sort(
            key=lambda t: parse_date(t.get("dataHora") or t.get("data") or t.get("dataApresentacao"))
            or date.min
        )
        return dados
    except Exception as exc:
        erros.append(f"Ficha HTML: {exc}")

    raise RuntimeError(
        "Não foi possível consultar as tramitações da proposição. " + " | ".join(erros)
    )

def build_periods_from_tramitacoes(
    tramitacoes: List[Dict[str, Any]],
    include_until_today: bool = True,
    minimum_visual_days: int = 0,
    end_date_override: Optional[date] = None,
) -> List[Period]:
    events = []
    last_sigla = "ND"
    for idx, tram in enumerate(tramitacoes):
        d = parse_date(tram.get("dataHora") or tram.get("data") or tram.get("dataApresentacao"))
        if not d:
            continue
        sigla = extract_org_sigla(tram)
        # Quando a API não informa o órgão em um evento intermediário, mantém o órgão anterior
        # para não quebrar a continuidade visual da barra.
        if sigla == "ND" and last_sigla != "ND":
            sigla = last_sigla
        if sigla != "ND":
            last_sigla = sigla
        descricao = extract_event_description(tram)
        sequencia = tram.get("sequencia") or tram.get("ordem") or idx
        events.append((d, int(sequencia) if str(sequencia).isdigit() else idx, sigla, descricao))

    events.sort(key=lambda x: (x[0], x[1]))
    if not events:
        return []

    # Compacta eventos consecutivos no mesmo órgão. Mantém o primeiro texto como descrição de entrada.
    compacted: List[Tuple[date, str, str]] = []
    for d, _, sigla, descricao in events:
        if not compacted or compacted[-1][1] != sigla:
            compacted.append((d, sigla, descricao))
        else:
            # Para mesmo órgão em sequência, preserva a data inicial e ignora repetição.
            continue

    end_date = end_date_override or (TODAY if include_until_today else compacted[-1][0])
    raw_periods: List[Period] = []
    for i, (start, sigla, descricao) in enumerate(compacted):
        if i + 1 < len(compacted):
            end = compacted[i + 1][0]
        else:
            end = end_date
        if end < start:
            continue
        real_days = max((end - start).days, 0)
        raw_periods.append(
            Period(
                orgao=sigla,
                nome_orgao=org_name(sigla),
                inicio=start,
                fim=end,
                dias=real_days,
                cor=deterministic_color(sigla),
                descricao_inicio=descricao,
            )
        )

    if not raw_periods:
        return []

    real_total = sum(p.dias for p in raw_periods)
    if real_total == 0:
        # Caso extremo: todos os marcos no mesmo dia. Distribui visualmente para não quebrar o gráfico.
        real_total = len(raw_periods)
        for p in raw_periods:
            p.dias = 0

    cursor = 0.0
    for p in raw_periods:
        width = (p.dias / real_total) * 100 if real_total else 100 / len(raw_periods)
        p.inicio_pct = cursor
        p.largura_pct = width
        cursor += width

    # Proporção visual com opção de largura mínima para trechos muito curtos.
    if minimum_visual_days > 0:
        visual_weights = [max(p.dias, minimum_visual_days) for p in raw_periods]
        total_visual = sum(visual_weights) or len(raw_periods)
    else:
        visual_weights = [p.dias for p in raw_periods]
        total_visual = sum(visual_weights)
        if total_visual == 0:
            visual_weights = [1 for _ in raw_periods]
            total_visual = len(raw_periods)

    cursor = 0.0
    for p, weight in zip(raw_periods, visual_weights):
        width = (weight / total_visual) * 100
        p.visual_inicio_pct = cursor
        p.visual_largura_pct = width
        cursor += width

    return raw_periods


def build_timeline_live(sigla: str, numero: int, ano: int, include_until_today: bool, minimum_visual_days: int) -> PropositionTimeline:
    prop = find_proposition(sigla, numero, ano)
    if not prop:
        raise ValueError(f"Proposição não encontrada: {sigla} {numero}/{ano}")

    prop_id = int(prop["id"])
    detail = fetch_proposition_detail(prop_id)
    tramitacoes = fetch_tramitacoes(prop_id)
    periodos = build_periods_from_tramitacoes(tramitacoes, include_until_today, minimum_visual_days)

    if not periodos:
        # Fallback conservador: se o endpoint de tramitações não trouxer eventos aproveitáveis,
        # monta um período único a partir da apresentação/situação atual, para o app não quebrar.
        status_fallback = detail.get("statusProposicao") or {}
        inicio_fb = parse_date(detail.get("dataApresentacao") or prop.get("dataApresentacao")) or TODAY
        org_fb = normalize_org(first_nonempty(status_fallback.get("siglaOrgao"), status_fallback.get("siglaOrgaoAtual"), "ND"))
        fim_fb = TODAY if include_until_today else inicio_fb
        dias_fb = max((fim_fb - inicio_fb).days, 0)
        periodos = [Period(orgao=org_fb, nome_orgao=org_name(org_fb), inicio=inicio_fb, fim=fim_fb, dias=dias_fb, cor=deterministic_color(org_fb), inicio_pct=0, largura_pct=100, visual_inicio_pct=0, visual_largura_pct=100, descricao_inicio="Período montado por fallback a partir dos dados básicos da proposição.")]

    ultima_data = max([p.fim for p in periodos], default=None)
    if tramitacoes:
        datas_eventos = [parse_date(t.get("dataHora") or t.get("data")) for t in tramitacoes]
        datas_eventos = [d for d in datas_eventos if d]
        ultima_data = max(datas_eventos) if datas_eventos else ultima_data

    status = detail.get("statusProposicao") or {}
    orgao_atual = normalize_org(first_nonempty(status.get("siglaOrgao"), status.get("siglaOrgaoAtual"), periodos[-1].orgao if periodos else "ND"))
    situacao = status.get("descricaoSituacao") or status.get("descricaoTramitacao") or "Situação não informada"

    codigo = f"{sigla} {numero}/{ano}"
    ementa = detail.get("ementa") or prop.get("ementa") or "Ementa não informada"
    alerta = build_alert(periodos, ultima_data)

    return PropositionTimeline(
        codigo=codigo,
        id_proposicao=prop_id,
        ementa=ementa,
        situacao=situacao,
        orgao_atual=orgao_atual,
        ultima_movimentacao=ultima_data,
        periodos=periodos,
        fonte="Dados Abertos da Câmara dos Deputados",
        alerta=alerta,
    )


def load_demo_timelines(minimum_visual_days: int = 0) -> List[PropositionTimeline]:
    # Dados demonstrativos embutidos: amostras reais simplificadas, sem necessidade de pasta data/.
    raw = DEMO_DATA
    timelines: List[PropositionTimeline] = []
    for item in raw["proposicoes"]:
        fake_trams = []
        for idx, ev in enumerate(item["eventos"]):
            fake_trams.append(
                {
                    "dataHora": ev["data"],
                    "sequencia": idx,
                    "siglaOrgao": ev["orgao"],
                    "descricaoTramitacao": ev.get("descricao", "Entrada no órgão"),
                }
            )
        end_override = parse_date(item.get("fim_periodo"))
        periodos = build_periods_from_tramitacoes(
            fake_trams,
            include_until_today=False,
            minimum_visual_days=minimum_visual_days,
            end_date_override=end_override,
        )
        ultima_data = parse_date(item.get("ultima_movimentacao")) or (periodos[-1].fim if periodos else None)
        timelines.append(
            PropositionTimeline(
                codigo=item["codigo"],
                id_proposicao=item.get("id_proposicao"),
                ementa=item["ementa"],
                situacao=item.get("situacao", "Dados demonstrativos"),
                orgao_atual=normalize_org(item.get("orgao_atual", periodos[-1].orgao if periodos else "ND")),
                ultima_movimentacao=ultima_data,
                periodos=periodos,
                fonte=item.get("fonte", "Modo demonstração: amostra real simplificada"),
                alerta=build_alert(periodos, ultima_data),
            )
        )
    return timelines


def build_alert(periodos: List[Period], ultima_movimentacao: Optional[date]) -> str:
    if not periodos:
        return "Sem histórico suficiente para gerar alerta."
    total = sum(p.dias for p in periodos)
    major = max(periodos, key=lambda p: p.dias)
    pct = (major.dias / total * 100) if total else 0
    dias_sem_mov = (TODAY - ultima_movimentacao).days if ultima_movimentacao else None
    parts = [f"Maior permanência: {major.orgao} ({pct:.0f}% do período analisado)."]
    if dias_sem_mov is not None and dias_sem_mov >= 180:
        parts.append(f"Atenção: sem nova movimentação registrada há {dias_sem_mov} dias.")
    elif dias_sem_mov is not None:
        parts.append(f"Última movimentação registrada há {dias_sem_mov} dias.")
    return " ".join(parts)


def timeline_summary(t: PropositionTimeline) -> Dict[str, Any]:
    total = sum(p.dias for p in t.periodos)
    major = max(t.periodos, key=lambda p: p.dias) if t.periodos else None
    dias_sem_mov = (TODAY - t.ultima_movimentacao).days if t.ultima_movimentacao else None
    return {
        "Proposição": t.codigo,
        "Tempo total analisado (dias)": total,
        "Órgão de maior permanência": major.orgao if major else "—",
        "Dias no órgão dominante": major.dias if major else 0,
        "% no órgão dominante": round((major.dias / total * 100), 1) if major and total else 0,
        "Última movimentação": fmt_date_br(t.ultima_movimentacao),
        "Dias sem movimentação": dias_sem_mov if dias_sem_mov is not None else "—",
        "Órgão atual": t.orgao_atual,
        "Situação": t.situacao,
    }


def safe_text(value: Any) -> str:
    return html.escape(str(value or ""))


def render_timeline(t: PropositionTimeline, height_px: int = 260, bar_height_px: int = 52) -> None:
    if not t.periodos:
        st.warning(f"{t.codigo}: não foi possível montar a timeline porque não há períodos válidos.")
        return

    total_dias = sum(p.dias for p in t.periodos)
    labels_html = []
    dates_html = []
    segs_html = []

    for p in t.periodos:
        tooltip = (
            f"{p.orgao} — {p.nome_orgao}\n"
            f"Início: {fmt_date_br(p.inicio)}\n"
            f"Fim: {fmt_date_br(p.fim)}\n"
            f"Duração real: {p.dias} dias\n"
            f"Percentual real: {(p.dias / total_dias * 100) if total_dias else 0:.1f}%\n"
            f"Evento inicial: {p.descricao_inicio[:250]}"
        )
        labels_html.append(
            f'<div class="lt-org-label" style="left:{p.visual_inicio_pct:.4f}%;" title="{safe_text(tooltip)}">{safe_text(p.orgao)}</div>'
        )
        dates_html.append(
            f'<div class="lt-date-label" style="left:{p.visual_inicio_pct:.4f}%;" title="{safe_text(fmt_date_br(p.inicio))}">{safe_text(fmt_date_br(p.inicio))}</div>'
        )
        segs_html.append(
            f'<div class="lt-segment" style="width:{p.visual_largura_pct:.6f}%; background:{p.cor};" title="{safe_text(tooltip)}"></div>'
        )

    # Data final no fim da barra.
    final_date = t.periodos[-1].fim
    dates_html.append(
        f'<div class="lt-date-label lt-date-final" style="left:100%;" title="{safe_text(fmt_date_br(final_date))}">{safe_text(fmt_date_br(final_date))}</div>'
    )

    legend_items = []
    seen_orgs = []
    for p in t.periodos:
        if p.orgao not in seen_orgs:
            seen_orgs.append(p.orgao)
            legend_items.append(
                f'<div class="lt-legend-item"><span class="lt-swatch" style="background:{p.cor}"></span><strong>{safe_text(p.orgao)}</strong><span>{safe_text(p.nome_orgao)}</span></div>'
            )

    html_doc = f"""
    <style>
      :root {{
        --text: #1f2937;
        --muted: #6b7280;
        --border: #e5e7eb;
        --bg: #ffffff;
        --soft: #f8fafc;
      }}
      .lt-card {{
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--text);
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 22px 24px 18px 24px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, .07);
        margin-bottom: 18px;
      }}
      .lt-header {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 4px;
      }}
      .lt-title {{
        font-size: 20px;
        font-weight: 800;
        letter-spacing: -.02em;
        margin: 0;
      }}
      .lt-subtitle {{
        font-size: 13px;
        color: var(--muted);
        line-height: 1.35;
        margin: 4px 0 0 0;
        max-width: 920px;
      }}
      .lt-badge {{
        flex: 0 0 auto;
        border-radius: 999px;
        background: #f1f5f9;
        color: #334155;
        font-size: 12px;
        font-weight: 650;
        padding: 7px 11px;
        white-space: nowrap;
      }}
      .lt-stage {{
        position: relative;
        height: {height_px}px;
        margin-top: 14px;
        padding-left: 2px;
        padding-right: 2px;
      }}
      .lt-label-layer {{
        position: relative;
        height: 86px;
      }}
      .lt-org-label {{
        position: absolute;
        bottom: 0;
        transform: rotate(-45deg);
        transform-origin: left bottom;
        font-size: 13px;
        font-weight: 800;
        color: #111827;
        letter-spacing: .02em;
        white-space: nowrap;
        z-index: 5;
      }}
      .lt-bar {{
        display: flex;
        width: 100%;
        height: {bar_height_px}px;
        border-radius: 14px;
        overflow: hidden;
        background: #e5e7eb;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,.32), 0 8px 20px rgba(15, 23, 42, .10);
      }}
      .lt-segment {{
        height: 100%;
        min-width: 0;
        transition: filter .15s ease-in-out;
      }}
      .lt-segment:hover {{
        filter: brightness(1.08) saturate(1.1);
      }}
      .lt-date-layer {{
        position: relative;
        height: 72px;
      }}
      .lt-date-label {{
        position: absolute;
        top: 10px;
        transform: rotate(45deg);
        transform-origin: left top;
        font-size: 12px;
        font-weight: 650;
        color: #374151;
        white-space: nowrap;
        z-index: 4;
      }}
      .lt-date-final {{
        margin-left: -2px;
      }}
      .lt-legend {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 8px 16px;
        margin-top: 8px;
        padding: 12px 14px;
        background: var(--soft);
        border: 1px solid var(--border);
        border-radius: 14px;
      }}
      .lt-legend-item {{
        display: flex;
        align-items: center;
        gap: 7px;
        font-size: 12px;
        color: #475569;
      }}
      .lt-swatch {{
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 4px;
        flex: 0 0 auto;
      }}
      .lt-note {{
        font-size: 11px;
        color: var(--muted);
        margin-top: 9px;
      }}
    </style>
    <div class="lt-card">
      <div class="lt-header">
        <div>
          <p class="lt-title">{safe_text(t.codigo)}</p>
          <p class="lt-subtitle">{safe_text(t.ementa)}</p>
        </div>
        <div class="lt-badge">{safe_text(t.fonte)}</div>
      </div>
      <div class="lt-stage">
        <div class="lt-label-layer">{''.join(labels_html)}</div>
        <div class="lt-bar">{''.join(segs_html)}</div>
        <div class="lt-date-layer">{''.join(dates_html)}</div>
      </div>
      <div class="lt-legend">{''.join(legend_items)}</div>
      <div class="lt-note">Passe o mouse sobre os segmentos para ver órgão, datas, duração real e descrição do evento inicial.</div>
    </div>
    """
    components.html(html_doc, height=height_px + 190, scrolling=False)


def build_prompt(timelines: List[PropositionTimeline]) -> str:
    if not timelines:
        return ""
    blocks = []
    for t in timelines:
        periods = []
        total = sum(p.dias for p in t.periodos)
        for p in t.periodos:
            periods.append(
                f"- {p.orgao} ({p.nome_orgao}): {fmt_date_br(p.inicio)} a {fmt_date_br(p.fim)}; "
                f"{p.dias} dias; {(p.dias / total * 100) if total else 0:.1f}% do período analisado."
            )
        blocks.append(
            f"PROPOSIÇÃO: {t.codigo}\n"
            f"EMENTA: {t.ementa}\n"
            f"SITUAÇÃO: {t.situacao}\n"
            f"ÓRGÃO ATUAL: {t.orgao_atual}\n"
            f"ÚLTIMA MOVIMENTAÇÃO: {fmt_date_br(t.ultima_movimentacao)}\n"
            f"PERÍODOS POR ÓRGÃO:\n" + "\n".join(periods) + f"\nALERTA AUTOMÁTICO: {t.alerta}\n"
        )

    return (
        "Atue como assessor legislativo experiente. Com base nos dados estruturados abaixo, "
        "elabore um briefing executivo, em português formal, sobre a tramitação das proposições. "
        "Explique a trajetória legislativa, destaque os órgãos em que houve maior permanência, "
        "indique possíveis gargalos, alerte sobre períodos de inatividade e sugira usos práticos "
        "para acompanhamento parlamentar, sem inventar informações além dos dados fornecidos.\n\n"
        + "\n---\n".join(blocks)
    )


def add_global_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container { max-width: 1220px; padding-top: 2rem; }
        .stMetric { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 12px 14px; box-shadow: 0 6px 18px rgba(15,23,42,.04); }
        div[data-testid="stMetricValue"] { font-size: 1.55rem; }
        .small-muted { color: #64748b; font-size: .92rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="LexTimeline",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    add_global_css()

    st.title("LexTimeline — Painel de Tramitação Legislativa")
    st.caption(
        "Linha do tempo proporcional da tramitação de proposições, com barra contínua, cores fixas por órgão, "
        "rótulos inclinados e datas marcantes."
    )

    with st.sidebar:
        st.header("Configurações")
        mode = st.radio(
            "Fonte dos dados",
            ["Modo demonstração", "Dados ao vivo da Câmara"],
            index=0,
            help="Use o modo demonstração na apresentação caso a API esteja instável.",
        )
        include_until_today = st.checkbox(
            "No modo ao vivo, contar permanência desde a última movimentação até hoje",
            value=True,
        )
        min_visual = st.checkbox(
            "Dar largura mínima visual a períodos muito curtos",
            value=False,
            help="Preserva segmentos curtos no gráfico. As durações reais continuam no tooltip e nos indicadores.",
        )
        min_visual_days = 3 if min_visual else 0
        bar_height = st.slider("Espessura da barra", min_value=32, max_value=72, value=54, step=2)
        fallback_demo = st.checkbox(
            "Se o modo ao vivo falhar, carregar automaticamente o modo demonstração",
            value=True,
            help="Recomendado para apresentação pública: garante que a página continue funcionando mesmo se a API da Câmara oscilar.",
        )
        show_diagnostics = st.checkbox(
            "Mostrar diagnóstico técnico de falhas",
            value=False,
            help="Exibe detalhes úteis para corrigir consultas ao vivo.",
        )
        st.divider()
        st.markdown(
            "**Formato de entrada:**  \n"
            "`PL 1291/2025`  \n"
            "`PL 5875/2013`  \n"
            "uma por linha, ou separadas por ponto e vírgula."
        )

    timelines: List[PropositionTimeline] = []

    if mode == "Modo demonstração":
        st.info(
            "Modo demonstração ativado. Os dados abaixo são amostras reais simplificadas, com datas e órgãos reais previamente selecionados. "
            "Para análise completa e atualizada, selecione 'Dados ao vivo da Câmara'."
        )
        timelines = load_demo_timelines(min_visual_days)
    else:
        default_input = "PL 2630/2020\nPL 5688/2023\nPL 5875/2013"
        raw_input = st.text_area("Informe uma ou várias proposições", value=default_input, height=120)
        parsed = parse_proposition_inputs(raw_input)
        if st.button("Gerar timeline", type="primary", use_container_width=False):
            if not parsed:
                st.error("Não consegui identificar proposições. Use o formato PL 1234/2025.")
            else:
                progress = st.progress(0)
                errors = []
                for i, (sigla, numero, ano) in enumerate(parsed, start=1):
                    try:
                        with st.spinner(f"Consultando {sigla} {numero}/{ano}..."):
                            timelines.append(build_timeline_live(sigla, numero, ano, include_until_today, min_visual_days))
                    except Exception as exc:  # noqa: BLE001 — mensagem amigável para app público.
                        errors.append((f"{sigla} {numero}/{ano}", str(exc)))
                        st.error(f"Falha ao consultar {sigla} {numero}/{ano}.")
                        if show_diagnostics:
                            st.code(str(exc))
                    progress.progress(i / len(parsed))
                progress.empty()
                if not timelines and errors and fallback_demo:
                    st.warning("Nenhuma consulta ao vivo retornou timeline válida. Carreguei o modo demonstração automaticamente para manter o app funcional.")
                    timelines = load_demo_timelines(min_visual_days)
        else:
            st.warning("Informe as proposições e clique em 'Gerar timeline'.")

    if timelines:
        summaries = [timeline_summary(t) for t in timelines]
        df_summary = pd.DataFrame(summaries)

        total_props = len(timelines)
        avg_days = int(df_summary["Tempo total analisado (dias)"].mean()) if total_props else 0
        most_recent = max([t.ultima_movimentacao for t in timelines if t.ultima_movimentacao], default=None)
        dominant = df_summary["Órgão de maior permanência"].mode().iloc[0] if not df_summary.empty else "—"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proposições analisadas", total_props)
        c2.metric("Tempo médio analisado", f"{avg_days} dias")
        c3.metric("Órgão dominante mais comum", dominant)
        c4.metric("Movimentação mais recente", fmt_date_br(most_recent))

        st.subheader("Linhas do tempo proporcionais")
        st.markdown(
            '<p class="small-muted">Os rótulos dos órgãos aparecem acima da barra, inclinados para a direita; as datas de transição aparecem abaixo, também inclinadas. A barra é contínua e não contém texto interno.</p>',
            unsafe_allow_html=True,
        )
        for t in timelines:
            render_timeline(t, height_px=270, bar_height_px=bar_height)
            st.warning(t.alerta, icon="⚠️")

        st.subheader("Tabela comparativa")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

        st.subheader("Prompt estruturado para análise no ChatGPT")
        prompt = build_prompt(timelines)
        st.text_area(
            "Copie o prompt abaixo e cole no ChatGPT para gerar briefing parlamentar ou análise acadêmica.",
            value=prompt,
            height=360,
        )

        st.download_button(
            "Baixar tabela comparativa em CSV",
            data=df_summary.to_csv(index=False).encode("utf-8-sig"),
            file_name="lextimeline_resumo.csv",
            mime="text/csv",
        )

    st.divider()
    st.caption(
        "LexTimeline v1.5 • Dados ao vivo obtidos dos Dados Abertos da Câmara dos Deputados. "
        "O modo demonstração usa amostras reais simplificadas para estabilidade em apresentações."
    )


if __name__ == "__main__":
    main()
