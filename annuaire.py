"""Authentification et groupes d'un compte directement auprès de l'Active Directory (LDAP).

Contrairement à LogonUser, aucune session n'est ouverte sur le poste local : un compte vert
(A-xxxx) peut donc être vérifié depuis un poste blanc, et inversement, même si la stratégie
du poste interdit à ce compte de s'y connecter.
"""
import ctypes
import re
from ctypes import wintypes

_ldap = ctypes.WinDLL("wldap32", use_last_error=True)

LDAP_PORT = 389
LDAP_SCOPE_BASE, LDAP_SCOPE_SUBTREE = 0, 2
LDAP_AUTH_NEGOTIATE = 0x0486   # Kerberos ou NTLM, mot de passe jamais envoyé en clair
LDAP_OPT_REFERRALS, LDAP_OPT_PROTOCOL_VERSION = 0x08, 0x11
LDAP_OPT_SERVER_ERROR, LDAP_OPT_SIGN, LDAP_OPT_ENCRYPT = 0x33, 0x95, 0x96
LDAP_SUCCESS, LDAP_INVALID_CREDENTIALS = 0x00, 0x31
SEC_WINNT_AUTH_IDENTITY_UNICODE = 2

# Code « data » renvoyé par le contrôleur de domaine -> code d'erreur Windows équivalent.
CODES_AD = {
    0x52E: 1326,   # identifiant ou mot de passe incorrect
    0x525: 1326,   # compte inconnu (présenté comme un mauvais mot de passe)
    0x775: 1909,   # compte verrouillé
    0x532: 1330,   # mot de passe expiré
    0x773: 1907,   # mot de passe à changer
    0x533: 1331,   # compte désactivé
    0x701: 1793,   # compte expiré
    0x530: 1328,   # hors des heures autorisées
    0x531: 1329,   # poste non autorisé pour ce compte
}


class AnnuaireInjoignable(OSError):
    """Pas de contrôleur de domaine joignable en LDAP : l'appelant peut tenter une autre méthode."""


class _Identite(ctypes.Structure):   # SEC_WINNT_AUTH_IDENTITY_W
    _fields_ = [("User", wintypes.LPWSTR), ("UserLength", wintypes.ULONG),
                ("Domain", wintypes.LPWSTR), ("DomainLength", wintypes.ULONG),
                ("Password", wintypes.LPWSTR), ("PasswordLength", wintypes.ULONG),
                ("Flags", wintypes.ULONG)]


class _Berval(ctypes.Structure):
    _fields_ = [("bv_len", wintypes.ULONG), ("bv_val", ctypes.c_void_p)]


class _Delai(ctypes.Structure):     # l_timeval
    _fields_ = [("tv_sec", wintypes.LONG), ("tv_usec", wintypes.LONG)]


_p = ctypes.c_void_p
_ldap.ldap_initW.argtypes = [wintypes.LPCWSTR, wintypes.ULONG]
_ldap.ldap_initW.restype = _p
_ldap.ldap_set_optionW.argtypes = [_p, ctypes.c_int, _p]
_ldap.ldap_get_optionW.argtypes = [_p, ctypes.c_int, _p]
_ldap.ldap_connect.argtypes = [_p, ctypes.POINTER(_Delai)]
_ldap.ldap_connect.restype = wintypes.ULONG
_ldap.ldap_bind_sW.argtypes = [_p, wintypes.LPCWSTR, _p, wintypes.ULONG]
_ldap.ldap_bind_sW.restype = wintypes.ULONG
_ldap.ldap_search_sW.argtypes = [_p, wintypes.LPCWSTR, wintypes.ULONG, wintypes.LPCWSTR,
                                 ctypes.POINTER(wintypes.LPWSTR), wintypes.ULONG, ctypes.POINTER(_p)]
