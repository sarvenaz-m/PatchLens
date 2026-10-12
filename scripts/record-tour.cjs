/* Records actual browser interactions; no fabricated frames or metrics. */
const {chromium}=require('playwright');
const path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.PATCHLENS_CHROMIUM_PATH||undefined,args:process.env.PATCHLENS_NO_SANDBOX?['--no-sandbox']:[]});
  const directory=path.resolve(__dirname,'../artifacts/tour');
  let context,page;
  try {
  context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:directory,size:{width:1440,height:1000}}});
  page=await context.newPage();
    await page.goto(pathToFileURL(path.resolve(__dirname,'../index.html')).href);
    await page.locator('#view-overview .stats-grid').waitFor();
    await page.waitForTimeout(2200);
    await page.locator('nav [data-route="benchmark"]').click();
    await page.waitForTimeout(2600);
    await page.evaluate(()=>window.scrollTo(0,420));
    await page.waitForTimeout(2400);
    await page.locator('nav [data-route="pairs"]').click();
    await page.waitForTimeout(2200);
    await page.locator('#pair-search').fill('CVE-2016-6802');
    await page.waitForTimeout(2200);
    await page.locator('nav [data-route="experiments"]').click();
    await page.locator('#threshold-slider').fill('0.9');
    await page.locator('#threshold-slider').dispatchEvent('change');
    await page.waitForTimeout(2000);
    await page.locator('[data-reset-threshold]').click();
    await page.locator('nav [data-route="diagnostics"]').click();
    await page.waitForTimeout(1800);
    await page.locator('nav [data-route="compare"]').click();
    await page.waitForTimeout(1800);
    await page.locator('nav [data-route="review"]').click();
    await page.waitForTimeout(1800);
    await page.locator('nav [data-route="tools"]').click();
    await page.waitForTimeout(2200);
    await page.locator('nav [data-route="embeddings"]').click();
    await page.locator('.scatter-point').first().focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(2200);
    await page.locator('#theme-toggle').click();
    await page.waitForTimeout(2200);
    await context.close();
    const destination=path.resolve(__dirname,'../docs/assets/workbench-tour.webm');
    fs.copyFileSync(await page.video().path(),destination);
    console.log('Recorded browser walkthrough: '+destination);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
