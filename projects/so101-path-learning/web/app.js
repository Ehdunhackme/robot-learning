import {mountDisclosure} from './disclosure.mjs';
mountDisclosure(document.querySelector('#settings'));
import {buildScene} from './scene.js';

const $ = id => document.getElementById(id);
const config = {
  pickup: {title:'Handle pickup', brief:'Locate the handle, lift the part and hold it between both jaws.',seed:813009,
    sliders:[['pixels','Mask width',48,128,96,'px']],methods:[['learned','Predicted grasp'],['direct','Fixed grasp']]},
  placement: {title:'Peg placement', brief:'Carry the part to the predicted peg pose and release it.',seed:813000,
    sliders:[['pixels','Mask width',48,128,96,'px'],['clearance','Peg clearance',1,4,2,'mm']],methods:[['learned','Predicted peg pose'],['direct','Fixed peg pose']]},
  shelf: {title:'Shelf inspection', brief:'Reach inside the shelf, hold at the target, then return home.', seed:720001,
    sliders:[['width','Opening width',85,190,110,'mm'],['depth','Inspection depth',45,105,75,'mm']],
    methods:[['learned','Learned route'],['fixed','Fixed route'],['direct','Direct reach']]},
  reach: {title:'Obstacle reach', brief:'Move the gripper to the marked point while clearing the fixture.', seed:700000,
    sliders:[['offset','Fixture offset',-55,55,0,'mm'],['angle','Target rotation',-18,18,0,'°']],
    methods:[['learned','Learned route'],['direct','Direct reach']]}
};
const url = new URL(location.href);
let task = url.searchParams.get('task') || url.searchParams.get('study') || 'reach';
if (!Object.hasOwn(config,task)) task='reach';
let info, view, run, seed, mode='learned', ticket=0, time=0, playing=false, last=0, inspect=false;
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const cache=new Map();
const pretty=s => s==='moving_jaw_so101_v1'?'Moving jaw':s.replaceAll('_',' ');
const method=()=>run?.[mode];
function message(text){$('status').textContent=text;$('status').hidden=!text;}
function option(v,label){return new Option(label,v);}
function applyTask(key,writeUrl=true){
  task=key;seed=config[key].seed;mode=config[key].methods[0][0];run=null;setPlay(false);inspect=false;
  $('loading').textContent='Preparing replay…';$('loading').hidden=false;$('viewport').classList.add('pending');
  $('outcome').textContent='';$('metrics').replaceChildren();$('time').textContent='0.00 s';$('duration').textContent='';$('scrub').value=0;
  if(writeUrl){const u=new URL(location.href);u.searchParams.delete('study');u.searchParams.set('task',key);u.hash='';history.replaceState(null,'',u);}
  for(const btn of document.querySelectorAll('[data-task]'))btn.setAttribute('aria-pressed',String(btn.dataset.task===key));
  $('sceneTitle').textContent=config[key].title;$('brief').textContent=config[key].brief;
  $('controller').replaceChildren(...config[key].methods.map(([v,label])=>option(v,label)));
  $('sliders').replaceChildren();
  for(const [id,title,min,max,value,unit] of config[key].sliders){
    const label=document.createElement('label');label.htmlFor=id;label.textContent=title;
    const out=document.createElement('output');out.value=value+' '+unit;label.append(out);
    const slider=document.createElement('input');Object.assign(slider,{id,type:'range',min,max,value});
    slider.oninput=()=>{out.value=slider.value+' '+unit;syncExample();message('Apply layout to replay these settings.');};
    $('sliders').append(label,slider);
  }
  const shelf=key==='shelf';
  for(const id of ['exampleRow','mouthView','sectionRow','closest'])$(id).hidden=!shelf;
  $('fixtureRow').hidden=key!=='reach';$('pathRow').hidden=false;
  $('family').value='0';$('camera').value='work';view?.paths($('paths').checked);
  $('section').checked=true;view?.cutaway(true);syncExample();
}
function syncExample(){
  if(task!=='shelf'||!info)return;
  const i=info.examples.findIndex(e=>e[1]===seed&&e[2]===+$('width').value&&e[3]===+$('depth').value);
  $('examples').value=i<0?'custom':String(i);
}
function busy(on){
  for(const id of ['controller','play','scrub'])$(id).disabled=on||!run;
  for(const id of ['new','run','closest'])$(id).disabled=on;
}
async function simulate(){
  if(!view)return;
  const seq=++ticket;setPlay(false);busy(true);message('');$('loading').hidden=false;$('loading').textContent='Preparing replay…';
  const query=new URLSearchParams({family:task==='pickup'?8:task==='placement'?9:task==='shelf'?3:$('family').value,seed});
  for(const [id] of config[task].sliders)query.set(id,$(id).value);
  try{
    let data=cache.get(query.toString());
    if(!data){const reply=await fetch('/api/run?'+query);data=await reply.json();if(!reply.ok)throw new Error(data.error||'Could not run this layout.');
      if(cache.size>=8)cache.delete(cache.keys().next().value);cache.set(query.toString(),data);}
    if(seq!==ticket)return;
    run=data;view.setup(data);view.cameraView($('camera').value);view.cutaway($('section').checked);
    $('viewport').classList.remove('pending');$('loading').hidden=true;busy(false);pick(mode);
  }catch(e){
    if(seq!==ticket)return;
    $('loading').hidden=!!run;if(!run)$('loading').textContent='Replay unavailable';
    message(e.message+(run?' Showing the previous layout.':' Try another layout.'));busy(false);
  }
}
function setPlay(on){
  playing=on;last=performance.now();
  $('play').textContent=on?'Pause':method()&&time>=method().seconds?'Replay':'Play';
}
function metric(label,value){
  const row=document.createElement('div'),name=document.createElement('dt'),v=document.createElement('dd');
  name.textContent=label;v.textContent=value;row.append(name,v);$('metrics').append(row);
}
function pick(key){
  if(!run?.[key])return;
  mode=key;time=0;inspect=false;$('controller').value=key;view.gap(null);view.showRoute(key);view.paths($('paths').checked);
  const p=method();
  $('duration').textContent='/ '+p.seconds.toFixed(2)+' s';$('metrics').replaceChildren();
  metric('Final outcome',outcomeText(p));metric('Layout',run.seed);
  metric('Gripper travel',p.distance_mm+' mm');
  if(run.observation){
    metric('Pose estimate error',p.pose_error_mm+' mm');metric('Peak lift',p.lift_mm+' mm');
    metric(task==='pickup'?'Time held':'Time seated',(task==='pickup'?p.held_s:p.seated_s)+' s');
  }
  if(task!=='pickup')metric(task==='shelf'?'Final home error':'Final target error',p.error_mm+' mm');
  if(task==='shelf'){const g=p.gaps[closestIndex(p)];metric('Closest surfaces',pretty(g.link)+' / '+g.panel.toLowerCase());metric('Sampled clearance',g.mm.toFixed(2)+' mm');}
  draw();setPlay(!reduced.matches&&!$('workbench').hidden);
}
function closestIndex(p){return p.gaps.reduce((best,g,i)=>g.mm<p.gaps[best].mm?i:best,0);}
function outcomeText(p){
  if(p.outcome==='contact')return 'Contact';
  if(p.outcome==='reached')return {pickup:'Lift held',placement:'Seated and released',shelf:'Inspection complete',reach:'Target reached'}[task];
  return 'Missed tolerance';
}
function progress(p,frame){
  const done=time>=p.seconds;
  const phase=task==='pickup'?'Lifting':task==='placement'?'Placing':task==='reach'?'Reaching':time<3.6?'Entering shelf':time<4?'Holding position':'Returning home';
  const label=done?outcomeText(p):time===0?'Ready':phase;
  const output=$('outcome');
  if(label!==output.textContent)output.textContent=label;
  if(done)output.dataset.ok=String(p.outcome==='reached');else delete output.dataset.ok;
}
function draw(){
  const p=method();if(!p)return;
  let lo=0,hi=p.frames.length-1;
  while(lo<hi){const m=Math.ceil((hi+lo)/2);if(p.frames[m][0]<=time)lo=m;else hi=m-1;}
  view.pose(p.frames[lo]);progress(p,p.frames[lo]);
  if(inspect&&p.gaps){const g=p.gaps[lo];view.gap(g.points,pretty(g.link)+' / '+g.panel.toLowerCase()+' · '+g.mm.toFixed(2)+' mm');}
  $('scrub').value=Math.round(1000*time/p.seconds);$('time').value=time.toFixed(2)+' s';
}
function animate(now){
  if(playing&&run&&!document.hidden){time=Math.min(method().seconds,time+(now-last)*+$('speed').value/1000);draw();if(time>=method().seconds)setPlay(false);}
  last=now;requestAnimationFrame(animate);
}
function navigate(){
  const log=location.hash==='#results';$('research').hidden=!log;$('workbench').hidden=log;
  for(const [id,active] of [['logTab',log],['workTab',!log]]){if(active)$(id).setAttribute('aria-current','page');else $(id).removeAttribute('aria-current');}
  if(log)setPlay(false);
}
window.addEventListener('hashchange',navigate);
for(const btn of document.querySelectorAll('[data-task]'))btn.onclick=()=>{if(btn.dataset.task===task)return;applyTask(btn.dataset.task);simulate();};
$('controller').onchange=()=>pick($('controller').value);
$('family').onchange=()=>{seed=info.scenes[+$('family').value][1];simulate();};
$('examples').onchange=()=>{const example=info.examples[+$('examples').value];if(!example)return;
  seed=example[1];for(const [index,id] of [[2,'width'],[3,'depth']]){$(id).value=example[index];$(id).previousElementSibling.querySelector('output').value=example[index]+' mm';}
  mode='learned';simulate();};
