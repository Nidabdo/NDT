"""Onglet « Scripts » : scripts du bureau technique avec variables à remplir
(repris de la page « Scripts BT » de Pause Cafew)."""
import json
import re
import uuid
import tkinter as tk
from fenetres import Popup, centrer_fenetre
from tkinter import filedialog, ttk

from diagnostic_form import RoundedPanel, SearchBox
from documentation import ArticleList, folded
from stockage import ecrire_json_atomique

VARIABLE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
LANGAGES = {"ps": "PowerShell", "cmd": "CMD", "bash": "Bash"}
SECRETS = ("MOT_DE_PASSE", "PASSWORD", "MDP", "PWD")   # champs masqués à la saisie
MONO = ("Consolas", 10)
CHAMPS = ("id", "section", "titre", "langage", "description", "code")

# Contenu initial : les scripts de Pause Cafew (assets/scripts-data.js).
SCRIPTS_INITIAUX = [
    {"id": "1", "section": "Active Directory", "titre": "Réinitialiser un mot de passe", "langage": "ps",
     "description": "Réinitialise le mot de passe d'un compte AD et force le changement à la prochaine connexion.",
     "code": "$user = \"{UTILISATEUR}\"\n"
             "$newPwd = ConvertTo-SecureString \"{MOT_DE_PASSE}\" -AsPlainText -Force\n"
             "Set-ADAccountPassword -Identity $user -NewPassword $newPwd -Reset\n"
             "Set-ADUser -Identity $user -ChangePasswordAtLogon $true"},
    {"id": "2", "section": "Active Directory", "titre": "Débloquer un compte", "langage": "ps",
     "description": "Débloque un compte AD verrouillé après trop de tentatives de connexion échouées.",
     "code": "$user = \"{UTILISATEUR}\"\nUnlock-ADAccount -Identity $user\nWrite-Host \"Compte $user débloqué.\""},
    {"id": "3", "section": "Active Directory", "titre": "Lister les groupes d'un utilisateur", "langage": "ps",
     "description": "Affiche tous les groupes AD auxquels appartient un utilisateur.",
     "code": "$user = \"{UTILISATEUR}\"\nGet-ADPrincipalGroupMembership -Identity $user |\n"
             "    Select-Object Name, GroupCategory |\n    Sort-Object Name"},
    {"id": "4", "section": "Active Directory", "titre": "Infos d'un compte utilisateur", "langage": "ps",
     "description": "Affiche les informations détaillées d'un compte AD (statut, dernière connexion, expiration).",
     "code": "$user = \"{UTILISATEUR}\"\nGet-ADUser -Identity $user -Properties * |\n"
             "    Select-Object Name, SamAccountName,\n    Enabled, LockedOut,\n"
             "    LastLogonDate, PasswordExpired,\n    PasswordLastSet"},
]


class ScriptsInvalides(ValueError):
    """Fichier de scripts illisible ; le message indique quoi faire."""


# ---------- Logique (sans interface) ----------
def libelle_langage(code):
    return LANGAGES.get(code, code.upper() if code else "Autre")


def code_langage(libelle):
    """« PowerShell » -> "ps" ; un langage libre est gardé tel quel, en minuscules."""
    libelle = libelle.strip()
    inverse = {v.casefold(): k for k, v in LANGAGES.items()}
    return inverse.get(libelle.casefold(), libelle.casefold())


def variables(code):
    """Variables {NOM} du code, sans doublon, dans l'ordre d'apparition."""
    vues = []
    for nom in VARIABLE.findall(code):
        if nom not in vues:
            vues.append(nom)
    return vues


def libelle_variable(nom):
    return nom.replace("_", " ").lower().capitalize()


def est_secret(nom):
    return any(mot in nom for mot in SECRETS)


def segments(code, valeurs):
    """Découpe le code pour l'aperçu : (texte, None | "rempli" | "manquant")."""
    morceaux, position = [], 0
    for trouve in VARIABLE.finditer(code):
        if trouve.start() > position:
            morceaux.append((code[position:trouve.start()], None))
        valeur = valeurs.get(trouve.group(1), "").strip()
        morceaux.append((valeur, "rempli") if valeur else (trouve.group(0), "manquant"))
        position = trouve.end()
    if position < len(code):
        morceaux.append((code[position:], None))
    return morceaux