_ldap.ldap_search_sW.restype = wintypes.ULONG
_ldap.ldap_first_entry.argtypes = [_p, _p]
_ldap.ldap_first_entry.restype = _p
_ldap.ldap_get_valuesW.argtypes = [_p, _p, wintypes.LPCWSTR]
_ldap.ldap_get_valuesW.restype = ctypes.POINTER(wintypes.LPWSTR)
_ldap.ldap_value_freeW.argtypes = [ctypes.POINTER(wintypes.LPWSTR)]
_ldap.ldap_get_values_lenW.argtypes = [_p, _p, wintypes.LPCWSTR]
_ldap.ldap_get_values_lenW.restype = ctypes.POINTER(ctypes.POINTER(_Berval))
_ldap.ldap_value_free_len.argtypes = [ctypes.POINTER(ctypes.POINTER(_Berval))]
_ldap.ldap_get_dnW.argtypes = [_p, _p]
_ldap.ldap_get_dnW.restype = _p
_ldap.ldap_memfreeW.argtypes = [_p]
_ldap.ldap_msgfree.argtypes = [_p]
_ldap.ldap_unbind.argtypes = [_p]
_ldap.LdapMapErrorToWin32.argtypes = [wintypes.ULONG]
_ldap.LdapMapErrorToWin32.restype = wintypes.ULONG

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_advapi32.LookupAccountSidW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPWSTR,
                                        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
                                        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_int)]


# ---------- Fonctions pures (testables hors domaine) ----------
def echapper_filtre(valeur):
    """Échappe une valeur pour un filtre LDAP (RFC 4515)."""
    return "".join(f"\\{ord(c):02x}" if c in "\\*()\0" else c for c in valeur)


def code_depuis_erreur_serveur(message):
    """« 80090308: LdapErr: ... data 52e, v4563 » -> 1326 (code Windows), sinon None."""
    trouve = re.search(r"\bdata ([0-9a-fA-F]+)", message or "")
    return CODES_AD.get(int(trouve.group(1), 16)) if trouve else None


def sid_en_texte(octets):
    """SID binaire -> « S-1-5-21-... » (pour les messages et les tests)."""
    if len(octets) < 8:
        return ""
    autorite = int.from_bytes(octets[2:8], "big")
    sous = [int.from_bytes(octets[8 + 4 * i:12 + 4 * i], "little") for i in range(octets[1])]
    return "S-" + "-".join(str(n) for n in [octets[0], autorite, *sous])


# ---------- Appels LDAP ----------
def _erreur(code_ldap, ld=None):
    detail = ""
    if ld:
        message = ctypes.c_void_p()
        if _ldap.ldap_get_optionW(ld, LDAP_OPT_SERVER_ERROR, ctypes.byref(message)) == LDAP_SUCCESS and message.value:
            detail = ctypes.wstring_at(message.value)
            _ldap.ldap_memfreeW(message)
    code = code_depuis_erreur_serveur(detail) or _ldap.LdapMapErrorToWin32(code_ldap)
    return OSError(code, ctypes.FormatError(code).strip() + (f" ({detail})" if detail else ""))


def _rechercher(ld, base, portee, filtre, attribut):
    attributs = (wintypes.LPWSTR * 2)(attribut, None)
    resultat = ctypes.c_void_p()
    code = _ldap.ldap_search_sW(ld, base, portee, filtre, attributs, 0, ctypes.byref(resultat))
    if code != LDAP_SUCCESS:
        if resultat:
            _ldap.ldap_msgfree(resultat)
        raise _erreur(code, ld)
    return resultat


def _valeur_texte(ld, resultat, attribut):
    entree = _ldap.ldap_first_entry(ld, resultat)
    if not entree:
        return None
    valeurs = _ldap.ldap_get_valuesW(ld, entree, attribut)
    if not valeurs:
        return None
    try:
        return valeurs[0]
    finally:
        _ldap.ldap_value_freeW(valeurs)


def _nom_du_sid(octets):
    tampon_sid = ctypes.create_string_buffer(octets, len(octets))
    nom, domaine = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
    t_nom, t_domaine, usage = wintypes.DWORD(256), wintypes.DWORD(256), ctypes.c_int()
    if _advapi32.LookupAccountSidW(None, tampon_sid, nom, ctypes.byref(t_nom), domaine,
                                   ctypes.byref(t_domaine), ctypes.byref(usage)):
        return nom.value
    return None   # SID orphelin (groupe supprimé) : ignoré


