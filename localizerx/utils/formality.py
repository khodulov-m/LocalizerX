"""Form-of-address (T–V distinction) handling for translation prompts.

Most languages LocalizerX targets distinguish a familiar and a polite way of
addressing the reader (German ``du``/``Sie``, French ``tu``/``vous``, Russian
``ты``/``вы``…). English does not, so a model translating from English picks
whatever register it considers safest — in practice almost always the polite
one. Products that speak informally to their users therefore had to fix every
German, French or Portuguese string by hand.

This module turns an explicit ``formality`` setting into a per-language prompt
block that pins the register down.
"""

from __future__ import annotations

from dataclasses import dataclass

from localizerx.utils.locale import normalize_language_code

FORMALITY_AUTO = "auto"
FORMALITY_FORMAL = "formal"
FORMALITY_INFORMAL = "informal"

VALID_FORMALITY = (FORMALITY_AUTO, FORMALITY_FORMAL, FORMALITY_INFORMAL)

# Accepted spellings, including the pronouns people naturally reach for.
_ALIASES: dict[str, str] = {
    "": FORMALITY_AUTO,
    "auto": FORMALITY_AUTO,
    "default": FORMALITY_AUTO,
    "none": FORMALITY_AUTO,
    "informal": FORMALITY_INFORMAL,
    "casual": FORMALITY_INFORMAL,
    "familiar": FORMALITY_INFORMAL,
    "du": FORMALITY_INFORMAL,
    "tu": FORMALITY_INFORMAL,
    "ty": FORMALITY_INFORMAL,
    "formal": FORMALITY_FORMAL,
    "polite": FORMALITY_FORMAL,
    "sie": FORMALITY_FORMAL,
    "vous": FORMALITY_FORMAL,
    "usted": FORMALITY_FORMAL,
    "vy": FORMALITY_FORMAL,
}


@dataclass(frozen=True)
class AddressForms:
    """How to address the reader in one language, per register."""

    informal: str
    formal: str


