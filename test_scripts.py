"""Onglet Scripts : variables, aperçu, fichier, import Pause Cafew et droits."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import droits
import outils_poste
import scripts_bt
from scripts_bt import (ScriptsInvalides, charger_scripts, code_langage, code_rempli, enregistrer_scripts,
                        est_secret, fusionner, libelle_langage, libelle_variable, lire_export_pause_cafew,
                        segments, variables)
from test_routes import ndt

EXPORT = '''// =============================================
//  BT — Scripts internes  (https://exemple, commentaire)
// =============================================
window.SCRIPTS_DATA = [
  {"id": 1, "section": "Réseau", "title": "Ping", "tag": "cmd", "desc": "Teste", "code": "ping {POSTE}"},
  {"id": 2, "section": "Réseau", "title": "Trace", "tag": "", "desc": "", "code": "tracert {POSTE}"}
];
'''


class LogiqueTest(unittest.TestCase):
    def test_variables(self):
        self.assertEqual(variables("{A} {B_1} {A} {minuscule} {2X}"), ["A", "B_1"])
        self.assertEqual(libelle_variable("MOT_DE_PASSE"), "Mot de passe")
        self.assertTrue(est_secret("MOT_DE_PASSE"))
        self.assertFalse(est_secret("UTILISATEUR"))

    def test_apercu_et_remplissage(self):
        code = 'Set-X "{UTILISATEUR}" {QUOTA} {UTILISATEUR}'
        valeurs = {"UTILISATEUR": " rg1 ", "QUOTA": ""}
        self.assertEqual(segments(code, valeurs), [
            ('Set-X "', None), ("rg1", "rempli"), ('" ', None), ("{QUOTA}", "manquant"),
            (" ", None), ("rg1", "rempli")])
        self.assertEqual(code_rempli(code, valeurs), 'Set-X "rg1" {QUOTA} rg1')

    def test_langages(self):
        self.assertEqual(code_langage("PowerShell"), "ps")
        self.assertEqual(code_langage(" Python "), "python")
        self.assertEqual(libelle_langage("bash"), "Bash")
        self.assertEqual(libelle_langage("python"), "PYTHON")
        self.assertEqual(libelle_langage(""), "Autre")

    def test_fichier(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "scripts.json"
            self.assertEqual(len(charger_scripts(chemin)), len(scripts_bt.SCRIPTS_INITIAUX))
            scripts = charger_scripts(chemin)[:2]
            enregistrer_scripts(chemin, scripts)
            self.assertEqual(charger_scripts(chemin), scripts)
            chemin.write_text(json.dumps({"version": 1, "scripts": scripts + scripts[:1]}), encoding="utf-8")
            with self.assertRaises(ScriptsInvalides):
                charger_scripts(chemin)
            chemin.write_text("pas du json", encoding="utf-8")
            with self.assertRaises(ScriptsInvalides):
                charger_scripts(chemin)

    def test_import_pause_cafew(self):
        importes = lire_export_pause_cafew(EXPORT)
        self.assertEqual([(s["titre"], s["langage"], s["code"]) for s in importes],
                         [("Ping", "cmd", "ping {POSTE}"), ("Trace", "", "tracert {POSTE}")])
        self.assertEqual(len({s["id"] for s in importes}), 2)
        tous, ajoutes = fusionner(importes[:1], importes)
        self.assertEqual((len(tous), ajoutes), (2, 1))
        with self.assertRaises(ScriptsInvalides):
            lire_export_pause_cafew("console.log('rien')")


class EcranTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dossier = Path(temp.name)
        self.fichier = self.dossier / "scripts.json"
        for cible, nom, valeur in ((ndt, "SETTINGS_FILE", self.dossier / "settings.json"),
                                   (ndt, "SCRIPTS_FILE", self.fichier),
                                   (outils_poste, "FICHIER_RECENTS", self.dossier / "r.json")):
            patcher = patch.object(cible, nom, valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ouvrir(self, ecrans=None):
        session = droits.session_bypass() if ecrans is None else droits.Session(login="RG1", ecrans=frozenset(ecrans))
        app = ndt.App(session=session)
        app.attributes("-alpha", 0)
        self.addCleanup(app.destroy)
        app.navigate("scripts")
        app.update()
        return app

    def choisir(self, ecran, titre):
        script = next(s for s in ecran.scripts if s["titre"] == titre)
        ecran.liste.selection_set(script["id"])
        return script

    def test_droits(self):
        app = self.ouvrir({"accueil"})
        self.assertEqual(app.screen, "home")
        app = self.ouvrir({"accueil", "scripts"})
        self.assertEqual(app.screen, "scripts")
        self.assertFalse(hasattr(app.scripts_bt, "boutons_edition"))
        app = self.ouvrir()
        self.assertEqual(len(app.scripts_bt.boutons_edition), 4)

    def test_remplir_et_copier(self):
        app = self.ouvrir({"accueil", "scripts"})
        ecran = app.scripts_bt
        self.choisir(ecran, "Réinitialiser un mot de passe")
        self.assertEqual(list(ecran.champs), ["UTILISATEUR", "MOT_DE_PASSE"])
        ecran.champs["UTILISATEUR"].set("rg1")
        with patch.object(app, "confirm", return_value=False) as confirmer:
            app.clipboard_clear()
            app.clipboard_append("avant")
            ecran.copier_rempli()   # mot de passe vide : confirmation refusée, rien n'est copié
        confirmer.assert_called_once()
        self.assertEqual(app.clipboard_get(), "avant")
        ecran.champs["MOT_DE_PASSE"].set("S3cret!")
        ecran.copier_rempli()
        self.assertIn('$user = "rg1"', app.clipboard_get())
        self.assertIn('"S3cret!"', app.clipboard_get())
        self.assertIn("rg1", ecran.apercu.get("1.0", "end"))
        ecran.query.set("debloquer")   # la recherche ignore les accents
        self.assertEqual([s["titre"] for s in ecran.resultats], ["Débloquer un compte"])

    def test_supprimer_et_importer(self):
        app = self.ouvrir()
        ecran = app.scripts_bt
        script = self.choisir(ecran, "Débloquer un compte")
        with patch.object(app, "confirm", return_value=True):
            ecran.supprimer_selection()
        enregistres = charger_scripts(self.fichier)
        self.assertNotIn(script["id"], {s["id"] for s in enregistres})
        export = self.dossier / "scripts-data.js"
        export.write_text(EXPORT, encoding="utf-8")
        with patch.object(scripts_bt.filedialog, "askopenfilename", return_value=str(export)), \
             patch.object(app, "info") as informer:
            ecran.importer()
        self.assertIn("2 script(s) ajouté(s)", informer.call_args.args[1])
        self.assertEqual(len(charger_scripts(self.fichier)), len(enregistres) + 2)


if __name__ == "__main__":
    unittest.main()
