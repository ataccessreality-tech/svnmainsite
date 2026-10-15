"""Latest supplied visual design plus crawlable pages, FAQ and PDF resources.
Loaded by build.py before generation. Uses only Python's standard library.
"""
FAQ = json.load(open(os.path.join(ROOT,'data/faq.json'), encoding='utf-8'))
RESOURCES = json.load(open(os.path.join(ROOT,'data/resources.json'), encoding='utf-8'))
BLOG = json.load(open(os.path.join(ROOT,'data/blog.json'), encoding='utf-8'))
BUYER_SOURCES = json.load(open(os.path.join(ROOT,'data/buyer-sources.json'), encoding='utf-8'))
FAQ_COUNT = sum(len(group['items']) for group in FAQ)
_head_html = head_html
_webpage_node = webpage_node
_footer_html = footer_html
_page_project = page_project
_page_person = page_person

def nav_items(home):
    return [('Projects','#projects' if home else '/projects/'),('Story','/about/'),
            ('Legacy','#legacy' if home else '/legacy/'),('FAQ','/faq/'),
            ('Resources','/resources/'),('Blog','/blog/'),('Contact','/contact/')]

def nav_html(home=False):
    items=nav_items(home)
    links=''.join(f'<a href="{u}">{n}</a>' for n,u in items)
    menu=links+(f'<a href="#enquire">Enquire</a>' if home else '')
    return f'''<nav class="nav" id="nav" aria-label="Primary"><a href="/" class="brand">{E(NAME)}</a><div class="links">{links}</div><a class="nav-phone" href="tel:{CO['phoneTel']}" aria-label="Call SVN on {E(CO['phone'])}">{E(CO['phone'])}</a><button class="burger" id="burger" aria-label="Open menu" aria-expanded="false" aria-controls="menu"><span></span><span></span><span></span></button></nav><div class="menu" id="menu" aria-hidden="true">{menu}</div>'''

def project_destination(p):
    return p['website']['url'] if p.get('_site_live') else p['_url']

def project_link(p):
    return f'<a href="{E(project_destination(p))}"'+(' target="_blank" rel="noopener"' if p.get('_site_live') else '')+f'>{E(p["name"])} →</a>'

def mobile_project_cards():
    cards=[]
    for p in PROJ:
        target=' target="_blank" rel="noopener"' if p.get('_site_live') else ''
        label='Visit project website' if p.get('_site_live') else 'Explore project'
        summary=f'<a class="project-summary" href="{p["_url"]}">Group overview</a>' if p.get('_site_live') else ''
        cards.append(f'''<article class="mobile-project-card"><img src="/{p['image']}" alt="{E(p.get('imageAlt',''))}" width="1600" height="900" loading="lazy"><div class="mobile-project-body"><span class="eyebrow">{E(p['homeMeta'])}</span><h3>{E(p['name'])}</h3><p>{E(p['homeDesc'])}</p><div class="project-actions"><a class="project-primary" href="{E(project_destination(p))}"{target}>{label} →</a>{summary}</div></div></article>''')
    return '<div class="mobile-projects wrap">'+''.join(cards)+'</div>'

def footer_html():
    t=_footer_html()
    t=t.replace('<div class="nm">','<img class="footer-logo" src="/assets/img/svn-logo.png" alt="SVN ShivaJyothi Group" width="1920" height="1080" loading="lazy"><div class="nm">')
    a=CO['address']
    old=f'<address>{E(a["street"])},<br>{E(a["city"])} {E(a["postalCode"])}, {E(a["state"])}<br><a href="tel:{CO["phoneTel"]}">{CO["phone"]}</a><br><a href="mailto:{CO["email"]}">{CO["email"]}</a></address>'
    street=''.join('<span>'+E(s.strip())+'</span>' for s in [', '.join(a['street'].split(',')[:2])])
    rest=', '.join(s.strip() for s in a['street'].split(',')[2:])
    address=f'<div class="footer-office"><span class="footer-label">Head office</span><address>{street}<span>{E(rest)}</span><span>{E(a["city"])} {E(a["postalCode"])}</span><span>{E(a["state"])}</span></address><div class="footer-contact"><a href="tel:{CO["phoneTel"]}">{CO["phone"]}</a><a href="mailto:{CO["email"]}">{CO["email"]}</a></div></div>'
    t=t.replace(old,address)
    return t.replace('<li><a href="/faq/">FAQ</a></li>',
      '<li><a href="/faq/">FAQ</a></li><li><a href="/resources/">Free handbooks</a></li><li><a href="/blog/">Buyer blog</a></li><li><a href="/vision/">Vision and mission</a></li><li><a href="/destinations/">Destinations</a></li>')

