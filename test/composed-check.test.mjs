import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveCheckDashboard, loadCompositionDependencies, COMPOSITION_MARKER } from '../src/composed-check.mjs';

const copy = value => structuredClone(value);
const metadata = { urlPath:'home-energy',title:'Home Energy',icon:'mdi:home-lightning-bolt',showInSidebar:true,requireAdmin:false };
const desiredMetadata = { title:metadata.title,icon:metadata.icon,show_in_sidebar:true,require_admin:false };
const routes = { energy:'home-energy',eg4:'eg4-energy',ev:'juicebox-local',network:'network-dashboard' };
function fixture({network=false}={}) {
  const baseCandidate = { views:['whole-home','solar-arrays','battery-backup','grid-srp','peak-strategy','peak-controls','diagnostics'].map(path=>({path,title:path,type:'sections',sections:[]})) };
  const existing = { id:'energy-id',url_path:'home-energy',mode:'storage',...desiredMetadata };
  const list = [copy(existing),{id:'eg4-id',url_path:'eg4-energy',mode:'storage',require_admin:false},
    {id:'ev-id',url_path:'juicebox-local',mode:'storage',require_admin:false}];
  const configs = {'eg4-energy':{views:[{path:'live',cards:[{type:'tile',entity:'sensor.pv'}]}]},
    'juicebox-local':{views:[{path:'status',cards:[{type:'button',tap_action:{action:'perform-action',perform_action:'input_button.press',target:{entity_id:'input_button.charge_request'}}}]}]}};
  if (network) { list.push({id:'network-id',url_path:'network-dashboard',mode:'storage',require_admin:true});configs['network-dashboard']={views:[{path:'overview'}],[COMPOSITION_MARKER]:{schema:1}}; }
  const calls=[],observed=[],states=[{entity_id:'sensor.pv',state:'1000'}];
  let strictCalls=0,loads=0;
  const composeNavigation=(input,{validateEg4})=>{
    observed.push(input);validateEg4(input.eg4.config,input.states);
    return {hubs:[{url_path:'home-energy',metadata:desiredMetadata,config:{...copy(input.energy.config),
      views:[...copy(input.energy.config.views),...['eg4','ev'].flatMap(role=>input[role].config.views.map(v=>({...copy(v),path:role+'-'+v.path,subview:true})))],
      [COMPOSITION_MARKER]:{schema:1,source_version:input.eg4.config.version??1}}}]};
  };
  const dependencies={routes,composeNavigation,validateEg4(config,s){strictCalls++;assert.equal(s,states);assert.ok(config.views);}};
  const loadDependencies=async()=>{loads++;return dependencies;};
  const input={states,energy:{metadata:existing,config:baseCandidate},eg4:{metadata:list[1],config:configs['eg4-energy']},ev:{metadata:list[2],config:configs['juicebox-local']}};
  const expected=composeNavigation(input,{validateEg4:()=>{}}).hubs[0].config;observed.length=0;
  const client={async call(command){calls.push(copy(command));
    if(command.type==='lovelace/dashboards/list')return copy(list);
    if(command.type==='lovelace/config')return copy(configs[command.url_path]);
    throw Error('Non-read call attempted');
  }};
  const args={client,baseCandidate,existing,existingConfig:copy(expected),states,metadata,loadDependencies};
  return {args,list,configs,calls,observed,expected,dependencies,get strictCalls(){return strictCalls;},get loads(){return loads;}};
}

