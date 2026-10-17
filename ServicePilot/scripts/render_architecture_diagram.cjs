// Render only the local SVG artifact, without navigating to the running product.
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const packageRoot = process.env.CODEX_NODE_PACKAGES;
  const { chromium } = packageRoot ? require(path.join(packageRoot, 'playwright')) : require('playwright');
  const base = path.resolve(__dirname, '../assets/architecture/servicepilot-system-2026-10-14');
  const browser = await chromium.launch({channel:'msedge', headless:true,args:['--disable-gpu','--disable-extensions']});
  try {
    const page = await browser.newPage({viewport:{width:1680,height:2110},deviceScaleFactor:1.5});
    await page.setContent('<!doctype html><html><head><style>html,body{margin:0;width:1680px;height:2110px;overflow:hidden}svg{display:block}</style></head><body>' + fs.readFileSync(base+'.svg','utf8') + '</body></html>');
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(() => [...document.querySelectorAll('text')].flatMap(t=>{
      const b=t.getBBox();
      return b.x<0||b.y<0||b.x+b.width>1680||b.y+b.height>2110 ? [{text:t.textContent,x:b.x,y:b.y,width:b.width,height:b.height}] : [];
    }));
    if(overflow.length) throw Error(JSON.stringify({textOutsideCanvas:overflow}));
    await page.screenshot({path:base+'.png',clip:{x:0,y:0,width:1680,height:2110},timeout:45000});
    fs.writeFileSync(base+'.render.json',JSON.stringify({kind:'local_svg_render',canvas:[1680,2110],png:[2520,3165],textOutsideCanvas:overflow,createdFor:'2026-10-14 architecture explanation'},null,2));
    console.log(JSON.stringify({png:base+'.png',textOutsideCanvas:overflow}));
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
