"""Onglet Relance : modèles, remplissage, envoi Exchange (faux serveur local) et interface."""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import droits
import envoi_mail
import relance
from relance import (MODELES_INITIAUX, ModelesInvalides, charger_modeles, enregistrer_modeles, modeles_du_type,
                     remplir, ticket_valide, variables_a_saisir)
from test_routes import ndt

SUCCES = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
          '<m:CreateItemResponse xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
          '<m:ResponseMessages><m:CreateItemResponseMessage ResponseClass="{classe}">'
          '<m:MessageText>{message}</m:MessageText></m:CreateItemResponseMessage></m:ResponseMessages>'
          '</m:CreateItemResponse></s:Body></s:Envelope>')


class FauxExchange(BaseHTTPRequestHandler):
    classe, message, recu = "Success", "", []

    def do_POST(self):
        FauxExchange.recu.append(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        corps = SUCCES.format(classe=FauxExchange.classe, message=FauxExchange.message).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_):
        pass


class ModelesTest(unittest.TestCase):
    def test_boutons_par_type(self):
        self.assertEqual([m["nom"] for m in modeles_du_type(MODELES_INITIAUX, "assistance")], ["J0", "J2", "J4", "J7"])
        self.assertEqual([m["nom"] for m in modeles_du_type(MODELES_INITIAUX, "service")], ["J0", "J2", "J4", "J7", "J14"])

    def test_variables_et_destinataires(self):
        par_id = {m["id"]: m for m in MODELES_INITIAUX}
        self.assertEqual(variables_a_saisir(par_id["j0"]), ["TELEPHONE"])
        self.assertEqual(variables_a_saisir(par_id["j4-a"]), [])
        self.assertEqual(variables_a_saisir(par_id["j7-a"]), ["DEMANDEUR"])
        self.assertEqual({m["id"] for m in MODELES_INITIAUX if m["destinataire"] == "tiers"}, {"j7-a", "j14-s"})
        self.assertIn("d'ici 3 jours", par_id["j4-a"]["texte"])
        self.assertIn("d'ici 7 jours", par_id["j7-s"]["texte"])

    def test_remplissage(self):
        texte = remplir("Demande {TICKET} au {TELEPHONE} ({AUTRE})", {"TICKET": "123", "TELEPHONE": " 04 "})
        self.assertEqual(texte, "Demande 123 au 04 ({AUTRE})")
        self.assertTrue(ticket_valide(" 12345678 "))
        for invalide in ("", "12a4", "XXXXXXXX"):
            self.assertFalse(ticket_valide(invalide))

    def test_fichier(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "relances.json"
            self.assertEqual(charger_modeles(chemin), MODELES_INITIAUX)
            enregistrer_modeles(chemin, MODELES_INITIAUX[:2])
            self.assertEqual(charger_modeles(chemin), MODELES_INITIAUX[:2])
            mauvais = dict(MODELES_INITIAUX[0], types=["incident"])
            chemin.write_text(json.dumps({"version": 1, "modeles": [mauvais]}), encoding="utf-8")
            with self.assertRaises(ModelesInvalides):
                charger_modeles(chemin)


class EnvoiTest(unittest.TestCase):
    def setUp(self):
        FauxExchange.classe, FauxExchange.message, FauxExchange.recu = "Success", "", []
        self.serveur = HTTPServer(("127.0.0.1", 0), FauxExchange)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur.server_port}/EWS/Exchange.asmx"

    def test_requete_envoyee_a_exchange(self):
        envoi_mail.envoyer(self.url, "prenom.nom@cea.fr", "Relance <J2> – n°1",
                           'Bonjour & "merci"\nligne 2 : é', "csig@cea.fr")
        soap = FauxExchange.recu[0]
        self.assertIn('MessageDisposition="SendAndSaveCopy"', soap)
        self.assertIn("<t:EmailAddress>prenom.nom@cea.fr</t:EmailAddress>", soap)
        self.assertIn("<t:From><t:Mailbox><t:EmailAddress>csig@cea.fr</t:EmailAddress>", soap)
        self.assertIn("<t:Subject>Relance &lt;J2&gt; – n°1</t:Subject>", soap)
        self.assertIn("Bonjour &amp; &quot;merci&quot;\r\nligne 2 : é", soap)

    def test_refus_exchange_remonte(self):
        FauxExchange.classe, FauxExchange.message = "Error", "Vous ne pouvez pas envoyer en tant que csig."
        with self.assertRaises(envoi_mail.EnvoiImpossible) as erreur:
            envoi_mail.envoyer(self.url, "a@cea.fr", "o", "t", "csig@cea.fr")
        self.assertIn("envoyer en tant que csig", str(erreur.exception))

    def test_donnees_hors_ligne_de_commande(self):
        with patch.object(envoi_mail.subprocess, "run") as lancer:
            lancer.return_value.returncode, lancer.return_value.stdout = 0, b"OK\r\n"
            envoi_mail.envoyer("https://ews", "a@cea.fr", "objet $(calc)", "texte", "csig@cea.fr")
        args, kwargs = lancer.call_args
        self.assertNotIn("objet $(calc)", " ".join(args[0]))
        self.assertEqual(json.loads(kwargs["env"]["NDT_MAIL"])["objet"], "objet $(calc)")


class EcranTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for nom, valeur in (("SETTINGS_FILE", Path(temp.name) / "s.json"), ("RELANCES_FILE", Path(temp.name) / "r.json")):
            patcher = patch.object(ndt, nom, valeur)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ouvrir(self, ecrans=None):
        session = droits.session_bypass() if ecrans is None else droits.Session(login="RG1", ecrans=frozenset(ecrans))
        app = ndt.App(session=session)
        app.attributes("-alpha", 0)
        self.addCleanup(app.destroy)
        app.navigate("relance")
        app.update()
        return app

    @staticmethod
    def boutons(ecran):
        return {w.cget("text"): w for w in ecran.ligne_relances.winfo_children() if w.winfo_class() == "TButton"}

    def test_droits(self):
        self.assertEqual(self.ouvrir({"accueil"}).screen, "home")
        app = self.ouvrir({"accueil", "relance"})
        self.assertEqual(app.screen, "relance")
        textes = {str(w.cget("text")) for w in app.relance.winfo_children()[0].body.winfo_children()[0].winfo_children()
                  if w.winfo_class() == "TButton"}
        self.assertNotIn("Gérer les modèles…", textes)

    def test_parcours_et_envoi(self):
        app = self.ouvrir()
        ecran = app.relance
        self.assertEqual(self.boutons(ecran), {})   # aucun bouton avant le choix du type
        ecran.choisir_type("assistance")
        self.assertEqual(list(self.boutons(ecran)), ["J0", "J2", "J4", "J7"])
        self.assertTrue(all(b.instate(["disabled"]) for b in self.boutons(ecran).values()))
        ecran.var_ticket.set("12345678")
        self.assertTrue(all(b.instate(["!disabled"]) for b in self.boutons(ecran).values()))
        ecran.choisir_type("service")
        self.assertEqual(list(self.boutons(ecran)), ["J0", "J2", "J4", "J7", "J14"])
        self.boutons(ecran)["J14"].invoke()
        self.assertTrue(ecran.apercu.winfo_manager())
        self.assertIn("DEMANDEUR", ecran.valeurs)
        ecran.valeurs["DEMANDEUR"].set("Dupont")
        texte = ecran.texte.get("1.0", "end")
        self.assertIn("N°12345678", texte)
        self.assertEqual(texte.count("M. / Mme Dupont"), 2)
        # Adresse invalide : pas d'envoi.
        ecran.adresses["tiers"].set("pas une adresse")
        with patch.object(relance.envoi_mail, "envoyer") as envoyer, patch.object(app, "error") as erreur:
            ecran.envoyer()
        erreur.assert_called_once()
        envoyer.assert_not_called()
        # Envoi confirmé : depuis csig@cea.fr, avec le texte affiché.
        ecran.adresses["tiers"].set("manager@cea.fr")
        with patch.object(relance.envoi_mail, "envoyer") as envoyer, patch.object(app, "confirm", return_value=True):
            ecran.envoyer()
            limite = time.monotonic() + 5
            while "envoyée" not in ecran.statut.get() and time.monotonic() < limite:
                app.update()
                time.sleep(0.01)
        url, destinataire, objet, corps, expediteur, _copie = envoyer.call_args.args
        self.assertEqual((url, destinataire, expediteur), (relance.EWS_URL, "manager@cea.fr", "csig@cea.fr"))
        self.assertIn("12345678", objet)
        self.assertEqual(corps, ecran.texte.get("1.0", "end-1c"))
        self.assertIn("envoyée à manager@cea.fr", ecran.statut.get())

    def test_texte_retouche_conserve(self):
        app = self.ouvrir()
        ecran = app.relance
        ecran.var_ticket.set("42")
        ecran.choisir_type("assistance")
        self.boutons(ecran)["J0"].invoke()
        ecran.texte.insert("end", "\nAjout manuel")
        ecran.texte_modifie = True
        ecran.valeurs["TELEPHONE"].set("0400")
        self.assertIn("Ajout manuel", ecran.texte.get("1.0", "end"))
        ecran.retablir()
        self.assertNotIn("Ajout manuel", ecran.texte.get("1.0", "end"))
        self.assertIn("0400", ecran.texte.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
