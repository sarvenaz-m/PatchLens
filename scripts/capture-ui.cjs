/* Reproducible screenshots of a fresh workspace with no reviewer annotations. */
const {chromium}=require('playwright');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.PATCHLENS_CHROMIUM_PATH||undefined,args:process.env.PATCHLENS_NO_SANDBOX?['--no-sandbox']:[]});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1080}});
    await page.goto(pathToFileURL(path.resolve(__dirname,'../index.html')).href);
    await page.locator('#view-overview .studio-hero').waitFor();
    for(const route of ['overview','benchmark','pairs','tools','diagnostics','compare','review']){
      await page.locator(`nav [data-route="${route}"]`).click();
      await page.locator(`#view-${route}`).waitFor();
      await page.screenshot({path:path.resolve(__dirname,`../docs/assets/workbench-${route}.png`),fullPage:true,animations:'disabled'});
    }
    await page.locator('nav [data-route="overview"]').click();
    await page.locator('#theme-toggle').click();
    await page.screenshot({path:path.resolve(__dirname,'../docs/assets/workbench-dark.png'),fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.resolve(__dirname,'../docs/assets/workbench-mobile.png'),fullPage:false,animations:'disabled'});
    await page.locator('nav [data-route="benchmark"]').click();
    await page.screenshot({path:path.resolve(__dirname,'../docs/assets/workbench-benchmark-mobile.png'),fullPage:false,animations:'disabled'});
    console.log('Ten actual version-2 interface screenshots captured.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
