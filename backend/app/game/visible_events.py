"""Shared helpers for narrative and dialogue WebSocket entries."""
from __future__ import annotations

import re
from typing import Any

from app.game.event_bus import EventType


def visible_event_type(entry_kind: str | None) -> str:
    """Return the canonical event type for a visible narrative-log entry."""
    return EventType.DIALOGUE if entry_kind == "dialogue" else EventType.NARRATION


def strip_visible_speaker_prefix(text: str, speaker: str | None) -> str:
    """Remove redundant leading speaker names from visible dialogue text.

    The UI already renders the speaker label. LLMs often start a line with
    "Syndra ..." or "Syndra Silvane: ...", which reads as a duplicate once the
    speaker metadata is present.
    """
    cleaned = str(text or "").lstrip()
    speaker_name = str(speaker or "").strip()
    if not cleaned or not speaker_name:
        return text

    names = [speaker_name]
    first_name = speaker_name.split()[0] if speaker_name.split() else ""
    if first_name and first_name != speaker_name:
        names.append(first_name)

    for name in sorted(names, key=len, reverse=True):
        match = re.match(
            rf"^{re.escape(name)}\s*(?:[:：,\-–—]\s*|\s+)(.+)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1)
    return text


# Paires de guillemets traitées comme "englobant" la réplique entière.
# L'apostrophe / guillemet simple est volontairement exclu (trop de faux positifs
# en français : « l'auberge », « j'ignore »).
_ENCLOSING_QUOTE_PAIRS: tuple[tuple[str, str], ...] = (
    ("«", "»"),
    ("“", "”"),  # “ … ”
    ('"', '"'),
)

# Verbes de parole qui trahissent une didascalie d'attribution résiduelle
# (« <Nom> dit : … », « <Nom> répond, « … »). Couvre les deux apostrophes.
_SPEECH_VERB_PATTERN = (
    r"(?:dit|répond|repond|réplique|replique|rétorque|retorque|déclare|declare|"
    r"ajoute|reprend|lance|murmure|souffle|chuchote|grogne|soupire|annonce|"
    r"explique|demande|poursuit|s['’](?:exclame|écrie|ecrie|enquiert))"
)

# Articles / titres antéposés : exclus comme candidats AUTONOMES de préfixe pour
# ne pas couper une réplique qui débute par « Le … », « Dame … ». Le nom complet
# et le token propre (souvent en fin : « Le Maire Valerius ») restent candidats.
_NAME_STOPWORDS: frozenset[str] = frozenset(
    "le la les l un une du de des d "
    "dame sieur messire maitre maître maire capitaine sergent "
    "frere frère soeur sœur pere père mere mère seigneur "
    "dom don lord lady ser saint sainte".split()
)


def _speaker_name_candidates(speaker_name: str) -> list[str]:
    """Noms candidats pour un préfixe : nom complet + tokens propres (≥ 3 car.,
    hors articles/titres), triés du plus long au plus court."""
    parts = speaker_name.split()
    names = {speaker_name}
    for tok in (parts[:1] + parts[-1:]) if parts else []:
        if len(tok) >= 3 and tok.lower() not in _NAME_STOPWORDS:
            names.add(tok)
    return sorted(names, key=len, reverse=True)


def _strip_enclosing_quotes(text: str) -> str:
    """Retire une unique paire de guillemets qui englobe TOUTE la réplique.

    Conservateur : on n'enlève les guillemets que s'ils forment un seul segment
    équilibré (et non « a », dit-elle, « b »). On garde donc le texte intact dès
    qu'il y a plus d'une paire.
    """
    s = str(text or "").strip()
    if len(s) < 2:
        return text
    for open_q, close_q in _ENCLOSING_QUOTE_PAIRS:
        if not (s.startswith(open_q) and s.endswith(close_q)):
            continue
        inner = s[len(open_q) : len(s) - len(close_q)]
        if open_q == close_q:
            # Guillemets droits : exactement deux occurrences = la seule paire.
            if s.count(open_q) == 2:
                return inner.strip()
        elif s.count(open_q) == 1 and s.count(close_q) == 1:
            # Guillemets appairés : un seul ouvrant, un seul fermant.
            return inner.strip()
    return text


def _strip_speaker_prefix(text: str, speaker: str) -> str:
    """Retire un préfixe de locuteur en tête de réplique.

    Trois formes, ancrées sur le nom du locuteur (jamais sur du texte nu) :
      (a) « <Nom> [verbe de parole <complément court>] : reste »
      (b) « <Nom> <verbe de parole> … « reste » » (guillemet conservé)
      (c) « <Nom><séparateur ou espace>reste » (nom redondant que l'UI affiche déjà)

    Le verbe de parole n'est retiré que suivi d'un séparateur/guillemet — jamais
    « Marc dit la vérité ». Les candidats excluent articles/titres (« Le … »
    reste intact). La forme (c) restaure la coupe de nom nu attendue côté
    compagnon (« Thorin s'accroupit… » → « s'accroupit… »).
    """
    s = str(text or "").lstrip()
    speaker_name = str(speaker or "").strip()
    if not s or not speaker_name:
        return text

    for name in _speaker_name_candidates(speaker_name):
        esc = re.escape(name)
        # (a) « <Nom> [<verbe> <complément court>] : reste »
        m = re.match(
            rf"^{esc}\b(?:\s+{_SPEECH_VERB_PATTERN}\b[^:：«»\"“”\n]{{0,40}})?\s*[:：]\s+(.+)$",
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m:
            return m.group(1).strip()
        # (b) « <Nom> <verbe> … « reste » » (on garde le guillemet pour l'étape suivante)
        m = re.match(
            rf"^{esc}\s+{_SPEECH_VERB_PATTERN}\b[^«\"“\n]{{0,40}}?([«\"“].+)$",
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m:
            return m.group(1).strip()
        # (c) « <Nom><séparateur ou espace>reste » — nom redondant en tête.
        m = re.match(
            rf"^{esc}\s*(?:[:：,\-–—]\s*|\s+)(.+)$",
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m:
            return m.group(1).strip()
    return text


def clean_dialogue_text(text: str, speaker: str | None) -> str:
    """Nettoie une réplique de PNJ destinée à l'affichage joueur.

    Séquence bornée et idempotente (aucune couture mécanique ne doit atteindre la
    bulle de dialogue, cf. thème de fidélité) :
      1. guillemets englobant toute la ligne ;
      2. préfixe de locuteur (« <Nom> : », « <Nom> dit : », « <Nom> dit « … » »,
         ou nom nu redondant) — candidats sans article/titre court, de sorte
         qu'une réplique débutant par « Le … » n'est jamais amputée ;
      3. guillemets de nouveau (cas « <Nom> dit « … » »).

    Le prompt reste le correctif primaire ; ce nettoyage est un filet de sécurité.
    """
    speaker_name = str(speaker or "")
    cleaned = _strip_enclosing_quotes(text)
    cleaned = _strip_speaker_prefix(cleaned, speaker_name)
    cleaned = _strip_enclosing_quotes(cleaned)
    return cleaned


async def publish_visible_entry(
    event_bus_instance: Any,
    session_id: str,
    payload: dict[str, Any],
    *,
    source: str,
) -> None:
    """Publish a visible entry using the canonical dialogue/narration split."""
    payload = dict(payload)
    entry_kind = payload.get("entry_kind")
    if entry_kind == "dialogue" and isinstance(payload.get("text"), str):
        payload["text"] = clean_dialogue_text(
            payload["text"],
            str(payload.get("speaker") or ""),
        )
    await event_bus_instance.publish_to_session(
        session_id,
        visible_event_type(str(entry_kind) if entry_kind is not None else None),
        payload,
        source=source,
    )
