"""Mode compact : barre façon CS Tools au premier plan, et retour à la fenêtre complète."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import droits
import outils_poste
from test_routes import ndt


class ModeCompactTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for cible, nom, valeur in ((ndt, "SETTINGS_FILE", Path(temp.name) / "s.json"),
                                   (outils_poste, "FICHIER_RECENTS", Path(temp.name) / "r.json")):
            patcher = patch.object(cible, nom, valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ouvrir(self, session=None):
        app = ndt.App(session=session or droits.session_bypass())
        app.attributes("-alpha", 0)
        self.addCleanup(app.destroy)
        app.geometry("1180x800+30+30")
        app.update()
        return app

    def test_aller_retour_conserve_l_ecran(self):
        app = self.ouvrir()
        self.assertTrue(app.compact_btn.winfo_manager())
        app.navigate("documentation")
        documentation = app.documentation
        app.compact_btn.invoke()
        app.update()
        self.assertTrue(app.mode_compact)
        self.assertFalse(app.sidebar.winfo_manager())
        self.assertFalse(app.workspace.winfo_manager())
        self.assertEqual(app.attributes("-topmost"), 1)
        self.assertEqual(list(app.barre_compacte.boutons), ["PMAD", "PING", "BAD", "IP", "C:\\", "D:\\"])
        self.assertLess(app.winfo_height(), 150)
        app.barre_compacte.bouton_agrandir.invoke()
        app.update()
        self.assertFalse(app.mode_compact)
        self.assertIsNone(app.barre_compacte)
        self.assertEqual(app.attributes("-topmost"), 0)
        self.assertTrue(app.sidebar.winfo_manager())
        self.assertEqual(app.geometry(), "1180x800+30+30")
        self.assertEqual(app.screen, "documentation")
        self.assertIs(app.documentation, documentation)   # rien n'a été reconstruit

    def test_reserve_aux_outils_poste(self):
        app = self.ouvrir(droits.Session(login="RG1", ecrans=frozenset({"accueil", "diagnostic"})))
        self.assertFalse(app.compact_btn.winfo_manager())
        app.passer_mode_compact()
        self.assertFalse(app.mode_compact)

    def test_ip_ouvre_le_diagnostic_oscar(self):
        app = self.ouvrir()
        app.passer_mode_compact()
        barre = app.barre_compacte
        barre.var_hote.set("grepc 1234")
        with patch.object(outils_poste, "ouvrir_url") as ouvrir:
            barre.ip()
        ouvrir.assert_called_once_with("https://gre-oscar-v2.intra.cea.fr/amdb/diag_poste?assettag=grepc1234")
        self.assertEqual(barre.recents, ["grepc1234"])
        barre.var_hote.set("10.0.0.1")
        with patch.object(outils_poste, "ouvrir_url") as ouvrir, patch.object(app, "error") as erreur:
            barre.ip()
        ouvrir.assert_not_called()
        erreur.assert_called_once()

    def test_pmad_avec_le_compte_de_la_session(self):
        session = droits.Session(login="RG1", domaine="INTRA", mot_de_passe="secret",
                                 ecrans=frozenset({"accueil", "outils"}))
        app = self.ouvrir(session)
        app.passer_mode_compact()
        barre = app.barre_compacte
        barre.var_hote.set("PC1")
        with patch.object(outils_poste, "resoudre_cible", return_value="PC1-DOCK"), \
             patch.object(outils_poste.os.path, "isfile", return_value=True), \
             patch.object(outils_poste.winapi, "run_as") as run_as:
            self.assertEqual(barre._entree(), "break")   # Entrée = PMAD, comme CS Tools
            limite = time.monotonic() + 5
            while barre._en_cours and time.monotonic() < limite:   # action terminée et affichée
                app.update()
                time.sleep(0.01)
        self.assertEqual(run_as.call_args.args[:3], ("RG1", "INTRA", "secret"))
        self.assertTrue(run_as.call_args.args[3].endswith(" PC1-DOCK"))
        self.assertEqual(barre.var_hote.get(), "PC1-DOCK")

    def test_raccourcis_du_diagnostic_inactifs(self):
        app = self.ouvrir()
        app.mode = "question"
        app.passer_mode_compact()
        self.assertIsNone(app.on_return())
        self.assertIsNone(app.on_arrow(1))


if __name__ == "__main__":
    unittest.main()