def webpage_node(path,name,desc,kind='WebPage',about=None,modified=None):
    if path.startswith('/leadership/') and path!='/leadership/': kind='ProfilePage'
    n=_webpage_node(path,name,desc,kind,about,modified)
    if kind=='ProfilePage': n['mainEntity']={'@id':absu(path)+'#person'}
    return n

def head_html(path,title,desc,robots='index,follow',og_type='website',graph=None,css_home=False,prefix='/'):
    title_map={p['_url']:p['name']+' | '+NAME for p in LAUNCHED}
    title_map.update({'/faq/':'75 Property Buyer FAQs | '+NAME,
                      '/resources/':'Buyer Guides and Downloads | '+NAME})
    blog_titles=['Three Checks Before Buying Property','Choosing a Property Location','Encumbrance Certificates Explained','Layout Approval and RERA Registration','Property Budgeting Beyond the Price','Plot Site Visit Checklist']
    title_map.update({'/blog/'+a['slug']+'/':title+' | SVN' for a,title in zip(BLOG,blog_titles)})
    if path.startswith('/leadership/') and path!='/leadership/':
        who=PEOPLE.get(path.strip('/').split('/')[-1])
        if who:title_map[path]=who['name']+' | '+NAME
    title=title_map.get(path,title)
    h=_head_html(path,title,desc,robots,og_type,graph,css_home,'/')
    img=F['site'].get('ogImages',{}).get(path,F['site']['ogImage'])
    old=absu('/'+F['site']['ogImage'].lstrip('/'));new=absu('/'+img.lstrip('/'))
    h=h.replace(old,new)
    h=re.sub(r'<link rel="icon"[^>]+>', '<link rel="icon" href="/assets/img/svn-logo.png" type="image/png">',h)
    return h+f'\n<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n<meta property="og:image:type" content="image/jpeg">\n<meta property="og:image:alt" content="{E(title)}">\n<meta name="twitter:image:alt" content="{E(title)}">\n<link rel="stylesheet" href="/assets/css/launch.css">\n<link rel="stylesheet" href="/assets/css/layout.css">\n'

def directors_html():
    cards=[]
    for p in F['people']:
        pic=(f'<div class="dir-pic"><img src="/{p["image"]}" alt="{E(p["imageAlt"])}" width="900" height="1200" loading="lazy"><span class="dir-gen">0{p["generation"]}</span></div>' if p.get('image') else '<div class="dir-pic dir-noimg"><span class="dir-mono">SVN</span><span class="dir-gen">01</span></div>')
        cards.append(f'<article class="dir">{pic}<div class="dir-body"><div class="dir-role">{E(p["role"])} · {p["generationLabel"]}</div><h3>{E(p["display"])}</h3><p>{E(" ".join(p["bio"]))}</p><a class="profile-link" href="/leadership/{p["id"]}/">Read profile →</a></div></article>')
    return ''.join(cards)

def resource_cards():
    return '<div class="resource-grid">'+''.join(f'''<article class="resource-card" id="{r['id']}"><span class="k">{r['category']} · PDF · {r['pages']} pages</span><h3>{r['title']}</h3><p>{r['description']}</p><a href="/downloads/{r['filename']}" download data-track="download_resource" data-resource="{r['id']}">Download PDF <span aria-hidden="true">↓</span></a></article>''' for r in RESOURCES)+'</div>'

