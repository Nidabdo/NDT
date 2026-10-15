"""Équivalents Windows des fonctions AutoIt Ping, RunAs, DriveMapAdd et _AD_Open (via ctypes)."""

import ctypes
import socket
import winreg

import annuaire
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
_mpr = ctypes.WinDLL("mpr", use_last_error=True)

_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def _erreur(code: int) -> OSError:
    return OSError(code, ctypes.FormatError(code).strip())


# --- Ping (IcmpSendEcho : pas besoin des droits admin, contrairement aux sockets raw) ---

class _IP_OPTION_INFORMATION(ctypes.Structure):
    _fields_ = [("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte),
                ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]


class _ICMP_ECHO_REPLY(ctypes.Structure):
    _fields_ = [("Address", wintypes.ULONG), ("Status", wintypes.ULONG),
                ("RoundTripTime", wintypes.ULONG), ("DataSize", wintypes.USHORT),
                ("Reserved", wintypes.USHORT), ("Data", ctypes.c_void_p),
                ("Options", _IP_OPTION_INFORMATION)]


_iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
_iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
_iphlpapi.IcmpSendEcho.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.WORD,
                                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
_iphlpapi.IcmpSendEcho.restype = wintypes.DWORD


def ping(hote: str, timeout_ms: int = 250) -> int | None:
    """Temps de réponse en ms, ou None si l'hôte ne répond pas (ou n'est pas résolu)."""
    try:
        ip = socket.getaddrinfo(hote, None, socket.AF_INET)[0][4][0]
    except OSError:
        return None

    adresse = int.from_bytes(socket.inet_aton(ip), "little")  # ordre réseau dans un ULONG
    donnees = b"CSTools2"
    reponse = ctypes.create_string_buffer(ctypes.sizeof(_ICMP_ECHO_REPLY) + len(donnees) + 64)

    handle = _iphlpapi.IcmpCreateFile()
    try:
        n = _iphlpapi.IcmpSendEcho(handle, adresse, donnees, len(donnees), None,
                                   reponse, len(reponse), timeout_ms)
    finally:
        _iphlpapi.IcmpCloseHandle(handle)

    if n == 0:
        return None
    echo = _ICMP_ECHO_REPLY.from_buffer(reponse)
    return echo.RoundTripTime if echo.Status == 0 else None


# --- Vérification des identifiants (remplace _AD_Open($user, $password)) ---

_advapi32.LogonUserW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]


def _logon(utilisateur: str, domaine: str, mot_de_passe: str) -> wintypes.HANDLE:
    LOGON32_LOGON_NETWORK, LOGON32_PROVIDER_DEFAULT = 3, 0
    jeton = wintypes.HANDLE()
    if not _advapi32.LogonUserW(utilisateur, domaine, mot_de_passe, LOGON32_LOGON_NETWORK,
                                LOGON32_PROVIDER_DEFAULT, ctypes.byref(jeton)):
        raise _erreur(ctypes.get_last_error())
    return jeton


def verifier_identifiants(utilisateur: str, domaine: str, mot_de_passe: str) -> None:
    """Lève OSError si le contrôleur de domaine refuse les identifiants."""
    ouvrir_session(utilisateur, domaine, mot_de_passe)


# --- Groupes du compte (remplace _AD_IsMemberOf) ---

class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


_advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                          wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
_advapi32.LookupAccountSidW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, wintypes.LPWSTR,
                                        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
                                        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_int)]


def _groupes_du_jeton(jeton: wintypes.HANDLE) -> list[str]:
    TOKEN_GROUPS_CLASSE, SE_GROUP_LOGON_ID = 2, 0xC0000000
    taille = wintypes.DWORD()
    _advapi32.GetTokenInformation(jeton, TOKEN_GROUPS_CLASSE, None, 0, ctypes.byref(taille))
    tampon = ctypes.create_string_buffer(taille.value)
    if not _advapi32.GetTokenInformation(jeton, TOKEN_GROUPS_CLASSE, tampon, taille, ctypes.byref(taille)):
        raise _erreur(ctypes.get_last_error())
    # TOKEN_GROUPS : un DWORD (nombre), puis le tableau aligné de SID_AND_ATTRIBUTES.
    nombre = wintypes.DWORD.from_buffer(tampon).value
    decalage = ctypes.alignment(_SID_AND_ATTRIBUTES)
    entrees = (_SID_AND_ATTRIBUTES * nombre).from_buffer(tampon, decalage)
    groupes = []
    for entree in entrees:
        if entree.Attributes & SE_GROUP_LOGON_ID == SE_GROUP_LOGON_ID:
            continue
        nom, domaine = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
        t_nom, t_domaine, usage = wintypes.DWORD(256), wintypes.DWORD(256), ctypes.c_int()
        if _advapi32.LookupAccountSidW(None, entree.Sid, nom, ctypes.byref(t_nom), domaine,
                                       ctypes.byref(t_domaine), ctypes.byref(usage)):
            groupes.append(nom.value)   # SID inconnu (groupe supprimé...) : ignoré
    return groupes


