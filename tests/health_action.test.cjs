const test = require('node:test');
const assert = require('node:assert/strict');
const { recover, report } = require('../tools/health_action.cjs');
function fixture() {
 const calls=[];
 const context={repo:{owner:'tv',repo:'site'},runId:99,payload:{}};
 const github={rest:{actions:{
  getWorkflowRun:async()=>({data:{run_attempt:1,status:'completed',conclusion:'failure'}}),
  reRunWorkflowFailedJobs:async x=>calls.push(['retry',x]),
  listWorkflowRuns:async()=>({data:{workflow_runs:[]}}),
  createWorkflowDispatch:async x=>calls.push(['dispatch',x])
 },issues:{create:async x=>calls.push(['create',x]),update:async x=>calls.push(['update',x])}},
 paginate:async()=>[]};
 return {github,context,calls};
}
test('only failed grade on main gets one retry',async()=>{
 const f=fixture();f.context.payload.workflow_run={id:1,head_branch:'main',conclusion:'failure'};
 await recover(f);assert.equal(f.calls[0][0],'retry');
 f.calls.length=0;f.github.rest.actions.getWorkflowRun=async()=>({data:{run_attempt:2,status:'completed'}});
 await recover(f);assert.equal(f.calls.length,0);
 f.context.payload.workflow_run.head_branch='other';await recover(f);assert.equal(f.calls.length,0);
});
test('stale publication dispatches once unless another build is recent or active',async()=>{
 const f=fixture();f.result={ok:false,errors:['publication is stale (over 12 hours)']};await recover(f);assert.equal(f.calls[0][0],'dispatch');
 f.calls.length=0;f.github.rest.actions.listWorkflowRuns=async()=>({data:{workflow_runs:[{status:'in_progress'}]}});
 await recover(f);assert.equal(f.calls.length,0);
});
test('one incident updated only on change; recovery closes it',async()=>{
 const f=fixture();f.result={ok:false,errors:['offline']};await report(f);assert.equal(f.calls[0][0],'create');
 const issue={number:3,title:f.calls[0][1].title,body:f.calls[0][1].body,user:{login:'github-actions[bot]'}};
 f.github.paginate=async()=>[issue];f.calls.length=0;await report(f);assert.equal(f.calls.length,0);
 f.result={ok:true,errors:[]};await report(f);assert.equal(f.calls[0][1].state,'closed');
});

test('healthy old delivery does not close a failed deployment incident',async()=>{
 const f=fixture();f.result={ok:true,errors:[]};
 f.github.paginate=async()=>[{number:3,title:'Kölja TV: falha de operação automática',body:'old',user:{login:'github-actions[bot]'}}];
 f.github.rest.actions.listWorkflowRuns=async()=>({data:{workflow_runs:[{status:'completed',conclusion:'failure',run_attempt:2}]}});
 await report(f);assert.ok(f.calls.length);assert.notEqual(f.calls[0][1].state,'closed');
 f.calls.length=0;f.github.rest.actions.listWorkflowRuns=async()=>({data:{workflow_runs:[{status:'completed',conclusion:'success'}]}});
 await report(f);assert.equal(f.calls[0][1].state,'closed');
});
