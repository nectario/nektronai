const byId = (id) => document.getElementById(id);
const scenarios = {
  orders: { question:'Which products brought in the most revenue this month?', answer:'Here are the top products by revenue.', caption:'Illustrative product revenue, not a live query', columns:['Product','Orders','Revenue'], rows:[['Studio Desk','128','$38,400'],['Arc Lamp','204','$24,480'],['Oak Shelf','96','$17,280']], followup:'And how does that compare with last month?', detail:'In this sample, Studio Desk revenue increased 20%, Arc Lamp increased 8%, and Oak Shelf decreased 4%. A real follow-up would query the comparison period in your database.' },
  support: { question:'Which topics generated the most support tickets this week?', answer:'These topics account for the most tickets in the example.', caption:'Illustrative support ticket counts, not a live query', columns:['Topic','Tickets','Resolved'], rows:[['Account access','86','79'],['Billing questions','54','48'],['Delivery updates','37','31']], followup:'Which topic has the longest resolution time?', detail:'In this sample, billing questions take the longest to resolve: a median of 6.2 hours. A real investigation would use your ticket timestamps and explain any missing values.' },
  operations: { question:'Which locations have the most orders waiting to ship?', answer:'Here is the unshipped order count for each location.', caption:'Illustrative fulfillment counts, not a live query', columns:['Location','Waiting','Over 2 days'], rows:[['East warehouse','42','8'],['Central warehouse','31','3'],['West warehouse','18','2']], followup:'What is holding up the East warehouse?', detail:'In this sample, five of the eight older orders are waiting for the same component. A real follow-up would use the returned order identifiers to inspect the related records.' }
};
let selectedScenario = 'orders';
const tabs = [...document.querySelectorAll('[data-scenario]')];
function renderScenario(name, focus = false) {
  selectedScenario = name;
  const data = scenarios[name];
  for (const tab of tabs) { const active = tab.dataset.scenario === name; tab.setAttribute('aria-selected',String(active)); tab.tabIndex = active ? 0 : -1; if(active && focus) tab.focus(); }
  byId('demo-panel').setAttribute('aria-labelledby',`${name}-tab`);
  byId('demo-question').textContent=data.question; byId('demo-answer').textContent=data.answer;
  const table=byId('demo-table'); table.querySelector('caption').textContent=data.caption;
  const headings=document.createElement('tr');
  for(const label of data.columns){const cell=document.createElement('th');cell.scope='col';cell.textContent=label;headings.append(cell);}
  table.tHead.replaceChildren(headings); table.tBodies[0].replaceChildren();
  for(const row of data.rows){const tr=document.createElement('tr');row.forEach((text,index)=>{const cell=document.createElement(index===0?'th':'td');if(index===0)cell.scope='row';cell.textContent=text;tr.append(cell);});table.tBodies[0].append(tr);}
  byId('demo-followup').textContent=data.followup+' ↗︎'; byId('demo-followup').setAttribute('aria-expanded','false');
  byId('demo-followup-answer').hidden=true;byId('demo-followup-answer').textContent='';
}
tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>renderScenario(tab.dataset.scenario));tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();renderScenario(tabs[next].dataset.scenario,true);});});
byId('demo-followup').setAttribute('aria-controls','demo-followup-answer');byId('demo-followup').setAttribute('aria-expanded','false');
byId('demo-followup').addEventListener('click',()=>{const output=byId('demo-followup-answer'),open=output.hidden;output.textContent=scenarios[selectedScenario].detail;output.hidden=!open;byId('demo-followup').setAttribute('aria-expanded',String(open));});
document.querySelector('[data-explore]').addEventListener('click',()=>{tabs.find(t=>t.dataset.scenario===selectedScenario).focus({preventScroll:true});});
document.querySelectorAll('[data-open-setup]').forEach(button=>button.addEventListener('click',()=>byId('setup-dialog').showModal()));
