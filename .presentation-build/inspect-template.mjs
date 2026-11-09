import fs from 'node:fs/promises';
import {FileBlob, PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('C:/Users/nicol/Downloads/PowerPoint 2026 Template v5.5 (4).potx'));
const out='C:/Users/nicol/OneDrive/Desktop/NDT/.presentation-build/template';
await fs.writeFile(out+'/source.json',JSON.stringify(p.toProto()));
await fs.writeFile(out+'/inspect.ndjson',(await p.inspect({kind:'slide,layout,textbox,shape,image',maxChars:500000})).ndjson);
console.log('Imported',p.slides.items.length,'masters',p.masters.items.length);
for(let i=0;i<p.slides.items.length;i++){await fs.writeFile(out+`/source-${i+1}.png`,new Uint8Array(await (await p.export({slide:p.slides.items[i],format:'png',scale:0.75})).arrayBuffer()));console.log('Rendered',i+1);}