# Keys are normalized locale codes. A region-specific entry (``pt-BR``) wins
# over the base-language one (``pt``).
_ADDRESS_FORMS: dict[str, AddressForms] = {
    "de": AddressForms(
        informal=(
            'Address the reader with the informal German "du" (plural "ihr"), using the '
            'matching verb endings and possessives ("dein", "euer"). Never use the polite '
            '"Sie"/"Ihnen"/"Ihr" forms.'
        ),
        formal=(
            'Address the reader with the polite German "Sie" (capitalised, with "Ihnen" and '
            'the possessive "Ihr") and the matching verb forms. Never use "du"/"ihr".'
        ),
    ),
    "nl": AddressForms(
        informal=(
            'Address the reader with the informal Dutch "je"/"jij" (possessive "je"/"jouw"). '
            'Never use the polite "u"/"uw".'
        ),
        formal=(
            'Address the reader with the polite Dutch "u" (possessive "uw"). '
            'Never use "je"/"jij".'
        ),
    ),
    "fr": AddressForms(
        informal=(
            'Address the reader with the informal French "tu" and second-person singular verb '
            'forms (possessives "ton"/"ta"/"tes"). Never use "vous" as a polite singular.'
        ),
        formal=(
            'Address the reader with the polite French "vous" and second-person plural verb '
            'forms (possessives "votre"/"vos"). Never use "tu".'
        ),
    ),
    "it": AddressForms(
        informal=(
            'Address the reader with the informal Italian "tu" and second-person singular verb '
            'forms (imperatives like "Inizia"). Never use the courtesy "Lei".'
        ),
        formal=(
            'Address the reader with the courtesy Italian "Lei" and third-person singular verb '
            'forms (imperatives like "Inizi"). Never use "tu".'
        ),
    ),
    "es": AddressForms(
        informal=(
            'Address the reader with the informal Spanish "tú" and second-person singular verb '
            'forms (imperatives like "Empieza", possessive "tu"). Never use "usted".'
        ),
        formal=(
            'Address the reader with the polite Spanish "usted" and third-person singular verb '
            'forms (imperatives like "Empiece", possessive "su"). Never use "tú".'
        ),
    ),
    # European Portuguese: "tu" is the familiar form, "você" already reads as distant.
    "pt": AddressForms(
        informal=(
            'Address the reader with the informal European Portuguese "tu" and second-person '
            'singular verb forms (imperatives like "Começa", possessives "teu"/"tua"). '
            'Never use "você" or "o(a) senhor(a)".'
        ),
        formal=(
            'Address the reader with the polite European Portuguese "você" (or "o(a) '
            'senhor(a)") and third-person singular verb forms (possessives "seu"/"sua"). '
            'Never use "tu".'
        ),
    ),
    # Brazilian Portuguese: "você" IS the everyday register; "tu" would sound wrong.
    "pt-BR": AddressForms(
        informal=(
            'Address the reader with the everyday Brazilian Portuguese "você" and third-person '
            'singular verb forms (possessives "seu"/"sua"). Never use the deferential '
            '"o(a) senhor(a)".'
        ),
        formal=(
            'Address the reader with the deferential Brazilian Portuguese "o(a) senhor(a)" and '
            'third-person singular verb forms. Avoid the casual "você".'
        ),
    ),
    "ru": AddressForms(
        informal=(
            "Address the reader with the informal Russian «ты» and second-person singular verb "
            "forms. Never use «вы»/«Вы» as a polite singular."
        ),
        formal=(
            "Address the reader with the polite Russian «вы» and second-person plural verb "
            "forms. Never use «ты»."
        ),
    ),
    "uk": AddressForms(
        informal=(
            "Address the reader with the informal Ukrainian «ти» and second-person singular "
            "verb forms. Never use «ви» as a polite singular."
        ),
        formal=(
            "Address the reader with the polite Ukrainian «ви» and second-person plural verb "
            "forms. Never use «ти»."
        ),
    ),
    "pl": AddressForms(
        informal=(
            'Address the reader with the informal Polish "ty" and second-person singular verb '
            'forms (imperatives like "Zacznij"). Never use the honorific "Pan"/"Pani".'
        ),
        formal=(
            'Address the reader with the honorific Polish "Pan"/"Pani" and third-person verb '
            'forms (or impersonal phrasing). Never use "ty".'
        ),
    ),
    "cs": AddressForms(
        informal=(
            'Use Czech tykání: the informal "ty" with second-person singular verb forms. '
            'Never use vykání ("vy").'
        ),
        formal=(
            'Use Czech vykání: the polite "vy" with second-person plural verb forms. '
            'Never use tykání ("ty").'
        ),
    ),
    "sk": AddressForms(
        informal=(
            'Use Slovak tykanie: the informal "ty" with second-person singular verb forms. '
            'Never use vykanie ("vy").'
        ),
        formal=(
            'Use Slovak vykanie: the polite "vy" with second-person plural verb forms. '
            'Never use tykanie ("ty").'
        ),
    ),
    "sl": AddressForms(
        informal=(
            'Address the reader with the informal Slovene "ti" and second-person singular verb '
            'forms. Never use the polite "vi".'
        ),
        formal=(
            'Address the reader with the polite Slovene "vi" and second-person plural verb '
            'forms. Never use "ti".'
        ),
    ),
    "hr": AddressForms(
        informal=(
            'Address the reader with the informal Croatian "ti" and second-person singular verb '
            'forms. Never use the polite "Vi".'
        ),
        formal=(
            'Address the reader with the polite Croatian "Vi" and second-person plural verb '
            'forms. Never use "ti".'
        ),
    ),
    "sr": AddressForms(
        informal=(
            'Address the reader with the informal Serbian "ti" and second-person singular verb '
            'forms. Never use the polite "Vi".'
        ),
        formal=(
            'Address the reader with the polite Serbian "Vi" and second-person plural verb '
            'forms. Never use "ti".'
        ),
    ),
    "bg": AddressForms(
        informal=(
            "Address the reader with the informal Bulgarian «ти» and second-person singular "
            "verb forms. Never use the polite «Вие»."
        ),
        formal=(
            "Address the reader with the polite Bulgarian «Вие» and second-person plural verb "
            "forms. Never use «ти»."
        ),
    ),
    "ro": AddressForms(
        informal=(
            'Address the reader with the informal Romanian "tu" and second-person singular verb '
            'forms. Never use "dumneavoastră".'
        ),
        formal=(
            'Address the reader with the polite Romanian "dumneavoastră" and second-person '
            'plural verb forms. Never use "tu".'
        ),
    ),
    "el": AddressForms(
        informal=(
            'Address the reader with the informal Greek singular "εσύ" and second-person '
            'singular verb forms. Never use the plural of politeness "εσείς".'
        ),
        formal=(
            'Address the reader with the polite Greek plural "εσείς" and second-person plural '
            'verb forms. Never use the singular "εσύ".'
        ),
    ),
    "tr": AddressForms(
        informal=(
            'Address the reader with the informal Turkish "sen" and second-person singular verb '
            'endings (imperatives like "Başla"). Never use the polite "siz".'
        ),
        formal=(
            'Address the reader with the polite Turkish "siz" and second-person plural verb '
            'endings (imperatives like "Başlayın"). Never use "sen".'
        ),
    ),
    "fi": AddressForms(
        informal=(
            'Address the reader with the informal Finnish "sinä" (sinuttelu, second-person '
            'singular). Never use the polite plural "te".'
        ),
        formal=(
            'Address the reader with the polite Finnish "te" (teitittely, second-person '
            'plural). Never use "sinä".'
        ),
    ),
    # Scandinavian: the polite pronouns are archaic, so "formal" means tone, not pronoun.
    "sv": AddressForms(
        informal=(
            'Address the reader with the standard Swedish "du" — the normal register for apps '
            'and websites. Never use the archaic polite "ni".'
        ),
        formal=(
            'Use a polite, professional Swedish register, but keep "du" as the pronoun: the '
            'archaic "ni" as a polite singular sounds dated and must not be used.'
        ),
    ),
    "da": AddressForms(
        informal=(
            'Address the reader with the standard Danish "du" — the normal register for apps '
            'and websites. Never use the archaic polite "De".'
        ),
        formal=(
            'Use a polite, professional Danish register, but keep "du" as the pronoun: the '
            'archaic "De" must not be used.'
        ),
    ),
    "no": AddressForms(
        informal=(
            'Address the reader with the standard Norwegian "du" — the normal register for apps '
            'and websites. Never use the archaic polite "De".'
        ),
        formal=(
            'Use a polite, professional Norwegian register, but keep "du" as the pronoun: the '
            'archaic "De" must not be used.'
        ),
    ),
    "nb": AddressForms(
        informal=(
            'Address the reader with the standard Norwegian Bokmål "du" — the normal register '
            'for apps and websites. Never use the archaic polite "De".'
        ),
        formal=(
            'Use a polite, professional Norwegian Bokmål register, but keep "du" as the '
            'pronoun: the archaic "De" must not be used.'
        ),
    ),
    "ja": AddressForms(
        informal=(
            "Write in the friendly Japanese です・ます style. Avoid heavy 敬語 "
            "(でございます, お客様) and also avoid the blunt plain form (だ・である)."
        ),
        formal=(
            "Write in the formal Japanese 敬語 register (でございます, お客様, いたします). "
            "Avoid casual phrasing."
        ),
    ),
    "ko": AddressForms(
        informal=(
            "Write in the friendly Korean 해요체 (…해요/…하세요). Never use 반말, and avoid the "
            "stiff 합쇼체."
        ),
        formal=("Write in the formal Korean 합쇼체 (…합니다/…하십시오). Avoid the casual 해요체."),
    ),
    "zh": AddressForms(
        informal="Address the reader with the informal Chinese 你. Never use the honorific 您.",
        formal="Address the reader with the honorific Chinese 您. Never use 你 for the reader.",
    ),
    "vi": AddressForms(
        informal=(
            'Address the reader with the informal Vietnamese "bạn". Never use "quý khách" or '
            '"Quý vị".'
        ),
        formal=(
            'Address the reader with the polite Vietnamese "quý khách" (or "Quý vị"). '
            'Avoid the casual "bạn".'
        ),
    ),
    "id": AddressForms(
        informal=(
            'Address the reader with the informal Indonesian "kamu". Never use the formal '
            '"Anda".'
        ),
        formal='Address the reader with the formal Indonesian "Anda". Never use "kamu".',
    ),
    "ms": AddressForms(
        informal=(
            'Address the reader with the informal Malay "kamu"/"awak". Never use the formal '
            '"anda".'
        ),
        formal='Address the reader with the formal Malay "anda". Avoid "kamu"/"awak".',
    ),
}