test('uncomposed operation returns base candidate without sibling imports or additional API calls',async()=>{
  const f=fixture();f.args.existingConfig=copy(f.args.baseCandidate);
  f.args.loadDependencies=async()=>{throw Error('Must not load sibling dependency');};
  const result=await resolveCheckDashboard(f.args);
  assert.equal(result.composed,false);assert.equal(result.candidate,f.args.baseCandidate);assert.equal(result.sourceCount,0);assert.equal(f.calls.length,0);
});
test('missing dashboard retains ordinary uncomposed behavior',async()=>{
  const f=fixture();f.args.existingConfig=null;f.args.existing=null;
  const result=await resolveCheckDashboard(f.args);assert.equal(result.composed,false);assert.equal(f.loads,0);
});
test('declared composite reads fresh exact sources, uses maintained base and strict validator, without mutation',async()=>{
  const f=fixture(),before=JSON.stringify(f.args.existingConfig),base=JSON.stringify(f.args.baseCandidate);
  const result=await resolveCheckDashboard(f.args);
  assert.equal(result.composed,true);assert.equal(result.sourceCount,2);assert.deepEqual(result.candidate,f.expected);
  assert.equal(f.strictCalls,1);assert.equal(f.loads,1);assert.equal(f.observed[0].energy.config,f.args.baseCandidate);
  assert.equal(JSON.stringify(f.args.existingConfig),before);assert.equal(JSON.stringify(f.args.baseCandidate),base);
  assert.deepEqual(f.calls.map(c=>c.type),['lovelace/dashboards/list','lovelace/config','lovelace/config']);
  assert.ok(f.calls.slice(1).every(c=>c.force===true));
});
test('optional existing Network is read, while missing Network is permitted',async()=>{
  const f=fixture({network:true});const result=await resolveCheckDashboard(f.args);
  assert.equal(result.sourceCount,3);assert.ok(f.observed[0].network);assert.ok(f.calls.some(c=>c.url_path==='network-dashboard'));
  f.list.find(d=>d.url_path==='network-dashboard').require_admin=false;
  await assert.rejects(()=>resolveCheckDashboard(f.args),/trusted administrator/);
});
test('unknown additions and edited base/overlay/marker cannot be waved through',async()=>{
  for(const edit of [c=>c.views.push({path:'unapproved'}),c=>c.views[0].title='Edited live base',
    c=>c.views.find(v=>v.path==='ev-status').cards[0].tap_action.target.entity_id='input_button.other',
    c=>c[COMPOSITION_MARKER].unapproved=true]){
    const f=fixture();edit(f.args.existingConfig);await assert.rejects(()=>resolveCheckDashboard(f.args),/exact fresh recomputation/);
  }
});
test('a fresh equipment source change invalidates an older composite',async()=>{
  const f=fixture();f.configs['eg4-energy'].version=2;
  await assert.rejects(()=>resolveCheckDashboard(f.args),/exact fresh recomputation/);
});
test('unsupported declared marker fails without imports or reads',async()=>{
  for(const marker of [null,{schema:2},{}]){
    const f=fixture();f.args.existingConfig[COMPOSITION_MARKER]=marker;
    await assert.rejects(()=>resolveCheckDashboard(f.args),/Unsupported/);assert.equal(f.loads,0);assert.equal(f.calls.length,0);
  }
});
test('missing, duplicate or non-storage required sources fail closed',async()=>{
  for(const change of [f=>f.list.splice(1,1),f=>f.list.push(copy(f.list[1])),f=>f.list[1].mode='yaml']){
    const f=fixture();change(f);await assert.rejects(()=>resolveCheckDashboard(f.args),/source dashboard/);
  }
});
test('dashboard identity and maintained metadata must remain exact',async()=>{
  for(const change of [f=>f.list[0].id='replacement',f=>f.list[0].require_admin=true,f=>f.list[0].show_in_sidebar=false]){
    const f=fixture();change(f);await assert.rejects(()=>resolveCheckDashboard(f.args),/identity|metadata/);
  }
});
test('trusted composer must target the same route and return exactly one expected metadata contract',async()=>{
  const f=fixture();f.dependencies.routes={...routes,energy:'other-energy'};
  await assert.rejects(()=>resolveCheckDashboard(f.args),/another Home Energy route/);
  for(const hubs of [[],[{url_path:'home-energy',metadata:{...desiredMetadata,require_admin:true},config:f.expected}]]){
    const g=fixture();g.dependencies.composeNavigation=()=>({hubs});
    await assert.rejects(()=>resolveCheckDashboard(g.args),/exactly one|metadata contract/);
  }
});
test('strict validator errors propagate rather than weakening source controls',async()=>{
  const f=fixture();f.dependencies.validateEg4=()=>{throw Error('Unsafe inert tile');};
  await assert.rejects(()=>resolveCheckDashboard(f.args),/Unsafe inert tile/);
});
test('declared-composition dependency failures are clear and do not leak underlying error text',async()=>{
  await assert.rejects(()=>loadCompositionDependencies(async()=>{throw Error('private import details');}),error=>/trusted sibling/.test(error.message)&&!/private import details/.test(error.message));
  await assert.rejects(()=>loadCompositionDependencies(async()=>({})),/unavailable or incompatible/);
});
