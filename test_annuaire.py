"""Vérification des comptes par l'annuaire : sans ouvrir de session sur le poste local."""
import unittest
from unittest.mock import patch

import annuaire
import poste_winapi
from connexion import message_erreur


class AnalyseTest(unittest.TestCase):
    def test_echappement_filtre(self):
        self.assertEqual(annuaire.echapper_filtre("A-RG768446"), "A-RG768446")
        self.assertEqual(annuaire.echapper_filtre("a*b(c)\\d"), "a\\2ab\\28c\\29\\5cd")

    def test_codes_du_controleur(self):
        message = "80090308: LdapErr: DSID-0C09042A, comment: AcceptSecurityContext error, data {}, v4563"
        for data, code in (("52e", 1326), ("775", 1909), ("532", 1330), ("773", 1907), ("533", 1331), ("531", 1329)):
            with self.subTest(data=data):
                self.assertEqual(annuaire.code_depuis_erreur_serveur(message.format(data)), code)
        self.assertIsNone(annuaire.code_depuis_erreur_serveur("autre erreur"))
        self.assertIsNone(annuaire.code_depuis_erreur_serveur(None))

    def test_sid(self):
        octets = bytes([1, 5, 0, 0, 0, 0, 0, 5, 21, 0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0, 0, 0xE9, 3, 0, 0])
        self.assertEqual(annuaire.sid_en_texte(octets), "S-1-5-21-1-2-3-1001")

    def test_messages(self):
        self.assertIn("ce poste", message_erreur(OSError(1385, "x")))
        self.assertIn("expiré", message_erreur(OSError(1793, "x")))


class SessionTest(unittest.TestCase):
    def test_annuaire_utilise_sans_session_locale(self):
        with patch.object(annuaire, "groupes_du_compte", return_value=["GRE - Infogerance_BT - Admin"]), \
             patch.object(poste_winapi, "_logon") as logon:
            self.assertEqual(poste_winapi.ouvrir_session("A-RG1", "INTRA", "x"), ["GRE - Infogerance_BT - Admin"])
        logon.assert_not_called()

    def test_secours_si_annuaire_injoignable(self):
        with patch.object(annuaire, "groupes_du_compte", side_effect=annuaire.AnnuaireInjoignable(1311, "x")), \
             patch.object(poste_winapi, "_logon", return_value="jeton") as logon, \
             patch.object(poste_winapi, "_groupes_du_jeton", return_value=["Local"]), \
             patch.object(poste_winapi._kernel32, "CloseHandle"):
            self.assertEqual(poste_winapi.ouvrir_session("RG1", "INTRA", "x"), ["Local"])
        logon.assert_called_once()

    def test_mot_de_passe_refuse_pas_retente(self):
        with patch.object(annuaire, "groupes_du_compte", side_effect=OSError(1326, "refusé")), \
             patch.object(poste_winapi, "_logon") as logon:
            with self.assertRaises(OSError) as erreur:
                poste_winapi.ouvrir_session("RG1", "INTRA", "faux")
        self.assertEqual(erreur.exception.errno, 1326)
        logon.assert_not_called()   # un seul essai : pas de double comptage du verrouillage

    def test_run_as_identifiants_reseau_uniquement(self):
        appels = []

        def faux(*args):
            appels.append(args)
            return 0
        with patch.object(poste_winapi._advapi32, "CreateProcessWithLogonW", faux), \
             self.assertRaises(OSError):
            poste_winapi.run_as("A-RG1", "INTRA", "x", "CmRcViewer.exe PC1")
        self.assertEqual(appels[0][3], 2)   # LOGON_NETCREDENTIALS_ONLY (runas /netonly)


if __name__ == "__main__":
    unittest.main()
