"""Droits d'accès : quels écrans une session peut voir. La configuration est dans acces.py."""
from dataclasses import dataclass, field

import acces

ECRANS = ("accueil", "diagnostic", "documentation", "outils", "scripts", "coordination")
# Droits qui ne sont pas des écrans : ils débloquent une action dans un écran.
DROITS = ("scripts_edition",)
# Clés de navigation de l'application -> écran de acces.py
ECRAN_PAR_CLE = {"home": "accueil", "question": "diagnostic", "documentation": "documentation",
                 "outils": "outils", "scripts": "scripts", "admin": "coordination"}


class ConfigInvalide(ValueError):
    """acces.py contient une erreur ; le message indique quoi corriger."""


@dataclass(frozen=True)
class Session:
    login: str
    domaine: str = ""
    mot_de_passe: str | None = field(default=None, repr=False)   # en mémoire uniquement
    groupes: tuple = ()
    ecrans: frozenset = frozenset()   # écrans et droits accordés
    profils: tuple = ()
    bypass: bool = False

    def autorise(self, cle):
        """`cle` : clé de navigation (« home »…), nom d'écran (« accueil »…) ou droit."""
        return ECRAN_PAR_CLE.get(cle, cle) in self.ecrans


def normaliser(nom):
    """Comparaison souple : casse et espaces ignorés, préfixe de domaine (INTRA\\) retiré."""
    texte = " ".join(str(nom).split())
    if "\\" in texte:
        texte = texte.split("\\", 1)[1]
    return texte.strip().casefold()


def verifier_config(config=acces):
    """Lève ConfigInvalide avec un message compréhensible si acces.py est mal rempli."""
    profils = getattr(config, "PROFILS", None)
    if not isinstance(profils, dict) or not profils:
        raise ConfigInvalide("PROFILS doit contenir au moins un profil.")
    for nom, ecrans in profils.items():
        if not isinstance(nom, str) or not isinstance(ecrans, (list, tuple)):
            raise ConfigInvalide(f"Dans PROFILS, la ligne {nom!r} est mal écrite : "
                                 'attendu "Nom": ["accueil", "diagnostic", ...],')
        for ecran in ecrans:
            if ecran not in ECRANS + DROITS:
                raise ConfigInvalide(f'Dans PROFILS, le profil "{nom}" contient {ecran!r}, '
                                     f"qui n'existe pas.\nÉcrans possibles : {', '.join(ECRANS)}.\n"
                                     f"Droits possibles : {', '.join(DROITS)}.")
    connus = ", ".join(profils)
    utilisateurs = getattr(config, "UTILISATEURS", None)
    if not isinstance(utilisateurs, dict):
        raise ConfigInvalide("UTILISATEURS doit être écrit entre accolades { }.")
    for qui, profil in utilisateurs.items():
        if not isinstance(qui, str) or not qui.strip():
            raise ConfigInvalide(f"Dans UTILISATEURS, la ligne {qui!r} n'a pas de groupe ni de login.")
        if profil not in profils:
            raise ConfigInvalide(f'Dans UTILISATEURS, la ligne "{qui}": {profil!r} utilise un profil '
                                 f"qui n'existe pas.\nProfils possibles : {connus}.")
    defaut = getattr(config, "PROFIL_PAR_DEFAUT", None)
    if defaut not in profils:
        raise ConfigInvalide(f"PROFIL_PAR_DEFAUT vaut {defaut!r}, qui n'est pas un profil.\n"
                             f"Profils possibles : {connus}.")
    if not isinstance(getattr(config, "AUTORISER_BYPASS", None), bool):
        raise ConfigInvalide("AUTORISER_BYPASS doit valoir True ou False.")


def ecrans_autorises(login, groupes, config=acces):
    """Écrans et profils d'un compte : union de toutes les lignes qui le concernent
    (login et groupes), ou le profil par défaut si aucune ne correspond."""
    noms = {normaliser(login)} | {normaliser(g) for g in groupes}
    profils = []
    for qui, profil in config.UTILISATEURS.items():
        if normaliser(qui) in noms and profil not in profils:
            profils.append(profil)
    if not profils:
        profils = [config.PROFIL_PAR_DEFAUT]
    ecrans = {"accueil"}
    for profil in profils:
        ecrans.update(config.PROFILS[profil])
    return frozenset(ecrans), tuple(profils)


def session_ad(login, domaine, mot_de_passe, groupes, config=acces):
    ecrans, profils = ecrans_autorises(login, groupes, config)
    return Session(login=login, domaine=domaine, mot_de_passe=mot_de_passe,
                   groupes=tuple(groupes), ecrans=ecrans, profils=profils)


def session_bypass():
    """Tous les écrans et tous les droits, sans compte AD (développement hors domaine)."""
    return Session(login="", ecrans=frozenset(ECRANS + DROITS), profils=("Bypass",), bypass=True)
