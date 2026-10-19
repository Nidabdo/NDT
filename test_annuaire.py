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


class GroupesTest(unittest.TestCase):
    """Résolution des noms de groupes : recherches LDAP groupées, secours un par un."""

    def test_echappement_sid(self):
        self.assertEqual(annuaire.echapper_sid(bytes([1, 5, 0, 0x15])), "\\01\\05\\00\\15")

    def test_recherches_groupees_par_lots(self):
        sids = [bytes([i]) for i in range(120)]
        filtres = []

        def rechercher(_ld, _base, _portee, filtre, *_attributs):
            filtres.append(filtre)
            return filtre   # le « résultat » transporte le lot, pour la suite simulée

        entrees = {}

        def premiere_entree(_ld, resultat):
            lot = [s for s in sids if f"(objectSid={annuaire.echapper_sid(s)})" in resultat]
            entrees[resultat] = lot
            return (resultat, 0) if lot else None

        def entree_suivante(_ld, entree):
            resultat, i = entree
            return (resultat, i + 1) if i + 1 < len(entrees[resultat]) else None

        with patch.object(annuaire, "_rechercher", rechercher), \
             patch.object(annuaire._ldap, "ldap_first_entry", premiere_entree), \
             patch.object(annuaire._ldap, "ldap_next_entry", entree_suivante), \
             patch.object(annuaire._ldap, "ldap_msgfree", lambda _r: 0), \
             patch.object(annuaire, "_valeurs_binaires", lambda _ld, e, _a: [entrees[e[0]][e[1]]]), \
             patch.object(annuaire, "_valeur_entree", lambda _ld, e, _a: f"G{entrees[e[0]][e[1]][0]}"), \
             patch.object(annuaire, "_nom_du_sid") as un_par_un:
            groupes = annuaire._noms_des_groupes("ld", "DC=intra", sids)
        self.assertEqual(len(filtres), 3)   # 120 groupes : 3 requêtes au lieu de 120
        self.assertEqual(groupes, [f"G{i}" for i in range(120)])
        un_par_un.assert_not_called()

    def test_secours_un_par_un(self):
        with patch.object(annuaire, "_rechercher", side_effect=OSError(5, "refusé")), \
             patch.object(annuaire, "_nom_du_sid", side_effect=lambda s: None if s == b"x" else s.decode()) as un_par_un:
            self.assertEqual(annuaire._noms_des_groupes("ld", "DC=intra", [b"a", b"x", b"b"]), ["a", "b"])
        self.assertEqual(un_par_un.call_count, 3)


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
