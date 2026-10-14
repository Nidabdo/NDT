"""Outils poste : validation, choix poste/dock et écran, sans réseau ni vrai compte."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import outils_poste
from poste_validation import SaisieInvalide, valider_hote
import droits
from test_routes import ndt


class ValidationTest(unittest.TestCase):
    def test_noms_et_ip(self):
        self.assertEqual(valider_hote("pc-gre 1234"), ("pc-gre1234", "NOM"))
        self.assertEqual(valider_hote("10.0.0.1"), ("10.0.0.1", "IP"))
        for invalide in ("", "1234", "-abc", "1abc", "a.b", "pc_1", "1.2.3", "10.0.0.256"):
            with self.subTest(invalide=invalide), self.assertRaises(SaisieInvalide):
                valider_hote(invalide)


class ResolutionTest(unittest.TestCase):
    def resoudre(self, repondent, hote="PC1", genre="NOM"):
        with patch.object(outils_poste.winapi, "ping", lambda h, _t: 1 if h in repondent else None):
            return outils_poste.resoudre_cible(hote, genre)

    def test_dock_prioritaire(self):
        self.assertEqual(self.resoudre({"PC1", "PC1-DOCK"}), "PC1-DOCK")
        self.assertEqual(self.resoudre({"PC1"}), "PC1")
        self.assertIsNone(self.resoudre(set()))

    def test_ip_sans_dock(self):
        self.assertEqual(self.resoudre({"10.0.0.1"}, "10.0.0.1", "IP"), "10.0.0.1")
        self.assertIsNone(self.resoudre(set(), "10.0.0.1", "IP"))


class EcranTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for cible, valeur in ((ndt, "SETTINGS_FILE"), (outils_poste, "FICHIER_RECENTS")):
            patcher = patch.object(cible, valeur, Path(temp.name) / f"{valeur}.json")
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = ndt.App(session=droits.session_bypass())
        self.app.attributes("-alpha", 0)
        self.addCleanup(self.app.destroy)

    def attendre(self, condition):
        limite = time.monotonic() + 5
        while not condition() and time.monotonic() < limite:
            self.app.update()
            time.sleep(0.01)
        self.assertTrue(condition())

    def test_navigation_et_boutons_sans_compte(self):
        self.app.navigate("outils")
        self.app.update()
        self.assertEqual(self.app.screen, "outils")
        ecran = self.app.outils_poste
        ecran.var_hote.set("PC1")
        with patch.object(self.app, "confirm", return_value=False) as proposer,              patch.object(outils_poste, "resoudre_cible") as resoudre:
            ecran.pmad()  # sans compte blanc : propose la connexion, ne lance rien
        proposer.assert_called_once()
        resoudre.assert_not_called()
        for _ in range(2):  # sombre puis clair : le repeint ne doit pas échouer
            self.app.toggle_theme()
            self.app.update()

    def test_saisie_invalide_affiche_une_erreur(self):
        self.app.navigate("outils")
        ecran = self.app.outils_poste
        ecran.var_hote.set("pc_1")
        with patch.object(self.app, "error") as erreur:
            ecran.bad()
        erreur.assert_called_once()

    def test_prise_en_main_lance_le_viewer_sur_le_dock(self):
        self.app.navigate("outils")
        self.app.compte_poste = ("blanc", "secret")
        ecran = self.app.outils_poste
        ecran._maj_compte()
        ecran.var_hote.set("PC1")
        with patch.object(outils_poste, "resoudre_cible", return_value="PC1-DOCK"), \
             patch.object(outils_poste.os.path, "isfile", return_value=True), \
             patch.object(outils_poste.winapi, "run_as") as run_as:
            ecran.pmad()
            self.attendre(lambda: ecran.var_statut.get().startswith("Prise en main lancée"))
        utilisateur, domaine, mdp, commande = run_as.call_args.args
        self.assertEqual((utilisateur, domaine, mdp), ("blanc", "INTRA", "secret"))
        self.assertIn("CmRcViewer.exe", commande)
        self.assertTrue(commande.endswith(" PC1-DOCK"))
        self.assertEqual(ecran.var_hote.get(), "PC1-DOCK")
        self.assertEqual(ecran.recents, ["PC1-DOCK"])

    def test_poste_injoignable_previent_l_utilisateur(self):
        self.app.navigate("outils")
        ecran = self.app.outils_poste
        ecran.var_hote.set("10.0.0.1")
        with patch.object(outils_poste, "resoudre_cible", return_value=None), \
             patch.object(self.app, "warn") as avertir, \
             patch.object(outils_poste.subprocess, "Popen") as popen:
            ecran.bad()
            self.attendre(lambda: avertir.called)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