def faq_preview():
    items=[FAQ[i]['items'][0] for i in (2,3,4,5,6)]
    return f'''<section class="home-answers pad" id="answers"><div class="wrap"><span class="eyebrow">A little clarity</span><h2>Questions, <em>answered.</em></h2><p class="answers-intro">Practical answers about buying property, checking documents and choosing a location.</p>{faq_block(items)}<a class="text-link" href="/faq/">Explore all {FAQ_COUNT} answers →</a></div></section><section class="home-resources pad" id="resources"><div class="wrap"><span class="eyebrow">Free buyer handbooks</span><h2>Start with the <em>right questions.</em></h2><p class="answers-intro">General property guidance with printable checklists. No form, no fee.</p>{resource_cards()}<a class="text-link" href="/resources/">View the resource library →</a></div></section><section class="home-blog pad" id="blog"><div class="wrap"><span class="eyebrow">The buyer journal</span><h2>Read. Check. <em>Decide.</em></h2><p class="answers-intro">Clear explanations for the decisions that come before a property purchase.</p>{blog_cards(BLOG[:3])}<a class="text-link" href="/blog/">Read all buyer articles →</a></div></section>'''

def build_home():
    title=NAME+' | Real Estate Developer in North Andhra'
    desc='A family-led developer in North Andhra. Explore SVN projects, the business legacy since 1971, leadership, FAQs and practical buyer guides.'
    graph=[website_node(),webpage_node('/',title,desc,about=absu('/#organization')),org_node(True)]+[person_node(p) for p in F['people']]
    source=open(os.path.join(ROOT,'src/home.src.html'),encoding='utf-8').read()
    blocks={
      'PROJECT_BGS':''.join(f'<div class="bgimg{" on" if i==0 else ""}"><img src="/{p["image"]}" alt="" width="1600" height="900" {"" if i==0 else "loading=\"lazy\""}></div>' for i,p in enumerate(PROJ)),
      'PROJECT_TITLES':''.join(f'<h3 class="{"on" if i==0 else ""}">{E(p["name"])}</h3>' for i,p in enumerate(PROJ)),
      'PROJECT_IMAGES':''.join(f'<img class="{"on" if i==0 else ""}" src="/{p["image"]}" alt="{E(p.get("imageAlt", ""))}" width="1600" height="900" {"" if i==0 else "loading=\"lazy\""}>' for i,p in enumerate(PROJ)),
      'PROJECT_DESCRIPTIONS':''.join(f'<p class="{"on" if i==0 else ""}">{E(p["homeDesc"])}</p>' for i,p in enumerate(PROJ)),
      'DIRECTORS':directors_html(),'FORM':form_html(PROJ,home=True),'FAQ_PREVIEW':faq_preview(),
      'PROJECT_LINKS':''.join(project_link(p) for p in PROJ)}
    for key,value in blocks.items():source=source.replace('{{'+key+'}}',value)
    source=source.replace('A route through <em>fifty years.</em>','A record across <em>generations.</em>')
    source=source.replace('SVN ShivaJyothi Group founded','Family enterprise founded')
    source=source.replace('property · fostering community','property · creating community')
    source=source.replace('<span class="k">5</span><span class="l">Active projects</span>',f'<span class="k">{len(PROJ)}</span><span class="l">Featured projects</span>')
    source=source.replace('<div class="portfolio-links wrap">',mobile_project_cards()+'<div class="portfolio-links wrap">')
    # The full timeline remains in server HTML for crawlers, keyboard users and no-JS visits.
    timeline='<details class="legacy-readable wrap" open><summary>Explore the full record, 1971 to 2026</summary><ol>'+''.join(f'<li><time datetime="{m["year"]}">{m["year"]}</time><strong>{E(m["title"])}</strong><p>{E(m["description"])}</p></li>' for m in MS)+'</ol><a href="/legacy/">Read the legacy page →</a></details>'
    source=source.replace('<h3>The story continues.</h3>', '<h3>The story continues.</h3><p><a class="text-link" href="/legacy/">Explore the full legacy →</a></p>')
    source=source.replace('<!-- RESORTS TEASER -->',timeline+'<!-- RESORTS TEASER -->') if '<!-- RESORTS TEASER -->' in source else source.replace('<section class="resorts-teaser" id="resorts">',timeline+'<section class="resorts-teaser" id="resorts">')
    if timeline not in source:source=source.replace('id="team"', 'id="team"')+timeline
    home_data={'projects':[{'meta':p['homeMeta'],'url':project_destination(p),'external':bool(p.get('_site_live'))} for p in PROJ],
      'milestones':[{'y':str(m['year']),'tag':m['tag'],'t':m['title'],'d':m['description'],'img':'/'+m['image']} for m in MS]}
    data=json.dumps(home_data,ensure_ascii=False).replace('<','\\u003c')
    page=f'''<!doctype html><html lang="en-IN"><head>{head_html('/',title,desc,graph=graph)}<link rel="preload" as="image" href="/assets/media/media-00.jpg" fetchpriority="high"></head><body><a class="skip" href="#main">Skip to content</a>{nav_html(True)}{WA_BTN}{source}{approvals_html()}{footer_html()}<script src="/assets/js/config.js"></script><script>window.SVN_HOME={data};</script><script src="/assets/js/site.js" defer></script><script src="/assets/js/home.js" defer></script></body></html>'''
    write('/',page);PAGES.append(('/',True,F['site']['lastUpdated']))

