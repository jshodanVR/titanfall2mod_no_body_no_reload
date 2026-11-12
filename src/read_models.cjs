'use strict';
// The reader itself is fetched separately from its pinned GPL-3.0 upstream release.
const fs = require('fs');
const path = require('path');
const [vpkDir, outputDir, libraryDir] = process.argv.slice(2);
const {VPK} = require(path.join(libraryDir, 'vpk.js'));
const wanted = new Set(['pov_mlt_hero_jack.mdl', 'pov_mlt_hero_jack_rifleman.mdl']);
(async () => {
  fs.mkdirSync(outputDir, {recursive: true});
  const archives = fs.readdirSync(vpkDir).filter(n => /^englishclient_sp_.*_dir\.vpk$/.test(n)).sort();
  for (const archive of archives) {
    const vpk = new VPK(path.join(vpkDir, archive));
    try {
      vpk.readTree();
      for (const virtualPath of vpk.files) {
        const name = path.posix.basename(virtualPath);
        if (!wanted.has(name) || !virtualPath.startsWith('models/weapons/arms/')) continue;
        fs.writeFileSync(path.join(outputDir, name), await vpk.readFile(virtualPath));
        wanted.delete(name);
      }
    } finally { vpk.close(); }
    if (!wanted.size) break;
  }
  if (wanted.size) throw new Error('Original local game models not found: ' + [...wanted].join(', '));
})().catch(err => { console.error(err.message); process.exitCode = 1; });
