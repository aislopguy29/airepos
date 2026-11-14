// usage: NODE_PATH=$(npm root -g) node puzzles/carousel.js <script.json> <out_dir>
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const [sj,outDir]=process.argv.slice(2);
(async()=>{
 const html=fs.readFileSync(path.join(__dirname,'carousel.html'),'utf8').replace('__SCRIPT__',fs.readFileSync(sj,'utf8'));
 const tmp=path.join(require('os').tmpdir(),'carousel_page.html');fs.writeFileSync(tmp,html);
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1350}});
 p.on('pageerror',e=>console.log('ERR',e.message));
 await p.goto('file://'+tmp);
 const n=await p.evaluate(()=>window.SLIDES);
 fs.mkdirSync(outDir,{recursive:true});
 const files=[];
 for(let i=0;i<n;i++){const d=await p.evaluate(i=>slide(i),i);
  const f=path.join(outDir,`slide_${String(i+1).padStart(2,'0')}.jpg`);
  fs.writeFileSync(f,Buffer.from(d,'base64'));files.push(f);}
 await b.close();console.log('SLIDES='+JSON.stringify(files));
})();
