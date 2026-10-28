"""
NDT v1 - Outil de diagnostic (application de bureau, sans navigateur)

Lancer en Python :   python "NDT v1.py"
Créer l'exécutable : pyinstaller --onefile --noconsole --name NDT_v1 "NDT v1.py"

Installer les dépendances : python -m pip install -r requirements.txt
Pillow gère les images de documentation ; tkinter est fourni avec Python.
Fichiers créés à côté du programme : questions.json (questions + modèle)
et settings.json (thème clair/sombre).
"""
import json
import hmac
import re
import sys
import tkinter as tk
from fenetres import Popup, centrer_fenetre
import unicodedata
import uuid
from pathlib import Path
from tkinter import messagebox, ttk
import droits
from connexion import demander_session
from parcours_editor import ParcoursEditor
from coordination_auth import verify_coordinateur, save_coordinateur_password
from documentation import Documentation, ArticleList
from diagnostic_form import SectionNavigation
from outils_poste import OutilsPoste
from pause_cafew import DonneesInvalides, PauseCafew, TuileOutil, verifier_donnees
from scripts_bt import ScriptsBT
from relance import Relance
from mode_compact import BarreCompacte
from diagnostic_form import DiagnosticForm, RoundedField, RoundedPanel, SearchBox, cercle, rounded, style_rounded_button

# Compte personnel, non affiché dans l'interface de connexion.
ADMIN_PASSWORD = "admin"
# Mot de passe initial du compte « coordinateur », à personnaliser ici.
# Un changement effectué dans l'application prend ensuite priorité sur cette valeur.
COORDINATEUR_PASSWORD = "coordinateur"

# Fichiers stockés à côté de l'exécutable (ou du script)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "questions.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
AUTH_FILE = BASE_DIR / "coordination_auth.json"
WIKI_BO_FILE = BASE_DIR / "wiki_bo.json"
SCRIPTS_FILE = BASE_DIR / "scripts.json"
RELANCES_FILE = BASE_DIR / "relances.json"

DEFAULT_TEMPLATE = "RÉSULTAT DU DIAGNOSTIC\n\n{reponses}"
RESERVED_TAGS = {"reponses"}
NOT_ANSWERED = ""
FONT = "Segoe UI"
NAV_ITEMS = (("Accueil", "home"), ("Diagnostic", "question"),
             ("Wiki BO", "documentation"), ("Outils poste", "outils"), ("Scripts", "scripts"),
             ("Relance", "relance"))

PALETTES = {
    "light": {
        "bg": "#eff3f2", "surface": "#ffffff", "fg": "#172b40", "muted": "#5c6e7c",
        "accent": "#087d72", "accent_hover": "#09695f", "accent_fg": "#ffffff",
        "border": "#d9e3df", "input": "#f3f7f5", "tab": "#e5ece9",
        "btn": "#ffffff", "btn_hover": "#e4f2ec", "select": "#e4f2ec",
        "hover": "#f3f7f5", "disabled": "#e5ece9", "ok": "#087d72",
        "sidebar": "#122a3d", "sidebar_select": "#23475a", "sidebar_hover": "#2b514f", "shadow": "#e0e8e4",
        "danger": "#dc2626",
    },
    "dark": {
        "bg": "#0d1724", "surface": "#152232", "fg": "#edf4fa", "muted": "#a4b6c7",
        "accent": "#72dfcd", "accent_hover": "#8ae8de", "accent_fg": "#102f32",
        "border": "#344758", "input": "#0f1b29", "tab": "#101e2c",
        "btn": "#152232", "btn_hover": "#203e45", "select": "#203e45",
        "hover": "#1d3345", "disabled": "#101e2c", "ok": "#72dfcd",
        "sidebar": "#0a1420", "sidebar_select": "#18313e", "sidebar_hover": "#203e45", "shadow": "#0a1420",
        "danger": "#f87171",
    },
}

# Écran net sous Windows (évite le rendu flou sur les écrans haute résolution)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


# ---------- Balises et modèle ----------
def clean_tag(raw):
    """Transforme 'Nom du client' en 'nom_du_client' (lettres, chiffres, _)."""
    s = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def next_tag(used):
    n = 1
    while f"q{n}" in used:
        n += 1
    return f"q{n}"


def render_template(template, values):
    """Remplace {balise} par sa valeur ; les balises inconnues restent telles quelles."""
    lookup = {clean_tag(k): v for k, v in values.items()}
    return re.sub(r"\{(\w+)\}",
                  lambda m: lookup.get(clean_tag(m.group(1)), m.group(0)),
                  template)


def align_routes(old_choices, old_routes, choices):
    """Les liens suivent le libellé, même quand les réponses sont réordonnées."""
    mapping = dict(zip(old_choices, old_routes))
    return [mapping.get(choice, "") for choice in choices]


def next_index(questions, current, value, history):
    q = questions[current]
    destination = q.get("next", "")
    if q["type"] == "choice" and isinstance(value, int):
        routes = q.get("routes", [])
        if 0 <= value < len(routes):
            destination = routes[value] or ""
    if destination == "__END__":
        return None
    if destination:
        target = next((i for i, item in enumerate(questions)
                       if item["id"] == destination), None)
        if target is None:
            raise ValueError("La question cible n'existe plus. Vérifiez la suite de cette question dans l'administration.")
    else:
        target = current + 1 if current + 1 < len(questions) else None
    if target is not None and target in history:
        raise ValueError("Ce parcours revient vers une question déjà posée. Corrigez la destination dans l'administration.")
    return target


# ---------- Stockage ----------
def normalize(questions):
    """Complète les anciennes questions (type, balise, obligatoire)."""
    used = set()
    for q in questions:
        q.setdefault("id", uuid.uuid4().hex[:8])
        q.setdefault("text", "")
        q.setdefault("choices", [])
        q.setdefault("next", "")
        routes = q.get("routes", [])
        if not isinstance(routes, list):
            routes = []
        q["routes"] = (routes + [""] * len(q["choices"]))[:len(q["choices"])]
        if q.get("type") not in ("choice", "free"):
            q["type"] = "choice"
        q.setdefault("required", True)
        tag = clean_tag(q.get("tag", ""))
        if not tag or tag in used or tag in RESERVED_TAGS:
            tag = next_tag(used)
        q["tag"] = tag
        used.add(tag)
    return questions


def load_data():
    data = {"questions": [], "template": ""}
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return data
        if isinstance(raw, list):            # ancien format (liste de questions)
            data["questions"] = raw
        elif isinstance(raw, dict):
            data["questions"] = raw.get("questions", [])
            data["template"] = raw.get("template", "")
    data["questions"] = normalize(data["questions"])
    return data


