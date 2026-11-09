import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile,FileBlob} from '@oai/artifact-tool';
const root='C:/Users/nicol/OneDrive/Desktop/NDT';
const tmp=root+'/.presentation-build/template';
const skill='C:/Users/nicol/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1026-487-0_26.1026.487.0_x64__3k8sg7r9htsxt/dependencies';
const original=await PresentationFile.importPptx(await FileBlob.load(root+'/presentation_client/NDT_Presentation_client_Inetum_2026.pptx'));
const proto=original.toProto();
function clone(i,id){const s=structuredClone(proto.slides[i]);s.id=id;s.elements=s.elements.filter(e=>['title','dt','ftr','sldNum'].includes(e.placeholderType));return s;}
const a=clone(2,'ndt-future-scope'),b=clone(7,'ndt-future-priorities');
proto.slides.splice(9,0,a,b);
proto.slides.forEach((s,i)=>{s.index=i;for(const e of s.elements)if(e.placeholderType==='sldNum')e.paragraphs=[{runs:[{text:String(i+1)}]}];});
const p=Presentation.load(proto);
const C={navy:'#232D4B',pink:'#E20074',yellow:'#F5F340',white:'#FFFFFF',grey:'#D3D5DB'};
function box(s,x,y,w,h,fill){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});}
function txt(s,t,x,y,w,h,size=24,color=C.navy,bold=false){const q=box(s,x,y,w,h,'none');q.text=t;q.text.style={typeface:'Poppins',fontSize:size,color,bold,insets:0,autoFit:'none',wrap:'square',verticalAlignment:'top'};return q;}
function title(s,t,color){const q=s.placeholders.items.find(q=>q.placeholder.type==='title');q.text=t;q.position={left:88,top:42,width:1080,height:105};q.text.style={typeface:'Poppins',fontSize:36,color,insets:0,autoFit:'none',verticalAlignment:'top'};}
{
const s=p.slides.items[9];title(s,'Élargir l’usage de NDT au N2 et au N3',C.yellow);
txt(s,'Périmètre actuel et perspectives d’évolution',88,136,1080,43,23,C.white);
const cols=[
['Aujourd’hui','N1 — FO / BO','Diagnostic guidé, ressources,\noutils poste et relances\npour accompagner\nla prise en charge.'],
['Extension envisagée','N2','Adapter les parcours aux\nincidents plus complexes\net proposer des procédures\ntechniques spécialisées.'],
['Extension envisagée','N3','Soutenir l’expertise et\nl’analyse des causes, puis\ncapitaliser les solutions\nutiles aux autres niveaux.']
];
cols.forEach(([label,t,body],i)=>{const x=88+i*365;txt(s,label,x,224,325,42,21,i===0?C.white:C.yellow);txt(s,t,x,282,325,65,36,C.yellow,true);box(s,x,363,320,2,C.pink);txt(s,body,x,391,330,155,23,C.white);});
box(s,88,573,1080,3,C.yellow);txt(s,'Objectif : un outil utile à chaque niveau, adapté à ses besoins métier.',88,597,1080,65,24,C.yellow,true);
s.speakerNotes.text='Le périmètre actuel FO / BO du N1 est confirmé par le porteur du projet. L’ouverture au N2 et au N3 est une perspective, et non une fonctionnalité déjà déployée ou un engagement de livraison. Les usages décrits pour le N2 et le N3 sont des propositions à préciser avec ces équipes selon leur organisation. Le but est de compléter le socle N1 par des parcours, contenus et outils pertinents pour chaque niveau. Aucun calendrier ni gain chiffré n’est annoncé.';
}
{
const s=p.slides.items[10];title(s,'Les évolutions à construire avec le N2 / N3',C.pink);
txt(s,'Pistes proposées, à prioriser avec les équipes concernées',88,139,1080,45,23,C.navy);
const cols=[
['Diagnostic\nspécialisé','Adapter les parcours aux\ndomaines techniques et\nrassembler les tests\net journaux utiles.','Mieux cibler l’investigation.'],
['Escalade\ndocumentée','Structurer la transmission :\ncontexte, impact, actions\ndéjà menées et résultats\nobtenus.','Faciliter la reprise du dossier.'],
['Connaissances\npartagées','Capitaliser les solutions\nissues du N2 / N3 et enrichir\nles procédures et scripts\nréutilisables par le N1.','Réutiliser l’expertise acquise.']
];
cols.forEach(([t,body,gain],i)=>{const x=88+i*365;txt(s,t,x,224,330,92,29,C.pink,true);txt(s,body,x,341,330,165,23,C.navy);txt(s,gain,x,517,330,62,21,C.navy,true);});
box(s,88,593,1080,3,C.pink);txt(s,'Démarche envisagée : recueillir les besoins, tester un périmètre pilote,\npuis ajuster les évolutions à partir des retours terrain.',88,610,1080,65,22,C.navy);
s.speakerNotes.text='Ces évolutions sont des pistes fonctionnelles proposées pour étendre l’utilité de NDT au N2 et au N3. Elles ne décrivent pas des capacités actuelles. La collecte des journaux et la transmission du dossier sont à concevoir selon les outils et processus du client, sans présumer d’une intégration automatique à SMAX. Proposition de démarche : identifier les cas d’usage avec des représentants N2 / N3, sélectionner un pilote, tester les contenus et fonctions utiles, puis décider des priorités à partir des retours. Les règles d’accès, la validation des scripts et la responsabilité des contenus devront accompagner cette extension.';
}
await fs.writeFile(tmp+'/evolutions.json',JSON.stringify(p.toProto()));
await (await PresentationFile.exportPptx(p)).save(tmp+'/candidate-evolutions.pptx');
for(let i=0;i<p.slides.items.length;i++){const im=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(tmp+`/evolution-${i+1}.png`,new Uint8Array(await im.arrayBuffer()));}
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
const r=await finalizePresentation({workspaceDir:root,candidatePath:tmp+'/candidate-evolutions.pptx',finalPath:root+'/presentation_client/NDT_Presentation_client_Inetum_N2_N3.pptx',pythonExecutable:runtime+'/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','2'],requiredNativeTableOwnerSlides:[2],explicitTotalSlideCount:12,fontPolicy:{basis:'reference',families:['Poppins'],referencePath:tmp+'/reference.pptx',referenceSha256:crypto.createHash('sha256').update(await fs.readFile(tmp+'/reference.pptx')).digest('hex')},verifyArtifactToolImport:true,receiptPath:tmp+'/validation-evolutions-final.json'});
console.log(JSON.stringify(r));