$('new').onclick=()=>{seed=crypto.getRandomValues(new Uint32Array(1))[0]%2147483647;syncExample();simulate();};
$('run').onclick=simulate;
$('play').onclick=()=>{if(!run)return;if(time>=method().seconds)time=0;setPlay(!playing);draw();};
$('scrub').oninput=()=>{if(!run)return;time=method().seconds*+$('scrub').value/1000;setPlay(false);draw();};
$('closest').onclick=()=>{const p=method();if(!p?.gaps)return;time=p.frames[closestIndex(p)][0];inspect=true;setPlay(false);draw();$('viewport').scrollIntoView({block:'nearest'});};
$('paths').onchange=()=>view?.paths($('paths').checked);
$('section').onchange=()=>view?.cutaway($('section').checked);
$('camera').onchange=()=>view?.cameraView($('camera').value);
$('resetView').onclick=()=>{$('camera').value='work';view?.reset();};
const films={pickup:'/pickup.mp4',placement:'/placement.mp4',shelf:'/shelf.mp4',reach:'/demo.mp4'};
$('watch').onclick=()=>{setPlay(false);$('filmTitle').textContent=config[task].title;$('video').src=films[task];$('film').showModal();$('video').play().catch(()=>{});};
$('closeFilm').onclick=()=>$('film').close();$('film').onclose=()=>$('video').pause();
function showResults(data){
  const root=$('findings');
  const add=(parent,tag,value)=>{const el=document.createElement(tag);el.textContent=value;parent.append(el);return el;};
  function table(parent,head,rows){
    const wrap=add(parent,'div','');wrap.className='tablewrap';
    const table=add(wrap,'table',''),h=table.createTHead().insertRow(),b=table.createTBody();
    for(const v of head)add(h,'th',v);
    for(const row of rows){const tr=b.insertRow();for(const v of row)add(tr,'td',v);}
  }
  const r=data.report,s=data.shelf;
  add(root,'h2','Supervised pose estimation');
  table(root,['Task','Fixed pose','Predicted pose','Mean XY error'],[['Handle pickup','pickup'],['Peg placement','placement']].map(([name,key])=>{
    const m=data.visual[key];return [name,m.direct.success+' / 32',m.learned.success+' / 32',m.learned.mean_pose_error_mm+' mm'];
  }));
  add(root,'h2','Shelf inspection');add(root,'p','The same 96 layouts were tested at each width. The arm had to enter, hold for 0.4 seconds and return home without contact.');
  table(root,['Opening','Direct','Fixed','Learned'],s.by_width.map(w=>[w.width+' mm',...['direct','fixed','learned'].map(k=>w[k]+' / '+w.n)]));
  const shelf=add(root,'details','');add(shelf,'summary','Shelf route coverage');
  add(shelf,'p','Layouts with at least one clear inward route at 81 sampled poses. Six candidates align the arm before entry.');
  table(shelf,['Opening','Original 13 routes','Expanded 19 routes'],s.by_width.map(w=>[w.width+' mm',w.legacy_feasible+' / '+w.n,w.feasible+' / '+w.n]));
  add(root,'h2','Obstacle reach');add(root,'p','Successful servo replays ended within 8 mm of the target without contact.');
  table(root,['Controller','Reached','Contact','Missed'],Object.entries(r.servo).map(([name,m])=>[name,m.reached,m.contact,m.miss]));
  const other=add(root,'details','');add(other,'summary','Geometric evaluation and training trials');
  add(other,'p','The collision test sampled 81 poses per path on the same '+r.test+' held-out scenes.');
  table(other,['Planner','Clear paths','Joint travel','Cost'],Object.entries(r.metrics).map(([name,m])=>[name,m.clear_count+' / '+r.test,m.mean_joint_length_rad.toFixed(2)+' rad',m.cost.toFixed(3)]));
  add(other,'p','Each A100 trial used 1,000 optimizer updates and the same 4,096 training scenes. Lower validation cost wins.');
  table(other,['Trial','Validation cost','Clear rate','Decision'],r.trials.map(t=>[t.trial,(+t.validation_cost).toFixed(4),(100*t.clear_rate).toFixed(1)+'%',t.status]));
}
(async()=>{
  navigate();applyTask(task,false);busy(true);
  try{
    const response=await fetch('/api/info');if(!response.ok)throw Error('The simulator is offline.');
    info=await response.json();showResults(info);info.examples.forEach(([name],i)=>$('examples').add(option(i,name)));
    const custom=option('custom','Custom layout');custom.disabled=true;$('examples').add(custom);syncExample();
    view=await buildScene($('viewport'));await simulate();requestAnimationFrame(animate);
  }catch(e){
    $('loading').textContent='3D replay unavailable';message(e.message);
    if(info){const a=document.createElement('a');a.href=films[task];a.textContent='Watch the recorded replay';$('loading').append(' · ',a);}
  }
})();
