"""LOT D — la réplique PNJ affichée ne porte ni guillemets englobants ni préfixe.

Thème de fidélité : aucune couture mécanique (guillemets bruts, didascalie
d'attribution « <Nom> : », « <Nom> dit : ») ne doit atteindre la bulle de
dialogue lue par le joueur. Le prompt est le correctif primaire ; ces tests
verrouillent le sanitizer (filet de sécurité, déterministe).
"""

from __future__ import annotations

import pytest

from app.game.visible_events import clean_dialogue_text


def _has_no_enclosing_quotes(text: str) -> bool:
    s = text.strip()
    return not (
        (s.startswith("«") and s.endswith("»"))
        or (s.startswith('"') and s.endswith('"'))
        or (s.startswith("“") and s.endswith("”"))
    )


@pytest.mark.parametrize(
    ("raw", "speaker", "expected"),
    [
        # Guillemets appairés englobant toute la réplique.
        ("« Bienvenue, voyageur. »", "Le Maire Valerius", "Bienvenue, voyageur."),
        # Guillemets droits englobants.
        ('"Que cherches-tu ici ?"', "Bram", "Que cherches-tu ici ?"),
        # Préfixe nom + deux-points.
        ("Le Maire Valerius : Bienvenue.", "Le Maire Valerius", "Bienvenue."),
        # Préfixe nom (prénom) + verbe de parole + deux-points.
        ("Valerius dit : Le contrat tient.", "Le Maire Valerius", "Le contrat tient."),
        # Nom + verbe + guillemets : on retire l'attribution ET les guillemets.
        ("Bram répond « Je n'ai rien vu. »", "Bram", "Je n'ai rien vu."),
        # Guillemets englobant l'attribution complète.
        ("« Valerius : Suis-moi. »", "Valerius", "Suis-moi."),
    ],
)
def test_clean_dialogue_strips_seams(raw: str, speaker: str, expected: str) -> None:
    cleaned = clean_dialogue_text(raw, speaker)
    assert cleaned == expected
    assert _has_no_enclosing_quotes(cleaned)
    # Jamais de préfixe « <Nom> : » résiduel en tête.
    assert not cleaned.lower().startswith(f"{speaker.lower()} :")
    assert not cleaned.lower().startswith(f"{speaker.split()[0].lower()} :")


def test_clean_dialogue_keeps_multiple_quote_spans_intact() -> None:
    # Deux paires de guillemets : ce ne sont PAS des guillemets englobants → on
    # ne touche pas (sinon on couperait le premier/dernier caractère).
    raw = "« Oui », souffle-t-il, « mais pas ici. »"
    assert clean_dialogue_text(raw, "Bram") == raw


def test_clean_dialogue_keeps_plain_reply_unchanged() -> None:
    raw = "Bienvenue, voyageur. (Il essuie ses mains.) Que viens-tu chercher ?"
    assert clean_dialogue_text(raw, "Le Maire Valerius") == raw


def test_clean_dialogue_keeps_reply_starting_with_speech_verb_without_name() -> None:
    # Verbe de parole en tête SANS le nom du locuteur : réplique légitime, intacte
    # (l'attribution est ancrée sur le nom, pas sur le verbe seul).
    raw = "Demande au garde, il te laissera passer."
    assert clean_dialogue_text(raw, "Bram") == raw


def test_clean_dialogue_is_idempotent() -> None:
    raw = "Valerius dit : « Le contrat tient. »"
    once = clean_dialogue_text(raw, "Le Maire Valerius")
    assert clean_dialogue_text(once, "Le Maire Valerius") == once
    assert once == "Le contrat tient."


def test_clean_dialogue_handles_empty_and_missing_speaker() -> None:
    assert clean_dialogue_text("", "Bram") == ""
    assert clean_dialogue_text("« Bonjour. »", None) == "Bonjour."
