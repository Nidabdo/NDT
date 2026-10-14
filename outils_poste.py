"""Outils poste repris de CS Tools 2 : PMAD (SCCM 2012 Remote Control), Ping, Bureau à distance, C$ / D$."""
import json
import os
import queue
import subprocess
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import ttk

import poste_winapi as winapi
from diagnostic_form import RoundedPanel, SearchBox
from poste_validation import SaisieInvalide, valider_hote

DOMAINE = "INTRA"
CMRC_VIEWER = (r"\\grewinshare02\dsl$\003-Applications SOGETI\Outils SD"
               r"\RemoteControl\SCCM 2012 Remote Control\RC Viewer 2012\CmRcViewer.exe")
OSCAR_DIAG = "https://gre-oscar-v2.intra.cea.fr/amdb/diag_poste?assettag={hote}"
NAVIGATEUR = "msedge"
PING_TIMEOUT_MS = 250
SUFFIXE_DOCK = "-DOCK"
NB_POSTES_RECENTS = 6
FICHIER_RECENTS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NDT" / "postes_recents.json"


class ActionImpossible(Exception):
    """Erreur à afficher telle quelle à l'utilisateur."""


def resoudre_cible(hote, genre):
    """Ping du poste et de son dock en parallèle ; le dock est prioritaire s'il répond."""
    if genre == "IP":
        return hote if winapi.ping(hote, PING_TIMEOUT_MS) is not None else None
    dock = hote + SUFFIXE_DOCK
    with ThreadPoolExecutor(2) as pool:
        r_hote, r_dock = pool.map(lambda h: winapi.ping(h, PING_TIMEOUT_MS), (hote, dock))
    if r_dock is not None:
        return dock
    if r_hote is not None:
        return hote
    return None


def charger_recents():
    try:
        return json.loads(FICHIER_RECENTS.read_text(encoding="utf-8"))[:NB_POSTES_RECENTS]
    except (OSError, ValueError):
        return []


def enregistrer_recents(recents):
    try:
        FICHIER_RECENTS.parent.mkdir(parents=True, exist_ok=True)
        FICHIER_RECENTS.write_text(json.dumps(recents), encoding="utf-8")
    except OSError:
        pass


# ----- Actions (exécutées en arrière-plan, sans toucher à l'interface) -----
def lancer_pmad(cible, compte):
    if not os.path.isfile(CMRC_VIEWER):
        raise ActionImpossible(f"Remote Control inaccessible :\n{CMRC_VIEWER}")
    utilisateur, mdp = compte
    winapi.run_as(utilisateur, DOMAINE, mdp, subprocess.list2cmdline([CMRC_VIEWER, cible]))
    return f"Prise en main lancée sur {cible} en tant que {utilisateur}."


def lancer_bad(cible, _compte):
    subprocess.Popen(["mstsc.exe", f"/v:{cible}"])
    return f"Bureau à distance lancé vers {cible}."


def ouvrir_partage(partage):
    def action(cible, compte):
        unc = rf"\\{cible}\{partage}"
        if not os.path.isdir(unc):
            utilisateur, mdp = compte
            winapi.connecter_partage(unc, utilisateur, DOMAINE, mdp)
            if not os.path.isdir(unc):
                raise ActionImpossible(f"Chemin inaccessible : {unc}")
        subprocess.Popen(["explorer.exe", unc])
        return f"{unc} ouvert."
    return action


def relancer_cmrc(hote, compte):
    utilisateur, mdp = compte
    for args in ("stop CmRcService", "config CmRcService start= delayed-auto", "start CmRcService"):
        winapi.run_as(utilisateur, DOMAINE, mdp, rf"sc.exe \\{hote} {args}", masque=True, attendre=True)
    return f"Service CmRcService redémarré sur {hote} en tant que {utilisateur}."


