# -*- coding: utf-8 -*-
"""
LexTimeline — Painel de Tramitação Legislativa
Versão 3.0: metodologia estrita baseada na seção oficial "Tramitação" da ficha da Câmara, sem dependência obrigatória da API dos Dados Abertos para localizar o PL.

Desenvolvido para uso em Streamlit Community Cloud.
"""

from __future__ import annotations

import html
import json
import re
import textwrap
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(
    page_title="LexTimeline — Painel de Tramitação Legislativa",
    page_icon="📊",
    layout="wide",
)

FICHA_URL = "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LexTimeline/3.0; +https://github.com/GPE-CD/LexTimeline)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

# Cache interno de IDs oficiais usados no projeto/demonstração.
# Ele evita depender da API dos Dados Abertos apenas para descobrir o idProposicao.
# A análise da tramitação continua sendo feita exclusivamente na ficha oficial da Câmara.
KNOWN_PL_IDS: Dict[Tuple[str, str], str] = {
    ("5875", "2013"): "582806",
    ("5688", "2023"): "2406422",
    ("2630", "2020"): "2256735",
}

CAMARA_SEARCH_URLS = [
    "https://www.camara.leg.br/busca-portal/proposicoes/pesquisa-simplificada?termo={query}",
    "https://www.camara.leg.br/busca-portal/proposicoes?termo={query}",
    "https://www.camara.leg.br/busca-portal?termo={query}",
]


# Paleta fixa por órgão. Mantém consistência entre diferentes PLs.
ORGAO_COLORS: Dict[str, str] = {
    "MESA": "#052c5c",
    "PLEN": "#b30000",
    "CSSF": "#005267",
    "CSAUDE": "#1f6fd8",
    "CCTI": "#10a783",
    "CFT": "#1d7f1d",
    "CCJC": "#6C3483",
    "CMULHER": "#b0198e",
    "CE": "#d97706",
    "CDC": "#0f766e",
    "CDE": "#b7791f",
    "CAPADR": "#4d7c0f",
    "CSPCCO": "#475569",
    "CTRAB": "#92400e",
    "CPASF": "#0e7490",
    "CIDOSO": "#7c3aed",
    "CDHM": "#be123c",
}

DEFAULT_COLORS = [
    "#2563eb", "#059669", "#7c3aed", "#dc2626", "#0891b2", "#9333ea",
    "#ea580c", "#16a34a", "#4f46e5", "#c026d3", "#0f766e", "#a16207",
]

DEFAULT_ORGAO_NAMES = {
    "MESA": "Mesa Diretora",
    "PLEN": "Plenário",
    "CSSF": "Comissão de Seguridade Social e Família",
    "CSAUDE": "Comissão de Saúde",
    "CCTI": "Comissão de Ciência, Tecnologia e Inovação",
    "CFT": "Comissão de Finanças e Tributação",
    "CCJC": "Comissão de Constituição e Justiça e de Cidadania",
    "CMULHER": "Comissão de Defesa dos Direitos da Mulher",
    "CE": "Comissão de Educação",
    "CDC": "Comissão de Defesa do Consumidor",
    "CDE": "Comissão de Desenvolvimento Econômico",
    "CAPADR": "Comissão de Agricultura, Pecuária, Abastecimento e Desenvolvimento Rural",
    "CSPCCO": "Comissão de Segurança Pública e Combate ao Crime Organizado",
    "CTRAB": "Comissão de Trabalho",
}

ACCESSORY_ORGS = {"CCP"}
DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
ORGAO_RE = re.compile(r"^(?P<name>.+?)\s*\(\s*(?P<sigla>[A-Z0-9]{2,12})\s*\)")
PL_RE = re.compile(r"(?:PL\s*)?(?P<num>\d{1,6})\s*/\s*(?P<ano>\d{4})", re.IGNORECASE)
ID_RE = re.compile(r"idProposicao=(\d+)")


@dataclass
class RawEvent:
    date: date
    date_label: str
    sigla: str
    orgao_nome: str
    text: str
    line_index: int = 0


@dataclass
class Marco:
    date: date
    date_label: str
    sigla: str
    orgao_nome: str
    descricao: str
    raw_text: str


@dataclass
class TimelineResult:
    input_label: str
    id_proposicao: str
    ficha_url: str
    situacao: str
    ementa: str
    marcos: List[Marco]
    terminal_date: date
    terminal_label: str
    terminal_note: str
    excluded_count: int
    raw_events_count: int
    warnings: List[str]


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_accents(text: str) -> str:
    """Normalize text for marker detection while preserving original text elsewhere."""
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return normalize_spaces(text).lower()


def marker_contains(line: str, *terms: str) -> bool:
    n = strip_accents(line)
    return all(strip_accents(t) in n for t in terms)


def parse_br_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%y")


def safe_get(url: str, *, params: Optional[dict] = None, timeout: int = 30) -> requests.Response:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp


