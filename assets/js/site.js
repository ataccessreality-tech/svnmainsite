/* SVN shared behaviour: menu, analytics events, attribution capture, enquiry form. No secrets here. */
(function(){
  var C=window.SVN_CONFIG||{};
  // Measure the header for anchors, menu and pinned stages, including browser zoom.
  var header=document.getElementById('nav');
  function measureHeader(){if(header)document.documentElement.style.setProperty('--nav-h',Math.ceil(header.getBoundingClientRect().height)+'px')}
  measureHeader();
  if(header&&window.ResizeObserver)new ResizeObserver(measureHeader).observe(header);
  addEventListener('resize',measureHeader,{passive:true});
  document.fonts&&document.fonts.ready.then(measureHeader);
  // ---------- analytics (GA4 only loads when an ID is configured) ----------
  window.dataLayer=window.dataLayer||[];
  function gtag(){dataLayer.push(arguments)}
  if(C.GA4_ID){
    var s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(C.GA4_ID);document.head.appendChild(s);
    gtag('js',new Date());gtag('config',C.GA4_ID);
  }
  function track(name,params){try{gtag('event',name,params||{})}catch(e){}}
  window.svnTrack=track;

  // ---------- attribution (UTM, referrer, landing page) ----------
  var KEYS=['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','fbclid'];
  var attr={};
  try{attr=JSON.parse(sessionStorage.getItem('svn_attr')||'{}')}catch(e){}
  var qs=new URLSearchParams(location.search),touched=false;
  KEYS.forEach(function(k){if(qs.get(k)){attr[k]=qs.get(k);touched=true}});
  if(!attr.landing_page){attr.landing_page=location.pathname;attr.referrer=document.referrer||'';touched=true}
  if(touched){try{sessionStorage.setItem('svn_attr',JSON.stringify(attr))}catch(e){}}


  // ---------- image fallbacks: any image that fails to load is replaced by a branded placeholder ----------
  var BASE=(document.currentScript&&document.currentScript.src)?new URL('../img/',document.currentScript.src).href:'/assets/img/';
  function phFor(src,el){
    var f=(src||'').split('?')[0].split('/').pop().toLowerCase();
    if(/bayparck|bay-parck/.test(f))return 'ph-bayparck.jpg';
    if(/parckwud/.test(f))return 'ph-parckwud.jpg';
    if(/miraya/.test(f))return 'ph-miraya.jpg';
    if(/ayodhara/.test(f))return 'ph-ayodhara.jpg';
    if(/siva|nithin|portrait/.test(f)||(el&&el.alt&&/portrait/i.test(el.alt)))return 'ph-portrait.jpg';
    if(/hero/.test(f))return 'ph-hero.jpg';
    return 'ph-generic.jpg';
  }
  document.addEventListener('error',function(e){
    var el=e.target;if(!el||el.tagName!=='IMG')return;
    if((el.currentSrc||el.src).indexOf('/ph-')>-1)return;
    el.src=BASE+phFor(el.currentSrc||el.src,el);
  },true);
  function fixBroken(){document.querySelectorAll('img').forEach(function(im){if(im.complete&&im.naturalWidth===0&&im.getAttribute('src')&&im.src.indexOf('/ph-')<0)im.src=BASE+phFor(im.src,im)})}
  function fixTiles(){
    document.querySelectorAll('.mtile').forEach(function(t){
      var m=(t.getAttribute('style')||'').match(/url\(['"]?([^'")]+)['"]?\)/);if(!m)return;
      var im=new Image();im.onerror=function(){t.style.setProperty('--img',"url('"+BASE+phFor(m[1])+"')")};im.src=m[1];
    });
  }
  document.addEventListener('DOMContentLoaded',function(){fixBroken();fixTiles()});
  addEventListener('load',fixBroken);

  // ---------- mobile menu ----------
  var b=document.getElementById('burger'),m=document.getElementById('menu'),prevFocus;if(m)m.inert=true;
  if(b&&m){
    var set=function(o){if(o)prevFocus=document.activeElement;m.inert=!o;m.classList.toggle('open',o);b.classList.toggle('x',o);b.setAttribute('aria-expanded',o);m.setAttribute('aria-hidden',!o);b.setAttribute('aria-label',o?'Close menu':'Open menu');document.body.style.overflow=o?'hidden':'';if(o)m.querySelector('a').focus();else if(prevFocus)prevFocus.focus()};
    b.addEventListener('click',function(){set(!m.classList.contains('open'))});
    m.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(){set(false)})});
    addEventListener('keydown',function(e){if(!m.classList.contains('open'))return;if(e.key==='Escape')set(false);if(e.key==='Tab'){var nodes=[b].concat(Array.from(m.querySelectorAll('a'))),i=nodes.indexOf(document.activeElement);if(e.shiftKey&&i<=0){e.preventDefault();nodes[nodes.length-1].focus()}else if(!e.shiftKey&&i===nodes.length-1){e.preventDefault();b.focus()}}});
  }

  // ---------- delegated click events ----------
  document.addEventListener('click',function(e){
    var a=e.target.closest&&e.target.closest('a');if(!a)return;
    var h=a.getAttribute('href')||'';
    if(h.indexOf('tel:')===0)track('click_call');
    else if(h.indexOf('mailto:')===0)track('click_email');
    else if(h.indexOf('wa.me')>-1)track('click_whatsapp');
    var t=a.getAttribute('data-track');if(t)track(t,{page:location.pathname,resource:a.getAttribute('data-resource')||''});
  });
  var pj=document.body.getAttribute('data-project');if(pj)track('view_project',{project:pj});

  // ---------- enquiry form ----------
  var f=document.querySelector('form[data-form="enquiry"]');
  initFaqSearch();if(!f)return;
  var msg=f.querySelector('.fs-msg'),started=false,t0=Date.now(),pending=false,submit=f.querySelector('[type=submit]');
  f.addEventListener('focusin',function(){if(!started){started=true;track('form_start')}});
  function say(x){if(msg)msg.textContent=x}
  f.addEventListener('submit',function(e){
    e.preventDefault();if(pending)return;
    var d=new FormData(f);
    var name=(d.get('name')||'').trim(),email=(d.get('email')||'').trim(),phone=(d.get('phone')||'').trim(),proj=d.get('project');
    if(d.get('company_website'))return; // honeypot: ignore automated submissions
    if(!name||!/^\S+@\S+\.\S+$/.test(email)||!/^\d{10,15}$/.test(phone.replace(/\D/g,''))||!proj||!f.querySelector('[name=consent]').checked){
      say('Please complete all fields, choose a project and tick the consent box.');return;
    }
    var payload={name:name,email:email,phone:phone,project:proj,interest:d.getAll('interest'),consent:true,
      source_page:location.pathname,landing_page:attr.landing_page,referrer:attr.referrer||document.referrer||'',
      timestamp:new Date().toISOString()};
    KEYS.forEach(function(k){if(attr[k])payload[k]=attr[k]});
    track('submit_enquiry',{project:proj});
    var wa=function(){
      var text=encodeURIComponent('Hello SVN, I would like to enquire.\nName: '+name+'\nPhone: '+phone+'\nEmail: '+email+'\nProject: '+proj+'\nInterested in: '+(payload.interest.join(', ')||'Not specified'));
      var url='https://wa.me/'+(C.WHATSAPP||'')+'?text='+text;var a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=' Open WhatsApp';if(msg)msg.appendChild(a);window.open(url,'_blank','noopener');
    };
    if(C.ENQUIRY_ENDPOINT){
      pending=true;if(submit)submit.disabled=true;say('Sending...');var controller=new AbortController(),timeout=setTimeout(function(){controller.abort()},12000);
      fetch(C.ENQUIRY_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal})
        .then(function(r){if(!r.ok)throw 0;say('Thank you. We will be in touch shortly.');track('generate_lead',{project:proj});f.reset()})
        .catch(function(){say('We could not send this just now. Continue in WhatsApp to reach us directly.');wa()}).finally(function(){clearTimeout(timeout);pending=false;if(submit)submit.disabled=false});
    }else{
      say('Continue in WhatsApp and press Send to share your enquiry with SVN.');track('open_enquiry_whatsapp',{project:proj});wa();
    }
  });
function initFaqSearch(){var input=document.getElementById('faq-search');if(!input)return;input.addEventListener('input',function(){var term=input.value.trim().toLowerCase(),count=0;document.querySelectorAll('.faq-group').forEach(function(group){var matches=0;group.querySelectorAll('details').forEach(function(detail){var show=detail.textContent.toLowerCase().includes(term);detail.hidden=!show;detail.open=!!term&&show;if(show){matches++;count++}});group.hidden=!matches});document.getElementById('faq-results').textContent=count?count+' matching answers':'No answers found. Try another word or contact SVN.'})}
})();
