"""Fenêtre de connexion au lancement de NDT : compte du domaine, ou Bypass hors domaine."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

import acces
import droits
import poste_winapi as winapi

DOMAINE = "INTRA"

MESSAGES_WINDOWS = {
    1326: "Identifiant ou mot de passe incorrect.",
    1909: "Ce compte est verrouillé. Contactez le support pour le débloquer.",
    1330: "Le mot de passe de ce compte a expiré. Changez-le depuis une session Windows.",
    1907: "Le mot de passe de ce compte doit être changé avant la première connexion.",
    1331: "Ce compte est désactivé.",
    1311: "Le domaine INTRA est injoignable depuis ce poste.",
}


def message_erreur(erreur):
    message = MESSAGES_WINDOWS.get(erreur.errno, f"Connexion refusée : {erreur.strerror or erreur}")
    if erreur.errno == 1311 and acces.AUTORISER_BYPASS:
        message += "\nPour travailler hors domaine, cochez « Bypass »."
    return message


def demander_session(app):
    """Ouvre la fenêtre de connexion et renvoie une droits.Session, ou None si l'on quitte."""
    resultat = {"session": None}
    resultats = queue.Queue()
    win = tk.Toplevel(app)
    win.title("NDT — Connexion")
    win.configure(bg=app.p["bg"])
    win.resizable(False, False)

    body = ttk.Frame(win, padding=28)
    body.pack()
    ttk.Label(body, text="NDT.", style="Eyebrow.TLabel").pack(anchor="w")
    ttk.Label(body, text="Connexion", style="H2.TLabel").pack(anchor="w", pady=(6, 0))
    ttk.Label(body, text=f"Votre compte du domaine {DOMAINE}.",
              style="Muted.TLabel").pack(anchor="w", pady=(4, 16))
    ttk.Label(body, text="Identifiant").pack(anchor="w")
    identifiant = ttk.Entry(body, width=36)
    identifiant.pack(fill="x", pady=(4, 12))
    ttk.Label(body, text="Mot de passe").pack(anchor="w")
    mot_de_passe = ttk.Entry(body, show="•", width=36)
    mot_de_passe.pack(fill="x")

    bypass = tk.BooleanVar(value=False)
    if acces.AUTORISER_BYPASS:
        def basculer_bypass():
            etat = ["disabled"] if bypass.get() else ["!disabled"]
            identifiant.state(etat)
            mot_de_passe.state(etat)
        ttk.Checkbutton(body, text="Bypass — travailler hors domaine (tous les accès)",
                        variable=bypass, command=basculer_bypass).pack(anchor="w", pady=(14, 0))

    statut = tk.StringVar()
    ttk.Label(body, textvariable=statut, style="Muted.TLabel", wraplength=320,
              justify="left").pack(anchor="w", pady=(12, 0))

    rangee = ttk.Frame(body)
    rangee.pack(fill="x", pady=(18, 0))
    bouton_ok = ttk.Button(rangee, text="Se connecter", style="Accent.TButton")
    bouton_ok.pack(side="right")
    ttk.Button(rangee, text="Quitter", command=win.destroy).pack(side="right", padx=8)

    def terminer(session):
        resultat["session"] = session
        win.destroy()

    def depiler():
        try:
            etat, valeur = resultats.get_nowait()
        except queue.Empty:
            win.after(50, depiler)
            return
        win.configure(cursor="")
        if etat == "ok":
            terminer(valeur)
            return
        bouton_ok.state(["!disabled"])
        statut.set(valeur)
        mot_de_passe.delete(0, "end")
        mot_de_passe.focus_set()

    def valider(_e=None):
        if bouton_ok.instate(["disabled"]):
            return "break"
        if bypass.get():
            terminer(droits.session_bypass())
            return "break"
        login = identifiant.get().strip()
        if "\\" in login:   # « INTRA\RG768446 » accepté
            login = login.split("\\", 1)[1]
        mdp = mot_de_passe.get()
        if not login or not mdp:
            statut.set("Saisissez votre identifiant et votre mot de passe.")
            return "break"
        bouton_ok.state(["disabled"])
        win.configure(cursor="watch")
        statut.set("Vérification du compte…")

        def travail():
            try:
                groupes = winapi.ouvrir_session(login, DOMAINE, mdp)
                resultats.put(("ok", droits.session_ad(login, DOMAINE, mdp, groupes)))
            except OSError as erreur:
                resultats.put(("erreur", message_erreur(erreur)))
            except Exception as erreur:  # noqa: BLE001 — afficher plutôt que bloquer la fenêtre
                resultats.put(("erreur", f"Erreur inattendue : {erreur!r}"))

        threading.Thread(target=travail, daemon=True).start()
        win.after(50, depiler)
        return "break"

    bouton_ok.configure(command=valider)
    win.bind("<Return>", valider)
    win.bind("<Escape>", lambda _e: win.destroy())
    win.protocol("WM_DELETE_WINDOW", win.destroy)

    # La fenêtre principale est masquée : on centre sur l'écran.
    win.update_idletasks()
    x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
    y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.lift()
    win.focus_force()
    identifiant.focus_set()
    app.wait_window(win)
    return resultat["session"]
