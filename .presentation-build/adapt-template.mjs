import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile,FileBlob} from '@oai/artifact-tool';
const root='C:/Users/nicol/OneDrive/Desktop/NDT';
const tmp=root+'/.presentation-build/template';
const source='C:/Users/nicol/Downloads/PowerPoint 2026 Template v5.5 (4).potx';
const skill='C:/Users/nicol/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1026-487-0_26.1026.487.0_x64__3k8sg7r9htsxt/dependencies';
const imported=await PresentationFile.importPptx(await FileBlob.load(source));
const proto=imported.toProto();
const selections=[1,13,14,6,13,20,13,13,18,30];
const originals=proto.slides;
proto.slides=selections.map((n,i)=>({...structuredClone(originals[n-1]),id:'ndt-inetum-'+i,index:i,creationId:undefined}));
// Replace the template's sample footers, including those in unused reusable layouts.
function clean(e){
 if(e.placeholderType==='ftr')e.paragraphs=[{runs:[{text:'© Inetum - NDT - Présentation client'}]}];
 if(e.placeholderType==='dt')e.paragraphs=[{runs:[{text:'04/11/2026'}]}];
 for(const c of e.children??[])clean(c);
}
for(const l of [...proto.layouts,...proto.slides])for(const e of l.elements??[])clean(e);
proto.slides.forEach((s,i)=>{
 s.elements=s.elements.filter(e=>e.placeholderType!=='pic' && !(e.placeholderType==='body'&&[13,14].includes(selections[i])));
 for(const e of s.elements)if(e.placeholderType==='sldNum')e.paragraphs=[{runs:[{text:String(i+1)}]}];
});
const p=Presentation.load(proto);
const old=Presentation.load(JSON.parse(await fs.readFile(root+'/.presentation-build/deck.json','utf8')));
p.slides.items.forEach((s,i)=>s.speakerNotes.text=old.slides.items[i].speakerNotes.text);
const C={navy:'#232D4B',pink:'#E20074',yellow:'#F5F340',grey:'#D3D5DB',white:'#FFFFFF',light:'#F2F2F2'};
function box(s,x,y,w,h,fill){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});}
function style(q,size=26,color=C.navy,bold=false,align='left'){q.text.style={typeface:'Poppins',fontSize:size,color,bold,insets:0,verticalAlignment:'top',autoFit:'none',wrap:'square',alignment:align};return q;}
function txt(s,t,x,y,w,h,size=26,color=C.navy,bold=false){const q=box(s,x,y,w,h,'none');q.text=t;return style(q,size,color,bold);}
function existing(s,id,t,size,color,bold=false){const q=s.shapes.items.find(e=>e.id===String(id));if(!q)throw Error('Missing shape '+id);q.text=t;if(size)style(q,size,color,bold);return q;}
function title(s,id,t,dark=false){const q=existing(s,id,t,36,dark?C.yellow:C.pink);q.position={left:88,top:42,width:1085,height:102};return q;}
function item(s,x,y,w,t,b,dark=false){txt(s,t,x,y,w,52,29,dark?C.yellow:C.pink,true);txt(s,b,x,y+64,w,140,25,dark?C.white:C.navy);}
function takeaway(s,t,dark=false){box(s,88,572,1080,3,dark?C.yellow:C.pink);txt(s,t,88,595,1070,64,25,dark?C.yellow:C.navy,true);}

