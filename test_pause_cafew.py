"""Accueil Pause Cafew : données, recherche SMAX, tuiles, équipes."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import droits
import outils_poste
import pause_cafew
from pause_cafew import DonneesInvalides, initiales, url_recherche, verifier_donnees
from test_routes import ndt


def donnees(**changes):
    valeurs = dict(
        OUTILS=[{"nom": "SMAX", "url": "https://smax.example/", "image": "smaxlogo.png"}],
        EQUIPES={"Equipe": [{"nom": "Lien", "url": "https://lien.example/", "image": None}]},
        RECHERCHE_SMAX={"Ticket": "https://smax.example/Request/{numero}/general"},
    )
    valeurs.update(changes)
    return SimpleNamespace(**valeurs)


class DonneesTest(unittest.TestCase):
    def test_donnees_livrees_valides(self):
        verifier_donnees()

    def test_erreurs_explicites(self):
        cas = {
            "https://": donnees(OUTILS=[{"nom": "X", "url": "intranet/x", "image": None}]),
            "absente": donnees(OUTILS=[{"nom": "X", "url": "https://x/", "image": "inexistante.png"}]),
            "nom": donnees(EQUIPES={"E": [{"nom": " ", "url": "https://x/", "image": None}]}),
            "{numero}": donnees(RECHERCHE_SMAX={"Ticket": "https://smax.example/Request/"}),
        }
        for attendu, mauvaises in cas.items():
            with self.subTest(attendu), self.assertRaises(DonneesInvalides) as erreur:
                verifier_donnees(mauvaises)
            self.assertIn(attendu, str(erreur.exception))

    def test_url_recherche(self):
        config = donnees()
        self.assertEqual(url_recherche("Ticket", " 123 ", config), "https://smax.example/Request/123/general")
        self.assertEqual(url_recherche("Ticket", "a b/c", config), "https://smax.example/Request/a%20b%2Fc/general")
        self.assertIsNone(url_recherche("Ticket", "   ", config))
        self.assertIsNone(url_recherche("Inconnu", "1", config))
        self.assertIn("/Incident/42/", url_recherche("Incident", "42"))

    def test_initiales(self):
        self.assertEqual(initiales("Ticket POST"), "TP")
        self.assertEqual(initiales("IC-BKL-02"), "IB")


class AccueilTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.reglages = Path(temp.name) / "settings.json"
        for cible, nom, valeur in ((ndt, "SETTINGS_FILE", self.reglages),
                                   (outils_poste, "FICHIER_RECENTS", Path(temp.name) / "r.json")):
            patcher = patch.object(cible, nom, valeur)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = ndt.App(session=droits.session_bypass())
        self.app.attributes("-alpha", 0)
        self.addCleanup(self.app.destroy)
        self.app.update()
        self.accueil = self.app.pause_cafew

    def test_grille_et_colonnes(self):
        self.assertEqual(len(self.accueil.tuiles), len(pause_cafew.donnees.OUTILS))
        colonnes = {}
        for taille in ("1180x800", "800x600"):
            self.app.geometry(taille)
            self.app.update()
            colonnes[taille] = self.accueil.colonnes
            self.assertTrue(all(t.winfo_manager() == "grid" for t in self.accueil.tuiles))
        self.assertGreater(colonnes["1180x800"], colonnes["800x600"])

    def test_tuile_et_recherche_ouvrent_le_lien(self):
        with patch.object(pause_cafew, "ouvrir_url") as ouvrir:
            self.accueil.tuiles[0].ouvrir()
            ouvrir.assert_called_once_with(pause_cafew.donnees.OUTILS[0]["url"])
            ouvrir.reset_mock()
            self.accueil.var_type.set("Incident")
            self.accueil.var_numero.set("4242")
            self.assertEqual(self.accueil.rechercher(), "break")
            self.assertIn("/Incident/4242/", ouvrir.call_args.args[0])
            self.assertEqual(self.accueil.var_numero.get(), "")
            ouvrir.reset_mock()
            self.accueil.rechercher()   # numéro vide : rien n'est ouvert
            ouvrir.assert_not_called()

    def test_equipe_memorisee_et_pagination(self):
        def tuiles_affichees():
            return [w.lien["nom"] for w in self.accueil.piste.winfo_children()]
        coordination = pause_cafew.donnees.EQUIPES["Coordination"]
        self.accueil.var_equipe.set("Coordination")
        self.accueil._changer_equipe()
        self.assertEqual(json.loads(self.reglages.read_text(encoding="utf-8"))["cafew_equipe"], "Coordination")
        self.assertEqual(tuiles_affichees(), [l["nom"] for l in coordination[:4]])
        self.accueil._tourner(1)
        self.assertEqual(tuiles_affichees(), [l["nom"] for l in coordination[4:8]])
        self.accueil._tourner(1)   # retour au début, comme le carrousel
        self.assertEqual(tuiles_affichees(), [l["nom"] for l in coordination[:4]])
        self.accueil.var_equipe.set("Back Office")
        self.accueil._changer_equipe()
        self.assertTrue(self.accueil.bouton_suiv.instate(["disabled"]))
        self.app.show_home()   # l'équipe choisie est retrouvée
        self.assertEqual(self.app.pause_cafew.var_equipe.get(), "Back Office")

    def test_changement_de_theme(self):
        for _ in range(2):
            self.app.toggle_theme()
            self.app.update()
        self.assertEqual(self.accueil.canvas.cget("bg"), self.app.p["bg"])


if __name__ == "__main__":
    unittest.main()
