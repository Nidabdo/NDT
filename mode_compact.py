"""Mode compact : petite barre toujours au premier plan, comme CS Tools 2.

Poste + PMAD / PING / BAD / IP / C:\\ / D:\\. Les actions sont celles de l'écran
« Outils poste » (ping du poste et de son dock, compte de la session, postes récents) :
seule la présentation change.
"""
import queue
import tkinter as tk
from tkinter import ttk

from outils_poste import OutilsPoste, charger_recents

FONT = "Segoe UI"


class BarreCompacte(OutilsPoste):
    def __init__(self, parent, app):
        ttk.Frame.__init__(self, parent, padding=(10, 8, 10, 6))   # pas l'interface d'OutilsPoste
        self.app = app
        self._resultats = queue.Queue()
        self._en_cours = 0
        self.var_hote = tk.StringVar()
        self.var_statut = tk.StringVar(value="Nom du poste ou adresse IP, puis une action.")
        self.var_compte = tk.StringVar()
        self.recents = charger_recents()

        # Boutons resserrés : mêmes formes et couleurs que le thème, police et marges réduites.
        for style in ("Compact.TButton", "Compact.Accent.TButton", "Compact.Ghost.TButton"):
            app.style.configure(style, font=(FONT, 9, "bold"), padding=(9, 4))

        ligne = ttk.Frame(self)
        ligne.pack(fill="x")
        self.saisie = ttk.Combobox(ligne, textvariable=self.var_hote, values=self.recents, width=18,
                                   font=(FONT, 10, "bold"))
        self.saisie.pack(side="left", padx=(0, 6))
        for touche in ("<Return>", "<KP_Enter>"):
            self.saisie.bind(touche, self._entree)
        self.boutons = {}
        for texte, commande, style in (
            ("PMAD", self.pmad, "Compact.Accent.TButton"),
            ("PING", self.ping, "Compact.TButton"),
            ("BAD", self.bad, "Compact.TButton"),
            ("IP", self.ip, "Compact.TButton"),
            ("C:\\", lambda: self.partage("c$"), "Compact.TButton"),
            ("D:\\", lambda: self.partage("d$"), "Compact.TButton"),
        ):
            # Largeur à la mesure du texte (sinon ttk impose une largeur minimale d'environ 11 caractères).
            bouton = ttk.Button(ligne, text=texte, style=style, command=commande, width=max(4, len(texte) + 1))
            bouton.pack(side="left", padx=2)
            self.boutons[texte] = bouton
        self.bouton_agrandir = ttk.Button(ligne, text="↗ Agrandir", style="Compact.Ghost.TButton",
                                          command=app.quitter_mode_compact)
        self.bouton_agrandir.pack(side="left", padx=(10, 0))
        self.statut = ttk.Label(self, textvariable=self.var_statut, style="Muted.TLabel")
        self.statut.pack(fill="x", pady=(6, 0))
        self.saisie.focus_set()

    # Points d'accroche d'OutilsPoste propres à cette présentation.
    def _afficher_recents(self):
        self.saisie.configure(values=self.recents)

    def _maj_compte(self):
        pass   # pas de panneau « Compte » dans la barre

    def _focus_saisie(self):
        self.saisie.focus_set()