def safe_get_text(url: str, *, params: Optional[dict] = None, timeout: int = 25) -> str:
    """Fetch HTML/text without assuming JSON.

    The app deliberately avoids using the Dados Abertos API as a mandatory
    locator. It works from the official ficha page and treats the public search
    pages only as optional locators when the user does not provide an id or URL.
    """
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "latin-1"}:
        resp.encoding = "utf-8"
    return resp.text or ""


def extract_id_from_html_for_pl(html_text: str, numero: str, ano: str) -> Optional[str]:
    """Conservatively extract an idProposicao from Câmara search HTML."""
    if not html_text:
        return None
    candidates = []
    # Find explicit ficha URLs.
    for match in re.finditer(r"fichadetramitacao\?idProposicao=(\d+)", html_text):
        start = max(0, match.start() - 500)
        end = min(len(html_text), match.end() + 500)
        context = html.unescape(html_text[start:end])
        score = 0
        if re.search(rf"PL\s*{re.escape(numero)}\s*/\s*{re.escape(ano)}", context, re.I):
            score += 10
        if numero in context and ano in context:
            score += 3
        candidates.append((score, match.group(1)))
    # Also capture generic idProposicao references.
    for match in re.finditer(r"idProposicao[=:%22'\s]+(\d+)", html_text):
        start = max(0, match.start() - 500)
        end = min(len(html_text), match.end() + 500)
        context = html.unescape(html_text[start:end])
        score = 0
        if re.search(rf"PL\s*{re.escape(numero)}\s*/\s*{re.escape(ano)}", context, re.I):
            score += 10
        if numero in context and ano in context:
            score += 3
        candidates.append((score, match.group(1)))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


@st.cache_data(ttl=3600, show_spinner=False)
def find_id_proposicao(numero: str, ano: str) -> Tuple[str, str]:
    """Find proposition id without mandatory Dados Abertos API dependency.

    Priority:
    1. internal cache for known PLs used in the project;
    2. public Câmara search pages, parsed for ficha links;
    3. explicit error requesting URL or idProposicao.
    """
    key = (str(int(numero)) if str(numero).isdigit() else str(numero), str(ano))
    if key in KNOWN_PL_IDS:
        return KNOWN_PL_IDS[key], f"PL {numero}/{ano}"

    from urllib.parse import quote_plus
    query = quote_plus(f"PL {numero}/{ano}")
    last_error = None
    for template in CAMARA_SEARCH_URLS:
        url = template.format(query=query)
        try:
            text = safe_get_text(url, timeout=18)
            found = extract_id_from_html_for_pl(text, numero, ano)
            if found:
                return found, f"PL {numero}/{ano}"
        except Exception as exc:
            last_error = exc
            continue

    suffix = f" Último erro de busca: {last_error}" if last_error else ""
    raise ValueError(
        f"Não consegui localizar automaticamente a ficha do PL {numero}/{ano} no portal da Câmara.{suffix} "
        "Cole a URL da ficha oficial ou informe diretamente o idProposicao."
    )


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_ficha_html(id_proposicao: str) -> str:
    url = FICHA_URL.format(id=id_proposicao)
    return safe_get_text(url, timeout=40)


def extract_basic_info(soup: BeautifulSoup) -> Tuple[str, str]:
    lines = [normalize_spaces(x) for x in soup.get_text("\n").splitlines()]
    lines = [x for x in lines if x]
    situacao = ""
    ementa = ""
    for i, line in enumerate(lines):
        if line.startswith("Situação:"):
            situacao = normalize_spaces(line.replace("Situação:", ""))
            if not situacao and i + 1 < len(lines):
                situacao = lines[i + 1]
        if line == "Ementa" and i + 1 < len(lines):
            ementa = lines[i + 1]
    return situacao, ementa


def get_tramitacao_lines(soup: BeautifulSoup) -> List[str]:
    """Extract text lines from the official Tramitação section of the ficha.

    The Câmara page is not always rendered with the same line breaks in all
    environments. This function therefore uses a hierarchy of conservative
    markers and, if necessary, falls back to scanning the whole official ficha
    for date + órgão patterns. It does not create or infer dates; it only makes
    the extraction of already printed table lines more tolerant.
    """
    all_lines = [normalize_spaces(x) for x in soup.get_text("\n").splitlines()]
    lines = [x for x in all_lines if x]

    def is_data_andamento(x: str) -> bool:
        n = strip_accents(x)
        return n == "data andamento" or ("data" in n and "andamento" in n and len(n) <= 40)

    def is_tramitacao_heading(x: str) -> bool:
        n = strip_accents(x)
        # Handles "Tramitação", "Tramitação Cadastrar para acompanhamento" etc.
        return "tramitacao" in n and "informacoes de tramitacao" not in n and "regime de tramitacao" not in n

    start = None

    # 1) Best marker: explicit "Data Andamento", preferably after the Tramitação heading.
    tram_indices = [i for i, x in enumerate(lines) if is_tramitacao_heading(x)]
    data_indices = [i for i, x in enumerate(lines) if is_data_andamento(x)]
    for di in data_indices:
        if not tram_indices or any(ti <= di for ti in tram_indices):
            start = di + 1
            break

    # 2) Official observation immediately before the table.
    if start is None:
        for i, x in enumerate(lines):
            if marker_contains(x, "o andamento da proposicao fora desta casa legislativa"):
                start = i + 1
                # If the next line is "Data Andamento", skip it too.
                if start < len(lines) and is_data_andamento(lines[start]):
                    start += 1
                break

    # 3) Fallback: after the last heading that looks like Tramitação.
    if start is None and tram_indices:
        start = tram_indices[-1] + 1
        if start < len(lines) and is_data_andamento(lines[start]):
            start += 1

    # 4) Last-resort fallback: scan the whole official ficha. This is safer than
    # failing, because later extraction still requires a date followed by an órgão.
    if start is None:
        start = 0

    end_markers_norm = [
        "versoes para impressao", "noticias", "sessoes e reunioes", "discursos",
        "informacoes externas", "camara dos deputados -", "disque-camara",
        "sobre o portal", "termos de uso", "aplicativos",
    ]
    end = len(lines)
    for j in range(start, len(lines)):
        n = strip_accents(lines[j])
        if any(n.startswith(m) or n == m for m in end_markers_norm):
            end = j
            break
    return lines[start:end]