def brand_page(key,path,title,desc):
    source=open(os.path.join(ROOT,'src/'+key+'.src.html'),encoding='utf-8').read()
    source=source.replace("one of North Andhra's most trusted developers",'a developer working across North Andhra')
    source=source.replace('from the first layout to the flagship resort on the coast','from its business beginnings to the real estate journey that began in 2003')
    crumbs=[('Home','/'),(title,path)]
    source=source.replace('<span class="eyebrow">',crumbs_html(crumbs)+'<span class="eyebrow">',1)
    graph=[website_node(),webpage_node(path,title,desc,'AboutPage' if key=='story' else 'WebPage',absu('/#organization')),crumb_node(crumbs),org_node(False)]
    # Hero headings supply the one page H1; these panels are independent public URLs.
    write(path,f'<!doctype html><html lang="en-IN"><head>{head_html(path,title+" | "+NAME,desc,graph=graph)}</head><body class="brand-page"><a class="skip" href="#main">Skip to content</a>{nav_html(False)}{WA_BTN}<main id="main">{source}<section class="brand-next wrap"><h2>Explore the group.</h2><p><a href="/legacy/">Legacy</a> · <a href="/leadership/">Leadership</a> · <a href="/projects/">Projects</a> · <a href="/faq/">FAQ</a></p></section></main>{footer_html()}<script src="/assets/js/config.js"></script><script src="/assets/js/site.js" defer></script></body></html>')
    PAGES.append((path,True,F['site']['lastUpdated']))

def page_about():
    brand_page('story','/about/','SVN Story','Explore the story of SVN ShivaJyothi Group: a family enterprise since 1971, a developer since 2003 and three generations in North Andhra.')
    for key,title in [('vision','Vision and Mission'),('commitment','Our Commitment'),('pillars','Our Pillars'),('sustainability','Sustainability')]:
        brand_page(key,'/'+key+'/',title,f'{title} at SVN ShivaJyothi Group: the principles behind the group’s development approach in North Andhra Pradesh.')

def page_faq():
    chips='<nav class="faq-categories" aria-label="FAQ categories">'+''.join(f'<a href="#{g["id"]}">{g["title"]}</a>' for g in FAQ)+'</nav>'
    body=f'''<h2>Start with your question.</h2><p>General answers for property buyers, plus a short guide to SVN and its projects. Legal requirements depend on the property and location; use independent professional advice for your transaction.</p><div class="faq-search"><label for="faq-search">Search all {FAQ_COUNT} answers</label><input id="faq-search" type="search" placeholder="Try EC, location, land use or budget" aria-describedby="faq-results"><p id="faq-results" role="status">{FAQ_COUNT} answers in {len(FAQ)} categories</p></div>{chips}'''
    for group in FAQ:body+=f'<section class="faq-group" id="{group["id"]}"><h2>{group["title"]}</h2>{faq_block(group["items"])}</section>'
    body+='<section class="faq-next"><h2>Still have a question?</h2><p>Tell us which project you have in mind. <a href="/contact/">Contact SVN</a> or <a href="/resources/">download a buyer guide</a>.</p></section>'+updated(F['site']['lastUpdated'])
    items=[x for group in FAQ for x in group['items']]
    body+=sources_html([0,1,2,3,4])
    sub_page('/faq/','Frequently Asked Questions | '+NAME,'75 property buyer FAQs about land documents, ECs, RERA, approvals, locations, budgets, site visits, agreements and SVN projects.','Asked. Answered.',f'{FAQ_COUNT} useful answers across {len(FAQ)} categories. Find your question, then follow the next check.',body,[('FAQ','/faq/')],[org_node(False),faq_schema(items,'/faq/')],eyebrow='Clarity before you buy')
    page_resources();page_destinations();page_blog()