def groupes_du_compte(utilisateur, domaine, mot_de_passe, delai=10):
    """Vérifie le compte auprès d'un contrôleur de domaine et renvoie ses groupes de sécurité.

    Lève OSError (code Windows : 1326 mauvais mot de passe, 1909 verrouillé...) si le compte
    est refusé, ou AnnuaireInjoignable si aucun contrôleur ne répond en LDAP.
    """
    ld = None
    for hote in (None, domaine):   # None : contrôleur du domaine du poste
        ld = _ldap.ldap_initW(hote, LDAP_PORT)
        if not ld:
            continue
        version = ctypes.c_ulong(3)
        _ldap.ldap_set_optionW(ld, LDAP_OPT_PROTOCOL_VERSION, ctypes.byref(version))
        _ldap.ldap_set_optionW(ld, LDAP_OPT_REFERRALS, None)
        for option in (LDAP_OPT_SIGN, LDAP_OPT_ENCRYPT):   # échanges signés et chiffrés
            _ldap.ldap_set_optionW(ld, option, ctypes.c_void_p(1))
        if _ldap.ldap_connect(ld, ctypes.byref(_Delai(delai, 0))) == LDAP_SUCCESS:
            break
        _ldap.ldap_unbind(ld)
        ld = None
    if not ld:
        raise AnnuaireInjoignable(1311, "Aucun contrôleur de domaine joignable en LDAP.")

    try:
        identite = _Identite(utilisateur, len(utilisateur), domaine, len(domaine),
                             mot_de_passe, len(mot_de_passe), SEC_WINNT_AUTH_IDENTITY_UNICODE)
        code = _ldap.ldap_bind_sW(ld, None, ctypes.byref(identite), LDAP_AUTH_NEGOTIATE)
        if code != LDAP_SUCCESS:
            erreur = _erreur(code, ld)
            if code == LDAP_INVALID_CREDENTIALS or erreur.errno in CODES_AD.values():
                raise erreur
            raise AnnuaireInjoignable(erreur.errno, erreur.strerror)

        racine = _rechercher(ld, "", LDAP_SCOPE_BASE, "(objectClass=*)", "defaultNamingContext")
        try:
            base = _valeur_texte(ld, racine, "defaultNamingContext")
        finally:
            _ldap.ldap_msgfree(racine)
        compte = _rechercher(ld, base, LDAP_SCOPE_SUBTREE,
                             f"(&(objectCategory=person)(sAMAccountName={echapper_filtre(utilisateur)}))",
                             "distinguishedName")
        try:
            entree = _ldap.ldap_first_entry(ld, compte)
            if not entree:
                raise OSError(1326, "Compte introuvable dans l'annuaire.")
            pointeur_dn = _ldap.ldap_get_dnW(ld, entree)
            dn = ctypes.wstring_at(pointeur_dn)
            _ldap.ldap_memfreeW(pointeur_dn)
        finally:
            _ldap.ldap_msgfree(compte)

        # tokenGroups : tous les groupes de sécurité du compte, imbrications comprises.
        jetons = _rechercher(ld, dn, LDAP_SCOPE_BASE, "(objectClass=*)", "tokenGroups")
        try:
            entree = _ldap.ldap_first_entry(ld, jetons)
            valeurs = _ldap.ldap_get_values_lenW(ld, entree, "tokenGroups") if entree else None
            groupes = []
            if valeurs:
                try:
                    i = 0
                    while valeurs[i]:
                        berval = valeurs[i].contents
                        nom = _nom_du_sid(ctypes.string_at(berval.bv_val, berval.bv_len))
                        if nom:
                            groupes.append(nom)
                        i += 1
                finally:
                    _ldap.ldap_value_free_len(valeurs)
        finally:
            _ldap.ldap_msgfree(jetons)
        return groupes
    finally:
        _ldap.ldap_unbind(ld)
