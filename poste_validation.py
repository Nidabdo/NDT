"""Portage de caractereAutorise() et HostNameSpaceFormat() de CSTools.au3."""

AIDE = (
    "Veuillez saisir un nom d'hôte ou une adresse IP !\n\n"
    "Caractères autorisés : A-Z, a-z, 0-9, « - » et « . »\n\n"
    "Un nom de poste ne comporte que des lettres, des chiffres et « - », "
    "et doit commencer par une lettre.\n"
    "Une adresse IP est de la forme _._._._ (nombres de 0 à 255)."
)


class SaisieInvalide(ValueError):
    pass


def _refus(detail: str) -> SaisieInvalide:
    return SaisieInvalide(f"{AIDE}\n\n{detail}")


def valider_hote(saisie: str) -> tuple[str, str]:
    """Nettoie et valide la saisie.

    Retourne (hôte, "NOM" | "IP"), ou lève SaisieInvalide avec le message à afficher.
    """
    hote = saisie.replace(" ", "")

    interdits = sorted({c for c in hote if not (c.isascii() and (c.isalnum() or c in ".-"))})
    if interdits:
        raise _refus("Contient un/des caractère(s) non autorisé(s) : " + " ".join(f'"{c}"' for c in interdits))

    lettres = sum(c.isalpha() for c in hote)
    chiffres = sum(c.isdigit() for c in hote)
    points = hote.count(".")
    tirets = hote.count("-")

    if lettres == 0 and chiffres >= 1 and points == 0 and tirets == 0:
        raise _refus(f"La valeur entrée est un nombre : {hote}")
    if lettres == 0 and chiffres == 0 and points >= 1:
        raise _refus("La valeur entrée contient un point sans chiffre ni lettre.")
    if lettres == 0 and chiffres == 0 and tirets >= 1:
        raise _refus("La valeur entrée contient un tiret sans chiffre ni lettre.")

    if points >= 1 and chiffres >= 1:
        blocs = hote.split(".")
        if len(blocs) != 4:
            raise _refus(f'Adresse IP invalide : doit être de la forme _._._._ : "{hote}"')
        for i, bloc in enumerate(blocs, 1):
            if not bloc.isdigit():
                raise _refus(f'Adresse IP invalide : le bloc {i} doit être un nombre : "{hote}"')
            if int(bloc) > 255:
                raise _refus(f'Adresse IP invalide : le bloc {i} doit être compris entre 0 et 255 : "{hote}"')
        return hote, "IP"

    if points >= 1:
        raise _refus(f'Nom de poste invalide : ne doit pas contenir de point "{hote}"')
    if lettres == 0:
        raise _refus(f'Nom de poste invalide : doit contenir des lettres "{hote}"')
    if not hote[0].isalpha():
        raise _refus(f'Nom de poste invalide : doit commencer par une lettre "{hote}"')
    return hote, "NOM"