def extract_raw_events(lines: List[str]) -> List[RawEvent]:
    events: List[RawEvent] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not DATE_RE.match(line):
            i += 1
            continue
        date_line_index = i
        date_label_full = line
        event_date = parse_br_date(line)
        i += 1

        # Find the org line, tolerating blank/irrelevant lines between date and órgão.
        org_line = ""
        org_idx = i
        while org_idx < len(lines):
            if DATE_RE.match(lines[org_idx]):
                break
            if ORGAO_RE.search(lines[org_idx]):
                org_line = lines[org_idx]
                break
            org_idx += 1
        if not org_line:
            i = org_idx
            continue

        org_match = ORGAO_RE.search(org_line)
        if not org_match:
            i = org_idx + 1
            continue
        orgao_nome = normalize_spaces(org_match.group("name").split("-")[0])
        sigla = org_match.group("sigla").strip().upper()

        # Collect text until next date.
        text_parts: List[str] = []
        k = org_idx + 1
        while k < len(lines) and not DATE_RE.match(lines[k]):
            # Skip repeated navigation/link noise.
            token = lines[k]
            if token not in {"Inteiro teor", "Cadastrar para acompanhamento", "Carregando", "Por favor, aguarde."}:
                text_parts.append(token)
            k += 1
        event_text = normalize_spaces(" ".join(text_parts))
        events.append(
            RawEvent(
                date=event_date,
                date_label=fmt_date(event_date),
                sigla=sigla,
                orgao_nome=orgao_nome,
                text=event_text,
                line_index=date_line_index,
            )
        )
        i = k
    return events


def is_initial_presentation(event: RawEvent, is_first_date: bool) -> bool:
    txt = event.text.lower()
    return event.sigla == "MESA" and is_first_date and ("apresentação do pl" in txt or "apresentacao do pl" in txt or "apresentação do projeto" in txt or "projeto de lei" in txt)


def is_initial_presentation_any_org(event: RawEvent, is_first_date: bool) -> bool:
    """Some propositions show the first presentation under PLEN instead of MESA."""
    txt = event.text.lower()
    return is_first_date and (
        "apresentação do pl" in txt
        or "apresentacao do pl" in txt
        or "apresentação do projeto" in txt
        or "apresentacao do projeto" in txt
        or "projeto de lei" in txt
    )


def is_accessory_mesa(event: RawEvent, first_date: Optional[date]) -> bool:
    if event.sigla != "MESA":
        return False
    # MESA is only accepted at the initial presentation.
    return not is_initial_presentation(event, bool(first_date and event.date == first_date))


def text_has_any(text: str, patterns: Iterable[str]) -> bool:
    text_l = text.lower()
    return any(p in text_l for p in patterns)


def looks_effective(event: RawEvent, previous_sigla: Optional[str], first_date: Optional[date]) -> bool:
    """Conservative rule set for effective passage by órgão."""
    txt = event.text.lower()
    sigla = event.sigla

    if sigla in ACCESSORY_ORGS:
        return False
    if is_initial_presentation_any_org(event, bool(first_date and event.date == first_date)):
        return True
    if sigla == "MESA":
        return False

    # Never create a new segment if órgão did not change. Later events in same órgão may be used only as terminal date.
    if previous_sigla == sigla:
        return False

    # Clear entry into a committee or órgão.
    effective_patterns = [
        "recebimento pela",
        "recebimento pelo",
        "recebida pela",
        "recebido pela",
        "designada relatora",
        "designado relator",
        "designada a relatora",
        "designado o relator",
        "parecer proferido em plenário",
        "parecer proferido em plenario",
        "discussão em turno único",
        "discussao em turno unico",
        "aprovado o requerimento",
        "alteração do regime de tramitação",
        "alteracao do regime de tramitacao",
        "apresentação do prl",
        "apresentacao do prl",
        "parecer da relatora",
        "parecer do relator",
        "lido o parecer",
        "aprovado o parecer",
    ]
    if text_has_any(txt, effective_patterns):
        # Exclude obvious procedural/deadline-only events even if in a comissão.
        non_effective = [
            "prazo para emendas",
            "encerrado o prazo",
            "encaminhada à publicação",
            "encaminhada a publicação",
            "parecer recebido para publicação",
            "parecer recebido para publicacao",
            "devolução à ccp",
            "devolucao a ccp",
            "devolvida pela relatora sem manifestação",
            "devolvida pelo relator sem manifestação",
            "informativo da conof",
        ]
        if text_has_any(txt, non_effective) and not text_has_any(txt, ["recebimento pela", "designada relatora", "designado relator", "aprovado o requerimento", "parecer proferido"]):
            return False
        return True

    return False