def save_data(questions, template):
    DATA_FILE.write_text(
        json.dumps({"questions": questions, "template": template},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings):
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


class ChoiceCard(tk.Canvas):
    """Carte de réponse arrondie, utilisable au clavier comme à la souris."""
    def __init__(self, parent, app, text, index):
        super().__init__(parent, height=104, width=200, highlightthickness=0,
                         takefocus=True, cursor="hand2")
        self.app, self.text, self.index = app, text, index
        self.hovered = False
        self.bind("<Configure>", lambda _e: self.draw())
        self.bind("<Button-1>", self.select)
        self.bind("<space>", self.select)
        self.bind("<FocusIn>", lambda _e: self.draw())
        self.bind("<FocusOut>", lambda _e: self.draw())
        self.bind("<Enter>", lambda _e: self.hover(True))
        self.bind("<Leave>", lambda _e: self.hover(False))

    def hover(self, value):
        self.hovered = value
        self.draw()

    def select(self, _event=None):
        self.focus_set()
        self.app.choice_var.set(self.index)
        if self.app.current == 0:
            self.app.next_question()
        return "break"

    def draw(self):
        p = self.app.p
        self.configure(bg=p["surface"])
        self.delete("all")
        w, h = max(self.winfo_width(), 80), self.winfo_height()
        selected = self.app.choice_var.get() == self.index
        fill = p["select"] if selected else p["hover"] if self.hovered else p["surface"]
        edge = p["accent"] if selected or self.focus_get() == self else p["border"]
        r, x, y = 16, w - 3, h - 3
        rounded(self,3,3,w-6,h-6,22,fill=fill,outline=edge,width=2)
        cercle(self, 27, 33, 8, outline=p["accent"] if selected else p["muted"], width=2)
        if selected:
            cercle(self, 27, 33, 4, fill=p["accent"])
        text_id = self.create_text(49, 20, text=self.text, anchor="nw", width=max(w-70, 20),
                                  font=(FONT, 13, "bold"), fill=p["fg"])
        bounds = self.bbox(text_id)
        bottom = bounds[3] if bounds else 50
        self.create_text(49, bottom+10, text="Sélectionné" if selected else "Choisir cette réponse",
                         anchor="nw", font=(FONT, 9), fill=p["accent"] if selected else p["muted"])
        needed = max(104, bottom + 42)
        if int(self.cget("height")) != needed:
            self.configure(height=needed)


# ---------- Application ----------
class App(tk.Tk):
    def __init__(self, session=None):
        """`session` : droits.Session déjà ouverte (tests) ; sinon la fenêtre de connexion s'affiche."""
        super().__init__()
        self.withdraw()   # rien n'apparaît avant la connexion
        self.session = None
        self.title("NDT 1.12 — Le diagnostic, guidé")
        self.geometry("1180x800")
        self.minsize(800, 600)

        self.settings = load_settings()
        if self.settings.get("design_version") != 3:
            self.settings.update(theme="light", design_version=3)
            save_settings(self.settings)
        self.theme = self.settings.get("theme", "dark")
        if self.theme not in PALETTES:
            self.theme = "dark"
        self.p = PALETTES[self.theme]

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.questions = []
        self.template = ""
        self.answers = {}
        self.current = 0
        self.history = []
        self.selected = None

        self.mode = None   # "question" quand le questionnaire est affiché
        self.mode_compact = False   # barre façon CS Tools, au premier plan
        self._pages = {}            # écrans construits une fois, puis masqués / réaffichés
        self.barre_compacte = None

        # Styles d'abord : la fenêtre de connexion en a besoin. L'interface principale n'est
        # construite qu'après la connexion, pour que celle-ci s'affiche au plus vite.
        self.apply_theme()

        if session is None:
            try:
                droits.verifier_config()
                verifier_donnees()
            except droits.ConfigInvalide as err:
                messagebox.showerror("Configuration des accès invalide",
                                     f"Le fichier acces.py contient une erreur :\n\n{err}")
                self.destroy()
                return
            except DonneesInvalides as err:
                messagebox.showerror("Liens de l'accueil invalides",
                                     f"Le fichier pause_cafew_donnees.py contient une erreur :\n\n{err}")
                self.destroy()
                return
            session = demander_session(self)
            if session is None:   # « Quitter »
                self.destroy()
                return

        self.build_header()
        self.theme_btn.configure(text="Mode clair" if self.theme == "dark" else "Mode sombre")
        self.container = ttk.Frame(self.workspace, padding=(32, 20))
        self.container.pack(fill="both", expand=True)
        self.bind('<Configure>', self.responsive_layout)

        # Raccourcis clavier du questionnaire
        self.bind("<Return>", self.on_return)
        self.bind("<KP_Enter>", self.on_return)
        self.bind("<Up>", lambda _e: self.on_arrow(-1))
        self.bind("<Down>", lambda _e: self.on_arrow(1))
        self.bind("<Key>", self.on_key)
        self.bind("<Control-Shift-A>", lambda _e: self.open_admin())

        self.session = session
        # Le compte saisi au lancement sert aussi aux outils poste (PMAD, C$...).
        self.compte_poste = (session.login, session.mot_de_passe) if session.mot_de_passe else None
        self.appliquer_droits()
        self.deiconify()
        self.show_home()

    # ===== Droits =====
    def autorise(self, cle):
        return self.session is not None and self.session.autorise(cle)

    def appliquer_droits(self):
        """Masque les écrans non autorisés et affiche qui est connecté."""
        self.vider_pages()
        for boutons in (self.nav_buttons, self.compact_nav_buttons):
            for cle, bouton in boutons.items():
                bouton.pack_forget()
            for cle, bouton in boutons.items():
                if self.autorise(cle):
                    if boutons is self.nav_buttons:
                        bouton.pack(fill="x", pady=5)
                    else:
                        bouton.pack(side="left", padx=(0, 8))
        if not self.autorise("admin"):
            self.coordination_btn.pack_forget()
        else:
            self.coordination_btn.pack(side="right")
        if self.autorise("outils"):
            self.compact_btn.pack(side="right", padx=(0, 4))
        else:
            self.compact_btn.pack_forget()
        for nom in ("session_label", "bypass_label"):
            label = getattr(self, nom, None)
            if label is not None:
                label.destroy()
                setattr(self, nom, None)
        self.title("NDT 1.12 — Le diagnostic, guidé")
        s = self.session
        if s.bypass:
            self.title(self.title() + "  —  MODE BYPASS")
            self.bypass_label = ttk.Label(self.top_bar, text="MODE BYPASS", style="Bypass.TLabel")
            self.bypass_label.pack(side="left", padx=(16, 0))
            texte = "Hors domaine\nTous les accès"
        else:
            texte = f"{s.domaine}\\{s.login}\n{' + '.join(s.profils)}"
        self.session_label = ttk.Label(self.nav_body, text=texte, style="Sidebar.Muted.TLabel",
                                       justify="left", wraplength=150)
        self.session_label.pack(side="bottom", anchor="w", padx=10, pady=(0, 12))

    def changer_compte(self):
        """Ferme la session courante puis demande un nouveau compte."""
        if self.session is None:
            return
        if getattr(self, "screen", None) == "admin":
            self.leave_admin()
            if self.screen == "admin":
                return
        elif self.diagnostic_engage():
            if not self.confirm("Changer de compte",
                                "Changer de compte ? Les réponses du diagnostic seront perdues.",
                                yes="Changer de compte", no="Continuer"):
                return
        self.withdraw()
        for widget in self.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()
        self.clear()
        self.vider_pages()   # rien de la session précédente ne doit rester affichable
        self.session = None
        self.compte_poste = None
        self.session_user = None
        self.questions = []
        self.template = ""
        self.answers = {}
        self.skipped = set()
        self.history = []
        self.current = 0
        self.selected = None
        session = demander_session(self)
        if session is None:
            self.destroy()
            return
        self.session = session
        self.compte_poste = (session.login, session.mot_de_passe) if session.mot_de_passe else None
        self.appliquer_droits()
        self.show_home()
        self.deiconify()

    # ===== Mode compact (barre façon CS Tools 2) =====
    def passer_mode_compact(self):
        """Réduit NDT à une barre PMAD / PING / BAD / IP / C:\\ / D:\\ toujours au premier plan.
        L'écran en cours est seulement masqué : il est retrouvé tel quel en agrandissant."""
        if self.mode_compact or not self.autorise("outils"):
            return
        self.mode_compact = True
        self.update_idletasks()   # taille réelle de la fenêtre, redimensionnement en attente compris
        self._avant_compact = (self.state(), self.geometry())
        if self.state() == "zoomed":
            self.state("normal")
        self.sidebar.pack_forget()
        self.workspace.pack_forget()
        self.barre_compacte = BarreCompacte(self, self)
        self.barre_compacte.pack(fill="both", expand=True)
        self.minsize(1, 1)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.update_idletasks()
        largeur = self.barre_compacte.winfo_reqwidth()
        hauteur = self.barre_compacte.winfo_reqheight()
        self.geometry(f"{largeur}x{hauteur}+{self.winfo_x()}+{self.winfo_y()}")

    def quitter_mode_compact(self):
        if not self.mode_compact:
            return
        self.barre_compacte.destroy()
        self.barre_compacte = None
        self.attributes("-topmost", False)
        self.resizable(True, True)
        self.minsize(800, 600)
        etat, geometrie = self._avant_compact
        self.geometry(geometrie)
        self.mode_compact = False
        self.sidebar.pack(side="left", fill="y", padx=(12, 0), pady=12)
        self.workspace.pack(side="left", fill="both", expand=True)
        if etat == "zoomed":
            self.state("zoomed")

    # ===== Thème =====
    def build_header(self):
        sidebar = RoundedPanel(self,self,padding=16,radius=20,surface='sidebar',
                               body_style='Sidebar.TFrame',autosize=False,shadow=False)
        sidebar.configure(width=190)
        self.sidebar = sidebar
        sidebar.pack(side="left", fill="y",padx=(12,0),pady=12)
        nav_body=sidebar.body
        self.nav_body = nav_body
        ttk.Label(nav_body, text="NDT.", style="Sidebar.Brand.TLabel").pack(anchor="w", padx=6,pady=(6,0))
        ttk.Label(nav_body, text="Le diagnostic, guidé.", style="Sidebar.Muted.TLabel").pack(anchor="w", padx=6, pady=(0, 38))
        self.nav_buttons = {}
        for label, key in NAV_ITEMS:
            btn = ttk.Button(nav_body, text=label, style="Sidebar.TButton",
                             command=lambda k=key: self.navigate(k))
            btn.pack(fill="x", pady=5)
            self.nav_buttons[key] = btn
        ttk.Label(nav_body, text="NDT 1.12\nESPACE ASSISTANCE",
                  style="Sidebar.Muted.TLabel", justify="left", wraplength=140).pack(side="bottom", anchor="w", padx=10)
        self.workspace = ttk.Frame(self)
        self.workspace.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(self.workspace, padding=(24, 10))
        bar.pack(fill="x")
        self.top_bar = bar
        self.breadcrumb = tk.StringVar(value="ESPACE ASSISTANCE  /  ACCUEIL")
        ttk.Label(bar, textvariable=self.breadcrumb, style="Muted.TLabel").pack(side="left")
        self.theme_btn = ttk.Button(bar, style="Ghost.TButton",
                                    command=self.toggle_theme)
        self.theme_btn.pack(side="right")
        self.compact_btn = ttk.Button(bar, text="Mode compact", style="Ghost.TButton",
                                      command=self.passer_mode_compact)
        self.compact_btn.pack(side="right", padx=(0, 4))
        self.compact_nav = ttk.Frame(self.workspace, padding=(18, 0))
        self.compact_nav_buttons={}
        for label, key in NAV_ITEMS:
            button=ttk.Button(self.compact_nav, text=label,style='Nav.TButton',command=lambda k=key:self.navigate(k))
            button.pack(side='left',padx=(0,8));self.compact_nav_buttons[key]=button
        footer = ttk.Frame(self.workspace, padding=(32, 0, 24, 16))
        footer.pack(side="bottom", fill="x")
        self.changer_compte_btn = ttk.Button(footer, text="Changer de compte",
                                             style="Ghost.TButton", command=self.changer_compte)
        self.changer_compte_btn.pack(side="left")
        self.coordination_btn = ttk.Button(footer, text="Coordination", style="Admin.TButton",
                                           command=self.open_admin)
        self.coordination_btn.pack(side="right")

    def responsive_layout(self, event):
        if event.widget != self or not hasattr(self, 'container') or self.mode_compact:
            return
        compact = self.winfo_width() < 1050 or self.winfo_height() < 750
        self.container.configure(padding=(18, 8) if compact else (28, 14))
        if self.winfo_width() < 980:
            if self.sidebar.winfo_manager(): self.sidebar.pack_forget()
            if not self.compact_nav.winfo_manager():self.compact_nav.pack(fill='x',before=self.container)
        elif not self.sidebar.winfo_manager():
            self.sidebar.pack(side='left', fill='y', before=self.workspace,padx=(12,0),pady=12)
            self.compact_nav.pack_forget()

    def set_screen(self, screen, title):
        self.screen = screen
        self.breadcrumb.set("ESPACE ASSISTANCE  /  " + title.upper())
        for key, button in self.nav_buttons.items():
            button.configure(style="Sidebar.Active.TButton" if key == screen else "Sidebar.TButton")
        for key,button in self.compact_nav_buttons.items():
            button.configure(style='Nav.Active.TButton' if key==screen else 'Nav.TButton')

    def navigate(self, target):
        if target == getattr(self, "screen", None) or not self.autorise(target):
            return
        if getattr(self, "screen", None) == "admin":
            self.leave_admin()
            if self.screen == "admin":
                return
        elif self.diagnostic_engage():
            if not self.confirm("Quitter le diagnostic", "Quitter ce parcours ? Vos réponses seront perdues.", yes="Quitter", no="Continuer"):
                return
        {"home": self.show_home, "question": self.start_user, "admin": self.open_admin, "documentation":self.show_documentation, "outils": self.show_outils, "scripts": self.show_scripts, "relance": self.show_relance}[target]()

    def show_documentation(self):
        self.clear()
        self.session_user = None
        self.set_screen('documentation', 'Wiki BO')

        def construire(page):
            ttk.Label(page, text='Wiki BO', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
            self.documentation = Documentation(page, self, WIKI_BO_FILE, editable=self.autorise("wiki_edition"))
            self.documentation.pack(fill='both', expand=True)
        self._page('documentation', construire)

    def show_scripts(self):
        self.clear()
        self.session_user = None
        self.set_screen('scripts', 'Scripts')

        def construire(page):
            ttk.Label(page, text='Scripts', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
            self.scripts_bt = ScriptsBT(page, self, SCRIPTS_FILE, edition=self.autorise('scripts_edition'))
            self.scripts_bt.pack(fill='both', expand=True)
        self._page('scripts', construire)

    def show_relance(self):
        self.clear()
        self.session_user = None
        self.set_screen('relance', 'Relance')

        def construire(page):
            ttk.Label(page, text='Relance', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
            self.relance = Relance(page, self, RELANCES_FILE, edition=self.autorise('relances_edition'))
            self.relance.pack(fill='both', expand=True)
        self._page('relance', construire)
        self.relance.champ_ticket.focus_set()

    def show_outils(self):
        self.clear()
        self.session_user = None
        self.set_screen('outils', 'Outils poste')

        def construire(page):
            ttk.Label(page, text='Outils poste', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
            self.outils_poste = OutilsPoste(page, self)
            self.outils_poste.pack(fill='both', expand=True)
        self._page('outils', construire)
        self.outils_poste.recherche.entry.focus_set()

    def apply_theme(self):
        p, s = self.p, self.style
        self.configure(bg=p["bg"])
        s.configure(".", background=p["bg"], foreground=p["fg"], font=(FONT, 11),
                    bordercolor=p["border"], troughcolor=p["tab"])

        # Cadres
        s.configure("TFrame", background=p["bg"])
        s.configure("Surface.TFrame", background=p["surface"])
        s.configure("Header.TFrame", background=p["surface"])
        s.configure("Line.TFrame", background=p["border"])
        s.configure("Card.TFrame", background=p["surface"], relief="solid",
                    borderwidth=1, bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"])

        # Étiquettes (une variante par fond : fenêtre, carte, en-tête)
        variants = {
            "TLabel": {},
            "Title.TLabel": {"font": (FONT, 22, "bold")},
            "H2.TLabel": {"font": (FONT, 15, "bold")},
            "Muted.TLabel": {"foreground": p["muted"], "font": (FONT, 10)},
            "Question.TLabel": {"font": (FONT, 17, "bold")},
            "Ok.TLabel": {"foreground": p["ok"], "font": (FONT, 10, "bold")},
        }
        for prefix, bg in (("", p["bg"]), ("Card.", p["surface"]),
                           ("Header.", p["surface"])):
            for name, extra in variants.items():
                opts = {"background": bg, "foreground": p["fg"], "font": (FONT, 11)}
                opts.update(extra)
                s.configure(prefix + name, **opts)
        s.configure("Brand.TLabel", background=p["surface"],
                    foreground=p["accent"], font=(FONT, 16, "bold"))

        # Boutons
        couleurs_boutons = {}

        def button(name, bg, fg, hover, font=(FONT, 10, "bold"), padding=(16, 9),indicator=None, outline=None):
            s.configure(name, background=bg, foreground=fg, bordercolor=bg,
                        lightcolor=bg, darkcolor=bg, focuscolor=bg,
                        relief="flat", borderwidth=1, padding=padding, font=font)
            s.map(name, background=[("active", hover), ("pressed", hover)],
                  bordercolor=[("active", hover), ("pressed", hover)],
                  lightcolor=[("active", hover), ("pressed", hover)],
                  darkcolor=[("active", hover), ("pressed", hover)])
            couleurs_boutons[name] = (bg, hover, indicator, outline)
            style_rounded_button(self, name, bg, hover,indicator, outline)
            # Le fond derrière les coins transparents doit rester celui du panneau.
            corner = p['sidebar'] if name.startswith('Sidebar.') else p['bg']
            s.configure(name, background=corner)
            s.map(name, background=[('active', corner), ('pressed', corner)])
        button("TButton", p["btn"], p["fg"], p["btn_hover"], outline=p["border"])
        button("Accent.TButton", p["accent"], p["accent_fg"], p["accent_hover"])
        button("Danger.TButton", p["btn"], p["danger"], p["btn_hover"], outline=p["border"])
        button("Admin.TButton", "#b42331", "#ffffff", "#991c29", padding=(14, 7))
        button("Ghost.TButton", p["bg"], p["muted"], p["select"],
               padding=(12, 6))
        button('Card.Ghost.TButton',p['surface'],p['muted'],p['select'],padding=(12,6))
        for base in ('TButton', 'Accent.TButton', 'Danger.TButton', 'Ghost.TButton'):
            s.configure('Card.' + base, background=p['surface'])
            s.map('Card.' + base, background=[('active', p['surface']), ('pressed', p['surface'])])
            if base != 'Ghost.TButton':   # Card.Ghost a déjà son propre style
                # Images propres aux cartes : les coins lissés se fondent dans la surface.
                style_rounded_button(self, 'Card.' + base, *couleurs_boutons[base])
        s.configure("Sidebar.TFrame", background=p['sidebar'])
        s.configure("Sidebar.Brand.TLabel", background=p['sidebar'], foreground="#65d8c6", font=(FONT, 30, "bold"))
        s.configure("Sidebar.Muted.TLabel", background=p['sidebar'], foreground="#b5c7d5", font=(FONT, 10))
        s.configure("Bypass.TLabel", background="#b42331", foreground="#ffffff",
                    font=(FONT, 9, "bold"), padding=(10, 3))
        s.configure("Eyebrow.TLabel", background=p["bg"], foreground=p["accent"], font=(FONT, 10, "bold"))
        button("Sidebar.TButton", p['sidebar'], "#bfd0de", p['sidebar_hover'], padding=(14, 12))
        button("Sidebar.Active.TButton", p['sidebar_select'], "#ffffff", p['sidebar_hover'], padding=(14, 12),indicator='#70ddc9')
        button('Nav.TButton',p['bg'],p['muted'],p['select'],padding=(14,9))
        button('Nav.Active.TButton',p['select'],p['accent'],p['select'],padding=(14,9),indicator=p['accent'])
        s.configure("Sidebar.TButton", anchor="w")
        s.configure("Sidebar.Active.TButton", anchor="w")

        # Boutons radio / cases à cocher
        s.configure("TRadiobutton", background=p["bg"], foreground=p["fg"],
                    indicatorcolor=p["input"], focuscolor=p["bg"])
        s.map("TRadiobutton", background=[("active", p["bg"])],
              indicatorcolor=[("selected", p["accent"]), ("pressed", p["accent"])])
        s.configure("TCheckbutton", background=p["bg"], foreground=p["fg"],
                    indicatorcolor=p["input"], focuscolor=p["bg"])
        s.map("TCheckbutton", background=[("active", p["bg"])],
              indicatorcolor=[("selected", p["accent"]), ("pressed", p["accent"])])
        s.configure("Option.TRadiobutton", background=p["surface"],
                    foreground=p["fg"], font=(FONT, 12), padding=(14, 11),
                    indicatorcolor=p["input"], focuscolor=p["surface"])
        s.map("Option.TRadiobutton",
              background=[("selected", p["select"]), ("active", p["hover"])],
              indicatorcolor=[("selected", p["accent"]), ("pressed", p["accent"])])

        # Champs de saisie
        s.configure("TEntry", fieldbackground=p["input"], foreground=p["fg"],
                    insertcolor=p["fg"], bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"], padding=7)
        s.map("TEntry", bordercolor=[("focus", p["accent"])],
              lightcolor=[("focus", p["accent"])],
              darkcolor=[("focus", p["accent"])])
        s.configure("TCombobox", fieldbackground=p["input"], background=p["btn"],
                    foreground=p["fg"], arrowcolor=p["fg"],
                    bordercolor=p["border"], lightcolor=p["border"],
                    darkcolor=p["border"], padding=6,
                    selectbackground=p["input"], selectforeground=p["fg"])
        s.map("TCombobox", fieldbackground=[("readonly", p["input"])],
              selectbackground=[("readonly", p["input"])],
              selectforeground=[("readonly", p["fg"])],
              background=[("active", p["btn_hover"])])
        self.option_add("*TCombobox*Listbox.background", p["input"])
        self.option_add("*TCombobox*Listbox.foreground", p["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        # Onglets, panneaux, barres
        s.configure('Library.Treeview', background=p['surface'], fieldbackground=p['surface'],
                    foreground=p['fg'], rowheight=64, borderwidth=0, font=(FONT,10))
        s.layout('Library.Treeview', [('Treeview.treearea', {'sticky':'nswe'})])
        s.map('Library.Treeview', background=[('selected',p['select'])],
              foreground=[('selected',p['accent'])])
        s.configure("TNotebook", background=p["bg"], borderwidth=0,
                    tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=p["tab"], foreground=p["muted"],
                    padding=(20, 10), font=(FONT, 10, "bold"), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", p["bg"]), ("active", p["btn_hover"])],
              foreground=[("selected", p["accent"])])
        s.configure("TLabelframe", background=p["bg"], bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"],
                    relief="solid", borderwidth=1)
        s.configure("TLabelframe.Label", background=p["bg"],
                    foreground=p["muted"], font=(FONT, 10, "bold"))
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar", background=p["btn"],
                        troughcolor=p["tab"], bordercolor=p["tab"],
                        lightcolor=p["btn"], darkcolor=p["btn"],
                        arrowcolor=p["muted"], relief="flat")
            s.map(f"{orient}.TScrollbar", background=[("active", p["btn_hover"])])
        s.configure("Horizontal.TProgressbar", background=p["accent"],
                    troughcolor=p["tab"], bordercolor=p["tab"],
                    lightcolor=p["accent"], darkcolor=p["accent"], thickness=8)

        if hasattr(self, "theme_btn"):   # absent avant la connexion
            self.theme_btn.configure(
                text="Mode clair" if self.theme == "dark" else "Mode sombre")

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.p = PALETTES[self.theme]
        self.settings["theme"] = self.theme
        save_settings(self.settings)
        self.apply_theme()
        self.repaint(self)   # pages masquées comprises
        for page in self._pages.values():
            page.theme_dessine = self.theme

    # Widgets tk "classiques" (Text, Listbox...) : coloriés à la main
    def paint(self, w):
        p = self.p
        apres_theme = getattr(w, "apres_theme", None)
        if callable(apres_theme):
            apres_theme()
        if isinstance(w, RoundedPanel):
            w.draw()
        elif isinstance(w, (RoundedField, SearchBox)):
            w.draw()
        elif isinstance(w, tk.Text) and isinstance(w.master, RoundedField):
            w.master.draw()
        elif isinstance(w, (ChoiceCard, ArticleList, TuileOutil)):
            w.draw()
        elif isinstance(w, tk.Canvas):
            w.configure(bg=p["surface"] if w == getattr(self, "choice_canvas", None) or getattr(w,'_surface_background',False) else p["bg"])
            if getattr(self, "screen", None) == "admin" and hasattr(self, "parcours_editor") and w == self.parcours_editor.canvas:
                self.parcours_editor.draw()
        elif isinstance(w, tk.Text):
            if getattr(w, '_documentation_content', False):
                w.configure(bg=p['surface'], fg=p['fg'], highlightthickness=0,
                            borderwidth=0, padx=0, pady=4, spacing1=3, spacing3=5,
                            selectbackground=p['accent'], selectforeground=p['accent_fg'])
                return
            grey = (getattr(w, "_grey_when_disabled", False)
                    and str(w.cget("state")) == "disabled")
            w.configure(bg=p["disabled"] if grey else p["input"],
                        fg=p["muted"] if grey else p["fg"],
                        insertbackground=p["fg"], selectbackground=p["accent"],
                        selectforeground="#ffffff", relief="flat", borderwidth=0,
                        highlightthickness=1, highlightbackground=p["border"],
                        highlightcolor=p["accent"])
        elif isinstance(w, tk.Listbox):
            w.configure(bg=p["input"], fg=p["fg"], selectbackground=p["accent"],
                        selectforeground="#ffffff", relief="flat", borderwidth=0,
                        highlightthickness=1, highlightbackground=p["border"],
                        highlightcolor=p["accent"])
        elif isinstance(w, tk.Toplevel):
            w.configure(bg=p["bg"])
        elif isinstance(w, ttk.Combobox):
            try:
                lb = f"{w}.popdown.f.l"
                if self.tk.call("winfo", "exists", lb):
                    self.tk.call(lb, "configure", "-background", p["input"],
                                 "-foreground", p["fg"], "-selectbackground",
                                 p["accent"], "-selectforeground", "#ffffff")
            except tk.TclError:
                pass

    def repaint(self, widget):
        for child in widget.winfo_children():
            self.paint(child)
            self.repaint(child)

    def make_text(self, parent, font_size=11, **kw):
        t = tk.Text(parent, wrap="word", font=(FONT, font_size), padx=12,
                    pady=10, **kw)
        self.paint(t)
        return t

    def make_listbox(self, parent):
        lb = tk.Listbox(parent, exportselection=False, activestyle="none",
                        font=(FONT, 11))
        self.paint(lb)
        return lb

    # ===== Boîtes de dialogue (aux couleurs du thème) =====
    def _center_modal(self, win):
        centrer_fenetre(win)
        try:
            if not win.winfo_viewable():win.wait_visibility()
            win.grab_set()
        except tk.TclError:
            pass
        win.focus_set()

    def _dialog(self, title, message, buttons, cancel=None, default=True):
        """buttons : liste (libellé, valeur, style) affichée de gauche à droite."""
        result = {"v": cancel}
        win = Popup(self)
        win.title(title)
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.resizable(False, False)

        body = ttk.Frame(win, padding=26)
        body.pack()
        ttk.Label(body, text=title, style="H2.TLabel").pack(anchor="w")
        ttk.Label(body, text=message, wraplength=430, justify="left").pack(
            anchor="w", pady=(10, 22))
        row = ttk.Frame(body)
        row.pack(fill="x")

        def choose(value):
            result["v"] = value
            win.destroy()

        for label, value, style in reversed(buttons):
            ttk.Button(row, text=label, style=style,
                       command=lambda v=value: choose(v)).pack(side="right",
                                                               padx=(8, 0))
        win.protocol("WM_DELETE_WINDOW", lambda: choose(cancel))
        win.bind("<Escape>", lambda _e: choose(cancel))
        win.bind("<Return>", lambda _e: choose(default))
        self._center_modal(win)
        self.wait_window(win)
        return result["v"]

    def info(self, title, message):
        self._dialog(title, message, [("OK", True, "Accent.TButton")])

    warn = info
    error = info

    def confirm(self, title, message, yes="Oui", no="Non"):
        return bool(self._dialog(
            title, message,
            [(no, False, "TButton"), (yes, True, "Accent.TButton")],
            cancel=False))

    def confirm3(self, title, message):
        """Renvoie True (oui), False (non) ou None (annuler)."""
        return self._dialog(
            title, message,
            [("Annuler", None, "TButton"), ("Non", False, "TButton"),
             ("Oui", True, "Accent.TButton")], cancel=None)

    def ask_password(self):
        result = {"v": None}
        win = Popup(self)
        win.title("Connexion — Coordination")
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.resizable(False, False)

        body = ttk.Frame(win, padding=26)
        body.pack()
        ttk.Label(body, text="Espace coordination", style="H2.TLabel").pack(anchor="w")
        ttk.Label(body, text="Saisissez vos identifiants pour continuer.",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 14))
        ttk.Label(body, text="Utilisateur").pack(anchor="w")
        username = ttk.Entry(body, width=34)
        username.pack(fill="x", pady=(4, 12))
        ttk.Label(body, text="Mot de passe").pack(anchor="w")
        entry = ttk.Entry(body, show="•", width=34)
        entry.pack(fill="x")

        def validate(_e=None):
            result["v"] = (username.get().strip().lower(), entry.get())
            win.destroy()

        def cancel(_e=None):
            win.destroy()

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(20, 0))
        ttk.Button(row, text="Valider", style="Accent.TButton",
                   command=validate).pack(side="right")
        ttk.Button(row, text="Annuler", command=cancel).pack(side="right", padx=8)
        win.bind("<Return>", validate)
        win.bind("<Escape>", cancel)
        win.protocol("WM_DELETE_WINDOW", cancel)
        self._center_modal(win)
        username.focus_set()
        self.wait_window(win)
        return result["v"]

    # ===== Navigation =====
    def clear(self):
        self.mode = None
        pages = set(self._pages.values())
        for widget in self.container.winfo_children():
            if widget in pages:
                widget.pack_forget()   # gardée pour un réaffichage instantané
            else:
                widget.destroy()

    def _page(self, cle, construire):
        """Affiche l'écran `cle` : construit au premier affichage, puis seulement réaffiché
        (il retrouve son état : recherche, saisie en cours...)."""
        page = self._pages.get(cle)
        if page is None or not page.winfo_exists():
            page = ttk.Frame(self.container)
            construire(page)
            page.theme_dessine = self.theme
            self._pages[cle] = page
        elif page.theme_dessine != self.theme:
            self.repaint(page)   # thème changé pendant que la page était masquée
            page.theme_dessine = self.theme
        page.pack(fill="both", expand=True)
        return page

    def vider_pages(self):
        """Oublie les écrans gardés : à faire quand les droits ou les données changent."""
        for page in self._pages.values():
            if page.winfo_exists():
                page.destroy()
        self._pages.clear()

    # ===== Menu principal =====
    def show_home(self):
        self.session_user = None
        self.clear()
        self.set_screen("home", "Pause Cafew")

        def construire(page):
            self.pause_cafew = PauseCafew(page, self)
            self.pause_cafew.pack(fill="both", expand=True)
        self._page("home", construire)

    def save_setting(self, key, value):
        self.settings[key] = value
        save_settings(self.settings)

    # ===== Partie utilisateur =====
    def start_user(self):
        data = load_data()
        self.template = data["template"]
        self.questions = [q for q in data["questions"]
                          if q["type"] == "free" or q["choices"]]
        if not self.questions:
            self.info("Aucune question",
                      "Aucune question n'a encore été configurée.\n"
                      "Contactez la personne qui gère vos questionnaires.")
            return
        self.answers = {}
        self.skipped = set()
        self.current = 0
        self.history = [0]
        self.show_question()

    def show_question(self):
        self.clear()
        self.set_screen("question", "Diagnostic")
        q = self.questions[self.current]
        ttk.Label(self.container, text="VOTRE DIAGNOSTIC", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(self.container, text="Commençons par votre poste.", style="Title.TLabel").pack(anchor="w", pady=(8, 6))
        ttk.Label(self.container, text="Choisissez votre réponse pour ouvrir le formulaire adapté.", style="Muted.TLabel").pack(anchor="w", pady=(0, 24))

        panel = RoundedPanel(self.container, self, padding=24)
        panel.pack(fill="both", expand=True)
        card = panel.body

        head = ttk.Frame(card, style="Surface.TFrame")
        head.pack(fill="x")
        step = len(self.history) if getattr(self, "history", None) else 1
        ttk.Label(head, text=f"Étape {step}  •  Parcours adapté à vos réponses",
                  style="Card.Muted.TLabel").pack(side="left")
        if not q["required"]:
            ttk.Label(head, text="Facultative",
                      style="Card.Muted.TLabel").pack(side="right")
        ttk.Separator(card).pack(fill="x", pady=(12, 26))

        label = ttk.Label(card, text=q["text"], style="Card.Question.TLabel",
                          justify="left")
        label.pack(fill="x", pady=(0, 18))
        label.bind("<Configure>",
                   lambda e, l=label: l.configure(wraplength=max(e.width - 10, 200)))

        nav = ttk.Frame(card, style="Surface.TFrame")
        nav.pack(side="bottom", fill="x", pady=(24, 0))
        previous = self.answers.get(self.current)
        if q["type"] == "free":
            ttk.Label(card, text="Saisissez votre réponse :",
                      style="Card.Muted.TLabel").pack(anchor="w")
            self.free_text = self.make_text(card, font_size=12, height=7)
            self.free_text.pack(fill="x", pady=(6, 0))
            if isinstance(previous, str):
                self.free_text.insert("1.0", previous)
            # Entrée valide ; Maj+Entrée garde le comportement normal (saut de ligne)
            self.free_text.bind("<Return>", self.on_return)
            self.free_text.bind("<KP_Enter>", self.on_return)
            self.free_text.bind("<Shift-Return>", lambda _e: None)
        else:
            self.choice_var = tk.IntVar(
                value=previous if isinstance(previous, int) else -1)
            choice_area = ttk.Frame(card, style="Surface.TFrame")
            choice_area.pack(fill="both", expand=True)
            canvas = tk.Canvas(choice_area, bg=self.p["surface"], highlightthickness=0)
            self.choice_canvas = canvas
            scroll = ttk.Scrollbar(choice_area, command=canvas.yview)
            canvas.pack(side="left", fill="both", expand=True)
            canvas.configure(yscrollcommand=scroll.set)
            choices_frame = ttk.Frame(canvas, style="Surface.TFrame")
            window = canvas.create_window(0, 0, window=choices_frame, anchor="nw")
            choices_frame.columnconfigure((0, 1), weight=1, uniform="choice")
            def resize(e):
                canvas.itemconfigure(window, width=e.width)
            canvas.bind("<Configure>", resize)
            def update_choices_scroll(_e=None):
                canvas.configure(scrollregion=canvas.bbox('all'))
                overflow = choices_frame.winfo_reqheight() > canvas.winfo_height()+2
                if overflow and not scroll.winfo_manager(): scroll.pack(side='right', fill='y', before=canvas)
                elif not overflow and scroll.winfo_manager(): scroll.pack_forget()
            choices_frame.bind("<Configure>", update_choices_scroll)
            canvas.bind('<Configure>', update_choices_scroll, add='+')
            self.choice_cards = []
            for i, choice in enumerate(q["choices"]):
                item = ChoiceCard(choices_frame, self, choice, i)
                item.grid(row=i // 2, column=i % 2, sticky="nsew", padx=5, pady=6)
                self.choice_cards.append(item)
            self.choice_var.trace_add("write", lambda *_: [c.draw() for c in self.choice_cards if c.winfo_exists()])

        ttk.Button(nav, text="Menu", style="Card.TButton", command=self.quit_to_home).pack(side="left")
        ttk.Button(nav, text="Valider et continuer  →",
                   style="Card.Accent.TButton",
                   command=self.next_question).pack(side="right")
        if len(getattr(self, "history", [])) > 1:
            ttk.Button(nav, text="←  Précédent", style="Card.TButton",
                       command=self.prev_question).pack(side="right", padx=8)

        hint = ("Entrée : valider   •   Maj + Entrée : saut de ligne"
                if q["type"] == "free"
                else "↑ ↓ : choisir   •   1-9 : raccourci   •   Entrée : valider")
        ttk.Label(self.container, text=hint, style="Muted.TLabel").pack(anchor="w", pady=(14, 0))

        self.mode = "question"
        self.focus_question()

    def focus_question(self):
        """Place le focus clavier pour que Entrée et les flèches fonctionnent."""
        if self.questions[self.current]["type"] == "free":
            self.free_text.focus_set()
        else:
            self.container.focus_set()

    # ----- Raccourcis clavier -----
    def on_return(self, _event=None):
        if self.mode != "question" or self.mode_compact:
            return None
        self.next_question()
        return "break"

    def on_arrow(self, step):
        """Flèches haut/bas : change le choix des questions à réponses prédéfinies."""
        if self.mode != "question" or self.mode_compact:
            return None
        q = self.questions[self.current]
        if q["type"] != "choice":
            return None            # réponse libre : les flèches déplacent le curseur
        n = len(q["choices"])
        current = self.choice_var.get()
        if current < 0:
            new = 0 if step > 0 else n - 1
        else:
            new = (current + step) % n
        self.choice_var.set(new)
        return "break"

    def on_key(self, event):
        """Touches 1 à 9 : sélection directe d'une réponse."""
        if self.mode != "question" or self.mode_compact:
            return None
        q = self.questions[self.current]
        if q["type"] != "choice" or not event.char or event.char not in "123456789":
            return None
        index = int(event.char) - 1
        if index < len(q["choices"]):
            self.choice_var.set(index)
            return "break"
        return None

    def read_current(self):
        """Réponse saisie à l'écran : texte (libre), index (choix) ou None."""
        q = self.questions[self.current]
        if q["type"] == "free":
            value = self.free_text.get("1.0", "end").strip()
            return value or None
        index = self.choice_var.get()
        return index if index >= 0 else None

    def store_current(self):
        value = self.read_current()
        if value is None:
            self.answers.pop(self.current, None)
        else:
            self.answers[self.current] = value
        return value

    def next_question(self):
        q = self.questions[self.current]
        value = self.store_current()
        if value is None and q["required"]:
            self.warn("Réponse manquante",
                      "Veuillez saisir une réponse." if q["type"] == "free"
                      else "Veuillez choisir une réponse.")
            self.focus_question()
            return
        try:
            target = next_index(self.questions, self.current, value, self.history)
        except ValueError as err:
            self.warn("Parcours invalide", str(err))
            return
        if target is None:
            self.show_result()
            return
        self.current = target
        self.history.append(target)
        self.show_form()

    def show_form(self):
        try:
            from diagnostic_form import visible_path
            visible_path(self.questions, self.answers, next_index, self.skipped)
        except ValueError as err:
            self.warn("Parcours invalide", str(err))
            return
        self.clear()
        self.set_screen("question", "Formulaire")
        self.form = DiagnosticForm(self.container, self, next_index)
        self.form.pack(fill="both", expand=True)
        self.mode = "form"

    def prev_question(self):
        if len(getattr(self, "history", [])) <= 1:
            return
        self.store_current()
        abandoned = self.history.pop()
        self.answers.pop(abandoned, None)
        self.current = self.history[-1]
        self.show_question()

    def diagnostic_engage(self):
        """Vrai dès qu'une réponse a été donnée (choix Windows / Linux compris) :
        quitter avant cela ne fait rien perdre, donc ne demande pas de confirmation."""
        if self.mode == "form":
            return True
        return self.mode == "question" and bool(self.answers or len(self.history) > 1)

    def quit_to_home(self):
        if not self.diagnostic_engage() or self.confirm("Abandonner ?",
                        "Revenir au menu ? Vos réponses seront perdues.",
                        yes="Revenir au menu", no="Rester"):
            self.show_home()

    def answer_text(self, i):
        value = self.answers.get(i)
        if value is None:
            return NOT_ANSWERED
        q = self.questions[i]
        return q["choices"][value] if q["type"] == "choice" else value

    def build_result_text(self):
        recap_lines = []
        values = {q["tag"]: NOT_ANSWERED for q in self.questions}
        for i in self.history:
            q = self.questions[i]
            answer = self.answer_text(i)
            if answer.strip():
                recap_lines.append(f"{len(recap_lines) + 1}. {q['text']}\n   → {answer}")
            values[q["tag"]] = answer
        values["reponses"] = "\n".join(recap_lines)
        template = self.template.strip() or DEFAULT_TEMPLATE
        return render_template(template, values)

    def show_result(self):
        self.clear()
        self.set_screen("question", "Synthèse")
        self.result_text = self.build_result_text()

        panel = RoundedPanel(self.container, self, padding=24)
        panel.pack(fill="both", expand=True)
        card = panel.body
        self.result_panel = panel
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)
        ttk.Label(card, text="Votre message", style="Card.H2.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Il est prêt à être copié et collé où vous le souhaitez.",
                  style="Card.Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 12))

        box = ttk.Frame(card, style="Surface.TFrame")
        box.grid(row=2, column=0, sticky="nsew")
        text = self.make_text(box, height=1, width=1)
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", self.result_text)
        text.configure(state="disabled")
        text._documentation_content=True
        self.paint(text)

        bar = ttk.Frame(card, style="Surface.TFrame")
        bar.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.result_buttons = [
            ttk.Button(bar, text="Copier le message", style="Card.Accent.TButton", command=self.copy_result),
            ttk.Button(bar, text="Modifier les réponses", style="Card.TButton", command=self.show_form),
            ttk.Button(bar, text="Recommencer", style="Card.TButton", command=self.start_user),
            ttk.Button(bar, text="Menu", style="Card.TButton", command=self.show_home),
        ]
        def arrange_actions(event=None):
            width = event.width if event else bar.winfo_width()
            required = sum(button.winfo_reqwidth()+10 for button in self.result_buttons)
            columns = 4 if width >= required else 2
            for col in range(4):
                bar.columnconfigure(col, weight=1 if col < columns else 0, uniform="actions" if col < columns else "")
            for index, button in enumerate(self.result_buttons):
                button.grid(row=index//columns, column=index%columns, sticky="ew", padx=4, pady=4)
        bar.bind('<Configure>', arrange_actions)
        arrange_actions()
        self.copy_msg = tk.StringVar()
        ttk.Label(card, textvariable=self.copy_msg,
                  style="Card.Ok.TLabel").grid(row=4, column=0, sticky="w")

    def copy_result(self):
        self.clipboard_clear()
        self.clipboard_append(self.result_text)
        self.update()  # garde le contenu dans le presse-papiers
        self.copy_msg.set("Copié ✔")
        self.after(2000, lambda: self.copy_msg.set(""))

    # ===== Partie administrateur =====
    def open_admin(self):
        if getattr(self, "screen", None) == "admin" or not self.autorise("admin"):
            return "break"
        credentials = self.ask_password()
        if credentials is None:
            return "break"
        username, password = credentials
        try:
            valid = self.authenticate(username, password)
        except (OSError, ValueError) as err:
            self.error("Connexion impossible", str(err))
            return "break"
        if not valid:
            self.error("Accès refusé", "Utilisateur ou mot de passe incorrect.")
            return "break"
        if self.diagnostic_engage() and not self.confirm("Quitter le diagnostic", "Ouvrir l’éditeur et abandonner les réponses en cours ?", yes="Ouvrir", no="Annuler"):
            return "break"
        data = load_data()
        self.session_user = username
        self.questions = data["questions"]
        self.template = data["template"]
        self.show_admin()
        return "break"

    def authenticate(self, username, password):
        if username == 'admin':
            return bool(ADMIN_PASSWORD) and hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
        if username == 'coordinateur':
            return verify_coordinateur(AUTH_FILE, password, COORDINATEUR_PASSWORD)
        return False

    def change_coordinateur_password(self):
        role = getattr(self, 'session_user', None)
        if role not in ('coordinateur', 'admin'):
            return
        win = Popup(self)
        win.title('Mot de passe coordinateur')
        win.transient(self)
        body = ttk.Frame(win, padding=24)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='Changer le mot de passe coordinateur', style='H2.TLabel').pack(anchor='w')
        fields=[]
        for label in (('Votre mot de passe actuel' if role == 'coordinateur' else 'Votre mot de passe administrateur'), 'Nouveau mot de passe', 'Confirmer le nouveau mot de passe'):
            ttk.Label(body, text=label).pack(anchor='w', pady=(14,4))
            field=ttk.Entry(body, show='•', width=42)
            field.pack(fill='x');fields.append(field)
        message=tk.StringVar()
        ttk.Label(body, textvariable=message, style='Muted.TLabel', wraplength=440).pack(anchor='w',pady=12)
        def save():
            current, new, confirmation = [field.get() for field in fields]
            if not new.strip():
                message.set('Saisissez un nouveau mot de passe.');return
            if new != confirmation:
                message.set('Les deux nouveaux mots de passe ne correspondent pas.');return
            try:
                if not self.authenticate(role,current):
                    message.set('Le mot de passe actuel est incorrect.');return
                save_coordinateur_password(AUTH_FILE,new)
            except (OSError, ValueError) as err:
                message.set(str(err));return
            win.destroy()
            self.info('Mot de passe modifié','Le nouveau mot de passe coordinateur sera utilisé à la prochaine connexion.')
        row=ttk.Frame(body);row.pack(fill='x')
        ttk.Button(row,text='Annuler',command=win.destroy).pack(side='left')
        ttk.Button(row,text='Enregistrer',style='Accent.TButton',command=save).pack(side='right')
        win.bind('<Escape>',lambda e:win.destroy())
        win.bind('<Return>',lambda e:save())
        self._center_modal(win)
        fields[0].focus_set()

    def show_admin(self):
        self.clear()
        self.vider_pages()   # la documentation peut être modifiée ici : la reconstruire ensuite
        self.set_screen("admin", "Coordination")
        f = self.container

        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Coordination", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Se déconnecter", command=self.leave_admin).pack(side="right")

        ttk.Label(f, text="Gérez les parcours, les logiciels et les accès depuis cet espace.",
                  style="Muted.TLabel", wraplength=860, justify="left").pack(
            anchor="w", pady=(8, 0))

        notebook = SectionNavigation(f)
        notebook.pack(fill="both", expand=True, pady=(16, 0))
        self.notebook = notebook
        tab_q = ttk.Frame(notebook, padding=(0, 16, 0, 0))
        tab_t = ttk.Frame(notebook, padding=(0, 16, 0, 0))
        notebook.add(tab_q, text="Parcours")
        notebook.add(tab_t, text="Synthèse")
        tab_docs = ttk.Frame(notebook, padding=(0,16,0,0))
        notebook.add(tab_docs, text="Wiki BO")
        self.documentation_editor = Documentation(tab_docs,self,WIKI_BO_FILE,editable=True)
        self.documentation_editor.pack(fill='both',expand=True)
        tab_account = ttk.Frame(notebook, padding=24)
        notebook.add(tab_account, text="Compte")
        ttk.Label(tab_account, text="Mot de passe du coordinateur", style="H2.TLabel").pack(anchor="w")
        ttk.Label(tab_account, text="Modifiez le mot de passe utilisé pour accéder à cet espace.", style="Muted.TLabel").pack(anchor="w", pady=12)
        ttk.Button(tab_account, text="Changer le mot de passe", style="Accent.TButton", command=self.change_coordinateur_password).pack(anchor="w")

        self.parcours_editor = ParcoursEditor(tab_q, self)
        self.parcours_editor.pack(fill="both", expand=True)
        self.build_template_tab(tab_t)
        self.refresh_placeholders()
        notebook.bind("<<NotebookTabChanged>>",
                      lambda _e: self.refresh_placeholders())

    # ----- Onglet Questions -----
    def build_questions_tab(self, tab):
        tab.columnconfigure(0, weight=1, uniform="col")
        tab.columnconfigure(1, weight=2, uniform="col")
        tab.rowconfigure(0, weight=1)

        # Colonne gauche : liste des questions
        left = ttk.LabelFrame(tab, text=" Questions ", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.listbox = self.make_listbox(list_frame)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(12, 0))
        ttk.Button(btns, text="↑", width=3,
                   command=lambda: self.move(-1)).pack(side="left")
        ttk.Button(btns, text="↓", width=3,
                   command=lambda: self.move(1)).pack(side="left", padx=6)
        ttk.Button(btns, text="Supprimer", style="Danger.TButton",
                   command=self.delete_q).pack(side="right")

        # Colonne droite : formulaire
        right = ttk.LabelFrame(tab, text=" Détail de la question ", padding=14)
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(right, text="Intitulé de la question").pack(anchor="w")
        self.q_entry = ttk.Entry(right)
        self.q_entry.pack(fill="x", pady=(4, 12))

        ttk.Label(right, text="Nom court pour le modèle (ex : nom, budget)",
                  ).pack(anchor="w")
        ttk.Label(right, text="Laissez vide pour un nom automatique.",
                  style="Muted.TLabel").pack(anchor="w")
        self.tag_entry = ttk.Entry(right)
        self.tag_entry.pack(fill="x", pady=(4, 12))

        type_row = ttk.Frame(right)
        type_row.pack(fill="x", pady=(0, 12))
        self.type_var = tk.StringVar(value="choice")
        ttk.Radiobutton(type_row, text="Réponses prédéfinies", value="choice",
                        variable=self.type_var,
                        command=self.update_type).pack(side="left")
        ttk.Radiobutton(type_row, text="Réponse libre", value="free",
                        variable=self.type_var,
                        command=self.update_type).pack(side="left", padx=12)
        self.req_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Réponse obligatoire",
                        variable=self.req_var).pack(anchor="w", pady=(0, 10))

        ttk.Label(right, text="Réponses possibles (une par ligne)").pack(anchor="w")
        ttk.Label(right, text="Puis « Choisir la suite… » pour relier chaque réponse à une question.",
                  style="Muted.TLabel", wraplength=460).pack(anchor="w")
        self.c_text = self.make_text(right, height=4)
        self.c_text._grey_when_disabled = True
        self.c_text.pack(fill="both", expand=True, pady=(4, 14))

        row = ttk.Frame(right)
        row.pack(fill="x")
        ttk.Button(row, text="Nouvelle",
                   command=self.new_q).pack(side="left")
        ttk.Button(row, text="Choisir la suite…",
                   command=self.edit_routes).pack(side="left", padx=8)
        ttk.Button(row, text="Enregistrer", style="Accent.TButton",
                   command=self.save_q).pack(side="right")

    def edit_routes(self):
        """Édite et enregistre les destinations de la question en cours."""
        is_choice = self.type_var.get() == "choice"
        choices = ([line.strip() for line in self.c_text.get("1.0", "end").splitlines()
                    if line.strip()] if is_choice else [])
        if is_choice and not choices:
            self.warn("Aucune réponse", "Saisissez d'abord les réponses possibles.")
            return
        win = Popup(self)
        win.title("Choisir la prochaine question")
        win.geometry("780x520")
        win.minsize(600, 400)
        win.configure(bg=self.p["bg"])
        win.transient(self)
        win.grab_set()
        body = ttk.Frame(win, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Après cette réponse, aller vers…", style="H2.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(body, text="Exemple : Linux → diagnostic Linux ; Windows → diagnostic Windows.\nÀ la fin de chaque branche, choisissez « Terminer le diagnostic » ou une question commune.", wraplength=700, justify="left", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        current_id = self.questions[self.selected].get("id") if self.selected is not None and self.selected < len(self.questions) else None
        options = [("Question suivante (ordre)", "")]
        for i, item in enumerate(self.questions):
            if item.get("id") != current_id:
                title = item.get("text", "").replace("\\n", " ")
                if len(title) > 60: title = title[:57] + "…"
                options.append((f"{i + 1}. {title}", item.get("id", "")))
        options.append(("Terminer le diagnostic", "__END__"))
        labels = [x[0] for x in options]
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", side="bottom", pady=(14, 0))
        canvas = tk.Canvas(body, bg=self.p["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        rows = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=rows, anchor="nw")
        rows.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        vars_ = []
        old_routes = align_routes(self.form_choices, self.form_routes, choices)
        destinations = old_routes + [self.form_next]
        row_labels = choices + [("Si aucune réponse (facultative)" if is_choice else "Après la réponse libre")]
        for choice, route in zip(row_labels, destinations):
            row = ttk.Frame(rows)
            row.pack(fill="x", pady=6)
            ttk.Label(row, text=choice, width=28, wraplength=230).pack(side="left", padx=(0, 10))
            var = tk.StringVar()
            if route and route not in [value for _, value in options]:
                options.append((f"Destination supprimée ({route}) — à corriger", route))
                labels = [label for label, _ in options]
            var.set(next((label for label, val in options if val == route), labels[0]))
            ttk.Combobox(row, textvariable=var, values=labels, state="readonly").pack(side="left", fill="x", expand=True)
            vars_.append(var)
        def apply():
            mapping = {label: val for label, val in options}
            self.form_choices = list(choices)
            self.form_routes = [mapping[v.get()] for v in vars_[:-1]]
            self.form_next = mapping[vars_[-1].get()]
            if self.save_q():
                win.destroy()
        ttk.Button(buttons, text="Annuler", command=win.destroy).pack(side="right")
        ttk.Button(buttons, text="Enregistrer la question et sa suite", style="Accent.TButton", command=apply).pack(side="right", padx=8)

    def persist(self):
        try:
            save_data(self.questions, self.template)
            return True
        except OSError as err:
            self.error("Erreur", f"Impossible d'enregistrer :\n{err}")
            return False

    def update_type(self):
        """Grise la zone des réponses quand la question est à réponse libre."""
        state = "normal" if self.type_var.get() == "choice" else "disabled"
        self.c_text.configure(state=state)
        self.paint(self.c_text)

    def fill_form(self, q=None):
        q = q or {"text": "", "tag": "", "type": "choice",
                  "choices": [], "required": True}
        self.form_choices = list(q["choices"])
        self.form_routes = list(q.get("routes", []))
        self.form_next = q.get("next", "")
        self.q_entry.delete(0, "end")
        self.q_entry.insert(0, q["text"])
        self.tag_entry.delete(0, "end")
        self.tag_entry.insert(0, q["tag"])
        self.type_var.set(q["type"])
        self.req_var.set(q["required"])
        self.c_text.configure(state="normal")
        self.c_text.delete("1.0", "end")
        self.c_text.insert("1.0", "\n".join(q["choices"]))
        self.update_type()

    def refresh_list(self, select=None):
        self.listbox.delete(0, "end")
        for i, q in enumerate(self.questions, start=1):
            t = q["text"]
            t = t if len(t) < 36 else t[:33] + "…"
            self.listbox.insert(
                "end", f" {i}.  {t}" + ("   ✎" if q["type"] == "free" else ""))
        if select is not None and 0 <= select < len(self.questions):
            self.listbox.selection_set(select)
            self.listbox.see(select)
            self.selected = select
            self.fill_form(self.questions[select])
        else:
            self.selected = None
            self.fill_form()

    def on_select(self, _event=None):
        sel = self.listbox.curselection()
        if sel:
            self.selected = sel[0]
            self.fill_form(self.questions[self.selected])

    def new_q(self):
        self.listbox.selection_clear(0, "end")
        self.selected = None
        self.fill_form()
        self.q_entry.focus()

    def save_q(self):
        text = self.q_entry.get().strip()
        qtype = self.type_var.get()
        choices = []
        if qtype == "choice":
            choices = [l.strip() for l in self.c_text.get("1.0", "end").splitlines()
                       if l.strip()]
        if not text:
            self.warn("Question vide", "Saisissez l'intitulé de la question.")
            return
        if qtype == "choice" and len(choices) < 2:
            self.warn("Réponses insuffisantes",
                      "Saisissez au moins deux réponses possibles (une par ligne), "
                      "ou choisissez « Réponse libre ».")
            return
        if len(set(choices)) != len(choices):
            self.warn("Réponses identiques", "Chaque réponse doit avoir un libellé différent pour conserver sa destination.")
            return

        others = {q["tag"] for k, q in enumerate(self.questions)
                  if k != self.selected}
        tag = clean_tag(self.tag_entry.get())
        if not tag:
            tag = next_tag(others)
        elif tag in others or tag in RESERVED_TAGS:
            self.warn("Nom court indisponible",
                      f"Le nom court « {tag} » est déjà utilisé ou réservé. "
                      "Choisissez-en un autre.")
            return

        routes = align_routes(self.form_choices, self.form_routes, choices)
        valid_ids = {q["id"] for i, q in enumerate(self.questions) if i != self.selected}
        if any(route and route != "__END__" and route not in valid_ids
               for route in routes + [self.form_next]):
            self.warn("Destination invalide", "Choisissez une question existante dans « Choisir la suite… ».")
            return
        new_data = {"text": text, "tag": tag, "type": qtype,
                    "choices": choices, "routes": routes, "next": self.form_next,
                    "required": self.req_var.get()}
        previous_questions = [dict(q) for q in self.questions]
        if self.selected is None:
            new_data["id"] = uuid.uuid4().hex[:8]
            self.questions.append(new_data)
            index = len(self.questions) - 1
        else:
            self.questions[self.selected].update(new_data)
            index = self.selected
        if self.persist():
            self.refresh_list(select=index)
            self.refresh_placeholders()
            return True
        self.questions = previous_questions
        return False

    def delete_q(self):
        if self.selected is None:
            self.info("Supprimer", "Sélectionnez d'abord une question.")
            return
        target_id = self.questions[self.selected]["id"]
        incoming = [q["text"] for i, q in enumerate(self.questions)
                    if i != self.selected and (target_id in q.get("routes", [])
                                               or q.get("next") == target_id)]
        if incoming:
            self.warn("Question utilisée dans un parcours",
                      "Modifiez d'abord les destinations des questions suivantes :\n\n" + "\n".join(incoming))
            return
        if not self.confirm("Supprimer", "Supprimer cette question ?",
                            yes="Supprimer", no="Annuler"):
            return
        self.questions.pop(self.selected)
        index = min(self.selected, len(self.questions) - 1)
        if self.persist():
            self.refresh_list(select=index if self.questions else None)
            self.refresh_placeholders()

    def move(self, direction):
        if self.selected is None:
            return
        j = self.selected + direction
        if 0 <= j < len(self.questions):
            self.questions[self.selected], self.questions[j] = (
                self.questions[j], self.questions[self.selected])
            if self.persist():
                self.refresh_list(select=j)

    # ----- Onglet Modèle du message final -----
    def build_template_tab(self, tab):
        ttk.Label(
            tab,
            text=("Rédigez le message remis à l'utilisateur à la fin du questionnaire. "
                  "Les réponses sont insérées grâce à des balises entre accolades, "
                  "par exemple {nom}. La balise {reponses} insère le récapitulatif "
                  "des questions effectivement parcourues."),
            wraplength=860, justify="left").pack(anchor="w")

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=14)
        self.ph_combo = ttk.Combobox(row, state="readonly")
        self.ph_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Insérer la balise",
                   command=self.insert_placeholder).pack(side="left", padx=(10, 0))

        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True)
        self.t_text = self.make_text(box, undo=True)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.t_text.yview)
        self.t_text.configure(yscrollcommand=scroll.set)
        self.t_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.t_text.insert("1.0", self.template or DEFAULT_TEMPLATE)

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(14, 0))
        ttk.Button(bar, text="Modèle par défaut",
                   command=self.reset_template).pack(side="left")
        ttk.Button(bar, text="Aperçu",
                   command=self.preview_template).pack(side="left", padx=8)
        ttk.Button(bar, text="Enregistrer le modèle", style="Accent.TButton",
                   command=self.save_template).pack(side="right")

    def refresh_placeholders(self):
        if not hasattr(self, "ph_combo") or not self.ph_combo.winfo_exists():
            return
        self.ph_items = [("reponses", "Récapitulatif complet de toutes les réponses")]
        self.ph_items += [(q["tag"], q["text"]) for q in self.questions]
        labels = []
        for tag, label in self.ph_items:
            label = label if len(label) < 55 else label[:52] + "…"
            labels.append("{" + tag + "}  -  " + label)
        self.ph_combo.configure(values=labels)
        if labels and self.ph_combo.current() < 0:
            self.ph_combo.current(0)

    def insert_placeholder(self):
        index = self.ph_combo.current()
        if index < 0:
            return
        self.t_text.insert("insert", "{" + self.ph_items[index][0] + "}")
        self.t_text.focus_set()

    def reset_template(self):
        if self.confirm("Modèle par défaut",
                        "Remplacer le texte par le modèle par défaut ?\n"
                        "(Rien n'est enregistré tant que vous ne cliquez pas "
                        "sur « Enregistrer le modèle ».)",
                        yes="Remplacer", no="Annuler"):
            self.t_text.delete("1.0", "end")
            self.t_text.insert("1.0", DEFAULT_TEMPLATE)

    def save_template(self, silent=False):
        """Enregistre le modèle. Renvoie True si c'est fait, False sinon."""
        template = self.t_text.get("1.0", "end").rstrip("\n")
        found = set(re.findall(r"\{(\w+)\}", template))
        if not found:
            if not self.confirm(
                    "Aucune balise",
                    "Votre modèle ne contient aucune balise : les réponses "
                    "n'apparaîtront pas dans le message final.\n\n"
                    "Enregistrer quand même ?",
                    yes="Enregistrer", no="Annuler"):
                return False
        known = {clean_tag(tag) for tag, _ in self.ph_items}
        unknown = sorted(u for u in found if clean_tag(u) not in known)
        if unknown:
            names = ", ".join("{" + u + "}" for u in unknown)
            if not self.confirm(
                    "Balises inconnues",
                    f"Ces balises ne correspondent à aucune question :\n{names}\n\n"
                    "Elles apparaîtront telles quelles dans le message final.\n"
                    "Enregistrer quand même ?",
                    yes="Enregistrer", no="Annuler"):
                return False
        self.template = template
        if not self.persist():
            return False
        if not silent:
            self.info("Modèle", "Modèle enregistré.")
        return True

    def preview_template(self):
        """Affiche le modèle avec des réponses d'exemple."""
        template = self.t_text.get("1.0", "end").strip() or DEFAULT_TEMPLATE
        values, recap = {}, []
        for i, q in enumerate(self.questions, start=1):
            sample = f"[réponse « {q['tag']} »]"
            values[q["tag"]] = sample
            recap.append(f"{i}. {q['text']}\n   → {sample}")
        values["reponses"] = "\n".join(recap) or "(aucune question)"

        win = Popup(self)
        win.title("Aperçu du message final")
        win.configure(bg=self.p["bg"])
        win.geometry("700x520")
        win.transient(self)
        body = ttk.Frame(win, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Aperçu du message final",
                  style="H2.TLabel").pack(anchor="w", pady=(0, 12))
        txt = self.make_text(body)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", render_template(template, values))
        txt.configure(state="disabled")

    def leave_admin(self):
        """Quitte l'admin en proposant d'enregistrer un modèle modifié."""
        current = self.t_text.get("1.0", "end").rstrip("\n")
        if current != (self.template or DEFAULT_TEMPLATE):
            answer = self.confirm3(
                "Modèle non enregistré",
                "Le modèle du message final a été modifié mais pas enregistré.\n\n"
                "L'enregistrer avant de quitter ?")
            if answer is None:
                return
            if answer and not self.save_template(silent=True):
                return
        self.show_home()


if __name__ == "__main__":
    app = App()
    if app.session is not None:
        app.mainloop()
