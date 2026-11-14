// usage: NODE_PATH=$(npm root -g) node serial/render.js script.json out.mp4 [audio.wav]   |   ... pv script.json t1,t2,...
const {chromium}=require('playwright');const {spawn}=require('child_process');const fs=require('fs');const path=require('path');
const [a1,a2,a3,a4]=process.argv.slice(2);
(async()=>{const mode=a1==='pv'?'pv':'vid';const sj=mode==='pv'?a2:a1;
const html=fs.readFileSync(path.join(__dirname,'page.html'),'utf8').replace('__SCRIPT__',fs.readFileSync(sj,'utf8'));
const tmp=path.join(require('os').tmpdir(),'serial_page.html');fs.writeFileSync(tmp,html);
const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+tmp);const D=await p.evaluate(()=>window.DUR);
if(mode==='pv'){for(const t of a3.split(',').map(Number)){fs.writeFileSync(`pv_${t}.jpg`,Buffer.from(await p.evaluate(t=>frame(t),t),'base64'))}await b.close();console.log('DUR',D);return}
const out=a2,aud=a3;const args=['-y','-loglevel','error','-f','image2pipe','-c:v','mjpeg','-framerate','60','-i','-'];
if(aud)args.push('-i',aud);args.push('-c:v','libx264','-crf','20','-preset','fast','-tune','animation','-r','60','-pix_fmt','yuv420p');
if(aud)args.push('-c:a','aac','-b:a','128k','-shortest');args.push('-movflags','+faststart',out);
const ff=spawn('ffmpeg',args,{stdio:['pipe','inherit','inherit']});
const n=Math.round(D*60);for(let k=0;k<n;k++){const d=await p.evaluate(t=>frame(t),k/60);if(!ff.stdin.write(Buffer.from(d,'base64')))await new Promise(r=>ff.stdin.once('drain',r))}
ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close();console.log('done',D)})();