def summarize_marco(event: RawEvent) -> str:
    txt = event.text
    low = txt.lower()
    if "apresentação do pl" in low or "apresentacao do pl" in low or "apresentação do projeto" in low or "projeto de lei" in low:
        return "Apresentação do projeto"
    if "aprovado o requerimento" in low and ("urgência" in low or "urgencia" in low):
        return "Aprovado o requerimento de urgência e alterado o regime de tramitação"
    if "parecer proferido em plenário" in low or "parecer proferido em plenario" in low:
        return "Parecer proferido em Plenário"
    if "discussão em turno único" in low or "discussao em turno unico" in low:
        return "Discussão, votação e deliberação em Plenário"
    if "recebimento pela" in low:
        # Prefer concise destination summary.
        return f"Recebimento pela {event.orgao_nome}"
    if "designada relatora" in low or "designado relator" in low or "designada a relatora" in low:
        if event.sigla == "PLEN":
            return "Designada relatora em Plenário"
        return f"Designação de relatoria na {event.orgao_nome}"
    if "apresentação do prl" in low or "apresentacao do prl" in low:
        if "substitutivo" in low:
            return "Apresentação de parecer da relatoria, pela aprovação com substitutivo"
        return "Apresentação de parecer da relatoria"
    if "parecer da relatora" in low or "parecer do relator" in low:
        if "substitutivo" in low:
            return "Parecer da relatoria, pela aprovação com substitutivo"
        return "Parecer da relatoria"
    if "aprovado o parecer" in low:
        return "Aprovado o parecer"
    # Conservative fallback: first sentence/clause, shortened.
    clean = normalize_spaces(re.sub(r"Inteiro teor", "", txt))
    if len(clean) > 120:
        clean = clean[:117].rsplit(" ", 1)[0] + "..."
    return clean or "Marco de tramitação oficial"


def dedupe_and_sort_events(events: List[RawEvent]) -> List[RawEvent]:
    """Remove duplicated events accidentally captured outside the Tramitação table
    and sort by official date while preserving same-day page order.
    """
    seen = set()
    deduped: List[RawEvent] = []
    for e in events:
        key = (e.date.isoformat(), e.sigla, normalize_spaces(e.text)[:220])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return sorted(deduped, key=lambda e: (e.date, e.line_index))


def select_marcos(events: List[RawEvent]) -> Tuple[List[Marco], int, List[str]]:
    if not events:
        return [], 0, ["Nenhum evento foi extraído da seção Tramitação."]
    first_date = min(e.date for e in events)
    marcos: List[Marco] = []
    excluded = 0
    warnings: List[str] = []
    previous_sigla: Optional[str] = None

    for event in events:
        if looks_effective(event, previous_sigla, first_date):
            marco = Marco(
                date=event.date,
                date_label=fmt_date(event.date),
                sigla=event.sigla,
                orgao_nome=event.orgao_nome or DEFAULT_ORGAO_NAMES.get(event.sigla, event.sigla),
                descricao=summarize_marco(event),
                raw_text=event.text,
            )
            marcos.append(marco)
            previous_sigla = event.sigla
        else:
            excluded += 1

    # If the first effective event after exclusions is not the initial presentation but there is a clear presentation, prepend it.
    if marcos:
        first_presentation = next((e for e in events if is_initial_presentation_any_org(e, e.date == first_date)), None)
        if first_presentation and marcos[0].date != first_presentation.date:
            marcos.insert(
                0,
                Marco(
                    date=first_presentation.date,
                    date_label=fmt_date(first_presentation.date),
                    sigla=first_presentation.sigla,
                    orgao_nome=first_presentation.orgao_nome or DEFAULT_ORGAO_NAMES.get(first_presentation.sigla, first_presentation.sigla),
                    descricao="Apresentação do projeto",
                    raw_text=first_presentation.text,
                ),
            )

    if len(marcos) < 2:
        warnings.append("A seção Tramitação não contém marcos suficientes, pelos critérios estritos, para uma timeline proporcional robusta.")
    return marcos, excluded, warnings


