"""Ouverture des liens web : Edge (navigateur du parc), ou le navigateur par défaut en secours."""
import os
import webbrowser

NAVIGATEUR = "msedge"


def ouvrir_url(url):
    try:
        os.startfile(NAVIGATEUR, arguments=f'"{url}"')
    except OSError:
        webbrowser.open(url)
