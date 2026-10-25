const { chromium } = require("/opt/node-tools/node_modules/playwright");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1376, height: 768 } });
  for (const f of process.argv.slice(2)) {
    await p.goto("file://" + require("path").resolve(f + ".svg"));
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(300);
    await p.screenshot({ path: f + ".png" });
  }
  await b.close();
})();
