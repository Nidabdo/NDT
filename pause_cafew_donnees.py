# =====================================================================
#  PAUSE CAFEW — LES LIENS DE LA PAGE D'ACCUEIL
# =====================================================================
#
#  Ce fichier décide des tuiles affichées sur l'accueil de NDT.
#  Après une modification, il faut recompiler l'exécutable.
#
#  Règles d'écriture (sinon NDT affiche une erreur au lancement) :
#    - chaque texte est entre guillemets : "comme ceci"
#    - chaque ligne d'une liste se termine par une virgule
#    - "image" : nom d'un fichier du dossier img_cafew (ou None : initiales)
# =====================================================================


# ---------------------------------------------------------------------
#  1. LES OUTILS : la grande grille de l'accueil, dans l'ordre affiché.
# ---------------------------------------------------------------------
OUTILS = [
    {"nom": "SMAX", "url": "https://gre-smax.intra.cea.fr/saw/cti?ctiUniqueId=24004&from=menu&TENANTID=852315340", "image": "smaxlogo.png"},
    {"nom": "Oscar", "url": "https://gre-oscar-v2.intra.cea.fr/dashboard", "image": "oscar.png"},
    {"nom": "Anamu", "url": "https://anamu.intra.cea.fr/index.php", "image": "anamu.png"},
    {"nom": "Vlan Bat", "url": "https://gre-infogerance-se.intra.cea.fr/infodoc/Infogerance/Service%20Desk/Batiment-IP.xls?Web=1", "image": "anamuip.png"},
    {"nom": "Quota", "url": "https://gre-powerbi.intra.cea.fr/Reports/report/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/AdministrationSSRS/2020_Quota_Report_Isilon", "image": "quota.png"},
    {"nom": "Déblocage Badge", "url": "https://cms-igc.intra.cea.fr/devices/", "image": "inca.png"},
    {"nom": "Console Deleg", "url": "https://gre-console-delegation.intra.cea.fr/", "image": "console_delegation.png"},
    {"nom": "DEFI", "url": "https://gre-workflowgen.intra.cea.fr/wfgen/show.aspx?QUERY=CONTEXT&REQUEST_QUERY=PROCESS_INSTANCE_REQUESTED_LIST&FILTER_PROCESSID=-1&ID_USER_DELEGATOR=-1", "image": "defi.png"},
    {"nom": "AAAWeb", "url": "https://www-mobipass/4tress-aaa/helpdesk/login", "image": "aaa.png"},
    {"nom": "CMDB", "url": "https://gre-cmdb.intra.cea.fr/", "image": "cmdb.png"},
    {"nom": "Sigma", "url": "https://espacesigma.cea.fr/idp/", "image": "sigma.png"},
    {"nom": "Backlog", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Backlog/Backlog%20CEA", "image": "backlog.png"},
    {"nom": "Info PC", "url": "https://siri.intra.cea.fr/Reports_SIRI/Pages/Report.aspx?ItemPath=/Infogerance/SOGETI/SCCM/Information+PC", "image": "info_pc.png"},
    {"nom": "JSP", "url": "https://siri.intra.cea.fr/Reports_SIRI/Pages/Report.aspx?ItemPath=/Infogerance/SOGETI/SCCM/Information+Add+Remove+Program+PC", "image": "info_logiciels.png"},
    {"nom": "Exchange", "url": "https://mail.intra.cea.fr/ecp", "image": "exchange.png"},
    {"nom": "InfoDoc", "url": "https://gre-infogerance-se.intra.cea.fr/infodoc/SitePages/Accueil.aspx", "image": "infodoc.png"},
]


# ---------------------------------------------------------------------
#  2. LES ÉQUIPES : choisies dans la liste sous la grille (le choix est
#     mémorisé). Une équipe = un nom, puis ses liens.
# ---------------------------------------------------------------------
EQUIPES = {
    "Bureau technique": [
        {"nom": "WIKI BT", "url": "https://gre-mediawiki.intra.cea.fr/", "image": "wikibt.png"},
        {"nom": "PLANNIF", "url": "https://gre-rdvinstallation.intra.cea.fr/backend", "image": "rdv.png"},
    ],
    "Back Office": [
        {"nom": "Plannification", "url": "https://gre-rdvinstallation-bo.intra.cea.fr/user/login", "image": "rdv.png"},
        {"nom": "Ticket POST", "url": "https://post.intra.cea.fr/", "image": None},
    ],
    "Coordination": [
        {"nom": "Evolution Quotidienne BI", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Backlog/Evolution%20quotidienne%20du%20Backlog", "image": "bi.png"},
        {"nom": "Backlog", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Backlog/Backlog%20CEA", "image": "bi.png"},
        {"nom": "Performance téléphonique", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Centre%20de%20Services/Performance%20t%C3%A9l%C3%A9phonie_v2", "image": "bi.png"},
        {"nom": "IC-BKL-02", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Backlog/IC-BKL-02%20-%20Maitrise%20de%20l%E2%80%99anciennet%C3%A9%20du%20backlog", "image": "bi.png"},
        {"nom": "Power Picker", "url": "https://gre-powerbi.intra.cea.fr/Reports/powerbi/DG-CEAGRE-DPEI-STIC-Infog%C3%A9rant/Services%20transverses/Qualit%C3%A9/%5bBETA%5d%20Power%20Picker", "image": "bi.png"},
    ],
}


# ---------------------------------------------------------------------
#  3. RECHERCHE SMAX : un type, puis l'adresse ; {numero} est remplacé
#     par le numéro saisi.
# ---------------------------------------------------------------------
RECHERCHE_SMAX = {
    "Ticket":   "https://gre-smax.intra.cea.fr/saw/Request/{numero}/general?TENANTID=852315340",
    "Incident": "https://gre-smax.intra.cea.fr/saw/Incident/{numero}/general?TENANTID=852315340",
    "Tâche":    "https://gre-smax.intra.cea.fr/home/task/{numero}/general?TENANTID=852315340",
    "Article":  "https://gre-smax.intra.cea.fr/saw/Article/{numero}/general?TENANTID=852315340",
}
