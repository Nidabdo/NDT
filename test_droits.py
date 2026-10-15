"""Droits d'accès : règles d'acces.py, sessions et filtrage de l'interface."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import droits
import outils_poste
from connexion import message_erreur
from test_routes import ndt


def config(**changes):
    valeurs = dict(
        PROFILS={"Minimal": ["accueil", "diagnostic"],
                 "Docs": ["documentation"],
                 "Support": ["accueil", "diagnostic", "documentation", "outils"]},
        UTILISATEURS={"GRE - Infogerance_BT - Admin": "Support", "RG768446": "Docs", "A-RG768446": "Support"},
        PROFIL_PAR_DEFAUT="Minimal",
        AUTORISER_BYPASS=True,
    )
    valeurs.update(changes)
    return SimpleNamespace(**valeurs)


class RegleTest(unittest.TestCase):
    def ecrans(self, login, groupes=()):
        return droits.ecrans_autorises(login, groupes, config())

    def test_login_et_groupe_souples(self):
        attendu = {"accueil", "documentation"}
        for login in ("RG768446", "rg768446", "INTRA\\RG768446", "  RG768446 "):
            with self.subTest(login=login):
                self.assertEqual(self.ecrans(login)[0], attendu)
        ecrans, profils = self.ecrans("XY1", ["INTRA\\gre - infogerance_bt  - ADMIN"])
        self.assertIn("outils", ecrans)
        self.assertEqual(profils, ("Support",))

    def test_compte_a_distinct(self):
        self.assertNotIn("outils", self.ecrans("RG768446")[0])
        self.assertIn("outils", self.ecrans("A-RG768446")[0])

    def test_union_et_defaut(self):
        ecrans, profils = self.ecrans("RG768446", ["Autre groupe", "GRE - Infogerance_BT - Admin"])
        self.assertEqual(set(profils), {"Docs", "Support"})
        self.assertEqual(ecrans, {"accueil", "diagnostic", "documentation", "outils"})
        self.assertEqual(self.ecrans("inconnu", ["Utilisateurs"]), (frozenset({"accueil", "diagnostic"}), ("Minimal",)))

    def test_accueil_toujours_present(self):
        self.assertIn("accueil", self.ecrans("RG768446")[0])

    def test_bypass_donne_tout(self):
        session = droits.session_bypass()
        self.assertTrue(session.bypass)
        self.assertIsNone(session.mot_de_passe)
        self.assertEqual(session.ecrans, set(droits.ECRANS + droits.DROITS))
        self.assertTrue(session.autorise("scripts_edition"))
        self.assertTrue(session.autorise("admin"))


class ConfigTest(unittest.TestCase):
    def test_configuration_livree_valide(self):
        droits.verifier_config()

    def test_erreurs_explicites(self):
        cas = {
            "Écrans possibles": config(PROFILS={"Minimal": ["accueil", "diagnostique"]}, UTILISATEURS={}),
            "Droits possibles": config(PROFILS={"Minimal": ["accueil", "script_edition"]}, UTILISATEURS={}),
            "profil": config(UTILISATEURS={"RG1": "Complett"}),
            "PROFIL_PAR_DEFAUT": config(PROFIL_PAR_DEFAUT="Rien"),
            "AUTORISER_BYPASS": config(AUTORISER_BYPASS="oui"),
        }
        for attendu, mauvaise in cas.items():
            with self.subTest(attendu), self.assertRaises(droits.ConfigInvalide) as erreur:
                droits.verifier_config(mauvaise)
            self.assertIn(attendu, str(erreur.exception))

    def test_messages_windows(self):
        self.assertIn("incorrect", message_erreur(OSError(1326, "x")))
        self.assertIn("Bypass", message_erreur(OSError(1311, "x")))
        self.assertIn("verrouillé", message_erreur(OSError(1909, "x")))


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for cible, nom in ((ndt, "SETTINGS_FILE"), (outils_poste, "FICHIER_RECENTS")):
            patcher = patch.object(cible, nom, Path(temp.name) / f"{nom}.json")
            patcher.start()
            self.addCleanup(patcher.stop)

    def ouvrir(self, session):
        app = ndt.App(session=session)
        app.attributes("-alpha", 0)
        self.addCleanup(app.destroy)
        app.update()
        return app

    def test_profil_minimal_filtre_tout(self):
        session = droits.session_ad("RG1", "INTRA", "secret", [], config())
        app = self.ouvrir(session)
        visibles = {cle for cle, b in app.nav_buttons.items() if b.winfo_manager()}
        self.assertEqual(visibles, {"home", "question"})
        self.assertFalse(app.coordination_btn.winfo_manager())
        app.navigate("outils")
        self.assertEqual(app.screen, "home")
        with patch.object(app, "ask_password") as demander:
            app.open_admin()
        demander.assert_not_called()
        self.assertEqual(app.compte_poste, ("RG1", "secret"))

    def test_bypass_tout_visible_et_signale(self):
        app = self.ouvrir(droits.session_bypass())
        self.assertTrue(all(b.winfo_manager() for b in app.nav_buttons.values()))
        self.assertTrue(app.coordination_btn.winfo_manager())
        self.assertIn("BYPASS", app.title())
        self.assertIsNone(app.compte_poste)

    def test_outils_poste_utilise_le_compte_du_lancement(self):
        session = droits.session_ad("RG1", "INTRA", "secret", [], config(PROFIL_PAR_DEFAUT="Support"))
        app = self.ouvrir(session)
        app.navigate("outils")
        ecran = app.outils_poste
        self.assertIn("INTRA\\RG1", ecran.var_compte.get())
        self.assertFalse(ecran.bouton_connexion.winfo_manager())


if __name__ == "__main__":
    unittest.main()
