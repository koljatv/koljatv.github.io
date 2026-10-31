const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
(async () => {
  const dir = process.argv[2], out = process.argv[3];
  const v = fs.readFileSync(path.join(dir, "../VERSION"), "utf8").trim();
  const d = new Date().toLocaleDateString("pt-BR");
  const html = fs.readFileSync(path.join(dir, "manual.html"), "utf8").replace("{{VERSAO}}", v).replace("{{DATA}}", d);
  const tmp = path.join(dir, ".manual.tmp.html"); fs.writeFileSync(tmp, html);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto("file://" + tmp); await p.waitForTimeout(800);
  await p.pdf({ path: out, format: "A4", printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: true, headerTemplate: "<span></span>",
    footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#888">Manual da Emissora · Estúdio KÖLJA TV · <span class="pageNumber"></span>/<span class="totalPages"></span></div>' });
  await b.close(); fs.unlinkSync(tmp);
})();