def is_final_situation(situacao: str, events: List[RawEvent]) -> bool:
    text = (situacao or "").lower() + " " + " ".join(e.text.lower() for e in events[-8:])
    final_terms = [
        "transformada na lei",
        "transformado na lei",
        "arquivada",
        "arquivado",
        "matéria vai ao senado",
        "materia vai ao senado",
        "remessa ao senado",
        "remetido ao senado",
        "vai à sanção",
        "vai a sanção",
        "remessa à sanção",
        "remessa a sanção",
    ]
    return any(t in text for t in final_terms)


def is_terminal_activity(event: RawEvent) -> bool:
    txt = event.text.lower()
    terminal_patterns = [
        "discussão em turno único",
        "discussao em turno unico",
        "parecer proferido em plenário",
        "parecer proferido em plenario",
        "aprovado o substitutivo",
        "aprovada a redação final",
        "aprovada a redacao final",
        "a matéria vai ao senado",
        "a materia vai ao senado",
        "votação em turno único",
        "votacao em turno unico",
        "encerrada a discussão",
        "encerrada a discussao",
        "aprovado o parecer",
    ]
    accessory_patterns = [
        "devolução à ccp",
        "devolucao a ccp",
        "parecer recebido para publicação",
        "encaminhada à publicação",
        "informativo da conof",
    ]
    return text_has_any(txt, terminal_patterns) and not text_has_any(txt, accessory_patterns)


def choose_terminal_date(events: List[RawEvent], marcos: List[Marco], situacao: str) -> Tuple[date, str]:
    today = date.today()
    if not marcos:
        return today, "Não foi possível determinar a data terminal."
    last = marcos[-1]
    same_org_after = [e for e in events if e.sigla == last.sigla and e.date >= last.date and is_terminal_activity(e)]
    if same_org_after:
        terminal = max(e.date for e in same_org_after)
        return terminal, "Data terminal: último marco oficial relevante no mesmo órgão."
    if is_final_situation(situacao, events):
        # If there is no terminal activity in the last órgão, use last marco itself to avoid inventing.
        return last.date, "Data terminal: último marco efetivo identificado; eventos posteriores acessórios não foram usados."
    return today, "Data terminal: último segmento considerado em curso até a data da análise."


def get_color(sigla: str) -> str:
    if sigla in ORGAO_COLORS:
        return ORGAO_COLORS[sigla]
    # Stable fallback color by hash-like sum.
    idx = sum(ord(c) for c in sigla) % len(DEFAULT_COLORS)
    return DEFAULT_COLORS[idx]


def wrap_svg_text(text: str, width_chars: int) -> List[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=width_chars, break_long_words=False) or [text]


def escape(s: str) -> str:
    return html.escape(s or "")


def compute_segment_widths(days: List[int], total_width: int, min_width: int = 12) -> List[float]:
    if not days:
        return []
    total_days = max(sum(max(d, 0) for d in days), 1)
    raw = [max(d, 0) / total_days * total_width for d in days]
    min_flags = [w < min_width for w in raw]
    fixed = sum(min_width for flag in min_flags if flag)
    remaining_width = max(total_width - fixed, total_width * 0.25)
    raw_remaining = sum(w for w, flag in zip(raw, min_flags) if not flag)
    widths = []
    for w, flag in zip(raw, min_flags):
        if flag:
            widths.append(float(min_width))
        else:
            widths.append(float(w / raw_remaining * remaining_width if raw_remaining else remaining_width / max(1, len(days))))
    # Normalize exactly to total_width.
    factor = total_width / sum(widths)
    return [w * factor for w in widths]


def estimate_rotated_span(text: str, font_size: int = 22, angle_deg: int = 28) -> float:
    """Approximate horizontal span occupied by a rotated label anchored at its start."""
    if not text:
        return 0.0
    # Empirical approximation suitable for SVG labels in this panel.
    return max(28.0, len(text) * font_size * 0.50)


def assign_label_levels(xs: List[float], texts: List[str], *, font_size: int, angle_deg: int, min_gap: float = 8.0, max_levels: int = 4) -> List[int]:
    """Assign staggered levels so rotated labels/dates do not overlap horizontally."""
    level_end = [-1e9] * max_levels
    assigned: List[int] = []
    for x, text in zip(xs, texts):
        span = estimate_rotated_span(text, font_size=font_size, angle_deg=angle_deg)
        chosen = None
        for lvl in range(max_levels):
            if x >= level_end[lvl] + min_gap:
                chosen = lvl
                break
        if chosen is None:
            # Reuse the least-colliding level.
            chosen = min(range(max_levels), key=lambda lvl: level_end[lvl])
        assigned.append(chosen)
        level_end[chosen] = x + span
    return assigned