def page_resources():
    body='<h2>Useful before you buy.</h2><p>Free handbooks about property buying, location choices and land documents. Each guide includes practical checks and printable worksheets. General information, without project offers or promotional introductions. Edition: 11 October 2026.</p>'+resource_cards()
    body+='<h2>Read a little. Ask better questions.</h2><p>Browse the <a href="/blog/">buyer blog</a> for explanations, or search <a href="/faq/">75 frequently asked questions</a>. Downloads are available directly without an enquiry form.</p><p class="buyer-note">These guides organize your questions; they do not certify a property or replace a lawyer, surveyor, engineer or financial adviser. Use current official requirements for the exact property and jurisdiction.</p>'+updated(F['site']['lastUpdated'])
    docs=[{'@type':'DigitalDocument','@id':absu('/resources/#'+r['id']),'name':r['title'],'description':r['description'],'url':absu('/resources/#'+r['id']),'inLanguage':'en-IN','isAccessibleForFree':True,'dateModified':F['site']['lastUpdated'],'publisher':{'@id':absu('/#organization')},'encoding':{'@type':'MediaObject','contentUrl':absu('/downloads/'+r['filename']),'encodingFormat':'application/pdf'}} for r in RESOURCES]
    listing={'@type':'ItemList','@id':absu('/resources/#downloads'),'numberOfItems':len(docs),'itemListElement':[{'@type':'ListItem','position':i+1,'item':{'@id':d['@id']}} for i,d in enumerate(docs)]}
    sub_page('/resources/','Buyer Guides and Downloads | '+NAME,'Download free property buyer handbooks: three checks before buying, choosing the right location and understanding land documents. No registration required.','Take a little clarity.','Three practical handbooks. Free to download. Ready to use.',body,[('Resources','/resources/')],[org_node(False),listing]+docs,eyebrow='The resource library',kind='CollectionPage')

def sources_html(ids):
    if not ids:return ''
    return '<aside class="buyer-sources"><h2>Official reading and verification</h2><ul>'+''.join(f'<li><a href="{E(BUYER_SOURCES[i]["url"])}" target="_blank" rel="noopener">{E(BUYER_SOURCES[i]["title"])}</a></li>' for i in ids)+'</ul><p>References checked for this edition. Portals and procedures can change; contact the relevant office when a service is unavailable.</p></aside>'

def blog_cards(articles):
    return '<div class="blog-grid">'+''.join(f'<article class="blog-card"><span class="k">{E(a["category"])}</span><h3><a href="/blog/{a["slug"]}/">{E(a["title"])}</a></h3><p>{E(a["description"])}</p><a class="read-link" href="/blog/{a["slug"]}/">Read article →</a></article>' for a in articles)+'</div>'

