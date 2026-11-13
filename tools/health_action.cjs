// Used only by the trusted main-branch health workflow. No downloaded scripts/artifacts.
const TITLE = 'Kölja TV: falha de operação automática';
async function recover({ github, context, result }) {
 const repo=context.repo, run=context.payload.workflow_run;
 if (run) {
  if(run.head_branch!=='main' || !['failure','timed_out'].includes(run.conclusion)) return;
  // Read current attempt: an old workflow_run event must not retry a run twice.
  const {data:current}=await github.rest.actions.getWorkflowRun({...repo,run_id:run.id});
  if(current.run_attempt===1 && current.status==='completed')
   await github.rest.actions.reRunWorkflowFailedJobs({...repo,run_id:run.id});
  return;
 }
 if(result?.ok!==false) return;
 // A periodic/manual probe can refresh stale content, bounded to once per hour.
 const {data}=await github.rest.actions.listWorkflowRuns({...repo,workflow_id:'grade.yml',branch:'main',per_page:10});
 if(data.workflow_runs.some(r=>r.status!=='completed' || Date.now()-Date.parse(r.created_at)<3600000))return;
 await github.rest.actions.createWorkflowDispatch({...repo,workflow_id:'grade.yml',ref:'main'});
}
async function report({ github, context, result }) {
 const issues=await github.paginate(github.rest.issues.listForRepo,{...context.repo,state:'open',per_page:100});
 const issue=issues.find(i=>i.title===TITLE && i.user?.login==='github-actions[bot]');
 if(result.ok){
  const {data}=await github.rest.actions.listWorkflowRuns({...context.repo,workflow_id:'grade.yml',branch:'main',per_page:20});
  const latest=data.workflow_runs.find(r=>r.status==='completed');
  if(latest && ['failure','timed_out'].includes(latest.conclusion) && (latest.run_attempt>=2 || issue)){
   result={...result,ok:false,errors:[...result.errors,'Publication has not recovered since its failed deployment.']};
  }
 }
 if(result.ok){
  if(issue)await github.rest.issues.update({...context.repo,issue_number:issue.number,state:'closed',state_reason:'completed'});
  return;
 }
 const body='A verificação automática encontrou:\n\n'+result.errors.map(e=>'- '+e).join('\n')+
  '\n\nDiagnóstico e tentativas de recuperação: [Actions](https://github.com/'+context.repo.owner+'/'+context.repo.repo+'/actions/workflows/health.yml).\n'+
  'O player mantém a última grade válida e usa programação alternativa se necessário. Este aviso será fechado quando a verificação pública passar.';
 if(!issue)await github.rest.issues.create({...context.repo,title:TITLE,body});
 else if(issue.body!==body)await github.rest.issues.update({...context.repo,issue_number:issue.number,body});
}
module.exports={recover,report};
