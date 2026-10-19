"""Onglet « Relance » : mails de relance des demandes SMAX (assistance / service), envoyés par Exchange."""
import json
import queue
import re
import threading
import uuid
import tkinter as tk
from tkinter import ttk

import envoi_mail
from diagnostic_form import RoundedPanel
from scripts_bt import libelle_variable, variables
from stockage import ecrire_json_atomique

# ---------------------------------------------------------------------
#  Réglages de l'envoi
# ---------------------------------------------------------------------
EWS_URL = "https://mail.intra.cea.fr/EWS/Exchange.asmx"
EXPEDITEUR = "csig@cea.fr"          # boîte partagée : droit « Envoyer en tant que » nécessaire
COPIE_DANS_BOITE_PARTAGEE = True    # copie dans les Éléments envoyés de csig@cea.fr

TYPES = {"assistance": "Demande d'assistance", "service": "Demande de service"}
TYPES_COURTS = {"assistance": "Assistance", "service": "Service"}
DESTINATAIRES = {"demandeur": "Le demandeur", "tiers": "Une autre personne (manager, collègue…)"}
VARIABLE_TICKET = "TICKET"          # remplie automatiquement avec le numéro saisi
LIBELLES = {"TELEPHONE": "Téléphone", "DEMANDEUR": "Demandeur (nom)",
            "OBJET_CONTACT": "Objet de la prise de contact"}   # sinon : nom de la variable
VERSION_FICHIER = 2   # 2 : ligne « Objet de la prise de contact : {OBJET_CONTACT} »
ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_TENTATIVE = ("Bonjour, \n\nNous avons tenté de vous contacter ce jour pour la demande {TICKET} à votre nom.\n"
              "Notre dernière tentative de prise de contact au numéro {TELEPHONE} a échouée.\n\n"
              "Objet de la prise de contact : {OBJET_CONTACT}\n\n"
              "Merci de contacter l'infogérance en appelant le 111 ou de nous communiquer vos disponibilités "
              "par mail à l'adresse suivante : csig@cea.fr, en précisant le numéro de votre demande. \n\nMerci,")
_CLOTURE = ("Bonjour, \n\nNous avons tenté de vous contacter ce jour pour la demande {TICKET} à votre nom.\n\n"
            "Objet de la prise de contact : {OBJET_CONTACT}\n\n"
            "Conformément au processus en vigueur au CEA nous vous informons que sans nouvelle de votre part "
            "d'ici {DELAI} jours votre de demande sera clôturée. \n\nMerci pour la prise en compte de ce mail.")
_TIERS = ("Bonjour, \n\nNous avons tenté de prendre contact avec M. / Mme {DEMANDEUR} pour la demande N°{TICKET}. \n\n"
          "Objet de la prise de contact : {OBJET_CONTACT}\n\n"
          "Nos tentatives de prise de contact ayant échouées pouvez-vous vous rapprocher de M. / Mme {DEMANDEUR} "
          "afin qu'il/elle nous contacte pour le traitement de sa demande s'il vous plait ?")


def _modele(id_, nom, types, texte, destinataire="demandeur"):
    return {"id": id_, "nom": nom, "types": types, "destinataire": destinataire,
            "objet": f"Relance {nom} – Demande n°{{TICKET}}", "texte": texte,
            "correspondant": nom != "J0"}   # champ « Correspondant informatique » en copie, dès J2


MODELES_INITIAUX = [
    _modele("j0", "J0", ["assistance", "service"], _TENTATIVE),
    _modele("j2", "J2", ["assistance", "service"], _TENTATIVE),
    _modele("j4-a", "J4", ["assistance"], _CLOTURE.replace("{DELAI}", "3")),
    _modele("j4-s", "J4", ["service"], _TENTATIVE),
    _modele("j7-a", "J7", ["assistance"], _TIERS, "tiers"),
    _modele("j7-s", "J7", ["service"], _CLOTURE.replace("{DELAI}", "7")),
    _modele("j14-s", "J14", ["service"], _TIERS, "tiers"),
]


class ModelesInvalides(ValueError):
    """Fichier des modèles illisible ; le message indique quoi faire."""


