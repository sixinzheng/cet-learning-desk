const fs = require('fs');
const path = require('path');
let chromium;
try { ({chromium} = require('playwright')); }
catch (_) { ({chromium} = require('C:\\Users\\Lenovo\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\playwright')); }

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:5099';
const output = process.argv[2] || path.join(process.cwd(),'browser-artifacts','mobile-orphan-audit');
const routes = ['/','/learn','/study','/review','/reading','/control','/growth','/profile'];
fs.mkdirSync(output,{recursive:true});

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-gpu']});
  const report=[];
  for(const viewport of [{width:320,height:720},{width:360,height:800},{width:390,height:844}]){
    const context=await browser.newContext({viewport,isMobile:true,hasTouch:true});
    for(const route of routes){
      const page=await context.newPage();
      const errors=[];
      page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
      page.on('pageerror',error=>errors.push(error.message));
      const response=await page.goto(`${baseUrl}${route}`,{waitUntil:'networkidle'});
      const findings=await page.evaluate(()=>{
        const candidates=[...document.querySelectorAll('h1,h2,h3,.btn,button,dt,dd,.metric-label,.stat-label')];
        return candidates.flatMap(element=>{
          const style=getComputedStyle(element);
          if(style.display==='none'||style.visibility==='hidden'||!element.getClientRects().length)return [];
          const fullText=(element.innerText||'').replace(/\s+/g,'').trim();
          if(fullText.length<2)return [];
          const lines=[];
          const lineHeight=parseFloat(style.lineHeight)||parseFloat(style.fontSize)*1.25||16;
          const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT);
          while(walker.nextNode()){
            const node=walker.currentNode;
            for(let index=0;index<node.data.length;index+=1){
              const char=node.data[index];
              if(/\s/.test(char))continue;
              const range=document.createRange();
              range.setStart(node,index);range.setEnd(node,index+1);
              const rect=range.getBoundingClientRect();
              if(!rect.width&&!rect.height)continue;
              let line=lines.find(item=>Math.abs(item.top-rect.top)<=lineHeight*.42);
              if(!line){line={top:rect.top,text:''};lines.push(line);}
              line.text+=char;
            }
          }
          const rows=lines.sort((a,b)=>a.top-b.top);
          if(rows.length<2)return [];
          const last=(rows.at(-1)?.text||'').replace(/\s+/g,'');
          if(!/^[\u3400-\u9fff]$/.test(last))return [];
          return [{tag:element.tagName,text:(element.innerText||'').trim(),lastLine:last,className:String(element.className||'')}];
        });
      });
      report.push({viewport:viewport.width,route,status:response?.status(),findings,errors});
      await page.close();
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
  const failures=report.filter(item=>item.status!==200||item.errors.length||item.findings.length);
  console.log(JSON.stringify({checked:report.length,failures},null,2));
  process.exit(failures.length?1:0);
})().catch(error=>{console.error(error);process.exit(1);});