// Cover: source slide 1, with its original logo, gradient and yellow rail.
{
const s=p.slides.items[0];const h=existing(s,5,'NDT',76,C.yellow);h.position={left:90,top:214,width:950,height:125};
const sub=existing(s,6,'L’application qui accompagne\nle support informatique',38,C.white);sub.position={left:90,top:355,width:1000,height:135};
const d=existing(s,7,'Présentation client\n4 novembre 2026',24,C.yellow);d.position={left:90,top:576,width:720,height:72};
}
// Needs, on the white standard layout.
{
const s=p.slides.items[1];title(s,35,'Les besoins couverts au quotidien');
const values=[['Besoin de l’équipe','Réponse de NDT'],['Structurer la prise en charge','Diagnostic guidé et synthèse à copier'],['Retrouver les bonnes informations','Wiki BO et accès aux outils métier'],['Accéder aux actions sur un poste','Prise en main, ping et accès distants'],['Préparer les opérations répétitives','Scripts avec variables à renseigner'],['Harmoniser les messages de suivi','Modèles de relance personnalisables']];
const t=s.tables.add({rows:6,columns:2,left:88,top:187,width:1080,height:402,columnWidths:[510,570],values});t.borders.assign({fill:C.white,width:2,style:'solid'});
for(let r=0;r<6;r++){t.rows[r].height=67;for(let c=0;c<2;c++){const q=t.getCell(r,c);q.fill=r===0?C.navy:r%2?C.light:'#E5E6EC';q.text.style={typeface:'Poppins',fontSize:22,bold:r===0,color:r===0?C.yellow:C.navy,insets:14,verticalAlignment:'middle'};}}
}
// Diagnosis, on the navy standard layout.
{
const s=p.slides.items[2];title(s,2,'Un diagnostic guidé et une synthèse réutilisable',true);
const data=[['01','Qualifier','Les questions s’adaptent\naux réponses données.'],['02','Compléter','Les champs obligatoires\nencadrent la saisie.'],['03','Transmettre','Une synthèse structurée\nest prête à être copiée.']];
data.forEach(([n,t,b],i)=>{const x=88+i*365;txt(s,n,x,206,200,86,64,C.yellow);box(s,x,309,320,2,C.pink);item(s,x,338,320,t,b,true)});
takeaway(s,'Besoin couvert : recueillir les informations utiles de façon homogène',true);
}
// Resource split: original source slide 6.
{
const s=p.slides.items[3];const h=existing(s,6,'Les ressources\nutiles réunies\ndans NDT',41,C.yellow);h.position={left:65,top:155,width:422,height:220};
txt(s,'Retrouver une procédure\nou un outil au même endroit.',65,438,410,115,25,C.white);
const a=existing(s,9,'Wiki BO',30,C.yellow,true);a.position={left:635,top:116,width:560,height:50};
const b=existing(s,7,'Recherche de fiches logiciel,\nprocédures illustrées et sources\naccessibles depuis la fiche.',26,C.white);b.position={left:635,top:183,width:570,height:150};
const c=existing(s,8,'Accueil Pause Cafew',30,C.yellow,true);c.position={left:635,top:378,width:570,height:50};
txt(s,'Liens vers les outils métier,\nressources par équipe et accès\nà une demande SMAX par numéro.',635,446,570,155,26,C.white);
}
// Remote tools.
{
const s=p.slides.items[4];title(s,35,'Les actions sur le poste à portée de main');
box(s,88,185,335,335,C.navy);txt(s,'Un poste\nou une adresse IP',110,215,290,125,30,C.yellow,true);txt(s,'La même cible sert\naux différentes actions.',110,412,285,90,24,C.white);
item(s,478,188,690,'Vérifier et accéder','Ping, prise en main\net bureau à distance.');
item(s,478,369,690,'Intervenir et garder l’accès','Partages C$ / D$, relance du service\nde prise en main et barre compacte.');
takeaway(s,'Besoin couvert : regrouper les accès techniques pendant l’intervention');
}
// Original four-stage diagram, source slide 20.
{
const s=p.slides.items[5];const q=existing(s,6,'Des scripts préparés pour le bon contexte',36,C.pink);q.position={left:88,top:71,width:1080,height:100};
const defs=[[131,'Choisir',130,'Sélectionner le script\nadapté à l’opération.'],[137,'Renseigner',136,'Saisir les données\ndu contexte.'],[134,'Vérifier',133,'Relire le code préparé\ndans l’aperçu.'],[140,'Copier',139,'Copier le code pour\nl’utiliser dans\nl’outil adapté.']];
for(const [tid,t,bid,b] of defs){const h=existing(s,tid,t,25,C.pink,true);h.position={...h.position,width:240,height:42};const a=existing(s,bid,b,21,C.navy);a.position={...a.position,height:126};}
txt(s,'Besoin couvert : réutiliser une commande sans la réécrire entièrement',100,634,1100,40,23,C.navy,true);
}
// Follow-up messages.
{
const s=p.slides.items[6];title(s,35,'Des relances cohérentes et personnalisables');
item(s,88,213,321,'Un modèle adapté','Assistance ou service,\nétape de relance et\ndestinataire concerné.');
item(s,453,213,321,'Un message ajusté','Numéro de ticket,\nobjet de contact et\ntexte modifiable.');
item(s,818,213,350,'Un envoi maîtrisé','Relecture du message,\npuis envoi déclenché\npar le technicien.');
txt(s,'Envoi via Exchange et la boîte partagée configurée.',88,478,1080,55,24,C.navy);
takeaway(s,'Besoin couvert : garder un cadre commun dans les échanges de suivi');
}
// Adaptability.
{
const s=p.slides.items[7];title(s,35,'Un fonctionnement adaptable aux équipes');
item(s,88,216,495,'Des contenus ajustables','Questions, parcours, synthèses,\nfiches du Wiki, scripts et modèles\nde relance peuvent évoluer.');
box(s,622,212,2,270,C.grey);
item(s,671,216,497,'Des accès selon les rôles','Les profils déterminent les écrans\net les possibilités d’édition selon\nle compte et les groupes.');
txt(s,'L’équipe conserve la responsabilité des procédures et de leur mise à jour.',88,490,1080,65,23,C.navy);
takeaway(s,'Besoin couvert : faire évoluer les pratiques dans un cadre commun');
}
// Six-stage timeline retained from source slide 18.
{
const s=p.slides.items[8];const h=existing(s,5,'Exemple de prise en charge d’une demande',35,C.pink);h.position={left:88,top:74,width:1080,height:104};
const labels=[57,18,71,31,85,44];const desc=[58,89,72,88,86,87];
const texts=['Accéder','Qualifier','Consulter','Intervenir','Documenter','Suivre'];
const bodies=['Ouvrir la demande\nSMAX.','Suivre le diagnostic\nguidé.','Consulter une\nprocédure utile.','Utiliser les outils\ndu poste.','Copier la synthèse\ndans le ticket.','Préparer une relance\nsi nécessaire.'];
for(let i=0;i<6;i++){const a=existing(s,labels[i],texts[i],17,i%2?C.white:C.yellow,true);a.text.verticalAlignment='middle';a.text.alignment='center';const b=existing(s,desc[i],bodies[i],18,C.navy);b.text.alignment='center';b.position={...b.position,height:80};}
}
// Closing: original yellow back cover and its brand assets.
{
const s=p.slides.items[9];txt(s,'Ce que NDT apporte\nau client',128,99,675,130,43,C.navy,true);
item(s,128,280,660,'Une prise en charge structurée','Questions guidées et synthèse réutilisable.');
item(s,128,403,660,'Des ressources plus accessibles','Procédures, outils et actions regroupés.');
item(s,128,526,660,'Des pratiques plus homogènes','Scripts et messages fondés\nsur des modèles communs.');
}

p.slides.items[9].shapes.items.at(-1).position={...p.slides.items[9].shapes.items.at(-1).position,height:75};
await fs.writeFile(tmp+'/adapted.json',JSON.stringify(p.toProto()));
await (await PresentationFile.exportPptx(p)).save(tmp+'/candidate-inetum.pptx');
for(let i=0;i<p.slides.items.length;i++){await fs.writeFile(tmp+`/final-${i+1}.png`,new Uint8Array(await (await p.export({slide:p.slides.items[i],format:'png',scale:1})).arrayBuffer()));console.log('Rendered',i+1);}
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
const result=await finalizePresentation({workspaceDir:root,candidatePath:tmp+'/candidate-inetum.pptx',finalPath:root+'/presentation_client/NDT_Presentation_client_Inetum_2026.pptx',pythonExecutable:runtime+'/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','2'],requiredNativeTableOwnerSlides:[2],fontPolicy:{basis:'reference',families:['Poppins'],referencePath:tmp+'/reference.pptx',referenceSha256:crypto.createHash('sha256').update(await fs.readFile(tmp+'/reference.pptx')).digest('hex')},verifyArtifactToolImport:true,receiptPath:tmp+'/validation-inetum.json'});
console.log(JSON.stringify(result));