# Used for languages without a grammaticalised T–V distinction (English, Hebrew…),
# where the setting still says something useful about tone.
_GENERIC_FORMS = AddressForms(
    informal=(
        "Use a warm, casual, conversational register — the way a modern consumer app talks to "
        "a friend — while staying clear and grammatical."
    ),
    formal="Use a polite, professional, respectful register suited to a business audience.",
)


def normalize_formality(value: str | None) -> str:
    """Normalize a formality setting to ``auto``/``formal``/``informal``.

    Accepts the pronoun spellings people reach for first (``du``, ``tu``,
    ``vous``, ``usted``…).

    Raises:
        ValueError: if the value is not a recognized formality setting.
    """
    if value is None:
        return FORMALITY_AUTO

    key = value.strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]

    valid = ", ".join(VALID_FORMALITY)
    raise ValueError(f"Invalid formality '{value}'. Valid values: {valid}")


def resolve_translator_formality(translator: object) -> str:
    """Read the formality setting off a translator, falling back to ``auto``.

    Translator implementations other than the built-in adapter may not carry the
    attribute at all, and use cases must not fail on that.
    """
    value = getattr(translator, "formality", FORMALITY_AUTO)
    if not isinstance(value, str):
        return FORMALITY_AUTO
    try:
        return normalize_formality(value)
    except ValueError:
        return FORMALITY_AUTO