class OutilsPoste(ttk.Frame):
    """Écran « Outils poste ». Le compte blanc est gardé sur l'application (app.compte_poste),
    en mémoire uniquement, pour survivre aux changements d'écran."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._resultats = queue.Queue()
        self._en_cours = 0
        self.var_hote = tk.StringVar()
        self.var_statut = tk.StringVar(value="Saisissez un nom de poste ou une adresse IP.")
        self.var_compte = tk.StringVar()
        self.recents = charger_recents()

        ttk.Label(self, text="Poste ou adresse IP", style="Muted.TLabel").pack(anchor="w")
        self.recherche = SearchBox(self, app, self.var_hote)
        self.recherche.pack(fill="x", pady=(4, 6))
        for touche in ("<Return>", "<KP_Enter>"):
            self.recherche.entry.bind(touche, self._entree)
        self.ligne_recents = ttk.Frame(self)
        self.ligne_recents.pack(fill="x", pady=(0, 14))
        self._afficher_recents()

        panneau = RoundedPanel(self, app, padding=22)
        panneau.pack(fill="x")
        corps = panneau.body
        ttk.Label(corps, text="Actions sur le poste", style="Card.H2.TLabel").pack(anchor="w")
        ttk.Label(corps, text="Le poste et son dock (-DOCK) sont testés au ping avant chaque action.",
                  style="Card.Muted.TLabel").pack(anchor="w", pady=(4, 14))
        rangee = ttk.Frame(corps, style="Surface.TFrame")
        rangee.pack(anchor="w")
        for texte, commande, style in (
            ("Prise en main", self.pmad, "Card.Accent.TButton"),
            ("Ping", self.ping, "Card.TButton"),
            ("Bureau à distance", self.bad, "Card.TButton"),
            ("Ouvrir C$", lambda: self.partage("c$"), "Card.TButton"),
            ("Ouvrir D$", lambda: self.partage("d$"), "Card.TButton"),
        ):
            ttk.Button(rangee, text=texte, style=style, command=commande).pack(side="left", padx=(0, 8))
        ttk.Button(corps, text="Relancer le service de prise en main (CmRcService)",
                   style="Card.Ghost.TButton", command=self.relancer_service_pmad).pack(anchor="w", pady=(12, 0))

        panneau = RoundedPanel(self, app, padding=22)
        panneau.pack(fill="x", pady=(14, 0))
        corps = panneau.body
        ttk.Label(corps, text="Compte blanc", style="Card.H2.TLabel").pack(anchor="w")
        ttk.Label(corps, textvariable=self.var_compte, style="Card.Muted.TLabel").pack(anchor="w", pady=(4, 12))
        self.bouton_connexion = ttk.Button(corps, style="Card.TButton", command=self.basculer_connexion)
        self.bouton_connexion.pack(anchor="w")

        ttk.Label(self, textvariable=self.var_statut, style="Muted.TLabel").pack(anchor="w", pady=(14, 0))
        self._maj_compte()

    # ----- État -----
    @property
    def compte(self):
        return getattr(self.app, "compte_poste", None)

    def _maj_compte(self):
        if self.compte:
            self.var_compte.set(f"Connecté en tant que {DOMAINE}\\{self.compte[0]}. "
                                "Utilisé pour la prise en main, C$ / D$ et le service CmRcService.")
            self.bouton_connexion.configure(text="Se déconnecter")
        else:
            self.var_compte.set("Non connecté. Requis pour la prise en main, C$ / D$ et le service CmRcService.")
            self.bouton_connexion.configure(text="Se connecter")

    def _afficher_recents(self):
        for widget in self.ligne_recents.winfo_children():
            widget.destroy()
        if not self.recents:
            return
        ttk.Label(self.ligne_recents, text="Récents :", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        for hote in self.recents:
            ttk.Button(self.ligne_recents, text=hote, style="Ghost.TButton",
                       command=lambda h=hote: self._choisir(h)).pack(side="left", padx=(0, 4))

    def _choisir(self, hote):
        self.var_hote.set(hote)
        self.recherche.entry.focus_set()
        self.recherche.entry.icursor("end")

    def _ajouter_recent(self, hote):
        self.recents = ([hote] + [h for h in self.recents if h.upper() != hote.upper()])[:NB_POSTES_RECENTS]
        enregistrer_recents(self.recents)
        self._afficher_recents()

    # ----- Arrière-plan (la fenêtre reste réactive pendant les pings) -----
    def _en_arriere_plan(self, tache, fin):
        def travail():
            try:
                resultat = ("ok", tache())
            except ActionImpossible as e:
                resultat = ("erreur", str(e))
            except OSError as e:
                resultat = ("erreur", f"Erreur Windows : {e.strerror or e}")
            except Exception as e:  # noqa: BLE001 — afficher plutôt que perdre l'erreur
                resultat = ("erreur", repr(e))
            self._resultats.put((fin, resultat))

        self._en_cours += 1
        self.app.configure(cursor="watch")
        threading.Thread(target=travail, daemon=True).start()
        if self._en_cours == 1:
            self.app.after(50, self._depiler)

    def _depiler(self):
        try:
            while True:
                fin, (etat, valeur) = self._resultats.get_nowait()
                self._en_cours -= 1
                if not self._en_cours:
                    self.app.configure(cursor="")
                if etat == "erreur":
                    if self.winfo_exists():
                        self.var_statut.set("Erreur.")
                    self.app.error("Outils poste", valeur)
                elif self.winfo_exists():
                    fin(valeur)
        except queue.Empty:
            pass
        if self._en_cours:
            self.app.after(50, self._depiler)

    # ----- Saisie -----
    def _lire_hote(self):
        try:
            hote, genre = valider_hote(self.var_hote.get())
        except SaisieInvalide as e:
            self.app.error("Saisie invalide", str(e))
            return None
        self.var_hote.set(hote)
        return hote, genre

    def _compte_requis(self):
        if self.compte:
            return True
        if self.app.confirm("Compte blanc requis",
                            "Cette action utilise votre compte blanc. Vous connecter maintenant ?",
                            yes="Se connecter", no="Annuler"):
            self.connexion()
        return False

    def _entree(self, _event=None):
        if self.compte:
            self.pmad()
        else:
            self.ping()
        return "break"

    # ----- Actions -----
    def _action_distante(self, libelle, action, diag_oscar=True):
        lu = self._lire_hote()
        if not lu:
            return
        hote, genre = lu
        compte = self.compte
        self.var_statut.set(f"{libelle} : ping de {hote}…")

        def tache():
            cible = resoudre_cible(hote, genre)
            return None if cible is None else (cible, action(cible, compte))

        def fin(resultat):
            if resultat is None:
                self.var_statut.set(f"{hote} ne répond pas.")
                self.app.warn("Poste injoignable", "L'hôte et son dock ne répondent pas au ping !")
                if diag_oscar and genre == "NOM":
                    os.startfile(NAVIGATEUR, arguments=f'"{OSCAR_DIAG.format(hote=hote)}"')
                return
            cible, message = resultat
            self.var_hote.set(cible)
            self._ajouter_recent(cible)
            self.var_statut.set(message)

        self._en_arriere_plan(tache, fin)

    def pmad(self):
        if self._compte_requis():
            self._action_distante("Prise en main", lancer_pmad)

    def bad(self):
        self._action_distante("Bureau à distance", lancer_bad)

    def partage(self, nom):
        if self._compte_requis():
            self._action_distante(nom.upper(), ouvrir_partage(nom), diag_oscar=False)

    def ping(self):
        lu = self._lire_hote()
        if lu:
            hote, _ = lu
            subprocess.Popen(["ping", "-t", hote], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self._ajouter_recent(hote)
            self.var_statut.set(f"Ping continu vers {hote} lancé.")

    def relancer_service_pmad(self):
        if not self._compte_requis():
            return
        lu = self._lire_hote()
        if not lu:
            return
        hote, _ = lu
        compte = self.compte
        self.var_statut.set(f"Redémarrage de CmRcService sur {hote}…")

        def fin(message):
            self.var_statut.set(message)
            self.app.info("Service de prise en main", message + "\n\nSi la prise en main ne fonctionne "
                          "toujours pas, une réparation du client SCCM est nécessaire.")

        self._en_arriere_plan(lambda: relancer_cmrc(hote, compte), fin)

    # ----- Compte blanc -----
    def basculer_connexion(self):
        if self.compte:
            self.app.compte_poste = None
            self._maj_compte()
            self.var_statut.set("Compte blanc déconnecté.")
        else:
            self.connexion()

    def connexion(self):
        saisie = self._demander_compte()
        if not saisie:
            return
        utilisateur, mdp = saisie
        self.var_statut.set(f"Vérification du compte {DOMAINE}\\{utilisateur}…")

        def tache():
            try:
                winapi.verifier_identifiants(utilisateur, DOMAINE, mdp)
            except OSError as e:
                raise ActionImpossible(f"Identifiant ou mot de passe incorrect.\n\n{e.strerror or e}") from e
            return utilisateur, mdp

        def fin(compte):
            self.app.compte_poste = compte
            self._maj_compte()
            self.var_statut.set(f"Connecté en tant que {DOMAINE}\\{utilisateur}.")
            self.recherche.entry.focus_set()

        self._en_arriere_plan(tache, fin)

    def _demander_compte(self):
        """Fenêtre de connexion au style de NDT (même construction que App.ask_password)."""
        app = self.app
        resultat = {"v": None}
        win = tk.Toplevel(app)
        win.title("Connexion — Compte blanc")
        win.configure(bg=app.p["bg"])
        win.transient(app)
        win.resizable(False, False)

        body = ttk.Frame(win, padding=26)
        body.pack()
        ttk.Label(body, text="Compte blanc", style="H2.TLabel").pack(anchor="w")
        ttk.Label(body, text=f"Identifiants du domaine {DOMAINE}.", style="Muted.TLabel").pack(anchor="w", pady=(4, 14))
        ttk.Label(body, text="Identifiant").pack(anchor="w")
        utilisateur = ttk.Entry(body, width=34)
        utilisateur.pack(fill="x", pady=(4, 12))
        if self.compte:
            utilisateur.insert(0, self.compte[0])
        ttk.Label(body, text="Mot de passe").pack(anchor="w")
        mdp = ttk.Entry(body, show="•", width=34)
        mdp.pack(fill="x")

        def valider(_e=None):
            if utilisateur.get().strip() and mdp.get():
                resultat["v"] = (utilisateur.get().strip(), mdp.get())
                win.destroy()
            return "break"

        def annuler(_e=None):
            win.destroy()
            return "break"

        rangee = ttk.Frame(body)
        rangee.pack(fill="x", pady=(20, 0))
        ttk.Button(rangee, text="Se connecter", style="Accent.TButton", command=valider).pack(side="right")
        ttk.Button(rangee, text="Annuler", command=annuler).pack(side="right", padx=8)
        win.bind("<Return>", valider)
        win.bind("<Escape>", annuler)
        win.protocol("WM_DELETE_WINDOW", annuler)
        app._center_modal(win)
        (mdp if utilisateur.get() else utilisateur).focus_set()
        app.wait_window(win)
        return resultat["v"]
