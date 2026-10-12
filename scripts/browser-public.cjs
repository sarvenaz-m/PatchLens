/* Validate real-study views and provenance in an actual offline browser. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.PATCHLENS_CHROMIUM_PATH||undefined,args:process.env.PATCHLENS_NO_SANDBOX?['--no-sandbox']:[]});
  const root=path.resolve(__dirname,'..'),out=path.join(root,'artifacts/public-browser');fs.mkdirSync(out,{recursive:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
  const routes=['overview','benchmark','pairs','experiments','compare','diagnostics','embeddings','tools','review','provenance'];
  try {
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    await page.locator('#view-overview .stats-grid').waitFor();
    assert.equal(await page.locator('#version').textContent(),'2.0.0');
    assert.equal(await page.locator('#model-select').inputValue(),'codebert');
    assert.equal(await page.locator('#corpus-select option').count(),7);
    assert.equal(await page.locator('#pair-count').textContent(),'62');
    assert.match(await page.locator('#view-overview').textContent(),/Identity/);
    assert.doesNotMatch(await page.locator('#view-overview').textContent(),/100\.0%.*renaming/);
    for(const route of routes){await page.locator(`nav [data-route="${route}"]`).click();assert.equal(await page.locator(`#view-${route}`).isVisible(),true);}
    await page.locator('nav [data-route="benchmark"]').click();
    assert.match(await page.locator('#view-benchmark').textContent(),/56\.0%/);
    assert.match(await page.locator('#view-benchmark').textContent(),/interval includes zero/);
    await page.screenshot({path:path.join(out,'benchmark-desktop.png'),fullPage:true});
    await page.locator('nav [data-route="pairs"]').click();
    assert.match(await page.locator('.source-link').getAttribute('href'),/^https:\/\/github\.com\//);
    assert.equal(await page.locator('.code-panel').count(),2);
    await page.screenshot({path:path.join(out,'pairs-desktop.png'),fullPage:true});
    await page.locator('nav [data-route="experiments"]').click();
    assert.match(await page.locator('#view-experiments').textContent(),/Not measured/);
    for(let fold=0;fold<5;fold++) {
      await page.locator('#corpus-select').selectOption(`fold-${fold}`);
      await page.locator('nav [data-route="diagnostics"]').click();
      const r=JSON.parse(fs.readFileSync(path.join(root,`examples/repository-cross-validation/fold-${fold}/run/report.json`)));
      assert.equal(await page.locator('.margin-row').count(),r.samples.filter(s=>s.split==='test').length/2);
      await page.locator('#model-select').selectOption('constant');
      await page.locator('nav [data-route="embeddings"]').click();
      assert.match(await page.locator('#view-embeddings').textContent(),/not supplied|No embedding/i);
    }
    await page.locator('#corpus-select').selectOption('current');
    await page.locator('nav [data-route="overview"]').click();
    await page.screenshot({path:path.join(out,'overview-desktop.png'),fullPage:true});
    await page.locator('#theme-toggle').click();
    await page.screenshot({path:path.join(out,'overview-dark.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    for(const route of routes){await page.locator(`nav [data-route="${route}"]`).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`Overflow: ${route}`);}
    await page.locator('nav [data-route="benchmark"]').click();
    await page.screenshot({path:path.join(out,'benchmark-mobile.png'),fullPage:true});
    const invalid=JSON.parse(fs.readFileSync(path.join(root,'examples/public-benchmark/report.json')));
    invalid.cross_validation.models.codebert.pooled_counts.fn='<img src=x onerror="window.publicXss=1">';
    await page.locator('#import-file').setInputFiles({name:'invalid-public.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
    await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Invalid report'));
    assert.equal(await page.evaluate(()=>window.publicXss),undefined);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    const result={status:'passed',chromium:browser.version(),viewports:[[1440,1000],[390,844]],routes:routes.length,repository_folds:5,corpora:7,page_errors:0,external_requests:0,page_overflow:false,scope:'Public study, all fold reports, identity-view status, original correction links, input validation and actual desktop/mobile layout'};
    fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