def code_rempli(code, valeurs):
    return "".join(texte for texte, _ in segments(code, valeurs))


def _valider(scripts):
    ids = set()
    for script in scripts:
        if not isinstance(script, dict) or any(not isinstance(script.get(c), str) for c in CHAMPS):
            raise ScriptsInvalides("Un script du fichier est mal formé.")
        if not script["id"] or script["id"] in ids:
            raise ScriptsInvalides("Deux scripts du fichier ont le même identifiant.")
        ids.add(script["id"])
    return scripts


def charger_scripts(path):
    """Scripts du fichier, ou le contenu initial s'il n'existe pas encore."""
    if not path.exists():
        return [dict(s) for s in SCRIPTS_INITIAUX]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ScriptsInvalides(f"Le fichier {path.name} est illisible : {err}") from err
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("scripts"), list):
        raise ScriptsInvalides(f"Le fichier {path.name} n'est pas un fichier de scripts NDT.")
    return _valider(data["scripts"])


def enregistrer_scripts(path, scripts):
    ecrire_json_atomique(path, {"version": 1, "scripts": scripts})


def lire_export_pause_cafew(texte):
    """Scripts d'un fichier scripts-data.js exporté depuis l'ancienne page Pause Cafew."""
    try:
        debut = texte.index("[", texte.index("SCRIPTS_DATA"))
        bruts = json.loads(texte[debut:texte.rindex("]") + 1])
    except ValueError as err:
        raise ScriptsInvalides("Ce fichier n'est pas un export « scripts-data.js » de Pause Cafew.") from err
    scripts = []
    for brut in bruts:
        if not isinstance(brut, dict) or not isinstance(brut.get("code"), str):
            raise ScriptsInvalides("Un script de l'export est mal formé.")
        scripts.append({"id": uuid.uuid4().hex[:8],   # nouveaux identifiants : aucun conflit
                        "section": str(brut.get("section") or "Divers"),
                        "titre": str(brut.get("title") or "Sans titre"),
                        "langage": str(brut.get("tag") or ""),
                        "description": str(brut.get("desc") or ""),
                        "code": brut["code"]})
    return scripts


def fusionner(existants, nouveaux):
    """Ajoute les scripts qui ne sont pas déjà présents (même section, titre et code)."""
    deja = {(s["section"], s["titre"], s["code"]) for s in existants}
    ajoutes = [s for s in nouveaux if (s["section"], s["titre"], s["code"]) not in deja]
    return existants + ajoutes, len(ajoutes)