def get_address_forms(lang: str) -> AddressForms | None:
    """Return the T–V forms for a language, or ``None`` if it has no distinction.

    Region-specific entries win over the base language, so ``pt-BR`` does not
    inherit the European Portuguese ``tu``.
    """
    code = normalize_language_code(lang)

    if code in _ADDRESS_FORMS:
        return _ADDRESS_FORMS[code]

    base = code.split("-")[0]
    return _ADDRESS_FORMS.get(base)


def supports_formality(lang: str) -> bool:
    """Check whether a language distinguishes familiar and polite address."""
    return get_address_forms(lang) is not None


def build_formality_directive(target_lang: str, formality: str | None) -> str:
    """Build the prompt block pinning the form of address for ``target_lang``.

    Returns an empty string for ``auto``, which leaves the register to the model
    (the behaviour before this setting existed).
    """
    mode = normalize_formality(formality)
    if mode == FORMALITY_AUTO:
        return ""

    forms = get_address_forms(target_lang) or _GENERIC_FORMS
    rule = forms.informal if mode == FORMALITY_INFORMAL else forms.formal

    return (
        "FORM OF ADDRESS (MANDATORY — overrides the register of the source text):\n"
        f"- {rule}\n"
        "- Keep this register in EVERY string: buttons, titles, alerts, errors and help text.\n"
        "- The source language may not mark this distinction at all — that is not a reason to "
        "fall back to the other register.\n"
        "- If a sentence would sound unnatural, rephrase it impersonally rather than switching "
        "register."
    )
