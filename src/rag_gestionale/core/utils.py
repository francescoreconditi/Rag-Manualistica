"""
Utilità core per il sistema RAG.
Include funzioni per hashing, normalizzazione testo e gestione URL.
"""

import hashlib
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse


def normalize_text(text: str) -> str:
    """
    Normalizza il testo per la deduplicazione e il processing.

    Args:
        text: Testo da normalizzare

    Returns:
        Testo normalizzato
    """
    # Rimuovi whitespace eccessivi
    text = re.sub(r'\s+', ' ', text.strip())

    # Normalizza punteggiatura
    text = re.sub(r'\.{2,}', '...', text)

    # Unifica forme alternative comuni
    replacements = {
        'N°': 'Numero',
        'n°': 'numero',
        'N.': 'Numero',
        'n.': 'numero',
        'impostaz.': 'impostazione',
        'config.': 'configurazione',
        'parametr.': 'parametro',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def compute_content_hash(content: str) -> str:
    """
    Calcola hash SHA-1 del contenuto per deduplicazione.

    Args:
        content: Contenuto da cui calcolare l'hash

    Returns:
        Hash SHA-1 come stringa esadecimale
    """
    normalized = normalize_text(content)
    return hashlib.sha1(normalized.encode('utf-8')).hexdigest()


def extract_breadcrumbs(section_path: str) -> List[str]:
    """
    Estrae breadcrumbs dal percorso della sezione.

    Args:
        section_path: Percorso come "contabilita/impostazioni/iva"

    Returns:
        Lista di breadcrumbs ["Contabilità", "Impostazioni", "IVA"]
    """
    if not section_path:
        return []

    parts = section_path.split('/')
    # Capitalizza e normalizza
    breadcrumbs = []
    for part in parts:
        if part:
            # Capitalizza prima lettera di ogni parte
            normalized = part.replace('_', ' ').replace('-', ' ')
            breadcrumbs.append(normalized.title())

    return breadcrumbs


def extract_error_codes(text: str) -> List[str]:
    """
    Estrae codici errore dal testo usando pattern regex.

    Args:
        text: Testo da cui estrarre i codici errore

    Returns:
        Lista di codici errore trovati
    """
    # Pattern per codici errore: 2-4 lettere seguite da numero
    pattern = r'\b[A-Z]{2,4}-?\d{2,4}\b'
    return list(set(re.findall(pattern, text.upper())))


def is_valid_url(url: str, allowed_domains: List[str]) -> bool:
    """
    Verifica se l'URL è valido e nel whitelist dei domini.

    Args:
        url: URL da verificare
        allowed_domains: Lista dei domini autorizzati

    Returns:
        True se l'URL è valido e autorizzato
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        domain = parsed.netloc.lower()
        # Rimuovi www. se presente
        if domain.startswith('www.'):
            domain = domain[4:]

        return any(domain == allowed or domain.endswith('.' + allowed)
                  for allowed in allowed_domains)
    except Exception:
        return False


def clean_html_tags(text: str) -> str:
    """
    Rimuove tag HTML residui dal testo.

    Args:
        text: Testo con possibili tag HTML

    Returns:
        Testo pulito
    """
    # Rimuovi tag HTML
    text = re.sub(r'<[^>]+>', '', text)

    # Decodifica entità HTML comuni
    html_entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' ',
    }

    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    return text


def extract_ui_path_from_text(text: str) -> Optional[str]:
    """
    Tenta di estrarre il percorso UI dal testo usando pattern comuni.

    Args:
        text: Testo da cui estrarre il percorso UI

    Returns:
        Percorso UI estratto o None
    """
    # Pattern comuni per percorsi UI
    patterns = [
        r'Menu\s*>\s*(.+?)(?:\.|$)',
        r'Vai\s+a\s*:\s*(.+?)(?:\.|$)',
        r'Percorso\s*:\s*(.+?)(?:\.|$)',
        r'(?:Sezione|Menu)\s*"([^"]+)"',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            # Pulisci e normalizza
            path = re.sub(r'\s*>\s*', ' > ', path)
            return path

    return None


def split_into_sentences(text: str) -> List[str]:
    """
    Divide il testo in frasi usando pattern italiani.

    Args:
        text: Testo da dividere

    Returns:
        Lista di frasi
    """
    # Pattern per fine frase in italiano
    sentence_endings = r'[.!?]+(?:\s|$)'

    # Split mantenendo la punteggiatura
    sentences = re.split(f'({sentence_endings})', text)

    # Ricomponi frasi con punteggiatura
    result = []
    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i + 1]

        sentence = sentence.strip()
        if sentence and len(sentence) > 10:  # Filtro frasi troppo corte
            result.append(sentence)

    return result


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Stima il numero di token nel testo.

    Args:
        text: Testo da analizzare
        chars_per_token: Caratteri per token (medio per italiano)

    Returns:
        Stima del numero di token
    """
    return max(1, int(len(text) / chars_per_token))


def truncate_to_tokens(text: str, max_tokens: int, chars_per_token: float = 4.0) -> str:
    """
    Tronca il testo al numero massimo di token stimati.

    Args:
        text: Testo da troncare
        max_tokens: Token massimi
        chars_per_token: Caratteri per token

    Returns:
        Testo troncato
    """
    max_chars = int(max_tokens * chars_per_token)
    if len(text) <= max_chars:
        return text

    # Tronca al carattere precedente uno spazio per evitare parole spezzate
    truncated = text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.8:  # Solo se non perdiamo troppo testo
        truncated = truncated[:last_space]

    return truncated + "..."