# ---------- Logique (sans interface) ----------
def remplir(texte, valeurs):
    """Remplace les {VARIABLES} renseignées ; les autres restent visibles telles quelles."""
    def remplacer(trouve):
        valeur = valeurs.get(trouve.group(1), "").strip()
        return valeur or trouve.group(0)
    return re.sub(r"\{([A-Z][A-Z0-9_]*)\}", remplacer, texte)


def variables_a_saisir(modele):
    """Variables du modèle (objet et texte) à demander, hors numéro de ticket."""
    return [v for v in variables(modele["objet"] + "\n" + modele["texte"]) if v != VARIABLE_TICKET]


def modeles_du_type(modeles, type_):
    return [m for m in modeles if type_ in m["types"]]


def ticket_valide(numero):
    return numero.strip().isdigit()


def _valider(modeles):
    ids = set()
    for modele in modeles:
        if isinstance(modele, dict) and "correspondant" not in modele:
            # Modèles enregistrés avant l'option : correspondant proposé à partir de J2.
            modele["correspondant"] = modele.get("nom") != "J0"
        if (not isinstance(modele, dict)
                or not isinstance(modele["correspondant"], bool)
                or any(not isinstance(modele.get(c), str) for c in ("id", "nom", "objet", "texte", "destinataire"))
                or not isinstance(modele.get("types"), list)
                or not set(modele["types"]) <= set(TYPES)
                or modele["destinataire"] not in DESTINATAIRES):
            raise ModelesInvalides("Un modèle de relance du fichier est mal formé.")
        if not modele["id"] or modele["id"] in ids:
            raise ModelesInvalides("Deux modèles de relance ont le même identifiant.")
        ids.add(modele["id"])
    return modeles


def charger_modeles(path):
    if not path.exists():
        return [dict(m) for m in MODELES_INITIAUX]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ModelesInvalides(f"Le fichier {path.name} est illisible : {err}") from err
    if (not isinstance(data, dict) or data.get("version") not in (1, VERSION_FICHIER)
            or not isinstance(data.get("modeles"), list)):
        raise ModelesInvalides(f"Le fichier {path.name} n'est pas un fichier de relances NDT.")
    modeles = _valider(data["modeles"])
    if data["version"] == 1:
        modeles = [_ajouter_objet_contact(m) for m in modeles]
    return modeles


def _ajouter_objet_contact(modele):
    """Version 1 -> 2 : la ligne « Objet de la prise de contact : » reçoit son champ à remplir.
    Faite une seule fois : un modèle enregistré ensuite (version 2) n'est plus modifié."""
    if "{OBJET_CONTACT}" in modele["texte"]:
        return modele
    texte = re.sub(r"Objet de la prise de contact\s*:[ \t]*", "Objet de la prise de contact : {OBJET_CONTACT}",
                   modele["texte"], count=1)
    return dict(modele, texte=texte)


def enregistrer_modeles(path, modeles):
    ecrire_json_atomique(path, {"version": VERSION_FICHIER, "modeles": modeles})