def render_svg(result: TimelineResult) -> str:
    marcos = result.marcos
    terminal = result.terminal_date
    if not marcos:
        return ""

    W = 1490
    margin_x = 55
    title_y = 60
    subtitle_y = 105
    table_x = 55
    table_w = W - 2 * margin_x
    col_w = [180, 190, table_w - 370]
    row_h_base = 44
    header_h = 48

    table_rows = []
    for m in marcos:
        desc_lines = wrap_svg_text(m.descricao, 72)
        row_h = max(row_h_base, 26 * len(desc_lines) + 20)
        table_rows.append((m, desc_lines, row_h))
    table_y = 130
    table_h = header_h + sum(row[2] for row in table_rows)

    timeline_y = table_y + table_h + 95
    bar_x = margin_x
    bar_y = timeline_y + 60
    bar_w = W - 2 * margin_x
    bar_h = 68

    starts = [m.date for m in marcos]
    ends = [marcos[i + 1].date for i in range(len(marcos) - 1)] + [terminal]
    days = [max((e - s).days, 0) for s, e in zip(starts, ends)]
    widths = compute_segment_widths(days, bar_w, min_width=16)

    start_xs: List[float] = []
    x = bar_x
    for w in widths:
        start_xs.append(x)
        x += w

    label_texts = [f"/{m.sigla}" for m in marcos]
    label_levels = assign_label_levels(start_xs, label_texts, font_size=22, angle_deg=28, min_gap=10.0, max_levels=4)
    label_gap = 24
    label_base_y = bar_y - 18
    max_label_level = max(label_levels) if label_levels else 0

    date_xs = start_xs + [bar_x + bar_w - 4]
    date_texts = [m.date_label for m in marcos] + [result.terminal_label]
    date_levels = assign_label_levels(date_xs, date_texts, font_size=19, angle_deg=45, min_gap=8.0, max_levels=4)
    date_gap = 24
    date_base_y = bar_y + bar_h + 56
    max_date_level = max(date_levels) if date_levels else 0

    legend_y = date_base_y + max_date_level * date_gap + 88

    org_order: List[str] = []
    org_names: Dict[str, str] = {}
    for m in marcos:
        if m.sigla not in org_order:
            org_order.append(m.sigla)
            org_names[m.sigla] = m.orgao_nome or DEFAULT_ORGAO_NAMES.get(m.sigla, m.sigla)

    legend_items = []
    legend_col_w = 640
    for idx, sigla in enumerate(org_order):
        col = idx % 2
        row = idx // 2
        lx = 110 + col * legend_col_w
        ly = legend_y + row * 48
        legend_items.append((sigla, lx, ly))
    legend_h = max(1, ((len(org_order) + 1) // 2)) * 48
    note_title_y = legend_y + legend_h + 62
    note_text_y = note_title_y + 30

    note = "Critério: foram considerados apenas marcos de efetiva tramitação por órgão. Registros acessórios de MESA e CCP não foram incluídos, salvo a etapa inicial de apresentação do projeto."
    if "em curso" in result.terminal_note.lower():
        note += " O último segmento foi considerado em curso até a data da análise."
    note_lines = wrap_svg_text(note, 118)
    note_h = len(note_lines) * 26
    H = note_text_y + note_h + 40

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append('<style>text{font-family:Arial, Helvetica, sans-serif;} .title{font-size:44px;font-weight:800;fill:#061833;} .sub{font-size:24px;fill:#1f2937;} .head{font-size:24px;font-weight:700;fill:#fff;} .cell{font-size:22px;fill:#111827;} .small{font-size:20px;fill:#111827;} .label{font-size:22px;font-weight:800;font-style:italic;} .date{font-size:19px;fill:#111827;} .note{font-size:20px;fill:#111827;} .noteB{font-size:21px;font-weight:800;fill:#111827;}</style>')

    parts.append(f'<text x="{W/2}" y="{title_y}" text-anchor="middle" class="title">LexTimeline — Painel de Tramitação Legislativa</text>')
    subtitle = f'{result.input_label} — timeline visual da tramitação (marcos oficiais da Câmara dos Deputados)'
    parts.append(f'<text x="{W/2}" y="{subtitle_y}" text-anchor="middle" class="sub">{escape(subtitle)}</text>')

    parts.append(f'<rect x="{table_x}" y="{table_y}" width="{table_w}" height="{table_h}" fill="#ffffff" stroke="#6b7280" stroke-width="1"/>')
    parts.append(f'<rect x="{table_x}" y="{table_y}" width="{table_w}" height="{header_h}" fill="#061d3a"/>')
    x1 = table_x + col_w[0]
    x2 = table_x + col_w[0] + col_w[1]
    parts.append(f'<line x1="{x1}" y1="{table_y}" x2="{x1}" y2="{table_y+table_h}" stroke="#9ca3af"/>')
    parts.append(f'<line x1="{x2}" y1="{table_y}" x2="{x2}" y2="{table_y+table_h}" stroke="#9ca3af"/>')
    parts.append(f'<text x="{table_x+col_w[0]/2}" y="{table_y+32}" text-anchor="middle" class="head">Data</text>')
    parts.append(f'<text x="{x1+col_w[1]/2}" y="{table_y+32}" text-anchor="middle" class="head">Órgão</text>')
    parts.append(f'<text x="{x2+col_w[2]/2}" y="{table_y+32}" text-anchor="middle" class="head">Marco considerado</text>')

    y = table_y + header_h
    for m, desc_lines, rh in table_rows:
        parts.append(f'<line x1="{table_x}" y1="{y}" x2="{table_x+table_w}" y2="{y}" stroke="#c7cdd6"/>')
        cy = y + rh / 2 + 8
        parts.append(f'<text x="{table_x+col_w[0]/2}" y="{cy}" text-anchor="middle" class="cell">{m.date_label}</text>')
        parts.append(f'<text x="{x1+col_w[1]/2}" y="{cy}" text-anchor="middle" class="cell">{escape(m.sigla)}</text>')
        text_y = y + 28 if len(desc_lines) > 1 else cy
        parts.append(f'<text x="{x2+28}" y="{text_y}" class="cell">')
        for j, line in enumerate(desc_lines):
            dy = 0 if j == 0 else 26
            parts.append(f'<tspan x="{x2+28}" dy="{dy}">{escape(line)}</tspan>')
        parts.append('</text>')
        y += rh
    parts.append(f'<line x1="{table_x}" y1="{table_y+table_h}" x2="{table_x+table_w}" y2="{table_y+table_h}" stroke="#6b7280"/>')

    x = bar_x
    for idx, (m, w) in enumerate(zip(marcos, widths)):
        color = get_color(m.sigla)
        rx = 6 if idx == 0 or idx == len(marcos) - 1 else 0
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w:.2f}" height="{bar_h}" fill="{color}" rx="{rx}" ry="{rx}"/>')
        lx = x + 8
        ly = label_base_y - label_levels[idx] * label_gap
        parts.append(f'<text x="{lx:.2f}" y="{ly:.2f}" class="label" fill="#111827" transform="rotate(-28 {lx:.2f} {ly:.2f})">/{escape(m.sigla)}</text>')
        dx = x + 4
        dy = date_base_y + date_levels[idx] * date_gap
        parts.append(f'<text x="{dx:.2f}" y="{dy:.2f}" class="date" transform="rotate(-45 {dx:.2f} {dy:.2f})">{m.date_label}</text>')
        x += w

    final_dx = bar_x + bar_w - 4
    final_dy = date_base_y + date_levels[-1] * date_gap
    parts.append(f'<text x="{final_dx:.2f}" y="{final_dy:.2f}" text-anchor="end" class="date" transform="rotate(-45 {final_dx:.2f} {final_dy:.2f})">{result.terminal_label}</text>')

    for sigla, lx, ly in legend_items:
        color = get_color(sigla)
        name = org_names.get(sigla) or DEFAULT_ORGAO_NAMES.get(sigla, sigla)
        label = f"{sigla} — {name}"
        lines = wrap_svg_text(label, 44)
        parts.append(f'<rect x="{lx}" y="{ly-20}" width="48" height="28" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{lx+68}" y="{ly}" class="small">')
        for j, line in enumerate(lines):
            dy = 0 if j == 0 else 24
            parts.append(f'<tspan x="{lx+68}" dy="{dy}">{escape(line)}</tspan>')
        parts.append('</text>')

    parts.append(f'<line x1="{margin_x}" y1="{note_title_y-28}" x2="{W-margin_x}" y2="{note_title_y-28}" stroke="#9ca3af"/>')
    parts.append(f'<text x="{margin_x+25}" y="{note_title_y}" class="noteB">Nota metodológica:</text>')
    parts.append(f'<text x="{margin_x+25}" y="{note_text_y}" class="note">')
    for j, line in enumerate(note_lines):
        dy = 0 if j == 0 else 26
        parts.append(f'<tspan x="{margin_x+25}" dy="{dy}">{escape(line)}</tspan>')
    parts.append('</text>')

    parts.append('</svg>')
    return "".join(parts)


def svg_to_data_uri(svg: str) -> str:
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def analyze_pl(raw_input: str) -> TimelineResult:
    numero, ano, direct_id = parse_pl_input(raw_input)
    if direct_id:
        id_prop = direct_id
        input_label = f"Proposição {id_prop}"
    else:
        if not numero or not ano:
            raise ValueError("Informe o PL no formato PL número/ano, por exemplo: PL 5875/2013.")
        id_prop, input_label = find_id_proposicao(numero, ano)

    ficha_url = FICHA_URL.format(id=id_prop)
    ficha_html = fetch_ficha_html(id_prop)
    soup = BeautifulSoup(ficha_html, "html.parser")
    situacao, ementa = extract_basic_info(soup)
    lines = get_tramitacao_lines(soup)
    raw_events = dedupe_and_sort_events(extract_raw_events(lines))
    if not raw_events:
        raise ValueError("Não extraí eventos oficiais de tramitação no padrão data + órgão. A ficha pode ter sido carregada de forma incompleta; tente colar a URL da ficha oficial ou repetir a consulta.")
    marcos, excluded_count, warnings = select_marcos(raw_events)
    terminal_date, terminal_note = choose_terminal_date(raw_events, marcos, situacao)

    if direct_id:
        # Try to recover title from page heading if user provided id directly.
        title = soup.find(["h1", "h2", "h3"])
        if title:
            txt = normalize_spaces(title.get_text(" "))
            m = PL_RE.search(txt)
            if m:
                input_label = f"PL {m.group('num')}/{m.group('ano')}"

    return TimelineResult(
        input_label=input_label,
        id_proposicao=id_prop,
        ficha_url=ficha_url,
        situacao=situacao,
        ementa=ementa,
        marcos=marcos,
        terminal_date=terminal_date,
        terminal_label=fmt_date(terminal_date),
        terminal_note=terminal_note,
        excluded_count=excluded_count,
        raw_events_count=len(raw_events),
        warnings=warnings,
    )


def render_result(result: TimelineResult):
    st.subheader(result.input_label)
    with st.expander("Informações da ficha oficial", expanded=False):
        st.write(f"**ID da proposição:** {result.id_proposicao}")
        st.write(f"**Ficha oficial:** {result.ficha_url}")
        if result.situacao:
            st.write(f"**Situação:** {result.situacao}")
        if result.ementa:
            st.write(f"**Ementa:** {result.ementa}")
        st.write(f"**Eventos brutos extraídos da seção Tramitação:** {result.raw_events_count}")
        st.write(f"**Eventos excluídos por critério metodológico:** {result.excluded_count}")
        st.write(f"**{result.terminal_note}**")

    if result.warnings:
        for w in result.warnings:
            st.warning(w)
    if not result.marcos:
        st.error("Não foi possível montar a timeline com segurança, pois nenhum marco efetivo foi identificado.")
        return

    table_data = [
        {"Data": m.date_label, "Órgão": m.sigla, "Marco considerado": m.descricao}
        for m in result.marcos
    ]
    st.markdown("### Tabela de marcos considerados")
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    st.markdown("### Timeline visual")
    svg = render_svg(result)
    # Use HTML wrapper for responsiveness.
    svg_uri = svg_to_data_uri(svg)
    html_block = f"""
    <div style="width:100%; overflow-x:auto; border:1px solid #e5e7eb; border-radius:10px; padding:8px; background:white;">
      <img src="{svg_uri}" style="width:100%; min-width:1100px; height:auto; display:block;" />
    </div>
    """
    st.components.v1.html(html_block, height=980, scrolling=True)

    st.download_button(
        "Baixar painel em SVG",
        data=svg.encode("utf-8"),
        file_name=f"lextimeline_{re.sub(r'[^0-9A-Za-z]+', '_', result.input_label).strip('_')}.svg",
        mime="image/svg+xml",
    )

    with st.expander("SVG autocontido", expanded=False):
        st.code(svg, language="xml")


def main():
    st.markdown(
        """
        <div style="padding: 10px 0 4px 0;">
          <h1 style="margin-bottom:0; color:#061833;">LexTimeline — Painel de Tramitação Legislativa</h1>
          <p style="font-size:1.05rem; color:#374151; margin-top:0.25rem;">
            Timeline visual proporcional da tramitação de Projetos de Lei, baseada diretamente na seção oficial <b>Tramitação</b> da ficha da Câmara dos Deputados.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "Metodologia estrita: o app não reconstrói datas por aproximação. Ele usa apenas marcos oficiais encontrados na seção Tramitação. "
        "Registros acessórios de MESA e CCP são excluídos, salvo a etapa inicial de apresentação do projeto."
    )

    with st.sidebar:
        st.header("Entrada")
        st.caption("Informe um ou vários PLs, um por linha. O app prioriza a ficha oficial da Câmara. Também é aceito colar uma URL da ficha ou um idProposicao.")
        examples = "PL 5875/2013\nPL 5688/2023"
        user_input = st.text_area("Projetos de Lei", value=examples, height=120)
        run = st.button("Gerar timeline", type="primary")
        st.divider()
        st.markdown("**Critério central**")
        st.write("A timeline mostra marcos de efetiva passagem por órgão, extraídos da tabela oficial de Tramitação.")

    if not run:
        st.markdown("#### Como usar")
        st.write("Digite um PL no menu lateral e clique em **Gerar timeline**.")
        st.write("Exemplos recomendados para teste: **PL 5875/2013** e **PL 5688/2023**.")
        return

    inputs = [x.strip() for x in user_input.splitlines() if x.strip()]
    if not inputs:
        st.warning("Informe pelo menos um Projeto de Lei.")
        return

    for idx, raw in enumerate(inputs, start=1):
        if idx > 1:
            st.divider()
        try:
            with st.spinner(f"Consultando {raw} na ficha oficial da Câmara..."):
                result = analyze_pl(raw)
            render_result(result)
        except Exception as e:
            st.error(f"Falha ao consultar {raw}: {e}")
            st.caption("Se o erro persistir, cole a URL da ficha da Câmara contendo idProposicao=... ou informe diretamente o idProposicao.")


if __name__ == "__main__":
    main()