def ouvrir_session(utilisateur: str, domaine: str, mot_de_passe: str) -> list[str]:
    """Vérifie le compte et renvoie ses groupes de sécurité, imbrications comprises.

    Le compte est vérifié par l'annuaire (LDAP), sans ouvrir de session sur ce poste :
    un compte vert fonctionne donc depuis un poste blanc et inversement. Si aucun
    contrôleur ne répond en LDAP, on se rabat sur une ouverture de session locale.
    Un refus du mot de passe n'est jamais retenté (verrouillage du compte).
    """
    try:
        return annuaire.groupes_du_compte(utilisateur, domaine, mot_de_passe)
    except annuaire.AnnuaireInjoignable:
        pass
    jeton = _logon(utilisateur, domaine, mot_de_passe)
    try:
        return _groupes_du_jeton(jeton)
    finally:
        _kernel32.CloseHandle(jeton)


# --- RunAs ---

class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


_advapi32.CreateProcessWithLogonW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR,
    wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.POINTER(_STARTUPINFOW), ctypes.POINTER(_PROCESS_INFORMATION)]


_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


def run_as(utilisateur: str, domaine: str, mot_de_passe: str, ligne_commande: str, *,
           masque: bool = False, attendre: bool = False,
           dossier: str = r"C:\Windows\System32") -> int:
    """Équivalent de « runas /netonly » : le programme tourne sous la session Windows du poste,
    mais présente le compte donné aux machines distantes (PMAD, sc \\\\poste...).

    Aucune session n'est ouverte localement avec ce compte : un compte vert fonctionne
    donc depuis un poste blanc et inversement.
    Retourne le PID, ou le code de sortie du processus si `attendre` est vrai.
    """
    LOGON_NETCREDENTIALS_ONLY = 2
    STARTF_USESHOWWINDOW, SW_HIDE, CREATE_NO_WINDOW = 0x1, 0, 0x08000000
    INFINITE = 0xFFFFFFFF
    si = _STARTUPINFOW(cb=ctypes.sizeof(_STARTUPINFOW))
    if masque:
        si.dwFlags, si.wShowWindow = STARTF_USESHOWWINDOW, SW_HIDE
    pi = _PROCESS_INFORMATION()
    commande = ctypes.create_unicode_buffer(ligne_commande)  # doit être modifiable
    if not _advapi32.CreateProcessWithLogonW(utilisateur, domaine, mot_de_passe, LOGON_NETCREDENTIALS_ONLY,
                                             None, commande, CREATE_NO_WINDOW if masque else 0,
                                             None, dossier, ctypes.byref(si), ctypes.byref(pi)):
        raise _erreur(ctypes.get_last_error())
    try:
        if not attendre:
            return pi.dwProcessId
        _kernel32.WaitForSingleObject(pi.hProcess, INFINITE)
        code = wintypes.DWORD()
        _kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
        return code.value
    finally:
        _kernel32.CloseHandle(pi.hThread)
        _kernel32.CloseHandle(pi.hProcess)


# --- Connexion à un partage administratif (remplace DriveMapAdd) ---

class _NETRESOURCEW(ctypes.Structure):
    _fields_ = [("dwScope", wintypes.DWORD), ("dwType", wintypes.DWORD),
                ("dwDisplayType", wintypes.DWORD), ("dwUsage", wintypes.DWORD),
                ("lpLocalName", wintypes.LPWSTR), ("lpRemoteName", wintypes.LPWSTR),
                ("lpComment", wintypes.LPWSTR), ("lpProvider", wintypes.LPWSTR)]


_mpr.WNetAddConnection2W.argtypes = [ctypes.POINTER(_NETRESOURCEW), wintypes.LPCWSTR,
                                     wintypes.LPCWSTR, wintypes.DWORD]
_mpr.WNetAddConnection2W.restype = wintypes.DWORD


def connecter_partage(unc: str, utilisateur: str, domaine: str, mot_de_passe: str) -> None:
    """Ouvre une connexion sans lettre de lecteur vers `unc` avec le compte donné.

    Une connexion déjà ouverte vers ce serveur (erreur 1219) n'est pas une erreur :
    l'appelant vérifie ensuite que le chemin est accessible.
    """
    RESOURCETYPE_DISK, CONNECT_TEMPORARY = 1, 4
    ERROR_SESSION_CREDENTIAL_CONFLICT = 1219
    ressource = _NETRESOURCEW(dwType=RESOURCETYPE_DISK, lpRemoteName=unc)
    code = _mpr.WNetAddConnection2W(ctypes.byref(ressource), mot_de_passe,
                                    f"{domaine}\\{utilisateur}", CONNECT_TEMPORARY)
    if code not in (0, ERROR_SESSION_CREDENTIAL_CONFLICT):
        raise _erreur(code)


# --- Couleur d'accent Windows (remplace ReloadAccent) ---

def couleur_accent(defaut: str = "#0063B1") -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as cle:
            abgr, _ = winreg.QueryValueEx(cle, "AccentColor")
    except OSError:
        return defaut
    return f"#{abgr & 0xFF:02X}{(abgr >> 8) & 0xFF:02X}{(abgr >> 16) & 0xFF:02X}"
