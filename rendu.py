"""Formes arrondies lissées (anticrénelage) pour tkinter.

Tk ne lisse ni les polygones du Canvas ni les images dessinées pixel par pixel sous Windows.
Les formes sont donc calculées ici (distance signée au bord, couverture partielle des pixels)
puis chargées en PNG, format géré nativement par Tk 8.6.

Les images sont rendues opaques, déjà fusionnées avec la couleur sur laquelle elles sont posées :
Tk mélange la transparence partielle en logiciel à chaque affichage, ce qui ralentissait
nettement les changements d'écran et de thème.
"""
import base64
import itertools
import math
import struct
import tkinter as tk
import zlib


def _rgb(couleur):
    c = couleur.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _borne(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _distance(px, py, w, h, r):
    """Distance signée au bord d'un rectangle arrondi (0,0)-(w,h) : négative à l'intérieur."""
    qx = abs(px - w / 2) - (w / 2 - r)
    qy = abs(py - h / 2) - (h / 2 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def _png(largeur, hauteur, lignes):
    def bloc(type_, donnees):
        return (struct.pack(">I", len(donnees)) + type_ + donnees
                + struct.pack(">I", zlib.crc32(type_ + donnees) & 0xFFFFFFFF))
    brut = b"".join(b"\x00" + bytes(ligne) for ligne in lignes)
    return (b"\x89PNG\r\n\x1a\n"
            + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 6, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b""))


def png_forme(w, h, r, fill=None, outline=None, width=0, indicator=None, zone=None, fond=None):
    """PNG (base64) d'un rectangle arrondi w×h, rayon r, lissé.

    `zone` = (x0, y0, x1, y1) ne rend qu'une partie de la forme (coins du Canvas).
    `indicator` trace un trait de 3 px qui épouse le bord gauche.
    `fond` : couleur sous la forme ; l'image devient alors opaque.
    """
    x0, y0, x1, y1 = zone or (0, 0, w, h)
    remplissage = _rgb(fill) if fill else None
    contour = _rgb(outline) if outline and width else None
    trait = _rgb(indicator) if indicator else None
    dessous = _rgb(fond) if fond else None
    vide = bytes(dessous) + b"\xff" if dessous else b"\x00\x00\x00\x00"
    plein = bytes(remplissage) + b"\xff" if remplissage else vide
    marge = math.ceil(width if contour else 0) + 1   # pixels touchés par le bord ou son lissage
    debut_plein = marge + (4 if trait else 0)
    lignes = []
    deja = {}   # forme symétrique haut/bas : une ligne et son miroir sont identiques
    for py in range(y0, y1):
        miroir = h - 1 - py
        if miroir in deja:
            lignes.append(deja[miroir])
            continue
        ligne = bytearray()
        bande_centrale = r <= py < h - r
        for px in range(x0, x1):
            # Intérieur franc (loin des bords et des coins) : couleur de fond directe.
            if marge <= py < h - marge and debut_plein <= px < w - marge and (
                    bande_centrale or r <= px < w - r):
                ligne += plein
                continue
            cx, cy = px + 0.5, py + 0.5
            d = _distance(cx, cy, w, h, r)
            exterieur = _borne(0.5 - d)
            interieur = _borne(0.5 - (d + width)) if contour else exterieur
            couleur_int = remplissage
            if trait and remplissage:
                part = _borne(0.5 + _distance(cx - 3, cy, w, h, r))
                couleur_int = tuple(a + (b - a) * part for a, b in zip(remplissage, trait))
            a_int = interieur if couleur_int else 0.0
            a_bord = (exterieur - interieur) if contour else 0.0
            alpha = a_int + a_bord
            if alpha <= 0:
                ligne += vide
                continue
            rgb = [((couleur_int[i] * a_int if couleur_int else 0)
                    + (contour[i] * a_bord if contour else 0)) / alpha for i in range(3)]
            if dessous:
                rgb = [v * alpha + d * (1 - alpha) for v, d in zip(rgb, dessous)]
                alpha = 1.0
            ligne += bytes(int(round(v)) for v in rgb) + bytes([int(round(alpha * 255))])
        deja[py] = ligne
        lignes.append(ligne)
    return base64.b64encode(_png(x1 - x0, y1 - y0, lignes)).decode("ascii")


def _image(widget, cle, fabrique):
    """Images mises en cache sur la fenêtre racine (une image Tk appartient à son interpréteur)."""
    racine = widget._root()
    cache = racine.__dict__.setdefault("_images_lissees", {})
    if cle not in cache:
        cache[cle] = tk.PhotoImage(master=racine, data=fabrique())
    return cache[cle]


# ---------- Canvas ----------
_identifiants = itertools.count()


def _fond_du_canvas(canvas):
    r, g, b = canvas.winfo_rgb(canvas.cget("bg"))
    return f"#{r >> 8:02x}{g >> 8:02x}{b >> 8:02x}"


def rounded(canvas, x, y, w, h, r, fill="", outline="", width=1, tags=()):
    """Rectangle arrondi lissé, posé sur le fond du Canvas (à configurer avant le dessin).

    Renvoie une étiquette commune à tous ses éléments.
    """
    etiquette = f"arrondi{next(_identifiants)}"
    tags = ((tags,) if isinstance(tags, str) else tuple(tags)) + (etiquette,)
    x, y, w, h = round(x), round(y), max(1, round(w)), max(1, round(h))
    r = max(0, min(round(r), w // 2, h // 2))
    epaisseur = round(width) if outline else 0
    fond = _fond_du_canvas(canvas)
    if fill:
        canvas.create_rectangle(x + r, y, x + w - r, y + h, fill=fill, outline="", tags=tags)
        canvas.create_rectangle(x, y + r, x + w, y + h - r, fill=fill, outline="", tags=tags)
    if epaisseur:
        for bord in ((x + r, y, x + w - r, y + epaisseur), (x + r, y + h - epaisseur, x + w - r, y + h),
                     (x, y + r, x + epaisseur, y + h - r), (x + w - epaisseur, y + r, x + w, y + h - r)):
            canvas.create_rectangle(*bord, fill=outline, outline="", tags=tags)
    if r:
        for qx, qy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            zone = (qx * r, qy * r, qx * r + r, qy * r + r)
            image = _image(canvas, ("coin", r, fill, outline, epaisseur, qx, qy, fond),
                           lambda z=zone: png_forme(2 * r, 2 * r, r, fill or None, outline, epaisseur,
                                                    zone=z, fond=fond))
            canvas.create_image(x + qx * (w - r), y + qy * (h - r), image=image, anchor="nw", tags=tags)
    return etiquette


def cercle(canvas, cx, cy, r, fill="", outline="", width=1, tags=()):
    """Cercle lissé centré sur (cx, cy)."""
    taille = round(2 * r)
    fond = _fond_du_canvas(canvas)
    image = _image(canvas, ("cercle", taille, fill, outline, width, fond),
                   lambda: png_forme(taille, taille, taille / 2, fill or None, outline,
                                     width if outline else 0, fond=fond))
    return canvas.create_image(cx, cy, image=image, anchor="center", tags=tags)


# ---------- Boutons ttk ----------
def style_rounded_button(app, name, bg, hover, indicator=None, outline=None):
    """Fond arrondi lissé d'un style de bouton : repos, survol/appui, focus clavier.

    Le fond sous le bouton dépend du style : menu latéral, carte (Card.*) ou fenêtre.
    Les images sont mises à jour sur place au changement de thème, l'élément ttk ne pouvant
    être créé qu'une fois.
    """
    if not hasattr(app, "button_images"):
        app.button_images = {}
    echelle = max(1.0, app.winfo_fpixels("1i") / 96)
    compact = name.startswith(("Sidebar.", "Nav."))
    rayon = round((8 if compact else 10) * echelle)
    trait = max(1, round(echelle))
    bordure = rayon + 2
    taille = 2 * bordure + 4
    if name.startswith("Sidebar."):
        focus = "#70ddc9"
    else:
        focus = app.p["fg"] if bg == app.p["accent"] else app.p["accent"]
    p = app.p
    fond = p["sidebar"] if name.startswith("Sidebar.") else p["surface"] if name.startswith("Card.") else p["bg"]
    rendus = [png_forme(taille, taille, rayon, bg, outline, trait, indicator, fond=fond),
              png_forme(taille, taille, rayon, hover, outline, trait, indicator, fond=fond),
              png_forme(taille, taille, rayon, bg, focus, 2 * trait, indicator, fond=fond)]

    images = app.button_images.get(name)
    if images is None:
        images = [tk.PhotoImage(master=app, data=donnees) for donnees in rendus]
        app.button_images[name] = images
        element = name.replace(".", "") + ".rounded"
        app.style.element_create(element, "image", images[0], ("pressed", images[1]), ("active", images[1]),
                                 ("focus", images[2]), border=bordure, padding=0, sticky="nsew")
        app.style.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
    else:
        for image, donnees in zip(images, rendus):
            image.blank()
            image.configure(data=donnees)