# ---------- Interface ----------
class ScriptsBT(ttk.Frame):
    """Liste à gauche, script sélectionné à droite. `edition` : ajout, modification,
    suppression et import (droit scripts_edition)."""

    def __init__(self, parent, app, path, edition=False):
        super().__init__(parent)
        self.app, self.path, self.edition = app, path, edition
        self.selected_id = None
        self.resultats = []
        self.champs = {}
        self.echec = False
        try:
            self.scripts = charger_scripts(path)
        except ScriptsInvalides as err:
            self.scripts, self.echec = [], True
            app.error("Scripts indisponibles", str(err))

        haut = ttk.Frame(self)
        haut.pack(fill="x", pady=(0, 8))
        ttk.Label(haut, text="Rechercher", style="Muted.TLabel").pack(side="left", padx=(0, 12))
        self.query = tk.StringVar()
        SearchBox(haut, app, self.query, radius=8).pack(side="left", fill="x", expand=True)
        self.compte = tk.StringVar()
        ttk.Label(haut, textvariable=self.compte, style="Muted.TLabel").pack(side="left", padx=(12, 0))

        if edition:
            actions = ttk.Frame(self)
            actions.pack(side="bottom", fill="x", pady=(12, 0))
            self.boutons_edition = []
            for texte, commande, style, cote in (
                ("+ Ajouter un script", lambda: self.editer(), "Accent.TButton", "left"),
                ("Modifier", self.editer_selection, "TButton", "left"),
                ("Supprimer", self.supprimer_selection, "Danger.TButton", "left"),
                ("Importer depuis Pause Cafew…", self.importer, "Ghost.TButton", "right"),
            ):
                bouton = ttk.Button(actions, text=texte, style=style, command=commande)
                bouton.pack(side=cote, padx=(0, 8) if cote == "left" else (8, 0))
                if self.echec:
                    bouton.state(["disabled"])
                self.boutons_edition.append(bouton)

        self.panneaux = ttk.Frame(self)
        self.panneaux.pack(fill="both", expand=True)
        self.panneaux.columnconfigure(1, weight=1)
        self.panneaux.rowconfigure(0, weight=1)
        cadre_liste = RoundedPanel(self.panneaux, app, padding=6, radius=8, shadow=False)
        cadre_liste.configure(width=280)
        cadre_liste.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.cadre_liste = cadre_liste
        self.liste = ArticleList(cadre_liste.body, app)
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<<ArticleSelect>>", self.selectionner)

        lecteur = RoundedPanel(self.panneaux, app, padding=20, radius=8, shadow=False)
        lecteur.grid(row=0, column=1, sticky="nsew")
        corps = lecteur.body
        self.titre = ttk.Label(corps, style="Card.H2.TLabel")
        self.titre.pack(anchor="w")
        self.meta = ttk.Label(corps, style="Card.Ok.TLabel")
        self.meta.pack(anchor="w", pady=(4, 0))
        self.description = ttk.Label(corps, style="Card.Muted.TLabel", justify="left", wraplength=500)
        self.description.pack(anchor="w", fill="x", pady=(6, 10))
        self.description.bind("<Configure>", lambda e: self.description.configure(wraplength=max(160, e.width)))
        self.zone_variables = ttk.Frame(corps, style="Surface.TFrame")
        self.zone_variables.pack(fill="x")
        self.zone_variables.columnconfigure(1, weight=1)

        ttk.Label(corps, text="Aperçu", style="Card.Muted.TLabel").pack(anchor="w", pady=(10, 4))
        zone_code = ttk.Frame(corps, style="Surface.TFrame")
        zone_code.pack(fill="both", expand=True)
        self.apercu = tk.Text(zone_code, wrap="none", font=MONO, height=8, width=1)
        self.apercu._documentation_content = True   # fond « carte », comme le lecteur de documentation
        defilement = ttk.Scrollbar(zone_code, command=self.apercu.yview)
        defilement.pack(side="right", fill="y")
        self.apercu.pack(fill="both", expand=True)
        self.apercu.configure(yscrollcommand=defilement.set, state="disabled")
        app.paint(self.apercu)

        boutons = ttk.Frame(corps, style="Surface.TFrame")
        boutons.pack(fill="x", pady=(12, 0))
        self.bouton_rempli = ttk.Button(boutons, text="Copier le script rempli", style="Card.Accent.TButton",
                                        command=self.copier_rempli)
        self.bouton_rempli.pack(side="left")
        self.bouton_brut = ttk.Button(boutons, text="Copier le brut", style="Card.TButton", command=self.copier_brut)
        self.bouton_brut.pack(side="left", padx=8)
        self.message = tk.StringVar()
        ttk.Label(boutons, textvariable=self.message, style="Card.Ok.TLabel").pack(side="left", padx=8)

        self.apres_theme()
        self.panneaux.bind("<Configure>", self._reflow)
        self.query.trace_add("write", lambda *_: self.rafraichir())
        self.rafraichir()

    # ----- Thème -----
    def apres_theme(self):
        """Appelée par App.paint au changement de thème : couleurs de l'aperçu."""
        p = self.app.p
        self.apercu.tag_configure("rempli", foreground=p["accent"], font=(MONO[0], MONO[1], "bold"))
        self.apercu.tag_configure("manquant", foreground=p["danger"], font=(MONO[0], MONO[1], "bold"))

    def _reflow(self, event):
        largeur = max(220, min(300, int(event.width * 0.32)))
        self.cadre_liste.configure(width=largeur)
        self.liste.configure(width=largeur - 12)

    # ----- Liste -----
    def script(self, script_id):
        return next((s for s in self.scripts if s["id"] == script_id), None)

    def rafraichir(self):
        termes = folded(self.query.get()).split()
        self.resultats = sorted(
            (s for s in self.scripts
             if all(t in folded(" ".join((s["section"], s["titre"], s["description"], s["code"],
                                          libelle_langage(s["langage"])))) for t in termes)),
            key=lambda s: (folded(s["section"]), folded(s["titre"])))
        self.liste.set_articles([{"id": s["id"], "title": s["titre"], "category": s["section"],
                                  "system": libelle_langage(s["langage"])} for s in self.resultats])
        self.compte.set("Fichier à vérifier" if self.echec else f"{len(self.resultats)} script(s)")
        ids = [s["id"] for s in self.resultats]
        choisi = self.selected_id if self.selected_id in ids else (ids[0] if ids else None)
        self.liste.selection_set(choisi)
        if choisi:
            self.liste.see(choisi)
        self.selectionner()

    def selectionner(self, _event=None):
        selection = self.liste.selection()
        script = self.script(selection[0]) if selection else None
        if script and script["id"] == self.selected_id and self.champs:
            return   # même script : on garde les valeurs déjà saisies
        self.selected_id = script["id"] if script else None
        for widget in self.zone_variables.winfo_children():
            widget.destroy()
        self.champs = {}
        if not script:
            self.titre.configure(text="Aucun script à afficher")
            self.meta.configure(text="")
            self.description.configure(text="Aucun résultat pour cette recherche." if self.scripts else
                                       "Aucun script pour l'instant.")
            self._afficher_apercu([])
            for bouton in (self.bouton_rempli, self.bouton_brut):
                bouton.state(["disabled"])
            return
        for bouton in (self.bouton_rempli, self.bouton_brut):
            bouton.state(["!disabled"])
        self.titre.configure(text=script["titre"])
        self.meta.configure(text=" · ".join(filter(None, [script["section"], libelle_langage(script["langage"])])))
        self.description.configure(text=script["description"])
        for ligne, nom in enumerate(variables(script["code"])):
            ttk.Label(self.zone_variables, text=libelle_variable(nom), style="Card.TLabel").grid(
                row=ligne, column=0, sticky="w", padx=(0, 12), pady=3)
            valeur = tk.StringVar()
            valeur.trace_add("write", lambda *_: self._maj_apercu())
            ttk.Entry(self.zone_variables, textvariable=valeur, show="•" if est_secret(nom) else "").grid(
                row=ligne, column=1, sticky="ew", pady=3)
            self.champs[nom] = valeur
        self.message.set("")
        self._maj_apercu()

    # ----- Aperçu et copie -----
    def valeurs(self):
        return {nom: var.get() for nom, var in self.champs.items()}

    def _maj_apercu(self):
        script = self.script(self.selected_id)
        self._afficher_apercu(segments(script["code"], self.valeurs()) if script else [])

    def _afficher_apercu(self, morceaux):
        self.apercu.configure(state="normal")
        self.apercu.delete("1.0", "end")
        for texte, etat in morceaux:
            self.apercu.insert("end", texte, etat or ())
        self.apercu.configure(state="disabled")

    def _copier(self, texte, message):
        self.clipboard_clear()
        self.clipboard_append(texte)
        self.update()   # garde le contenu dans le presse-papiers
        self.message.set(message)
        self.after(2000, lambda: self.message.set(""))

    def copier_rempli(self):
        script = self.script(self.selected_id)
        if not script:
            return
        manquantes = [libelle_variable(n) for n in variables(script["code"]) if not self.valeurs().get(n, "").strip()]
        if manquantes and not self.app.confirm(
                "Variables non remplies",
                "Ces variables sont vides : " + ", ".join(manquantes) + ".\nCopier le script quand même ?",
                yes="Copier", no="Annuler"):
            return
        self._copier(code_rempli(script["code"], self.valeurs()), "Copié ✔")

    def copier_brut(self):
        script = self.script(self.selected_id)
        if script:
            self._copier(script["code"], "Copié (brut) ✔")

    # ----- Édition (droit scripts_edition) -----
    def _enregistrer(self, scripts):
        try:
            enregistrer_scripts(self.path, scripts)
        except OSError as err:
            self.app.error("Enregistrement impossible", str(err))
            return False
        self.scripts = scripts
        return True

    def editer_selection(self):
        script = self.script(self.selected_id)
        if script:
            self.editer(script)

    def supprimer_selection(self):
        script = self.script(self.selected_id)
        if script and self.app.confirm("Supprimer le script", f"Supprimer « {script['titre']} » ?",
                                       yes="Supprimer", no="Annuler"):
            if self._enregistrer([s for s in self.scripts if s["id"] != script["id"]]):
                self.selected_id = None
                self.rafraichir()

    def importer(self):
        chemin = filedialog.askopenfilename(
            parent=self, title="Importer des scripts Pause Cafew",
            filetypes=[("Export Pause Cafew", "*.js"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            with open(chemin, encoding="utf-8-sig") as fichier:
                nouveaux = lire_export_pause_cafew(fichier.read())
        except (OSError, ScriptsInvalides) as err:
            self.app.error("Import impossible", str(err))
            return
        scripts, ajoutes = fusionner(self.scripts, nouveaux)
        if ajoutes and not self._enregistrer(scripts):
            return
        self.rafraichir()
        self.app.info("Import terminé", f"{ajoutes} script(s) ajouté(s), "
                                        f"{len(nouveaux) - ajoutes} déjà présent(s).")

    def editer(self, script=None):
        app = self.app
        win = Popup(app)
        win.title("Modifier le script" if script else "Nouveau script")
        win.configure(bg=app.p["bg"])
        win.transient(app)
        corps = ttk.Frame(win, padding=24)
        corps.pack(fill="both", expand=True)
        corps.columnconfigure(1, weight=1)
        sections = sorted({s["section"] for s in self.scripts}, key=folded)
        champs = {}
        for ligne, (cle, libelle) in enumerate((("section", "Section"), ("titre", "Titre"),
                                                ("langage", "Langage"), ("description", "Description"))):
            ttk.Label(corps, text=libelle).grid(row=ligne, column=0, sticky="w", padx=(0, 12), pady=4)
            if cle in ("section", "langage"):
                valeurs = sections if cle == "section" else list(LANGAGES.values())
                champ = ttk.Combobox(corps, values=valeurs, width=40)
            else:
                champ = ttk.Entry(corps, width=60)
            champ.grid(row=ligne, column=1, sticky="ew", pady=4)
            champs[cle] = champ
        if script:
            champs["section"].insert(0, script["section"])
            champs["titre"].insert(0, script["titre"])
            champs["langage"].insert(0, libelle_langage(script["langage"]))
            champs["description"].insert(0, script["description"])
        else:
            champs["langage"].insert(0, LANGAGES["ps"])
        ttk.Label(corps, text="Code  (variables : {NOM_EN_MAJUSCULES})").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(10, 4))
        cadre_code = ttk.Frame(corps)
        cadre_code.grid(row=5, column=0, columnspan=2, sticky="nsew")
        corps.rowconfigure(5, weight=1)
        code = app.make_text(cadre_code, height=14, width=80, undo=True)
        code.configure(font=MONO, wrap="none")
        defilement = ttk.Scrollbar(cadre_code, command=code.yview)
        defilement.pack(side="right", fill="y")
        code.pack(fill="both", expand=True)
        code.configure(yscrollcommand=defilement.set)
        if script:
            code.insert("1.0", script["code"])
        erreur = tk.StringVar()
        ttk.Label(corps, textvariable=erreur, style="Muted.TLabel").grid(row=6, column=0, columnspan=2,
                                                                       sticky="w", pady=(8, 0))

        def enregistrer():
            titre = champs["titre"].get().strip()
            contenu = code.get("1.0", "end-1c")
            if not titre or not contenu.strip():
                erreur.set("Le titre et le code sont obligatoires.")
                return
            nouveau = {"id": script["id"] if script else uuid.uuid4().hex[:8],
                       "section": champs["section"].get().strip() or "Divers",
                       "titre": titre,
                       "langage": code_langage(champs["langage"].get()),
                       "description": champs["description"].get().strip(),
                       "code": contenu}
            scripts = ([nouveau if s["id"] == nouveau["id"] else s for s in self.scripts] if script
                       else self.scripts + [nouveau])
            if self._enregistrer(scripts):
                win.destroy()
                self.selected_id = nouveau["id"]
                self.champs = {}   # force l'affichage du script modifié
                self.rafraichir()

        rangee = ttk.Frame(corps)
        rangee.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(rangee, text="Enregistrer", style="Accent.TButton", command=enregistrer).pack(side="right")
        ttk.Button(rangee, text="Annuler", command=win.destroy).pack(side="right", padx=8)
        win.bind("<Escape>", lambda _e: win.destroy())
        app._center_modal(win)
        champs["titre" if script else "section"].focus_set()
