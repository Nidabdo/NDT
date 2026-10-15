"""Accueil « Pause Cafew » : tuiles d'outils, liens d'équipe et recherche SMAX (repris du portail web)."""
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageOps, ImageTk

import pause_cafew_donnees as donnees
from navigateur import ouvrir_url
from rendu import rounded

DOSSIER_IMAGES = "img_cafew"
TUILES_PAR_PAGE = 4   # section équipe, comme le carrousel d'origine
FONT = "Segoe UI"


class DonneesInvalides(ValueError):
    """pause_cafew_donnees.py contient une erreur ; le message indique quoi corriger."""


def ressource(*parties):
    """Fichier livré avec NDT : dans l'exe (PyInstaller) ou à côté des sources."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parties)


def verifier_donnees(config=donnees):
    def verifier_lien(ou, lien):
        nom = lien.get("nom") if isinstance(lien, dict) else None
        if not isinstance(nom, str) or not nom.strip():
            raise DonneesInvalides(f"Dans {ou}, une ligne n'a pas de nom : {lien!r}")
        url = lien.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise DonneesInvalides(f'Dans {ou}, « {nom} » : l\'adresse doit commencer par https:// '
                                   f"(lu : {url!r}).")
        image = lien.get("image")
        if image is not None and not ressource(DOSSIER_IMAGES, image).is_file():
            raise DonneesInvalides(f'Dans {ou}, « {nom} » : l\'image {image!r} est absente '
                                   f"du dossier {DOSSIER_IMAGES}.")

    for lien in config.OUTILS:
        verifier_lien("OUTILS", lien)
    for equipe, liens in config.EQUIPES.items():
        for lien in liens:
            verifier_lien(f"EQUIPES, équipe « {equipe} »", lien)
    for type_, url in config.RECHERCHE_SMAX.items():
        if "{numero}" not in url:
            raise DonneesInvalides(f"Dans RECHERCHE_SMAX, « {type_} » : l'adresse doit contenir {{numero}}.")


def url_recherche(type_, numero, config=donnees):
    """Adresse SMAX de la fiche, ou None si le numéro est vide ou le type inconnu."""
    numero = numero.strip()
    if not numero or type_ not in config.RECHERCHE_SMAX:
        return None
    return config.RECHERCHE_SMAX[type_].replace("{numero}", quote(numero, safe=""))


def initiales(nom):
    mots = [m for m in nom.replace("-", " ").split() if m[:1].isalnum()]
    return "".join(m[0] for m in mots[:2]).upper() or "?"


def _logo(widget, fichier, taille, fond):
    """Logo recadré au carré, coins arrondis lissés, déjà posé sur la couleur `fond`
    (une image opaque s'affiche bien plus vite qu'une image transparente sous Tk)."""
    racine = widget._root()
    cache = racine.__dict__.setdefault("_logos_cafew", {})
    cle = (fichier, taille, fond)
    if cle not in cache:
        with Image.open(ressource(DOSSIER_IMAGES, fichier)) as source:
            image = ImageOps.fit(source.convert("RGBA"), (taille, taille), Image.LANCZOS)
        plaque = Image.new("RGBA", (taille, taille), "#ffffff")   # logos transparents : fond blanc
        plaque.alpha_composite(image)
        echelle = 4   # masque dessiné en grand puis réduit : bords lissés
        masque = Image.new("L", (taille * echelle, taille * echelle), 0)
        ImageDraw.Draw(masque).rounded_rectangle((0, 0, taille * echelle - 1, taille * echelle - 1),
                                                 radius=max(4, taille // 8) * echelle, fill=255)
        masque = masque.resize((taille, taille), Image.LANCZOS)
        resultat = Image.new("RGB", (taille, taille), fond)
        resultat.paste(plaque.convert("RGB"), (0, 0), masque)
        cache[cle] = ImageTk.PhotoImage(resultat, master=racine)
    return cache[cle]


class TuileOutil(tk.Canvas):
    """Tuile cliquable : logo (ou initiales) et nom ; Entrée / Espace l'ouvrent aussi."""

    def __init__(self, parent, app, lien):
        echelle = max(1.0, app.winfo_fpixels("1i") / 96)
        self.largeur, self.hauteur = round(150 * echelle), round(172 * echelle)
        self.taille_logo = round(104 * echelle)
        super().__init__(parent, width=self.largeur, height=self.hauteur, highlightthickness=0,
                         takefocus=True, cursor="hand2", bg=app.p["bg"])
        self.app, self.lien = app, lien
        self.survol = False
        for evenement, action in (("<Enter>", lambda _e: self._survoler(True)),
                                  ("<Leave>", lambda _e: self._survoler(False)),
                                  ("<FocusIn>", lambda _e: self.draw()),
                                  ("<FocusOut>", lambda _e: self.draw()),
                                  ("<Button-1>", self.ouvrir),
                                  ("<Return>", self.ouvrir),
                                  ("<KP_Enter>", self.ouvrir),
                                  ("<space>", self.ouvrir)):
            self.bind(evenement, action)
        self.draw()

    def _survoler(self, valeur):
        self.survol = valeur
        self.draw()

    def ouvrir(self, _event=None):
        self.focus_set()
        ouvrir_url(self.lien["url"])
        return "break"

    def draw(self):
        p = self.app.p
        self.configure(bg=p["bg"])
        self.delete("all")
        fond = p["select"] if self.survol else p["surface"]
        focus = self.focus_get() == self
        rounded(self, 1, 1, self.largeur - 2, self.hauteur - 2, 16, fill=fond,
                outline=p["accent"] if self.survol or focus else p["border"], width=2 if focus else 1)
        x, y = (self.largeur - self.taille_logo) // 2, round(self.hauteur * 0.08)
        if self.lien.get("image"):
            self.create_image(x, y, image=_logo(self, self.lien["image"], self.taille_logo, fond), anchor="nw")
        else:
            rounded(self, x, y, self.taille_logo, self.taille_logo, max(4, self.taille_logo // 8), fill=p["accent"])
            self.create_text(self.largeur / 2, y + self.taille_logo / 2, text=initiales(self.lien["nom"]),
                             fill=p["accent_fg"], font=(FONT, 22, "bold"))
        self.create_text(self.largeur / 2, y + self.taille_logo + (self.hauteur - y - self.taille_logo) / 2,
                         text=self.lien["nom"], width=self.largeur - 16, justify="center",
                         fill=p["fg"], font=(FONT, 10, "bold"))


class PauseCafew(ttk.Frame):
    """Écran d'accueil. `app` fournit le thème (app.p), les réglages (app.settings,
    app.save_setting) et la liaison de la molette (défilement de la page)."""

    def __init__(self, parent, app, config=donnees):
        super().__init__(parent)
        self.app, self.config_cafew = app, config
        self.colonnes = 0
        self.page = 0

        # Page défilante : un Canvas porte tout le contenu.
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=app.p["bg"])
        self.barre = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.barre.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.contenu = ttk.Frame(self.canvas)
        self.fenetre = self.canvas.create_window(0, 0, window=self.contenu, anchor="nw")
        self.canvas.bind("<Configure>", self._redimensionner)
        self.contenu.bind("<Configure>", lambda _e: self._maj_defilement())

        self._construire_entete()
        self.grille = ttk.Frame(self.contenu)
        self.grille.pack(fill="x", pady=(22, 0))
        self.tuiles = [TuileOutil(self.grille, app, lien) for lien in config.OUTILS]
        self._construire_equipe()
        self._lier_molette(self)

    # ----- En-tête : titre et recherche SMAX -----
    def _construire_entete(self):
        entete = ttk.Frame(self.contenu)
        entete.pack(fill="x")
        titre = ttk.Frame(entete)
        titre.pack(side="left", anchor="w")
        ttk.Label(titre, text="Pause Cafew", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titre, text="Centralisation des outils", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        recherche = ttk.Frame(entete)
        recherche.pack(side="right", anchor="e")
        ttk.Label(recherche, text="Recherche SMAX", style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        types = list(self.config_cafew.RECHERCHE_SMAX)
        self.var_type = tk.StringVar(value=types[0])
        self.choix_type = ttk.Combobox(recherche, textvariable=self.var_type, values=types,
                                       state="readonly", width=9)
        self.choix_type.grid(row=1, column=0, padx=(0, 6), pady=(4, 0))
        self.var_numero = tk.StringVar()
        self.champ_numero = ttk.Entry(recherche, textvariable=self.var_numero, width=16)
        self.champ_numero.grid(row=1, column=1, padx=(0, 6), pady=(4, 0))
        for touche in ("<Return>", "<KP_Enter>"):
            self.champ_numero.bind(touche, self.rechercher)
        ttk.Button(recherche, text="Ouvrir", style="Accent.TButton",
                   command=self.rechercher).grid(row=1, column=2, pady=(4, 0))

    def rechercher(self, _event=None):
        url = url_recherche(self.var_type.get(), self.var_numero.get(), self.config_cafew)
        if url:
            ouvrir_url(url)
            self.var_numero.set("")
        self.champ_numero.focus_set()
        return "break"   # Entrée ne doit pas déclencher les raccourcis du diagnostic

    # ----- Section équipe -----
    def _construire_equipe(self):
        section = ttk.Frame(self.contenu)
        section.pack(fill="x", pady=(30, 0))
        entete = ttk.Frame(section)
        entete.pack(fill="x")
        equipes = list(self.config_cafew.EQUIPES)
        memorisee = self.app.settings.get("cafew_equipe")
        self.var_equipe = tk.StringVar(value=memorisee if memorisee in equipes else equipes[0])
        self.titre_equipe = ttk.Label(entete, style="H2.TLabel")
        self.titre_equipe.pack(side="left")
        choix = ttk.Combobox(entete, textvariable=self.var_equipe, values=equipes, state="readonly", width=20)
        choix.pack(side="right")
        choix.bind("<<ComboboxSelected>>", lambda _e: self._changer_equipe())
        ttk.Label(entete, text="Équipe", style="Muted.TLabel").pack(side="right", padx=(0, 8))

        rangee = ttk.Frame(section)
        rangee.pack(fill="x", pady=(14, 0))
        # Hérite de TButton (formes arrondies, couleurs du thème) ; seule la police change.
        self.app.style.configure("Fleche.TButton", font=(FONT, 13), padding=(12, 4))
        self.bouton_prec = ttk.Button(rangee, text="❮", width=2, style="Fleche.TButton",
                                      command=lambda: self._tourner(-1))
        self.bouton_prec.pack(side="left")
        self.bouton_suiv = ttk.Button(rangee, text="❯", width=2, style="Fleche.TButton",
                                      command=lambda: self._tourner(1))
        self.bouton_suiv.pack(side="right")
        self.piste = ttk.Frame(rangee)
        self.piste.pack(side="left", fill="x", expand=True, padx=12)
        self._afficher_equipe()

    def _liens_equipe(self):
        return self.config_cafew.EQUIPES[self.var_equipe.get()]

    def _changer_equipe(self):
        self.app.save_setting("cafew_equipe", self.var_equipe.get())
        self.page = 0
        self._afficher_equipe()

    def _tourner(self, sens):
        pages = max(1, -(-len(self._liens_equipe()) // TUILES_PAR_PAGE))
        self.page = (self.page + sens) % pages   # boucle, comme le carrousel d'origine
        self._afficher_equipe()

    def _afficher_equipe(self):
        self.titre_equipe.configure(text=self.var_equipe.get().upper())
        for widget in self.piste.winfo_children():
            widget.destroy()
        liens = self._liens_equipe()
        debut = self.page * TUILES_PAR_PAGE
        for colonne in range(TUILES_PAR_PAGE):
            self.piste.columnconfigure(colonne, weight=1, uniform="equipe")
        for colonne, lien in enumerate(liens[debut:debut + TUILES_PAR_PAGE]):
            TuileOutil(self.piste, self.app, lien).grid(row=0, column=colonne)
        plusieurs = len(liens) > TUILES_PAR_PAGE
        for bouton in (self.bouton_prec, self.bouton_suiv):
            bouton.state(["!disabled"] if plusieurs else ["disabled"])
        self._lier_molette(self.piste)

    # ----- Disposition et défilement -----
    def _redimensionner(self, event):
        self.canvas.itemconfigure(self.fenetre, width=event.width)
        largeur_tuile = self.tuiles[0].largeur if self.tuiles else 150
        colonnes = max(1, (event.width + 14) // (largeur_tuile + 14))
        if colonnes != self.colonnes:
            self.colonnes = colonnes
            for index, tuile in enumerate(self.tuiles):
                tuile.grid(row=index // colonnes, column=index % colonnes, padx=7, pady=7)
            for colonne in range(max(colonnes, self.grille.grid_size()[0])):
                self.grille.columnconfigure(colonne, weight=1 if colonne < colonnes else 0,
                                            uniform="outils" if colonne < colonnes else "")
        self._maj_defilement()

    def _maj_defilement(self):
        self.canvas.configure(scrollregion=(0, 0, self.contenu.winfo_reqwidth(), self.contenu.winfo_reqheight()))
        deborde = self.contenu.winfo_reqheight() > self.canvas.winfo_height() + 2
        if deborde and not self.barre.winfo_manager():
            self.barre.pack(side="right", fill="y", before=self.canvas)
        elif not deborde and self.barre.winfo_manager():
            self.barre.pack_forget()
            self.canvas.yview_moveto(0)

    def _lier_molette(self, widget):
        def molette(event):
            if self.barre.winfo_manager():
                self.canvas.yview_scroll(-int(event.delta / 120), "units")
            return "break"
        widget.bind("<MouseWheel>", molette)   # remplace une liaison existante : pas de doublon
        for enfant in widget.winfo_children():
            if not isinstance(enfant, ttk.Combobox):   # la molette y change la valeur
                self._lier_molette(enfant)

    def draw(self):
        """Changement de thème : fond de la page et tuiles."""
        self.canvas.configure(bg=self.app.p["bg"])
