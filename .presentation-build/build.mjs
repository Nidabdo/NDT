import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';

const root='C:/Users/nicol/OneDrive/Desktop/NDT';
const tmp=path.join(root,'.presentation-build');
const skill='C:/Users/nicol/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1026-487-0_26.1026.487.0_x64__3k8sg7r9htsxt/dependencies';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#122A3D',green:'#087D72',mint:'#72DFCD',paper:'#F3F7F5',ink:'#172B40',muted:'#5C6E7C',line:'#D9E3DF',white:'#FFFFFF'};
function box(s,x,y,w,h,fill){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}})}
function txt(s,t,x,y,w,h,size=26,color=C.ink,bold=false){const q=box(s,x,y,w,h,'none');q.text=t;q.text.style={typeface:'Segoe UI',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square'};return q;}
function base(title,notes,dark=false){const s=p.slides.add();s.background.fill=dark?C.navy:C.paper;const fg=dark?C.white:C.ink;box(s,64,57,48,5,C.green);txt(s,title,64,85,1145,105,42,fg,true);txt(s,String(p.slides.items.length).padStart(2,'0'),1156,662,60,25,16,dark?C.mint:C.muted);s.speakerNotes.text=notes;return s;}
function benefit(s,text,y=568){box(s,64,y,1152,78,C.green);txt(s,text,86,y+18,1100,46,27,C.white,true);}
function item(s,x,y,w,title,body){txt(s,title,x,y,w,46,29,C.green,true);txt(s,body,x,y+53,w,105,25,C.ink);}
function line(s,x,y,w){box(s,x,y,w,2,C.line)}

// 1. Cover
{
const s=p.slides.add();s.background.fill=C.navy;
box(s,72,72,70,7,C.mint);txt(s,'NDT',72,132,900,155,116,C.white,true);
txt(s,'L’application qui accompagne\nle support informatique',78,319,1080,140,49,C.white,true);
txt(s,'Diagnostic, ressources et actions du quotidien\nPrésentation client',80,537,1050,90,27,C.mint);
s.speakerNotes.text='NDT rassemble plusieurs fonctions utiles au support dans une application Windows. Le fil conducteur de cette présentation est le besoin de l’équipe et la réponse concrète de l’application. Les bénéfices présentés sont qualitatifs, sans mesure de productivité annoncée. Source : NDT v1.py, NAV_ITEMS et modules associés, version du projet consultée le 4 novembre 2026.';
}
// 2. Needs table
{
const s=base('Les besoins couverts au quotidien','Présenter ces besoins comme des usages couverts par NDT, sans affirmer qu’un audit client les a quantifiés. Le diagnostic structure la collecte, le Wiki rend les procédures accessibles, les outils regroupent les accès, les scripts préparent des commandes et les relances réutilisent des modèles. Sources : diagnostic_form.py, documentation.py, outils_poste.py, scripts_bt.py, relance.py.');
const values=[['Besoin de l’équipe','Réponse de NDT'],['Structurer la prise en charge','Diagnostic guidé et synthèse à copier'],['Retrouver les bonnes informations','Wiki BO et accès aux outils métier'],['Accéder aux actions sur un poste','Prise en main, ping et accès distants'],['Préparer les opérations répétitives','Scripts avec variables à renseigner'],['Harmoniser les messages de suivi','Modèles de relance personnalisables']];
const t=s.tables.add({rows:6,columns:2,left:64,top:210,width:1152,height:372,columnWidths:[552,600],values});
t.borders.assign({fill:C.paper,width:2,style:'solid'});
for(let r=0;r<6;r++){t.rows[r].height=62;for(let c=0;c<2;c++){const cell=t.getCell(r,c);cell.fill=r===0?C.navy:r%2?C.white:'#E7EFEC';cell.text.style={typeface:'Segoe UI',fontSize:24,bold:r===0,color:r===0?C.white:C.ink,insets:16,verticalAlignment:'middle'};}}
}
// 3. Diagnosis
{
const s=base('Un diagnostic guidé, une synthèse réutilisable','Le parcours dépend des réponses et peut comporter des champs obligatoires. Les questions et le modèle de synthèse se configurent. La synthèse reprend les réponses du parcours et peut être copiée dans un ticket ou un message. Cette copie reste une action de l’utilisateur : NDT ne met pas automatiquement à jour un ticket SMAX. Sources : NDT v1.py, next_index, build_result_text et copy_result ; diagnostic_form.py.');
const cols=[['01','Qualifier','Les questions s’adaptent\naux réponses données.'],['02','Compléter','Les champs obligatoires\nencadrent la saisie.'],['03','Transmettre','Une synthèse structurée\nest prête à être copiée.']];
cols.forEach(([n,t,b],i)=>{const x=64+i*394;txt(s,n,x,216,200,70,56,C.green,true);line(s,x,307,348);item(s,x,330,345,t,b);});
benefit(s,'Besoin couvert : recueillir les informations utiles de façon homogène');
}
// 4. Resources
{
const s=base('Les ressources utiles réunies dans NDT','Le Wiki BO permet de chercher une fiche logiciel, de consulter son contenu, ses images et ses sources, et d’ouvrir les liens ou répertoires associés. L’accueil Pause Cafew rassemble des outils et des liens par équipe, ainsi qu’un accès à une fiche SMAX par numéro. Les ressources doivent être alimentées et tenues à jour. Sources : documentation.py ; article_images.py ; pause_cafew.py.');
item(s,64,222,520,'Wiki BO','Recherche de fiches logiciel,\nprocédures illustrées et sources\naccessibles depuis la fiche.');
box(s,624,214,2,280,C.line);
item(s,684,222,510,'Accueil Pause Cafew','Liens vers les outils métier,\nressources par équipe et accès\nà une demande SMAX par numéro.');
benefit(s,'Besoin couvert : retrouver une procédure ou un outil au même endroit');
}
// 5. Remote tools
{
const s=base('Les actions sur le poste à portée de main','Le technicien saisit un nom de poste ou une adresse IP. L’application vérifie la disponibilité du poste et, pour un nom de poste, du dock. Elle peut lancer la prise en main SCCM, le bureau à distance, le ping et les partages administratifs. Le mode compact garde une petite barre au premier plan et réutilise les mêmes actions. Les services et les droits réseau doivent être disponibles. Sources : outils_poste.py ; mode_compact.py.');
box(s,64,215,348,310,C.navy);txt(s,'Un poste\nou une adresse IP',88,244,300,110,36,C.white,true);txt(s,'La même cible sert\naux différentes actions.',88,407,290,85,25,C.mint);
item(s,460,215,720,'Vérifier et accéder','Ping, prise en main et bureau à distance.');
item(s,460,343,720,'Intervenir et garder l’accès','Partages C$ / D$, relance du service de prise\nen main et barre compacte au premier plan.');
benefit(s,'Besoin couvert : regrouper les accès techniques pendant l’intervention');
}
// 6. Scripts
{
const s=base('Des scripts préparés pour le bon contexte','Le catalogue propose notamment des scripts Active Directory et accepte plusieurs langages. L’utilisateur sélectionne un script, renseigne ses variables, visualise le résultat puis copie le code. NDT prépare les scripts ; leur exécution a lieu dans l’outil adapté, avec les droits nécessaires. Les droits d’édition permettent de gérer la bibliothèque. Source : scripts_bt.py, variables, segments, copier_rempli et editer.');
txt(s,'Une bibliothèque de commandes\nréutilisables',64,215,600,110,37,C.ink,true);
txt(s,'Exemples : déblocage de compte,\nréinitialisation de mot de passe,\nconsultation des groupes utilisateur.',64,357,610,130,26,C.muted);
const steps=['Choisir un script','Renseigner les variables','Vérifier l’aperçu','Copier le code préparé'];
steps.forEach((t,i)=>{txt(s,String(i+1).padStart(2,'0'),751,216+i*77,60,48,29,C.green,true);txt(s,t,820,218+i*77,380,55,27,C.ink);});
benefit(s,'Besoin couvert : réutiliser une commande sans la réécrire entièrement');
}
// 7. Follow-up
{
const s=base('Des relances cohérentes et personnalisables','L’utilisateur choisit une demande d’assistance ou de service et un modèle adapté à l’étape de relance. Il saisit le numéro de ticket, les destinataires et les informations utiles. Il peut modifier l’objet et le texte avant de déclencher l’envoi par Exchange. Les libellés J0, J2, J4, J7 et J14 servent à choisir un modèle ; ils ne constituent pas une planification automatique. L’envoi nécessite les accès Exchange et les droits sur la boîte partagée. Sources : relance.py ; envoi_mail.py.');
item(s,64,221,340,'Un modèle adapté','Assistance ou service,\nétape de relance et\ndestinataire concerné.');
item(s,470,221,340,'Un message ajusté','Numéro de ticket,\nobjet de contact et\ntexte modifiable.');
item(s,876,221,340,'Un envoi maîtrisé','Relecture du message,\npuis envoi déclenché\npar le technicien.');
txt(s,'Envoi via la messagerie Exchange et la boîte partagée configurée.',64,482,1152,45,24,C.muted);
benefit(s,'Besoin couvert : garder un cadre commun dans les échanges de suivi');
}
// 8. Customization
{
const s=base('Un fonctionnement adaptable aux équipes','Les parcours et le modèle de synthèse sont administrables. Le Wiki, les scripts et les modèles de relance disposent de droits d’édition distincts. Les profils sont attribués selon le compte ou les groupes Active Directory. Le niveau d’accès réel dépend de la configuration. Avant un usage en production, valider cette configuration et désactiver le mode de développement hors domaine actuellement autorisé. Les contenus sont conservés dans des fichiers locaux : organiser leur diffusion et leur sauvegarde. Sources : acces.py ; droits.py ; NDT v1.py ; documentation.py ; scripts_bt.py ; relance.py.');
item(s,64,220,530,'Des contenus ajustables','Questions, parcours, synthèses,\nfiches du Wiki, scripts et modèles\nde relance peuvent évoluer.');
item(s,684,220,530,'Des accès selon les rôles','Les profils déterminent les écrans\net les possibilités d’édition selon\nle compte et les groupes de l’équipe.');
line(s,64,472,1152);txt(s,'L’équipe conserve la responsabilité des procédures et de leur mise à jour.',64,495,1152,48,25,C.muted);
benefit(s,'Besoin couvert : faire évoluer les pratiques dans un cadre commun');
}
// 9. Illustrative journey
{
const s=base('Exemple de prise en charge d’une demande','Scénario illustratif, à adapter au processus du client. Un technicien ouvre la demande SMAX depuis l’accueil, recueille les réponses dans Diagnostic, consulte une procédure dans le Wiki, utilise les outils poste si nécessaire, copie la synthèse dans le ticket et prépare une relance si le demandeur est indisponible. Ce schéma décrit un usage possible, pas une intégration automatique entre tous les modules. Sources : fonctions des modules présentés dans les slides précédentes.');
const steps=[['Accéder à la demande','Retrouver la fiche SMAX depuis l’accueil.'],['Qualifier et consulter','Suivre le diagnostic et consulter la procédure utile.'],['Intervenir sur le poste','Ouvrir les outils techniques selon le besoin.'],['Documenter et suivre','Copier la synthèse et préparer une relance si nécessaire.']];
steps.forEach(([t,b],i)=>{const y=207+i*100;txt(s,String(i+1).padStart(2,'0'),64,y,80,65,42,C.green,true);txt(s,t,174,y,1000,43,29,C.ink,true);txt(s,b,174,y+45,1000,43,25,C.muted);if(i<3)line(s,174,y+91,1042);});
}
// 10. Value and adoption
{
const s=base('Ce que NDT apporte au client','Conclure sur les apports concrets : un cadre de diagnostic commun, des ressources et des accès regroupés, des contenus réutilisables. Les gains de temps ou de qualité restent à mesurer en situation réelle. Pour la mise en service, valider les parcours métier, les profils et les connexions aux services existants, organiser la mise à jour et la diffusion des contenus. Proposition de mesure pour un essai : temps de préparation de synthèse, complétude des informations et retour des techniciens. Ces indicateurs sont des propositions, pas des résultats observés.',true);
const vals=[['Une prise en charge structurée','Questions guidées et synthèse réutilisable.'],['Des ressources plus accessibles','Procédures, outils et actions regroupés.'],['Des pratiques plus homogènes','Scripts et messages fondés sur des modèles communs.']];
vals.forEach(([t,b],i)=>{const y=215+i*104;txt(s,t,64,y,1152,48,33,C.mint,true);txt(s,b,64,y+48,1152,45,26,C.white);});
box(s,64,564,1152,2,'#355366');txt(s,'Pour la mise en service',64,588,360,40,25,C.mint,true);txt(s,'Valider les contenus, les droits et les accès aux services\npuis confirmer les bénéfices sur des cas réels.',444,586,760,74,24,C.white);
}

await fs.writeFile(path.join(tmp,'deck.json'),JSON.stringify(p.toProto()));
await (await PresentationFile.exportPptx(p)).save(path.join(tmp,'candidate.pptx'));
console.log('PPTX exported');
for(let i=0;i<p.slides.items.length;i++){
 const blob=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(tmp,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
 console.log(`Rendered ${i+1}`);
}
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({workspaceDir:root,candidatePath:path.join(tmp,'candidate.pptx'),finalPath:path.join(root,'presentation_client','NDT_Presentation_client.pptx'),pythonExecutable:path.join(runtime,'python/python.exe'),integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','2'],requiredNativeTableOwnerSlides:[2],fontPolicy:{basis:'design',families:['Segoe UI']},verifyArtifactToolImport:true,receiptPath:path.join(tmp,'validation.json')});
console.log(JSON.stringify(result));
