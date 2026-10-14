"""Équivalents Windows des fonctions AutoIt Ping, RunAs, DriveMapAdd et _AD_Open (via ctypes)."""

import ctypes
import socket
import winreg
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


def verifier_identifiants(utilisateur: str, domaine: str, mot_de_passe: str) -> None:
    """Lève OSError si le contrôleur de domaine refuse les identifiants."""
    LOGON32_LOGON_NETWORK, LOGON32_PROVIDER_DEFAULT = 3, 0
    jeton = wintypes.HANDLE()
    if not _advapi32.LogonUserW(utilisateur, domaine, mot_de_passe, LOGON32_LOGON_NETWORK,
                                LOGON32_PROVIDER_DEFAULT, ctypes.byref(jeton)):
        raise _erreur(ctypes.get_last_error())
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
    """Équivalent de RunAs / RunAsWait (avec profil).

    Retourne le PID, ou le code de sortie du processus si `attendre` est vrai.
    """
    LOGON_WITH_PROFILE = 1
    STARTF_USESHOWWINDOW, SW_HIDE, CREATE_NO_WINDOW = 0x1, 0, 0x08000000
    INFINITE = 0xFFFFFFFF
    si = _STARTUPINFOW(cb=ctypes.sizeof(_STARTUPINFOW))
    if masque:
        si.dwFlags, si.wShowWindow = STARTF_USESHOWWINDOW, SW_HIDE
    pi = _PROCESS_INFORMATION()
    commande = ctypes.create_unicode_buffer(ligne_commande)  # doit être modifiable
    if not _advapi32.CreateProcessWithLogonW(utilisateur, domaine, mot_de_passe, LOGON_WITH_PROFILE,
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