def page_blog():
    body='<h2>Start with what you need to know.</h2><p>Original, practical articles for property buyers. Read about ownership checks, location decisions, approvals, budgets and the questions to take on a site visit.</p>'+blog_cards(BLOG)+'<h2>Keep a checklist close.</h2><p><a href="/resources/">Download the free handbooks</a> or <a href="/faq/">search the buyer FAQs</a>.</p>'
    listing={'@type':'ItemList','@id':absu('/blog/#articles'),'numberOfItems':len(BLOG),'itemListElement':[{'@type':'ListItem','position':i+1,'url':absu('/blog/'+a['slug']+'/'),'name':a['title']} for i,a in enumerate(BLOG)]}
    sub_page('/blog/','Property Buyer Blog | '+NAME,'Practical property buyer articles on land documents, ECs, RERA, location, budgets and plot site visits, with free downloadable checklists.','Read. Check. Decide.','Helpful reading for the questions that come before a property purchase.',body,[('Blog','/blog/')],[org_node(False),listing],eyebrow='The buyer journal',kind='CollectionPage')
    for a in BLOG:
        path='/blog/'+a['slug']+'/'
        words=sum(len(p.split()) for _,ps in a['sections'] for p in ps);minutes=max(2,(words+199)//200)
        body=f'<article class="buyer-article"><p class="article-meta">{E(a["category"])} · {minutes} min read · <time datetime="{a["date"]}">{D(a["date"])}</time></p>'
        body+='<nav class="article-toc" aria-label="In this article"><strong>In this article</strong><ol>'+''.join(f'<li><a href="#section-{i+1}">{E(title)}</a></li>' for i,(title,_) in enumerate(a['sections']))+'</ol></nav>'
        body+=''.join(f'<section id="section-{i+1}"><h2>{E(title)}</h2>'+''.join('<p>'+E(p)+'</p>' for p in paragraphs)+'</section>' for i,(title,paragraphs) in enumerate(a['sections']))
        body+='<p class="buyer-note">General buyer education. This article does not assess any specific property or replace transaction-specific legal, tax, financial or technical advice.</p>'+sources_html(a['sources'])+'</article>'
        r=next(r for r in RESOURCES if r['id']==a['guide'])
        body+=f'<aside class="article-download"><span class="k">Free companion handbook</span><h2>{E(r["title"])}</h2><p>{E(r["description"])}</p><a href="/downloads/{r["filename"]}" download data-track="download_resource" data-resource="{r["id"]}">Download the PDF →</a></aside>'
        related=[x for x in BLOG if x['slug']!=a['slug']][:2]
        body+='<h2>Keep reading.</h2>'+blog_cards(related)
        post={'@type':'BlogPosting','@id':absu(path)+'#article','headline':a['title'],'description':a['description'],'url':absu(path),'mainEntityOfPage':{'@id':absu(path)+'#webpage'},'datePublished':a['date'],'dateModified':a['date'],'inLanguage':'en-IN','wordCount':words,'articleSection':a['category'],'author':{'@id':absu('/#organization')},'publisher':{'@id':absu('/#organization')},'image':absu('/'+F['site']['ogImages'][path]),'isAccessibleForFree':True}
        sub_page(path,a['title']+' | '+NAME,a['description'],a['title'],a['description'],body,[('Blog','/blog/'),(a['title'],path)],[org_node(False),post],eyebrow='Buyer education',og_type='article')

def page_destinations():
    projects=[p for p in LAUNCHED if p['slug'] in ('bay-parck','parckwud','miraya')]
    cards=''.join(f'<article class="destination-card"><img src="/{p["image"]}" width="1600" height="900" loading="lazy" alt="{E(p["imageAlt"])}"><div><h2>{p["name"]}</h2><p>{E(p["homeDesc"])}</p><a href="{p["_url"]}">Explore the project →</a></div></article>' for p in projects)
    body='<h2>Different settings. One portfolio.</h2><p>Explore coastal and nature-oriented developments in the SVN portfolio. Internal layout amenities and separately operated hospitality facilities have different scopes and access terms.</p>'+cards+'<h2>Ask about access.</h2><p>This page is a project introduction. It does not offer room bookings or promise access to every facility shown. For current facilities, visit arrangements and applicable membership terms, <a href="/contact/">contact SVN</a>.</p>'+updated(F['site']['lastUpdated'])
    sub_page('/destinations/','Destination Projects | '+NAME,'Explore SVN Bay Parck, Parckwud and miraya: different project settings across North Andhra, with project-specific facilities and access terms.','Places to experience.','Explore the destinations. Ask about the details.',body,[('Destinations','/destinations/')],[org_node(False)],eyebrow='A sense of place',kind='CollectionPage')

def page_project(p):
    _page_project(p)
    fp=os.path.join(OUT,p['_url'].strip('/'),'index.html');t=open(fp,encoding='utf-8').read()
    t=t.replace('<h2>Frequently asked questions</h2>','<h2>Useful before your visit</h2><p><a href="/resources/">Download a document checklist or site visit planner</a>. For questions across the portfolio, explore the <a href="/faq/">FAQ library</a>.</p><h2>Frequently asked questions</h2>')
    if p['slug']=='ayodhara':t=t.replace('<h2>Project facts</h2>','<p>Ask the team for the current RERA registration status and applicable documents. A layout approval number alone does not state that RERA registration has been confirmed.</p><h2>Project facts</h2>')
    if p['slug']=='bay-parck':t=t.replace('<h2>Project facts</h2>','<p>Confirm with SVN which approval and registration documents apply to the current phase and specific plot you are considering.</p><h2>Project facts</h2>')
    open(fp,'w',encoding='utf-8').write(t)

