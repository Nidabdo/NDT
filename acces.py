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
#    "accueil"        page d'accueil (toujours visible, même si on l'oublie)
#    "diagnostic"     questionnaire de diagnostic
#    "documentation"  procédures
#    "outils"         outils poste : prise en main, ping, C$ / D$...
#    "coordination"   espace de coordination (demande aussi son mot de passe)
# =====================================================================


# ---------------------------------------------------------------------
#  1. LES PROFILS : un nom de profil, puis la liste des écrans visibles.
#     On peut en ajouter, en retirer ou les renommer.
# ---------------------------------------------------------------------
PROFILS = {
    "Minimal":    ["accueil", "diagnostic"],
    "Technicien": ["accueil", "diagnostic", "documentation"],
    "Support":    ["accueil", "diagnostic", "documentation", "outils"],
    "Complet":    ["accueil", "diagnostic", "documentation", "outils", "coordination"],
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
    "GRE - Infogerance_BT - Admin": "Support",
    "NL767921":   "Complet",
    "RG768446":   "Complet",
    "A-RG768446": "Complet",
}


# ---------------------------------------------------------------------
#  3. PROFIL de ceux qui ne correspondent à aucune ligne ci-dessus.
# ---------------------------------------------------------------------
PROFIL_PAR_DEFAUT = "Minimal"


# ---------------------------------------------------------------------
#  4. CASE « BYPASS » sur la fenêtre de connexion : donne TOUS les écrans
#     sans compte AD, pour travailler hors du domaine INTRA.
#     Mettre False pour la mise en production : la case disparaît.
# ---------------------------------------------------------------------
AUTORISER_BYPASS = True
