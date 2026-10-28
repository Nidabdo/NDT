# =====================================================================
#  NDT — QUI VOIT QUOI
# =====================================================================
#
#  Ce fichier décide quels écrans chaque personne voit dans NDT.
#  Après une modification, il faut recompiler l'exécutable.
#
#  Règles d'écriture (à respecter, sinon NDT affiche une erreur au lancement) :
#    - chaque texte est entre guillemets : "comme ceci"
#    - chaque ligne d'une liste se termine par une virgule
#    - ne pas toucher aux accolades { } ni aux crochets [ ]
#
#  Écrans possibles :
#    "accueil"        Pause Cafew : outils, équipes, recherche SMAX (toujours visible)
#    "diagnostic"     questionnaire de diagnostic
#    "documentation"  Wiki BO (consultation)
#    "outils"         outils poste : prise en main, ping, C$ / D$...
#    "scripts"        scripts du bureau technique (consulter, remplir, copier)
#    "relance"        mails de relance des tickets (J0, J2, J4, J7, J14)
#    "coordination"   espace de coordination (demande aussi son mot de passe)
#
#  Droits possibles (ils se placent dans un profil comme un écran) :
#    "wiki_edition"      ajouter, modifier et supprimer des logiciels du Wiki BO
#    "scripts_edition"   ajouter, modifier et supprimer des scripts
#    "relances_edition"  ajouter, modifier et supprimer des modèles de relance
# =====================================================================


# ---------------------------------------------------------------------
#  1. LES PROFILS : un nom de profil, puis la liste des écrans et droits.
#     On peut en ajouter, en retirer ou les renommer.
# ---------------------------------------------------------------------
PROFILS = {
    "Minimal":    ["accueil", "diagnostic"],
    "FO":         ["accueil", "diagnostic", "documentation", "outils", "relance"],
    "BO":         ["accueil", "diagnostic", "documentation", "outils", "scripts", "relance", "wiki_edition"],
    "Complet":    ["accueil", "diagnostic", "documentation", "outils", "scripts", "relance",
                   "scripts_edition", "relances_edition", "wiki_edition", "coordination"],
}


# ---------------------------------------------------------------------
#  2. QUI A QUEL PROFIL : un groupe AD ou un login, puis le nom du profil.
#
#     - Majuscules / minuscules : sans importance.
#     - "A-RG768446" et "RG768446" sont deux comptes différents :
#       déclarer chacun s'il le faut.
#     - Si une personne correspond à plusieurs lignes (son login et
#       plusieurs groupes), elle voit l'ensemble de leurs écrans.
#     - Seuls les groupes de SÉCURITÉ sont reconnus (pas les listes
#       de distribution).
# ---------------------------------------------------------------------
UTILISATEURS = {
    "LR782730":   "BO",
    "LB771989":   "BO",
    "TC774837":   "BO",
    "RB773612":   "BO",
    "A-LR782730": "BO",
    "A-LB771989": "BO",
    "A-TC774837": "BO",
    "A-RB773612": "BO",
    "NL767921":   "Complet",
    "RG768446":   "Complet",
    "A-RG768446": "Complet",
}


# ---------------------------------------------------------------------
#  3. PROFIL de ceux qui ne correspondent à aucune ligne ci-dessus.
# ---------------------------------------------------------------------
PROFIL_PAR_DEFAUT = "Minimal"


# ---------------------------------------------------------------------
#  4. CASE « BYPASS » sur la fenêtre de connexion : donne TOUS les écrans et droits
#     sans compte AD, pour travailler hors du domaine INTRA.
#     Mettre False pour la mise en production : la case disparaît.
# ---------------------------------------------------------------------
AUTORISER_BYPASS = True
