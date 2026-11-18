const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public/tv/tv.js', 'utf8');
const picker = source.slice(source.indexOf('  function fillPick()'), source.indexOf('  function oursPick()'));
function pick(items, dead = new Set()) {
 const context = {F: {list: items, used: new Set(), v: []}, S: {}, cur: {it: {block:'toons'}, target:{id:'main'}}, PREFER:{night:['toons']}, partOfDay:()=> 'night', isDead:u=>dead.has(u)};
 return vm.runInNewContext(picker+'; fillPick()', context);
}
const slow={id:'slow',title:'Slow',block:'toons',dur:40,copies:['https://media.example/slow.mp4']};
const reliable={id:'reliable',title:'Reliable',block:'domingo',dur:40,copies:['https://github.com/koljatv/koljatv.github.io/releases/download/docs_20261102/clip.mp4']};
test('station-hosted reserve precedes a stalled external programme of matching block',()=>assert.equal(pick([slow,reliable]).id,'reliable'));
test('unavailable station copy does not hide another reserve',()=>assert.equal(pick([slow,reliable],new Set(reliable.copies)).id,'slow'));
test('unrelated release host has no station priority',()=>assert.equal(pick([slow,{...reliable,copies:['https://github.com/other/channel/releases/download/a/clip.mp4']}]).id,'slow'));
