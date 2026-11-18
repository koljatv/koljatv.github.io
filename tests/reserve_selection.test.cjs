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
const fillTickSource = source.slice(source.indexOf('  function fillTick()'), source.indexOf('\n  function tick()'));
test('a healthy main programme does not cut a reserve during its opening',()=>{
 let cut=false;
 const f={pk:{dur:40},currentTime:8,duration:40,liveAt:0,chk:[9000,7],waitAt:0,crawl:false};
 const context={Date:{now:()=>10000},F:{on:f},document:{hidden:false},host:{classList:{add(){}}},FILL_STALL:8000,FILL_CUT:20000,FILL_HOLD:240000,fillWanted:()=>false,cur:{target:{p:{}}},onTarget:()=>true,dropF:()=>{cut=true;},fillGone(){}};
 vm.runInNewContext(fillTickSource+'; fillTick()',context);
 assert.equal(cut,false,'reserve opening was cut by return-to-grade rule');
});

test('station Pages copy is preferred before a release copy of the same programme',()=>{
 const pages='https://tv.kolja.com.br/tv/ours/reserve.mp4';
 assert.equal(pick([{...reliable,copies:[pages,...reliable.copies]}]).url,pages);
});