# ---------- Interface ----------
class Relance(ttk.Frame):
    """Numéro de ticket, type de demande, relance (J0, J2...), aperçu puis envoi.
    `edition` : gestion des modèles (droit relances_edition)."""

    def __init__(self, parent, app, path, edition=False):
        super().__init__(parent)
        self.app, self.path, self.edition = app, path, edition
        self.type_ = None
        self.modele = None
        self.texte_modifie = False
        self.valeurs = {}                                     # variables partagées entre relances
        self.adresses = {cle: tk.StringVar() for cle in DESTINATAIRES}
        self.var_correspondant = tk.StringVar()                # copie facultative, gardée entre relances
        self._resultats = queue.Queue()
        self.echec = False
        try:
            self.modeles = charger_modeles(path)
        except ModelesInvalides as err:
            self.modeles, self.echec = [], True
            app.error("Modèles de relance indisponibles", str(err))

        # --- Ticket et type ---
        panneau = RoundedPanel(self, app, padding=22)
        panneau.pack(fill="x")
        corps = panneau.body
        ligne = ttk.Frame(corps, style="Surface.TFrame")
        ligne.pack(fill="x")
        ttk.Label(ligne, text="Numéro de ticket", style="Card.TLabel").pack(side="left")
        self.var_ticket = tk.StringVar()
        self.var_ticket.trace_add("write", lambda *_: self._maj())
        self.champ_ticket = ttk.Entry(ligne, textvariable=self.var_ticket, width=18)
        self.champ_ticket.pack(side="left", padx=(12, 24))
        self.boutons_type = {}
        for cle, libelle in TYPES.items():
            bouton = ttk.Button(ligne, text=libelle, style="Card.TButton", command=lambda c=cle: self.choisir_type(c))
            bouton.pack(side="left", padx=(0, 8))
            self.boutons_type[cle] = bouton
        if edition:
            ttk.Button(ligne, text="Gérer les modèles…", style="Card.Ghost.TButton",
                       command=self.gerer_modeles).pack(side="right")
        self.ligne_relances = ttk.Frame(corps, style="Surface.TFrame")
        self.ligne_relances.pack(fill="x", pady=(16, 0))
        self.indication = tk.StringVar()
        etiquette = ttk.Label(corps, textvariable=self.indication, style="Card.Muted.TLabel")

        def afficher_indication(*_):   # masquée quand vide : la place revient à l'aperçu du mail
            if self.indication.get():
                etiquette.pack(anchor="w", pady=(10, 0))
            else:
                etiquette.pack_forget()
        self.indication.trace_add("write", afficher_indication)

        # --- Aperçu du mail (affiché après le choix d'une relance) ---
        self.apercu = RoundedPanel(self, app, padding=22)
        corps = self.apercu.body
        self.titre_apercu = ttk.Label(corps, style="Card.H2.TLabel")
        self.titre_apercu.pack(anchor="w")
        ttk.Label(corps, text=f"Envoyé depuis {EXPEDITEUR}", style="Card.Ok.TLabel").pack(anchor="w", pady=(4, 12))
        self.champs = ttk.Frame(corps, style="Surface.TFrame")
        self.champs.pack(fill="x")
        self.champs.columnconfigure(1, weight=1)
        ttk.Label(corps, text="Message", style="Card.Muted.TLabel").pack(anchor="w", pady=(12, 4))
        # Boutons placés avant le message : ils restent visibles même dans une petite fenêtre.
        actions = ttk.Frame(corps, style="Surface.TFrame")
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        cadre = ttk.Frame(corps, style="Surface.TFrame")
        cadre.pack(fill="both", expand=True)
        self.texte = app.make_text(cadre, height=6, width=1)
        defilement = ttk.Scrollbar(cadre, command=self.texte.yview)
        defilement.pack(side="right", fill="y")
        self.texte.pack(fill="both", expand=True)
        self.texte.configure(yscrollcommand=defilement.set)
        self.texte.bind("<Key>", self._texte_saisi)
        self.bouton_envoyer = ttk.Button(actions, text="Envoyer", style="Card.Accent.TButton", command=self.envoyer)
        self.bouton_envoyer.pack(side="left")
        self.bouton_retablir = ttk.Button(actions, text="Rétablir le modèle", style="Card.TButton",
                                          command=self.retablir)
        self.bouton_retablir.pack(side="left", padx=8)
        self.statut = tk.StringVar()
        ttk.Label(actions, textvariable=self.statut, style="Card.Ok.TLabel").pack(side="left", padx=8)
        self._maj()

    # ----- Choix du type et de la relance -----
    def choisir_type(self, type_):
        self.type_ = type_
        self.modele = None
        self._maj()

    def _maj(self):
        """Boutons de type et de relance selon le ticket et le type choisis."""
        for cle, bouton in self.boutons_type.items():
            bouton.configure(style="Card.Accent.TButton" if cle == self.type_ else "Card.TButton")
        for widget in self.ligne_relances.winfo_children():
            widget.destroy()
        if self.type_ is None:
            self.indication.set("Saisissez le numéro du ticket puis choisissez le type de demande.")
        else:
            ttk.Label(self.ligne_relances, text="Relance", style="Card.TLabel").pack(side="left", padx=(0, 12))
            actif = ticket_valide(self.var_ticket.get())
            for modele in modeles_du_type(self.modeles, self.type_):
                bouton = ttk.Button(self.ligne_relances, text=modele["nom"], width=5,
                                    style="Card.Accent.TButton" if modele is self.modele else "Card.TButton",
                                    command=lambda m=modele: self.choisir_relance(m))
                bouton.pack(side="left", padx=(0, 8))
                if not actif:
                    bouton.state(["disabled"])
            self.indication.set("" if actif else "Le numéro de ticket ne doit contenir que des chiffres.")
        if self.modele and ticket_valide(self.var_ticket.get()):
            if not self.apercu.winfo_manager():
                self.apercu.pack(fill="both", expand=True, pady=(14, 0))
            self._regenerer()
        elif self.apercu.winfo_manager():
            self.apercu.pack_forget()

    def choisir_relance(self, modele):
        self.modele = modele
        self.texte_modifie = False
        self.statut.set("")
        for widget in self.champs.winfo_children():
            widget.destroy()
        self.titre_apercu.configure(text=f"Relance {modele['nom']} – {TYPES[self.type_]}")
        # Champs sur deux colonnes, pour laisser de la hauteur à l'aperçu du message.
        libelle = "À  (demandeur)" if modele["destinataire"] == "demandeur" else "À  (personne à solliciter)"
        champs = [(libelle, self.adresses[modele["destinataire"]])]
        if modele["correspondant"]:
            champs.append(("Correspondant informatique (en copie, facultatif)", self.var_correspondant))
        for nom in variables_a_saisir(modele):
            if nom not in self.valeurs:
                self.valeurs[nom] = tk.StringVar()
                self.valeurs[nom].trace_add("write", lambda *_: self._regenerer())
            champs.append((LIBELLES.get(nom, libelle_variable(nom)), self.valeurs[nom]))
        for colonne in (1, 3):
            self.champs.columnconfigure(colonne, weight=1, uniform="champs")
        for index, (texte, variable) in enumerate(champs):
            ligne, colonne = divmod(index, 2)
            ttk.Label(self.champs, text=texte, style="Card.TLabel", wraplength=230).grid(
                row=ligne, column=2 * colonne, sticky="w", padx=(0 if colonne == 0 else 16, 10), pady=3)
            ttk.Entry(self.champs, textvariable=variable).grid(row=ligne, column=2 * colonne + 1, sticky="ew", pady=3)
        ligne = (len(champs) + 1) // 2
        ttk.Label(self.champs, text="Objet", style="Card.TLabel").grid(row=ligne, column=0, sticky="w", padx=(0, 10), pady=3)
        self.var_objet = tk.StringVar()
        ttk.Entry(self.champs, textvariable=self.var_objet).grid(row=ligne, column=1, columnspan=3, sticky="ew", pady=3)
        self._maj()

    # ----- Texte du mail -----
    def valeurs_courantes(self):
        valeurs = {nom: var.get() for nom, var in self.valeurs.items()}
        valeurs[VARIABLE_TICKET] = self.var_ticket.get().strip()
        return valeurs

    def _texte_saisi(self, event):
        if event.char or event.keysym in ("BackSpace", "Delete"):
            self.texte_modifie = True   # le texte retouché à la main n'est plus régénéré

    def _regenerer(self):
        if not self.modele:
            return
        valeurs = self.valeurs_courantes()
        self.var_objet.set(remplir(self.modele["objet"], valeurs))
        if not self.texte_modifie:
            self.texte.delete("1.0", "end")
            self.texte.insert("1.0", remplir(self.modele["texte"], valeurs))

    def retablir(self):
        self.texte_modifie = False
        self._regenerer()

    # ----- Envoi -----
    def envoyer(self):
        if not self.modele:
            return
        destinataire = self.adresses[self.modele["destinataire"]].get().strip()
        objet = self.var_objet.get().strip()
        texte = self.texte.get("1.0", "end-1c")
        if not ADRESSE.match(destinataire):
            self.app.error("Destinataire invalide", "Saisissez une adresse e-mail valide (ex. prenom.nom@cea.fr).")
            return
        copie = self.var_correspondant.get().strip() if self.modele["correspondant"] else ""
        if copie and not ADRESSE.match(copie):
            self.app.error("Correspondant informatique invalide",
                           "Saisissez une adresse e-mail valide, ou laissez le champ vide.")
            return
        restantes = sorted(set(variables(objet + "\n" + texte)))
        if restantes and not self.app.confirm(
                "Champs non remplis",
                "Le message contient encore : " + ", ".join("{" + v + "}" for v in restantes) + ".\nEnvoyer quand même ?",
                yes="Envoyer", no="Corriger"):
            return
        if not self.app.confirm("Envoyer la relance",
                                f"Envoyer la relance {self.modele['nom']} à {destinataire}\n"
                                + (f"avec {copie} en copie\n" if copie else "")
                                + f"depuis {EXPEDITEUR} ?", yes="Envoyer", no="Annuler"):
            return
        nom = self.modele["nom"]
        self.bouton_envoyer.state(["disabled"])
        self.statut.set("Envoi en cours…")
        self.app.configure(cursor="watch")

        def travail():
            try:
                envoi_mail.envoyer(EWS_URL, destinataire, objet, texte, EXPEDITEUR, COPIE_DANS_BOITE_PARTAGEE,
                                   copie=copie)
                self._resultats.put(("ok", None))
            except envoi_mail.EnvoiImpossible as err:
                self._resultats.put(("erreur", str(err)))

        threading.Thread(target=travail, daemon=True).start()
        self.app.after(100, lambda: self._attendre(nom, destinataire))

    def _attendre(self, nom, destinataire):
        try:
            etat, message = self._resultats.get_nowait()
        except queue.Empty:
            self.app.after(100, lambda: self._attendre(nom, destinataire))
            return
        self.app.configure(cursor="")
        if not self.winfo_exists():
            if etat == "erreur":
                self.app.error("Relance non envoyée", message)
            return
        self.bouton_envoyer.state(["!disabled"])
        if etat == "ok":
            self.statut.set(f"Relance {nom} envoyée à {destinataire} ✔")
        else:
            self.statut.set("Échec de l'envoi.")
            self.app.error("Relance non envoyée", message)

    # ----- Modèles (droit relances_edition) -----
    def _enregistrer(self, modeles):
        try:
            enregistrer_modeles(self.path, modeles)
        except OSError as err:
            self.app.error("Enregistrement impossible", str(err))
            return False
        self.modeles = modeles
        self.modele = None
        self._maj()
        return True

    def gerer_modeles(self):
        app = self.app
        win = tk.Toplevel(app)
        win.title("Modèles de relance")
        win.configure(bg=app.p["bg"])
        win.transient(app)
        corps = ttk.Frame(win, padding=24)
        corps.pack(fill="both", expand=True)
        ttk.Label(corps, text="Modèles de relance", style="H2.TLabel").pack(anchor="w")
        ttk.Label(corps, text="Variables : {TICKET} (rempli automatiquement), {TELEPHONE}, {DEMANDEUR}… "
                              "Toute autre {VARIABLE} devient un champ à remplir.",
                  style="Muted.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(4, 12))
        liste = app.make_listbox(corps)
        liste.configure(height=10, width=60)
        liste.pack(fill="both", expand=True)

        def libelle(m):
            types = " + ".join(TYPES_COURTS[t] for t in m["types"])
            return f"{m['nom']:5}  {types}" + ("   → autre personne" if m["destinataire"] == "tiers" else "")

        def rafraichir(choisi=None):
            liste.delete(0, "end")
            for m in self.modeles:
                liste.insert("end", libelle(m))
            if choisi is not None:
                liste.selection_set(choisi)

        def selection():
            index = liste.curselection()
            return index[0] if index else None

        def modifier(index=None):
            existant = self.modeles[index] if index is not None else None
            nouveau = self.editer_modele(win, existant)
            if nouveau is None:
                return
            modeles = list(self.modeles)
            if index is None:
                modeles.append(nouveau)
                index = len(modeles) - 1
            else:
                modeles[index] = nouveau
            if self._enregistrer(modeles):
                rafraichir(index)

        def deplacer(sens):
            index = selection()
            if index is None or not 0 <= index + sens < len(self.modeles):
                return
            modeles = list(self.modeles)
            modeles[index], modeles[index + sens] = modeles[index + sens], modeles[index]
            if self._enregistrer(modeles):
                rafraichir(index + sens)

        def supprimer():
            index = selection()
            if index is None:
                return
            if app.confirm("Supprimer le modèle", f"Supprimer le modèle « {self.modeles[index]['nom']} » ?",
                           yes="Supprimer", no="Annuler"):
                if self._enregistrer([m for i, m in enumerate(self.modeles) if i != index]):
                    rafraichir()

        rangee = ttk.Frame(corps)
        rangee.pack(fill="x", pady=(12, 0))
        for texte, commande, style in (("+ Ajouter", lambda: modifier(None), "Accent.TButton"),
                                       ("Modifier", lambda: selection() is not None and modifier(selection()), "TButton"),
                                       ("Monter", lambda: deplacer(-1), "TButton"),
                                       ("Descendre", lambda: deplacer(1), "TButton"),
                                       ("Supprimer", supprimer, "Danger.TButton")):
            ttk.Button(rangee, text=texte, style=style, command=commande).pack(side="left", padx=(0, 8))
        ttk.Button(rangee, text="Fermer", command=win.destroy).pack(side="right")
        liste.bind("<Double-Button-1>", lambda _e: selection() is not None and modifier(selection()))
        win.bind("<Escape>", lambda _e: win.destroy())
        rafraichir(0 if self.modeles else None)
        app._center_modal(win)

    def editer_modele(self, parent, modele=None):
        """Fenêtre d'édition d'un modèle ; renvoie le modèle modifié, ou None si annulé."""
        app = self.app
        resultat = {"modele": None}
        win = tk.Toplevel(parent)
        win.title("Modifier le modèle" if modele else "Nouveau modèle")
        win.configure(bg=app.p["bg"])
        win.transient(parent)
        corps = ttk.Frame(win, padding=24)
        corps.pack(fill="both", expand=True)
        corps.columnconfigure(1, weight=1)
        ttk.Label(corps, text="Nom du bouton").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        nom = ttk.Entry(corps, width=12)
        nom.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(corps, text="Types de demande").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        cases = ttk.Frame(corps)
        cases.grid(row=1, column=1, sticky="w", pady=4)
        types = {cle: tk.BooleanVar(value=modele is None or cle in modele["types"]) for cle in TYPES}
        for cle, libelle in TYPES.items():
            ttk.Checkbutton(cases, text=libelle, variable=types[cle]).pack(side="left", padx=(0, 16))
        ttk.Label(corps, text="Envoyé à").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
        destinataire = ttk.Combobox(corps, values=list(DESTINATAIRES.values()), state="readonly", width=40)
        destinataire.set(DESTINATAIRES[modele["destinataire"] if modele else "demandeur"])
        destinataire.grid(row=2, column=1, sticky="w", pady=4)
        correspondant = tk.BooleanVar(value=modele["correspondant"] if modele else True)
        ttk.Checkbutton(corps, text="Proposer le correspondant informatique en copie (facultatif)",
                        variable=correspondant).grid(row=2, column=1, sticky="e", pady=4)
        ttk.Label(corps, text="Objet").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
        objet = ttk.Entry(corps, width=70)
        objet.grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(corps, text="Message").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 4))
        texte = app.make_text(corps, height=14, width=80, undo=True)
        texte.grid(row=5, column=0, columnspan=2, sticky="nsew")
        corps.rowconfigure(5, weight=1)
        if modele:
            nom.insert(0, modele["nom"])
            objet.insert(0, modele["objet"])
            texte.insert("1.0", modele["texte"])
        else:
            objet.insert(0, "Relance – Demande n°{TICKET}")
        erreur = tk.StringVar()
        ttk.Label(corps, textvariable=erreur, style="Muted.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def valider():
            choisis = [cle for cle, var in types.items() if var.get()]
            if not nom.get().strip() or not texte.get("1.0", "end-1c").strip():
                erreur.set("Le nom du bouton et le message sont obligatoires.")
                return
            if not choisis:
                erreur.set("Cochez au moins un type de demande.")
                return
            cle_destinataire = next(c for c, v in DESTINATAIRES.items() if v == destinataire.get())
            resultat["modele"] = {"id": modele["id"] if modele else uuid.uuid4().hex[:8],
                                  "nom": nom.get().strip(), "types": choisis, "destinataire": cle_destinataire,
                                  "objet": objet.get().strip(), "texte": texte.get("1.0", "end-1c"),
                                  "correspondant": correspondant.get()}
            win.destroy()

        rangee = ttk.Frame(corps)
        rangee.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(rangee, text="Enregistrer", style="Accent.TButton", command=valider).pack(side="right")
        ttk.Button(rangee, text="Annuler", command=win.destroy).pack(side="right", padx=8)
        win.bind("<Escape>", lambda _e: win.destroy())
        app._center_modal(win)
        nom.focus_set()
        win.wait_window()
        return resultat["modele"]
