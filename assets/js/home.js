/* Content stays readable; scroll stages start below the measured header. */
(function(){
 'use strict';
 const data=window.SVN_HOME;if(!data)return;
 const motion=matchMedia('(prefers-reduced-motion: reduce)');
 const narrow=matchMedia('(max-width: 860px)'),short=matchMedia('(max-height: 720px)');
 const root=document.documentElement,scenes=document.getElementById('scenes'),stage=document.querySelector('.scenes-sticky'),panel=document.querySelector('.scene-panel');
 const lx=document.getElementById('lx'),lxStage=document.querySelector('.lx-stage'),record=document.querySelector('.legacy-readable');
 let sceneIndex=-1,milestoneIndex=-1,queued=false;
 const navHeight=()=>document.getElementById('nav')?.getBoundingClientRect().height||84;
 if(!motion.matches)root.classList.add('js');
 root.style.setProperty('--mile-count',data.milestones.length);
 const reveal=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');reveal.unobserve(e.target)}})},{threshold:0});
 document.querySelectorAll('.reveal').forEach(el=>reveal.observe(el));
 function setScene(index){
  if(index===sceneIndex)return;sceneIndex=index;
  ['#bgs .bgimg','#ttls h3','#pimgs img','#descs p'].forEach(selector=>{document.querySelectorAll(selector).forEach((el,i)=>{el.classList.toggle('on',i===index);el.setAttribute('aria-hidden',String(i!==index))})});
  document.getElementById('cnow').textContent=String(index+1).padStart(2,'0');
  document.getElementById('cbar').style.width=((index+1)/data.projects.length*100)+'%';
  document.querySelector('#metas .mon').textContent=data.projects[index].meta;
  const link=document.getElementById('sceneDiscover');link.href=data.projects[index].url;
  link.querySelector('.sd-txt').textContent=data.projects[index].external?'Visit project website':'Explore project';
  if(data.projects[index].external){link.target='_blank';link.rel='noopener'}else{link.removeAttribute('target');link.removeAttribute('rel')}
 }
 function setMilestone(index){
  if(index===milestoneIndex)return;milestoneIndex=index;const m=data.milestones[index];
  document.querySelector('#lxyear span').textContent=m.y;
  document.getElementById('lxtag').textContent=m.tag;document.getElementById('lxtitle').textContent=m.t;
  document.getElementById('lxdesc').textContent=m.d;
  document.getElementById('lxcoord').textContent=String(index+1).padStart(2,'0')+' / '+String(data.milestones.length).padStart(2,'0');
  document.getElementById('lxnow').textContent=m.y;
 }
 function progress(section,pinned){const total=section.offsetHeight-pinned.offsetHeight;return total>0?Math.max(0,Math.min(1,(navHeight()-section.getBoundingClientRect().top)/total)):0}
 const path=document.getElementById('lxpath'),fill=document.getElementById('lxpathfill'),dot=document.getElementById('lxdot');
 const length=path?path.getTotalLength():0;if(fill){fill.style.strokeDasharray=length;fill.style.strokeDashoffset=length}
 function update(){
  queued=false;
  if(!motion.matches&&!narrow.matches&&!short.matches){
   if(scenes&&!root.classList.contains('project-flow')){const p=progress(scenes,stage);setScene(Math.min(data.projects.length-1,Math.floor(p*data.projects.length)))}
   if(lx&&!root.classList.contains('timeline-flow')){
    const p=progress(lx,lxStage);setMilestone(Math.min(data.milestones.length-1,Math.floor(p*data.milestones.length)));
    document.getElementById('lxfill').style.width=(p*100)+'%';fill.style.strokeDashoffset=length*(1-p);
    const point=path.getPointAtLength(length*p);dot.style.left=(point.x/400*100)+'%';dot.style.top=(point.y/1000*100)+'%';
   }
  }
 }
 function schedule(){if(!queued){queued=true;requestAnimationFrame(update)}}
 function adapt(){
  root.classList.toggle('js',!motion.matches);root.classList.remove('project-flow','timeline-flow');
  if(!narrow.matches&&!short.matches&&!motion.matches){
   // Fall back to content in flow if text expansion or zoom exceeds the stage.
   if(panel.getClientRects().length&&panel.scrollHeight>innerHeight-navHeight()-48)root.classList.add('project-flow');
   if(lxStage.getClientRects().length&&lxStage.scrollHeight>lxStage.clientHeight+2)root.classList.add('timeline-flow');
  }
  if(record)record.open=narrow.matches||short.matches||motion.matches||root.classList.contains('timeline-flow');
  if(motion.matches){document.querySelectorAll('video').forEach(v=>{v.removeAttribute('autoplay');v.pause()});document.querySelectorAll('.reveal').forEach(el=>el.classList.add('in'))}
  schedule();
 }
 if(scenes)setScene(0);if(lx)setMilestone(0);adapt();
 addEventListener('scroll',schedule,{passive:true});addEventListener('resize',adapt,{passive:true});addEventListener('load',adapt,{once:true});
 document.fonts?.ready.then(adapt);motion.addEventListener('change',adapt);narrow.addEventListener('change',adapt);
})();
