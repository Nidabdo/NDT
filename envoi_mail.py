"""Envoi d'un mail par Exchange (EWS) avec le compte de la session Windows.

Reprend le script Send-Mail-EWS.ps1 : PowerShell gère l'authentification Windows
(-UseDefaultCredentials), ce que Python ne sait pas faire sans bibliothèque externe.
Les données du mail passent par une variable d'environnement (JSON), jamais par la
ligne de commande : aucun caractère saisi ne peut être interprété comme du code.
"""
import json
import os
import subprocess

SCRIPT_EWS = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
function X([string]$s) { [System.Security.SecurityElement]::Escape($s) }
try {
    $m = $env:NDT_MAIL | ConvertFrom-Json
    $expediteur = ''
    $dossier = '<t:DistinguishedFolderId Id="sentitems"/>'
    if ($m.expediteur) {
        $boite = "<t:Mailbox><t:EmailAddress>$(X $m.expediteur)</t:EmailAddress></t:Mailbox>"
        $expediteur = "<t:From>$boite</t:From>"
        if ($m.copie_boite_expediteur) { $dossier = "<t:DistinguishedFolderId Id=`"sentitems`">$boite</t:DistinguishedFolderId>" }
    }
    $copie = ''
    if ($m.copie) { $copie = "<t:CcRecipients><t:Mailbox><t:EmailAddress>$(X $m.copie)</t:EmailAddress></t:Mailbox></t:CcRecipients>" }
    $texte = ([string]$m.texte) -replace "`r?`n", "`r`n"
    $soap = @"
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
 xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
 <soap:Header><t:RequestServerVersion Version="Exchange2013_SP1"/></soap:Header>
 <soap:Body>
  <m:CreateItem MessageDisposition="SendAndSaveCopy">
   <m:SavedItemFolderId>$dossier</m:SavedItemFolderId>
   <m:Items>
    <t:Message>
     <t:Subject>$(X $m.objet)</t:Subject>
     <t:Body BodyType="Text">$(X $texte)</t:Body>
     <t:ToRecipients><t:Mailbox><t:EmailAddress>$(X $m.destinataire)</t:EmailAddress></t:Mailbox></t:ToRecipients>
     $copie
     $expediteur
    </t:Message>
   </m:Items>
  </m:CreateItem>
 </soap:Body>
</soap:Envelope>
"@
    $reponse = Invoke-WebRequest -Uri $m.url -Method Post -ContentType 'text/xml; charset=utf-8' `
        -Headers @{ SOAPAction = 'http://schemas.microsoft.com/exchange/services/2006/messages/CreateItem' } `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($soap)) `
        -UseDefaultCredentials -UseBasicParsing -TimeoutSec 30
    [xml]$xml = $reponse.Content
    $erreurs = @()
    # Exchange répond avec CreateItemResponseMessage : on vérifie tout élément portant ResponseClass.
    foreach ($n in $xml.SelectNodes("//*[@ResponseClass]")) {
        if ($n.GetAttribute('ResponseClass') -ne 'Success') { $erreurs += $n.InnerText.Trim() }
    }
    if ($erreurs.Count -gt 0) { Write-Output ("ERREUR:Exchange a refusé l'envoi : " + ($erreurs -join ' ')); exit 1 }
    Write-Output 'OK'
} catch {
    Write-Output ("ERREUR:" + $_.Exception.Message)
    exit 1
}
'''


class EnvoiImpossible(Exception):
    """L'envoi a échoué ; le message est celui d'Exchange ou de Windows."""


def envoyer(url, destinataire, objet, texte, expediteur="", copie_boite_expediteur=True, delai=60, copie=""):
    """Envoie le mail ; `copie` : adresse en copie (Cc), facultative.
    Lève EnvoiImpossible avec un message lisible en cas d'échec."""
    mail = {"url": url, "destinataire": destinataire, "objet": objet, "texte": texte,
            "expediteur": expediteur, "copie_boite_expediteur": copie_boite_expediteur, "copie": copie}
    env = dict(os.environ, NDT_MAIL=json.dumps(mail, ensure_ascii=False))
    try:
        resultat = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", SCRIPT_EWS],
            env=env, capture_output=True, timeout=delai, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as err:
        raise EnvoiImpossible("Exchange n'a pas répondu à temps.") from err
    except OSError as err:
        raise EnvoiImpossible(f"PowerShell est introuvable : {err}") from err
    sortie = resultat.stdout.decode("utf-8", "replace").strip()
    lignes = [l for l in sortie.splitlines() if l.strip()]
    if resultat.returncode == 0 and lignes and lignes[-1] == "OK":
        return
    erreur = next((l[len("ERREUR:"):] for l in reversed(lignes) if l.startswith("ERREUR:")), None)
    raise EnvoiImpossible(erreur or resultat.stderr.decode("utf-8", "replace").strip()
                          or "Envoi impossible (raison inconnue).")
