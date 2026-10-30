const fs = require("fs");
const html = fs.readFileSync(__dirname + "/index.html", "utf8");
const core = html.split("// CORE-START")[1].split("// CORE-END")[0];
const api = new Function(core + "; return {de2000, labToRgb, rgbToLab, hexLab, MST_HEX, lesionOffset, maxDE, makeStair, stairUpdate, stairThreshold};")();
let fails = 0;
const near = (a, b, tol, msg) => { const ok = Math.abs(a - b) <= tol; if (!ok) fails++; console.log(ok ? "PASS" : "FAIL", msg, a.toFixed(4), "expected", b, "tol", tol.toFixed(2)); };
near(api.de2000([50, 2.6772, -79.7751], [50, 0, -82.7485]), 2.0425, 1e-3, "Sharma pair 1");
near(api.de2000([50, 3.1571, -77.2803], [50, 0, -82.7485]), 2.8615, 1e-3, "Sharma pair 2");
near(api.de2000([50, 2.5, 0], [73, 25, -18]), 27.1492, 1e-3, "Sharma pair 11");
near(api.de2000([60.2574, -34.0099, 36.2677], [60.4626, -34.1751, 39.4387]), 1.2644, 1e-3, "Sharma pair 15");
for (const rgb of [[246, 237, 228], [160, 126, 86], [41, 36, 32]]) { const back = api.labToRgb(...api.rgbToLab(...rgb)); near(Math.abs(back[0] - rgb[0]) + Math.abs(back[1] - rgb[1]) + Math.abs(back[2] - rgb[2]), 0, 0.01, "roundtrip " + rgb); }
// reachable targets hit within 8-bit quantisation error (≈0.35 dE at the low end)
for (const m of [2, 4, 6, 10]) {
  const base = api.hexLab(api.MST_HEX[m]), mx = api.maxDE(base);
  console.log(`MST${m} max reachable dE00 = ${mx.toFixed(1)}`);
  for (const t of [1, 2, 4, 6, 8, 12, 18]) if (t <= mx * 0.97) near(api.lesionOffset(base, t).realized, t, Math.max(0.35, t * 0.05), `target ${t} MST${m}`);
}
// observer with true threshold 6
let s = api.makeStair(10, 6, 45), n = 0; while (!s.done && n++ < 60) api.stairUpdate(s, s.lvl > 6);
near(api.stairThreshold(s), 6, 1.6, "staircase converges to true threshold");
// observer who never sees anything: must stop and be flagged as censored, not loop forever
s = api.makeStair(6, 6, 7.9); n = 0; while (!s.done && n++ < 60) api.stairUpdate(s, false);
console.log(s.done && s.censored && n < 20 ? "PASS" : "FAIL", "never-sees observer is censored after", n, "trials"); if (!(s.done && s.censored)) fails++;
// observer who always says yes: must terminate (lowest level) without a bogus threshold below the floor
s = api.makeStair(10, 6, 45); n = 0; while (!s.done && n++ < 60) api.stairUpdate(s, true);
console.log(s.done ? "PASS" : "FAIL", "always-yes observer terminates after", n, "trials; level", s.lvl.toFixed(2)); if (!s.done) fails++;
console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED"); process.exitCode = fails ? 1 : 0;
