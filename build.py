#!/usr/bin/env python3
"""
SVN ShivaJyothi Group: static site builder.
Reads data/facts.json (single source of truth) and src/home.src.html (the premium homepage),
and writes a deployable site to dist/.

    python3 build.py                              # normal build
    python3 build.py --site-url https://svn.example   # real domain
    python3 build.py --today 2026-10-12           # simulate a date (project auto-promotion)
    python3 build.py --include-drafts             # also emit unpublished location pages for template testing
"""
import json, re, os, sys, shutil, html, argparse, datetime, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--site-url'); ap.add_argument('--today'); ap.add_argument('--out', default='dist')
ap.add_argument('--include-drafts', action='store_true'); ap.add_argument('--live', default='', help='comma list of project slugs to treat as having a live project website (testing)')
A = ap.parse_args()

F = json.load(open(os.path.join(ROOT, 'data/facts.json'), encoding='utf-8'))
SITE = (A.site_url or F['site']['url']).rstrip('/')
TODAY = datetime.date.fromisoformat(A.today) if A.today else datetime.date.today()
OUT = os.path.join(ROOT, A.out)
CO = F['company']; NAME = CO['officialName']
E = lambda s: html.escape(str(s), quote=True)

# ------------------------------------------------------------------ launch states
PUBLISHED_STATES = ('launched', 'completed', 'sold-out')
for p in F['projects']:
    p['_state'] = p['state']
    if p['state'] == 'teaser' and p.get('autoPromoteOn') and TODAY >= datetime.date.fromisoformat(p['autoPromoteOn']):
        p['_state'] = 'launched'
    p['_pub'] = p['_state'] in PUBLISHED_STATES
    p['_url'] = f"/projects/{p['slug']}/"
LIVE_OVERRIDE = {s.strip() for s in A.live.split(',') if s.strip()}
for p in F['projects']:
    w = p.get('website') or {}
    p['_site_live'] = bool((w.get('live') or p['slug'] in LIVE_OVERRIDE) and w.get('url'))
PROJ = [p for p in F['projects'] if p['_state'] != 'draft']      # visible on homepage (launched or teaser)
LAUNCHED = [p for p in F['projects'] if p['_pub']]
PEOPLE = {p['id']: p for p in F['people']}
LOCS = [l for l in F['locations'] if l.get('publish') or A.include_drafts]

def D(s): return datetime.date.fromisoformat(s).strftime('%-d %B %Y')
def absu(path): return SITE + path
def addr_line():
    a = CO['address']; return f"{a['street']}, {a['city']} {a['postalCode']}, {a['state']}"

# ------------------------------------------------------------------ schema
def org_node(full=True):
    n = {"@type": "Organization", "@id": absu('/#organization'), "name": NAME, "url": absu('/')}
    if not full: return n
    n.update({"foundingDate": str(CO['businessSince']),
              "founder": {"@id": absu(f"/leadership/{CO['founderId']}/#person")},
              "address": {"@type": "PostalAddress", "streetAddress": CO['address']['street'], "addressLocality": CO['address']['city'],
                          "addressRegion": CO['address']['state'], "postalCode": CO['address']['postalCode'], "addressCountry": CO['address']['country']},
              "contactPoint": {"@type": "ContactPoint", "contactType": "sales", "telephone": CO['phone'], "email": CO.get('emailProjects') or CO['email'], "areaServed": "IN"},
              "location": [{"@type": "Place", "name": o['name'], "address": {"@type": "PostalAddress", "streetAddress": o['street'], "addressLocality": o['city'], "postalCode": o['postalCode'], "addressRegion": "Andhra Pradesh", "addressCountry": "IN"}} for o in CO['offices']],
              "memberOf": [{"@type": "Organization", "name": m_} for m_ in CO.get('memberships', [])],
              "telephone": CO['phone'], "email": CO['email'],
              "areaServed": [{"@type": "AdministrativeArea", "name": x} for x in CO['areaServed']],
              "description": f"{NAME} is a family-led real estate developer in North Andhra Pradesh. The family enterprise began in {CO['businessSince']} and entered real estate in {CO['realEstateSince']}.",
              "member": [{"@id": absu(f"/leadership/{p['id']}/#person")} for p in F['people'] if p['id'] != CO['founderId']]})
    if F['site'].get('logo'): n['logo'] = absu('/' + F['site']['logo'].lstrip('/'))
    sa = [v for v in CO['social'].values() if v]
    if sa: n['sameAs'] = sa
    return n

def website_node():
    return {"@type": "WebSite", "@id": absu('/#website'), "url": absu('/'), "name": NAME, "publisher": {"@id": absu('/#organization')}, "inLanguage": "en-IN"}

def webpage_node(path, name, desc, kind="WebPage", about=None, modified=None):
    n = {"@type": kind, "@id": absu(path) + '#webpage', "url": absu(path), "name": name, "description": desc,
         "isPartOf": {"@id": absu('/#website')}, "inLanguage": "en-IN", "dateModified": modified or F['site']['lastUpdated']}
    if about: n['about'] = {"@id": about}
    return n

def crumb_node(crumbs):
    return {"@type": "BreadcrumbList", "@id": absu(crumbs[-1][1]) + '#breadcrumb',
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": absu(u)} for i, (n, u) in enumerate(crumbs)]}

def person_node(p):
    n = {"@type": "Person", "@id": absu(f"/leadership/{p['id']}/#person"), "name": p['name'],
         "jobTitle": p.get('roleDetail') or p['role'], "worksFor": {"@id": absu('/#organization')},
         "url": absu(f"/leadership/{p['id']}/")}
    if p.get('image'): n['image'] = absu('/' + p['image'])
    if p.get('education'): n['alumniOf'] = [{"@type": "CollegeOrUniversity", "name": x} for x in p['education']]
    if p.get('linkedin'): n['sameAs'] = [p['linkedin']]
    children = [q for q in F['people'] if q['generation'] == p['generation'] + 1]
    if children:
        n['children'] = [{"@id": absu(f"/leadership/{q['id']}/#person")} for q in children]
    if p['generation'] > 1:
        par = 'venkateswara-rao' if p['generation'] == 2 else 'shiva-kumar'
        n['parent'] = [{"@id": absu(f"/leadership/{par}/#person")}]
    return n

def place_node(p):
    n = {"@type": "Place", "@id": absu(p['_url']) + '#place', "name": p['fullName'], "url": absu(p['_url']),
         "description": ' '.join(p['overview']),
         "address": {"@type": "PostalAddress", "addressLocality": p.get('locality') or '', "addressRegion": "Andhra Pradesh", "addressCountry": "IN"},
         "additionalProperty": [{"@type": "PropertyValue", "name": "Developer", "value": p.get('jv') or NAME}]}
    if p.get('image') and not p['image'].startswith('http'): n['image'] = absu('/' + p['image'])
    if p.get('areaAcres'): n['additionalProperty'].append({"@type": "PropertyValue", "name": "Project area", "value": p['areaAcres'], "unitText": "acres"})
    if p.get('units'): n['additionalProperty'].append({"@type": "PropertyValue", "name": "Number of plots", "value": p['units']})
    if p.get('_site_live'): n['sameAs'] = [p['website']['url']]
    if p.get('lat') and p.get('lng'): n['geo'] = {"@type": "GeoCoordinates", "latitude": p['lat'], "longitude": p['lng']}
    if p['approvals'].get('rera'): n['additionalProperty'].append({"@type": "PropertyValue", "name": "AP RERA registration", "value": p['approvals']['rera']})
    return n

def ld(graph): return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False) + '</script>'

# ------------------------------------------------------------------ shared HTML
def nav_items(home):
    h = '' if home else '/'
    if not home: return [("Projects", "/projects/"), ("Story", "/about/"), ("Legacy", "/legacy/"), ("Leadership", "/leadership/"), ("Contact", "/contact/")]
    items = [("Projects", "#projects"), ("Story", "/about/"), ("Principles", "#principles"), ("Legacy", "#legacy"), ("Directors", "#team")]
    if F['site'].get('showJournal', True): items.append(("Journal", "#blog"))
    return items + [("Contact", "#contact")]

def nav_html(home=False):
    items = nav_items(home)
    links = ''.join(f'<a href="{u}">{n}</a>' for n, u in items)
    menu = ''.join(f'<a href="{u}">{n}</a>' for n, u in items + [("Enquire", "#enquire" if home else "/contact/")] ) if home else ''.join(f'<a href="{u}">{n}</a>' for n, u in items)
    return (f'<nav class="nav" id="nav" aria-label="Primary"><a href="/" class="brand">{NAME}</a><div class="links">{links}</div>'
            f'<button class="burger" id="burger" aria-label="Open menu" aria-expanded="false" aria-controls="menu"><span></span><span></span><span></span></button></nav>\n'
            f'<div class="menu" id="menu" aria-hidden="true">{menu}</div>\n')

WA_BTN = (f'<a class="wa" href="https://wa.me/{F["site"]["whatsapp"]}?text=Hello%20SVN%2C%20I%20would%20like%20to%20know%20more%20about%20your%20projects." target="_blank" rel="noopener" aria-label="Chat on WhatsApp">'
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.1a8.1 8.1 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.1 8.1 0 1 1 12 20.1zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.6 6.6 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.1.7a2.6 2.6 0 0 0 1.7-1.2 2.1 2.1 0 0 0 .1-1.2c-.1-.1-.2-.2-.5-.3z"/></svg><span>WhatsApp</span></a>')

def approvals_html():
    cols = []
    for p in LAUNCHED:
        ap_ = p['approvals']; lines = []
        if ap_.get('rera'):
            lines.append(f'<div><dt>AP RERA</dt><dd>{E(ap_["rera"])}</dd></div>')
        elif ap_.get('reraStatus') == 'In process':
            lines.append('<div><dt>RERA status</dt><dd>Registration in process</dd></div>')
        if ap_.get('other'): lines.append('<div><dt>Layout approval</dt><dd>'+E(ap_['other'])+'</dd></div>')
        if not lines: lines.append('<div><dt>Documents</dt><dd>Available on request at our office</dd></div>')
        cols.append(f'<article class="ap-col"><h3>{E(p["name"])}</h3><dl>{"".join(lines)}</dl></article>')
    return ('<section class="approvals" id="approvals" aria-labelledby="ap-h"><div class="wrap ap-wrap"><div class="ap-heading"><h2 id="ap-h">Project registrations</h2><a href="https://rera.ap.gov.in" target="_blank" rel="noopener">Verify on AP RERA ↗</a></div><div class="ap-inner">' + ''.join(cols) +
            '</div><p class="ap-note">Images, renders and illustrations are artistic impressions. Project details, specifications and amenities are indicative, subject to change and final approvals. Verify the registration and documents for your specific project and phase before booking.</p></div></section>\n')

def footer_html():
    proj = ''.join(f'<li><a href="{p["_url"]}">{E(p["name"])}</a></li>' for p in LAUNCHED) or '<li>Projects revealed soon</li>'
    tease = ''.join(f'<li>{E(p["name"])}<span style="opacity:.6"> (coming soon)</span></li>' for p in PROJ if not p['_pub'])
    locs = ''.join(f'<li><a href="/locations/{l["slug"]}/">{E(l["name"])}</a></li>' for l in F['locations'] if l.get('publish'))
    soc = ''.join(f'<li><a href="{E(v)}" rel="me noopener" target="_blank">{k.capitalize()}</a></li>' for k, v in CO['social'].items() if v)
    a = CO['address']
    return f'''<footer class="sfoot"><div class="sfoot-in"><div class="sfoot-top">
<div><div class="nm">{NAME}</div><p>A family-led real estate developer in North Andhra Pradesh. The family enterprise began in {CO['businessSince']} and entered real estate in {CO['realEstateSince']}. Three generations lead it today.</p>
<address>{E(a['street'])},<br>{E(a['city'])} {E(a['postalCode'])}, {E(a['state'])}<br><a href="tel:{CO['phoneTel']}">{CO['phone']}</a><br><a href="mailto:{CO['email']}">{CO['email']}</a></address></div>
<div><h2>Projects</h2><ul>{proj}{tease}</ul></div>
<div><h2>Company</h2><ul><li><a href="/about/">About SVN</a></li><li><a href="/legacy/">Legacy since {CO['businessSince']}</a></li><li><a href="/leadership/">Leadership</a></li><li><a href="/faq/">FAQ</a></li><li><a href="/contact/">Contact</a></li>{locs}{soc}</ul></div>
<div><h2>Legal</h2><ul><li><a href="/privacy/">Privacy</a></li><li><a href="/terms/">Terms</a></li><li><a href="/disclaimer/">Disclaimer</a></li></ul></div>
</div><div class="sfoot-base"><span>&copy; {TODAY.year} {NAME} &middot; Building since {CO['businessSince']}</span><span>Images are artistic impressions. Verify registrations at rera.ap.gov.in.</span></div></div></footer>
'''

def head_html(path, title, desc, robots='index,follow', og_type='website', graph=None, css_home=False, prefix='/'):
    og_img = absu('/' + F['site']['ogImage'].lstrip('/'))
    css = ''.join(f'<link rel="stylesheet" href="{prefix}assets/css/{c}.css">' for c in (['site', 'extra']))
    ver = ''
    if F['site'].get('googleVerification'): ver += f'<meta name="google-site-verification" content="{E(F["site"]["googleVerification"])}">\n'
    if F['site'].get('bingVerification'): ver += f'<meta name="msvalidate.01" content="{E(F["site"]["bingVerification"])}">\n'
    return f'''<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{absu(path)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{E(NAME)}">
<meta property="og:locale" content="en_IN">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{absu(path)}">
<meta property="og:image" content="{og_img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
<meta name="twitter:image" content="{og_img}">
<meta name="theme-color" content="#2B3530">
{ver}<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%232B3530'/%3E%3Ctext x='32' y='42' font-family='Arial' font-weight='700' font-size='26' text-anchor='middle' fill='%23E4DFD3'%3ESVN%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://api.fontshare.com"><link rel="preconnect" href="https://cdn.fontshare.com" crossorigin>
<link href="https://api.fontshare.com/v2/css?f[]=clash-display@400,500,600,700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
{css}
{ld(graph) if graph else ''}
<!-- Analytics: set site.ga4Id in data/facts.json; assets/js/config.js is generated -->
'''

def crumbs_html(crumbs):
    li = ''.join((f'<li><a href="{u}">{E(n)}</a></li>' if i < len(crumbs) - 1 else f'<li aria-current="page">{E(n)}</li>') for i, (n, u) in enumerate(crumbs))
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{li}</ol></nav>'

def form_html(projects, home=False, default_project=None):
    rv = ' reveal' if home else ''
    opts = '<option value="" disabled selected>Select a project</option>' + ''.join(
        f'<option{" selected" if default_project==p["name"] else ""}>{E(p["name"].replace("SVN ","") if p["name"].startswith("SVN ") else p["name"])}</option>' for p in projects) + '<option>General enquiry</option>'
    return f'''<form id="enqForm" data-form="enquiry" novalidate>
    <div style="position:absolute;left:-9999px" aria-hidden="true"><label>Company website<input type="text" name="company_website" tabindex="-1" autocomplete="off"></label></div>
    <div class="fs-fields">
      <div class="fs-field{rv}"><label for="f-name">Full Name</label><input id="f-name" name="name" type="text" placeholder="Enter your name" autocomplete="name" required></div>
      <div class="fs-field{rv}"><label for="f-email">Email Address</label><input id="f-email" name="email" type="email" placeholder="Enter your email address" autocomplete="email" required></div>
      <div class="fs-field{rv}"><label for="f-phone">Phone Number</label><input id="f-phone" name="phone" type="tel" placeholder="Enter your phone number" autocomplete="tel" inputmode="tel" required></div>
      <div class="fs-field{rv}"><label for="f-project">Interested In</label><select id="f-project" name="project" required>{opts}</select></div>
    </div>
    <fieldset class="fs-check{rv}" style="border:0;padding:0"><legend class="fs-lbl">I would like to receive information on</legend>
      <div class="fs-tags">
        <label><input type="checkbox" name="interest" value="Residences">Residences</label>
        <label><input type="checkbox" name="interest" value="Communities">Communities</label>
        <label><input type="checkbox" name="interest" value="Destinations">Destinations</label>
        <label><input type="checkbox" name="interest" value="New Launches">New Launches</label>
      </div></fieldset>
    <label class="fs-consent{rv}"><input type="checkbox" name="consent" required><span>I agree to be contacted by {NAME} by phone, WhatsApp or email about my enquiry, as described in the <a href="/privacy/">Privacy Policy</a>.</span></label>
    <button type="submit" class="fs-submit{rv}">Submit</button>
    <p class="fs-msg" role="status" aria-live="polite"></p>
  </form>'''

# ------------------------------------------------------------------ page writer
PAGES = []   # (path, indexable, lastmod)
def write(path, content):
    fp = os.path.join(OUT, path.strip('/'), 'index.html') if path != '/' else os.path.join(OUT, 'index.html')
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, 'w', encoding='utf-8').write(content)

def sub_page(path, title, desc, h1, lead, body, crumbs, graph, eyebrow='', robots='index,follow', body_attr='', kind='WebPage', about=None, modified=None, og_type='website', register=True):
    crumbs = [("Home", "/")] + crumbs
    g = [website_node(), webpage_node(path, title, desc, kind, about, modified), crumb_node(crumbs)] + graph
    g[1]['breadcrumb'] = {"@id": absu(path) + '#breadcrumb'}
    doc = f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
{head_html(path, title, desc, robots, og_type, g)}</head>
<body class="sub" {body_attr}>
<a class="skip" href="#main">Skip to content</a>
{nav_html(False)}{WA_BTN}
<main id="main">
<section class="phero"><div class="wrap">{crumbs_html(crumbs)}<span class="eyebrow" style="display:block;margin-top:28px">{E(eyebrow)}</span><h1>{E(h1)}</h1><p class="lead">{lead}</p></div></section>
<div class="doc"><div class="wrap narrow">
{body}
</div></div>
</main>
{footer_html()}
<script src="/assets/js/config.js"></script><script src="/assets/js/site.js" defer></script>
</body>
</html>
'''
    write(path, doc)
    if register: PAGES.append((path, robots.startswith('index'), modified or F['site']['lastUpdated']))

def updated(date): return f'<p class="updated">Last updated: <time datetime="{date}">{D(date)}</time></p>'

def faq_block(items):
    return '<div class="faq">' + ''.join(f'<details><summary>{E(q)}</summary><p>{a}</p></details>' for q, a in items) + '</div>'

def faq_schema(items, path):
    import re as _re
    strip = lambda s: html.unescape(_re.sub(r'<[^>]+>', '', s))
    return {"@type": "FAQPage", "@id": absu(path) + '#faq', "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip(a)}} for q, a in items]}

MS = F['milestones']; Y0 = CO['businessSince']; YR = CO['realEstateSince']
YEARS_RE = TODAY.year - YR

# ------------------------------------------------------------------ /about/
def page_about():
    founder = PEOPLE[CO['founderId']]
    ms_cards = ''
    sectors = ("trade (SVN Color Lab, 1983)", "real estate layouts and residential flats (from 2003)", "commercial development (Pasupathi Plaza, 2013)",
               "hospitality (Hotel SVN Lake Palace, 2007, and Hotel SVN Grand, Kakinada, 2013)", "temple commissions (2005 and 2009)", "catering (Swadya Gourmet Catering, 2025)")
    body = f'''<h2>Who is {NAME}?</h2>
<p>{NAME} is a family-led real estate developer operating across North Andhra Pradesh. The family enterprise traces its origins to {Y0}, while its real estate development journey began in {YR}. Three generations of the Gudisa family lead the group today.</p>
<h2>Where does the group operate?</h2>
<p>The group's work is concentrated in North Andhra Pradesh, across Vizianagaram, Srikakulam, Visakhapatnam and Kakinada, along the growth corridor that includes Bhogapuram. Its head office is in Visakhapatnam and it has an office in Vizianagaram. Its layouts carry VUDA, BUDA and SUDA approvals, and the group is a member of CREDAI and NAREDCO.</p>
<h2>When did the family enterprise begin, and when did real estate start?</h2>
<p>The enterprise was founded in {Y0} by Lt. Gudisa Venkateswara Rao. The group formally entered real estate in {YR} with SVN Nagar, a twenty-five-acre layout. That is {Y0 and TODAY.year - Y0} years of business history and {YEARS_RE} years in real estate as of {TODAY.year}.</p>
<h2>Which sectors has the group worked in?</h2>
<p>Across its history the group has worked in {', '.join(sectors[:-1])} and {sectors[-1]}. The full record is on the <a href="/legacy/">legacy timeline</a>.</p>
<h2>Who leads the group today?</h2>
<ul>{''.join(f'<li><a href="/leadership/{p["id"]}/">{E(p["display"])}</a>, {E(p.get("roleDetail") or p["role"])} ({p["generationLabel"].lower()})</li>' for p in F['people'])}</ul>
<h2>What kind of developments does SVN create?</h2>
<p>SVN develops residential communities and destination projects, including plotted layouts, residential apartments, commercial buildings, hotels and resort developments. Recent work is organised around place and landscape rather than layout alone.</p>
<h2>Current projects</h2>
<div class="cards">{''.join((f'<a class="card" href="{p["_url"]}"><span class="k">Project</span><h3>{E(p["name"])}</h3><p>{E(p["homeDesc"])}</p></a>') for p in LAUNCHED)}{''.join((f'<div class="card"><span class="k">Coming soon</span><h3>{E(p["name"])}</h3><p>{E(p.get("teaserDesc") or "")}</p></div>') for p in PROJ if not p['_pub'])}</div>
<h2>Contact and head office</h2>
<address style="font-style:normal;font-size:17px;line-height:1.75">{NAME}<br>{E(CO['address']['street'])},<br>{E(CO['address']['city'])} {E(CO['address']['postalCode'])}, {E(CO['address']['state'])}<br>
<a href="tel:{CO['phoneTel']}">{CO['phone']}</a><br><a href="mailto:{CO['email']}">{CO['email']}</a></address>
{updated(F['site']['lastUpdated'])}'''
    t = f"About {NAME} | Real Estate Developer in North Andhra"
    d = f"{NAME} is a family-led real estate developer in North Andhra Pradesh. Business legacy since {Y0}, real estate since {YR}, led by three generations."
    sub_page('/about/', t, d, f"About {NAME}", f"{NAME} is a family-led real estate developer in North Andhra Pradesh, with a business legacy since {Y0} and real estate operations since {YR}.", body,
             [("About", "/about/")], [org_node(True)] + [person_node(p) for p in F['people']], eyebrow=f"Since {Y0}", kind="AboutPage", about=absu('/#organization'))

# ------------------------------------------------------------------ /legacy/
def page_legacy():
    items = ''
    for m in MS:
        items += (f'<li id="y{m["year"]}-{re.sub(r"[^a-z0-9]+","-",m["title"].lower()).strip("-")[:40]}"><time datetime="{m["year"]}">{m["year"]}</time><article>'
                  f'<span class="tag">{E(m["tag"])}</span><h3>{E(m["title"])}</h3><p>{E(m["description"])}</p></article></li>')
    body = f'''<h2>The record, {Y0} to {TODAY.year}</h2>
<p>The SVN story begins in {Y0}, when Lt. Gudisa Venkateswara Rao founded the family enterprise. The group entered real estate in {YR}. The timeline below lists each milestone in the group's own record.</p>
<ol class="tl-list">{items}</ol>
<p style="margin-top:34px">Related: <a href="/about/">About {NAME}</a> &middot; <a href="/leadership/">Leadership across three generations</a> &middot; <a href="/projects/">Current projects</a></p>
{updated(F['site']['lastUpdated'])}'''
    g = [{"@type": "ItemList", "@id": absu('/legacy/') + '#timeline', "name": f"{NAME} milestones", "numberOfItems": len(MS),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": f"{m['year']}: {m['title']}", "description": m['description']} for i, m in enumerate(MS)]}]
    sub_page('/legacy/', f"Legacy since {Y0}: the {NAME} timeline", f"A year-by-year record of {NAME}: founded in {Y0}, in real estate since {YR}, with layouts, hotels, temples, commercial and coastal destination projects.",
             f"A legacy built on purpose, since {Y0}", f"{NAME} traces its origins to {Y0}. This is the group's year-by-year record of {len(MS)} milestones, from the first venture to the current projects.", body,
             [("Legacy", "/legacy/")], g, eyebrow="The record", about=absu('/#organization'))

# ------------------------------------------------------------------ leadership
def page_leadership_index():
    cards = ''.join(f'<a class="card" href="/leadership/{p["id"]}/"><span class="k">{p["generationLabel"]}</span><h3>{E(p["display"])}</h3><p>{E(p.get("roleDetail") or p["role"])}</p></a>' for p in F['people'])
    body = f'''<div class="leadership-intro"><figure><img src="/{CO['familyImage']}" alt="SVN family portrait" width="1280" height="1920" loading="lazy"></figure><div><h2>Three generations, one name</h2>
<p>The SVN family enterprise began with Gudisa Venkateswara Rao in {Y0}. Gudisa Shiva Kumar carried it into real estate in {YR}. Today, the third generation includes Gudisa Nithin in construction and real estate operations, and Gudisa Yashwanth in hotel management.</p></div></div>
<div class="cards">{cards}</div>{updated(F['site']['lastUpdated'])}'''
    sub_page('/leadership/', f"Leadership | {NAME}", 'Meet the SVN family across three generations: Gudisa Venkateswara Rao, Gudisa Shiva Kumar, Gudisa Nithin and Gudisa Yashwanth.',
             "Three generations of leadership", f"The Gudisa family has led {NAME} across three generations, from {Y0} to today.", body,
             [("Leadership", "/leadership/")], [org_node(True)] + [person_node(p) for p in F['people']], eyebrow="The family", about=absu('/#organization'))

def page_person(p):
    path = f"/leadership/{p['id']}/"
    img = f'<img src="/{p["image"]}" alt="{E(p["imageAlt"])}" width="600" height="800" loading="lazy">' if p.get('image') else ''
    facts = [("Role", p.get('roleDetail') or p['role']), ("Generation", p['generationLabel']), ("Organisation", f'<a href="/about/">{NAME}</a>')]
    if p.get('education'): facts.append(("Education", ', '.join(p['education'])))
    dl = '<dl class="facts">' + ''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in facts) + '</dl>'
    bio = ''.join(f'<p>{E(x)}</p>' for x in p['bio'])
    resp = '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in p['responsibilities']) + '</ul>'
    aff = ''
    if p.get('affiliations'): aff = '<h2>Associations</h2><ul>' + ''.join(f'<li>{E(x)}</li>' for x in p['affiliations']) + '</ul>'
    projs = ''
    if p.get('focus') == 'hospitality':
        projs = '<h2>Hospitality</h2><p>Yashwanth’s work focuses on managing the group’s hotels and their day-to-day operations.</p>'
    elif p['generation'] > 1 and LAUNCHED:
        projs = '<h2>Developments</h2><p>' + ' &middot; '.join(f'<a href="{x["_url"]}">{E(x["name"])}</a>' for x in LAUNCHED) + '</p>'
    rel = '<h2>Family</h2><p>' + ' &middot; '.join(f'<a href="/leadership/{q["id"]}/">{E(q["display"])} ({q["generationLabel"].lower()})</a>' for q in F['people'] if q['id'] != p['id']) + '</p>'
    body = f'''<div class="person-head">{img}<div><h2>About {E(p["name"])}</h2>{bio}{dl}</div></div>
<h2>Contribution to the group</h2>{resp}{aff}{projs}{rel}
<p>Back to <a href="/about/">{NAME}</a> &middot; <a href="/legacy/">legacy since {Y0}</a></p>{updated(F['site']['lastUpdated'])}'''
    role = p.get('roleDetail') or p['role']
    sub_page(path, (lambda t_: t_ if len(t_) <= 70 else f"{p['name']} | {p['role']}")(f"{p['name']} | {p['role']} | {NAME}"), p.get('seoDescription') or f"{p['name']} is {'the founder' if p['role']=='Founder' else ('the Chairman and Managing Director' if p['id']=='shiva-kumar' else 'Director, Operations')} of {NAME} and represents the {p['generationLabel'].lower().replace(' generation','')} generation of the Gudisa family enterprise in North Andhra Pradesh.",
             p['name'], p.get('profileLead') or f"{p['name']} is {role} at {NAME}, representing the {p['generationLabel'].lower().replace(' generation','')} generation of the family enterprise.", body,
             [("Leadership", "/leadership/"), (p['name'], path)], [org_node(False), person_node(p)], eyebrow=p['generationLabel'], kind="ProfilePage", about=absu(path) + '#person', og_type='profile')

# ------------------------------------------------------------------ projects
def page_projects_index():
    cards = ''.join(f'<a class="card" href="{p["_url"]}"><span class="k">Project</span><h3>{E(p["name"])}</h3><p>{E(p["homeDesc"])}</p></a>' for p in LAUNCHED)
    soon = ''.join(f'<div class="card"><span class="k">Coming soon</span><h3>{E(p["name"])}</h3><p>{E(p.get("teaserDesc") or "")}</p></div>' for p in PROJ if not p['_pub'])
    body = f'''<h2>Current projects</h2><div class="cards">{cards}</div>
{('<h2>Coming soon</h2><div class="cards">'+soon+'</div>') if soon else ''}
<p style="margin-top:34px">Projects are developed by <a href="/about/">{NAME}</a> or, where stated, in a joint venture. To register interest, use the <a href="/contact/">enquiry form</a>.</p>{updated(F['site']['lastUpdated'])}'''
    g = [{"@type": "ItemList", "@id": absu('/projects/') + '#list', "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": absu(p['_url']), "name": p['name']} for i, p in enumerate(LAUNCHED)]}]
    sub_page('/projects/', f"Projects | {NAME}", f"Current developments by {NAME} in North Andhra Pradesh: " + ', '.join(p['name'] for p in LAUNCHED) + '.',
             "Projects", f"The developments of {NAME} across North Andhra Pradesh.", body, [("Projects", "/projects/")], g, eyebrow="The portfolio")

def page_project(p):
    path = p['_url']; ap_ = p['approvals']
    facts = [("Developer", E(p['jv']) if p.get('jv') else f'<a href="/about/">{NAME}</a>')]
    if p.get('type'): facts.append(("Type", E(p['type'])))
    loc = p.get('locationLine') or ', '.join(x for x in [p.get('locality'), (p.get('district') + ' district') if p.get('district') else None, 'Andhra Pradesh'] if x)
    facts.append(("Location", E(loc)))
    live = p.get('_site_live')   # project has its own website: this page becomes a short entity summary
    if p.get('areaAcres'): facts.append(("Project area", f"{p['areaAcres']} acres"))
    if p.get('units'): facts.append(("Plots" if p.get('unitsLabel') == 'plots' else "Units", f"{p['units']}{E(p.get('unitsNote',''))}"))
    if not live:
        if p.get('plotSizes'): facts.append(("Plot sizes", E(p['plotSizes'])))
        if p.get('parksSqFt'): facts.append(("Parks", f"{p['parksSqFt']} sq ft"))
        if p.get('roads'): facts.append(("Roads", E(p['roads'])))
        for dsc in p['distances']: facts.append((E(dsc['label']), E(dsc['value'])))
    if ap_.get('authority'): facts.append(("Approving authority", E(ap_['authority'])))
    if ap_.get('other'): facts.append(("Approval", E(ap_['other'])))
    if ap_.get('verifyNote'): facts.append(("Verify approval", ap_['verifyNote']))
    if ap_.get('rera'): facts.append(("AP RERA", f'{E(ap_["rera"])} (verify at <a href="{E(ap_.get("reraUrl","https://rera.ap.gov.in"))}" target="_blank" rel="noopener">rera.ap.gov.in</a>)'))
    elif ap_.get('reraStatus') == 'In process': facts.append(("RERA", "Registration in process"))
    if live: facts.append((E(p['website']['label']), f'<a href="{E(p["website"]["url"])}" target="_blank" rel="noopener">{E(p["website"]["text"])}</a>'))
    dl = '<dl class="facts">' + ''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in facts) + '</dl>'
    fig = f'<figure><img src="/{p["image"]}" alt="{E(p["imageAlt"])}" width="1600" height="1000" loading="lazy"><figcaption>Artistic impression.</figcaption></figure>' if p.get('imageAlt') else ''
    am = ''
    for z in p.get('amenityZones', []):
        am += f'<h3>{E(z["heading"])}</h3>' + (f'<p>{E(z["note"])}</p>' if z.get('note') else '') + '<ul>' + ''.join(f'<li>{E(x)}</li>' for x in z['items']) + '</ul>'
    if am: am = '<h2>Amenities</h2>' + am
    elif p['amenities']: am = '<h2>Amenities</h2><ul>' + ''.join(f'<li>{E(x)}</li>' for x in p['amenities']) + '</ul>'
    if live: am = ''
    infra = ('<h2>Infrastructure</h2><ul>' + ''.join(f'<li>{E(x)}</li>' for x in p['infrastructure']) + '</ul>') if p.get('infrastructure') else ''
    mem = ''
    if p.get('membership') and not live:
        mem = f'<h2>SVN Resorts Membership</h2><p>{E(p["membership"]["text"])}</p><p style="font-size:14px">{E(p["membership"]["footnote"])}</p>'
    dev_line = (f'{p["name"]} is a joint venture. {E(p["jv"])}. SVN ShivaJyothi Group is a family-led developer whose enterprise began in {Y0} and entered real estate in {YR}.' if p.get('jv')
                else f'{p["name"]} is developed by <a href="/about/">{NAME}</a>, whose family enterprise began in {Y0} and entered real estate in {YR}.')
    faq = [(f"Who is the developer of {p['name']}?", (f"{p['name']} is a joint venture. {E(p['jv'])}." if p.get('jv') else f"{p['name']} is developed by {NAME}, a family-led real estate developer in North Andhra Pradesh.")),
           (f"Where is {p['name']} located?", f"{p['name']} is located at {E(loc)}.")]
    for dsc in ([] if live else p['distances']):
        if dsc.get('faqQ'): faq.append((dsc['faqQ'], E(dsc['faqA'])))
    if ap_.get('other'): faq.append((f"Is {p['name']} approved?", f"Yes. The layout carries {E(ap_['other'])}."))
    if ap_.get('rera'): faq.append((f"What is the RERA number of {p['name']}?", f"The AP RERA registration number is {E(ap_['rera'])}. Buyers can verify it at <a href=\"{E(ap_.get('reraUrl','https://rera.ap.gov.in'))}\" target=\"_blank\" rel=\"noopener\">rera.ap.gov.in</a>."))
    elif ap_.get('reraStatus') == 'In process': faq.append((f"Is {p['name']} RERA registered?", "RERA registration is in process."))
    faq.append((f"How can I schedule a site visit to {p['name']}?", f"Call <a href=\"tel:{CO['phoneTel']}\">{CO['phone']}</a>, email <a href=\"mailto:{CO.get('emailProjects') or CO['email']}\">{CO.get('emailProjects') or CO['email']}</a> or use the enquiry form on the <a href=\"/contact/\">contact page</a>."))
    infra = '' if live else infra
    site_block = (f'<aside class="project-website"><h2>Project website</h2><p>Explore the dedicated website for {p["name"]}.</p><a class="project-primary" href="{E(p["website"]["url"])}" target="_blank" rel="noopener">{E(p["website"]["text"])} →</a></aside>' if live else '')
    body = f"""<h2>Overview</h2>{''.join(f'<p>{E(x)}</p>' for x in p['overview'])}{fig}
{site_block}<h2>Project facts</h2>{dl}{am}{infra}{mem}
<h2>Developer</h2><p>{dev_line} See the <a href="/legacy/">legacy timeline</a> and the <a href="/leadership/">leadership</a>.</p>
<h2>Frequently asked questions</h2>{faq_block(faq)}
<h2>Enquire</h2><div class="fs-form enq">{form_html(PROJ, default_project=p['name'])}</div>
<p style="margin-top:30px;font-size:14px">All images are artistic impressions. Details are subject to change and final approvals. <a href="/disclaimer/">Read the disclaimer</a>.</p>
{updated(p['lastUpdated'])}"""
    title = f"{p['fullName']} at {p.get('titleLocality') or p.get('locality') or 'Andhra Pradesh'} | {NAME}"
    desc = p['overview'][0][:300]
    g = [org_node(False), place_node(p), faq_schema(faq, path)]
    sub_page(path, title, desc, p['fullName'], E(p['overview'][0]), body, [("Projects", "/projects/"), (p['name'], path)], g,
             eyebrow=p.get('type') or 'Project', about=absu(path) + '#place', modified=p['lastUpdated'], body_attr=f'data-project="{E(p["name"])}"')

# ------------------------------------------------------------------ locations (template; emitted only when publish=true)
def page_location(l):
    path = f"/locations/{l['slug']}/"
    near = [p for p in LAUNCHED if l['name'].lower() in (p.get('locality') or '').lower() or l['name'].lower() == (p.get('district') or '').lower()]
    projs = ('<ul>' + ''.join(f'<li><a href="{p["_url"]}">{E(p["name"])}</a></li>' for p in near) + '</ul>') if near else f'<p>No launched {NAME} project is currently listed in {E(l["name"])}.</p>'
    body = f'''<h2>Where is {E(l['name'])}?</h2><p>{E(l['full'])}.</p>
<h2>{NAME} projects in and near {E(l['name'])}</h2>{projs}
<h2>Infrastructure</h2><p>VERIFIED_DATA_REQUIRED: infrastructure status (operational, under construction, approved, proposed or announced) and primary sources must be added before this page is published.</p>
{updated(F['site']['lastUpdated'])}'''
    sub_page(path, f"{l['name']} real estate and development context | {NAME}", f"{l['full']}: location context and {NAME} projects.", l['name'], f"{E(l['full'])}.", body,
             [("Locations", "/locations/"), (l['name'], path)], [org_node(False)], eyebrow="Location",
             robots='index,follow' if l.get('publish') else 'noindex,follow', register=bool(l.get('publish')))

# ------------------------------------------------------------------ contact / faq / legal
def page_contact():
    body = f'''<section class="contact-direct"><span class="eyebrow">Call SVN</span><h2><a href="tel:{CO['phoneTel']}">{CO['phone']}</a></h2><p>Arrange a site visit or ask about a project. Tap the number to call.</p></section><h2>Offices</h2>
<h3>Visakhapatnam head office</h3>
<address style="font-style:normal;font-size:17px;line-height:1.8">{NAME}<br>{E(CO['address']['street'])},<br>{E(CO['offices'][0]['landmark'])},<br>{E(CO['address']['city'])} {E(CO['address']['postalCode'])}, {E(CO['address']['state'])}</address>
<h3>Vizianagaram office</h3>
<address style="font-style:normal;font-size:17px;line-height:1.8">{E(CO['offices'][1]['street'])},<br>{E(CO['offices'][1]['city'])} {E(CO['offices'][1]['postalCode'])}, Andhra Pradesh</address>
<dl class="facts"><dt>Phone</dt><dd><a href="tel:{CO['phoneTel']}">{CO['phone']}</a></dd><dt>Email</dt><dd><a href="mailto:{CO['email']}">{CO['email']}</a></dd><dt>Project enquiries</dt><dd><a href="mailto:{CO['emailProjects']}">{CO['emailProjects']}</a></dd><dt>WhatsApp</dt><dd><a href="https://wa.me/{F['site']['whatsapp']}" target="_blank" rel="noopener">Message us</a></dd></dl>
<h2>Register your interest</h2><div class="fs-form enq">{form_html(PROJ)}</div>{updated(F['site']['lastUpdated'])}'''
    sub_page('/contact/', f"Contact {NAME} | Visakhapatnam", f"Contact {NAME}: head office at Geetha Towers, Beach Road, Visakhapatnam, and an office in Vizianagaram. Call {CO['phone']} or send an enquiry.",
             "Contact", f"Reach {NAME} in Visakhapatnam to arrange a site visit, ask about a project or start a conversation.", body, [("Contact", "/contact/")],
             [org_node(True)], eyebrow="Get in touch", kind="ContactPage", about=absu('/#organization'))

def page_faq():
    pk = ', '.join(p['name'] for p in LAUNCHED)
    items = [(f"Who is {NAME}?", f"{NAME} is a family-led real estate developer operating across North Andhra Pradesh."),
             (f"When was {NAME} founded?", f"The family enterprise was founded in {Y0}."),
             (f"How long has {NAME} been in real estate?", f"The group entered real estate in {YR}, which is {YEARS_RE} years as of {TODAY.year}."),
             ("Who founded the group?", f"Lt. Gudisa Venkateswara Rao founded the family enterprise in {Y0}."),
             (f"Who currently leads {NAME}?", f"Gudisa Shiva Kumar is the Chairman and Managing Director and Gudisa Nithin is Director, Operations. See the <a href=\"/leadership/\">leadership page</a>."),
             (f"Where does {NAME} operate?", "Across North Andhra Pradesh: Vizianagaram, Srikakulam, Visakhapatnam and Kakinada, and along the Bhogapuram growth corridor."),
             (f"What projects does {NAME} have?", f"Launched: {pk}. More are coming soon. See the <a href=\"/projects/\">projects page</a>." if pk else "See the <a href=\"/projects/\">projects page</a>."),
             ("How do I contact SVN?", f"Call <a href=\"tel:{CO['phoneTel']}\">{CO['phone']}</a> or email <a href=\"mailto:{CO['email']}\">{CO['email']}</a>.")]
    body = f'<h2>Questions about {NAME}</h2>{faq_block(items)}{updated(F["site"]["lastUpdated"])}'
    sub_page('/faq/', f"FAQ | {NAME}", f"Answers about {NAME}: who founded it, when it entered real estate, who leads it and where it operates.", "Frequently asked questions",
             f"Direct answers about {NAME}, its history, its leadership and its projects.", body, [("FAQ", "/faq/")], [org_node(False), faq_schema(items, '/faq/')], eyebrow="FAQ")

LEGAL_NOTE = '<p class="draft-note"><strong>Draft text.</strong> This page is held back from search indexing until it has been reviewed by a qualified legal professional.</p>'
def legal(path, title, h1, lead, secs):
    body = LEGAL_NOTE + ''.join(f'<h2>{E(h)}</h2>{t}' for h, t in secs) + updated(F['site']['lastUpdated'])
    sub_page(path, f"{title} | {NAME}", lead, h1, lead, body, [(h1, path)], [org_node(False)], eyebrow="Legal", robots='noindex,follow', register=True)

def page_legal():
    legal('/privacy/', 'Privacy Policy', 'Privacy Policy', f"How {NAME} collects and uses information submitted through this website.", [
        ("What we collect", f"<p>When you submit an enquiry we collect your name, email address, phone number, the project you are interested in and your information preferences. We also record the page you enquired from, how you reached the site (referrer and campaign parameters) and the time of submission.</p>"),
        ("Why we collect it", "<p>To respond to your enquiry, arrange site visits and share information about our projects, only where you have given consent.</p>"),
        ("WhatsApp", "<p>If you choose to continue on WhatsApp, your enquiry text is sent through WhatsApp under its own terms.</p>"),
        ("Analytics and cookies", "<p>When enabled, we use Google Analytics to understand how the site is used. This may set cookies in your browser. You can block cookies in your browser settings.</p>"),
        ("Your choices", f"<p>You can ask us to access, correct or delete your information, or withdraw consent, by writing to <a href=\"mailto:{CO['email']}\">{CO['email']}</a>.</p>")])
    legal('/terms/', 'Terms of Use', 'Terms of Use', f"Terms for using the {NAME} website, including intellectual property and the general-information nature of its content.", [
        ("Use of this website", "<p>The content of this website is provided for general information about our projects and company. It is not an offer or contract.</p>"),
        ("Intellectual property", f"<p>All text, images, renders and marks on this website belong to {NAME} or its licensors and may not be reproduced without permission.</p>"),
        ("Contact", f"<p>Questions about these terms: <a href=\"mailto:{CO['email']}\">{CO['email']}</a>.</p>")])
    legal('/disclaimer/', 'Disclaimer', 'Project and RERA Disclaimer', f"Disclaimer for project information published by {NAME}.", [
        ("Artistic impressions", "<p>All images, renders and illustrations are artistic impressions and are indicative only.</p>"),
        ("Subject to change", "<p>Project details, specifications, amenities and timelines are subject to change and to final approvals.</p>"),
        ("Verify registration", "<p>Please verify each project's registration on the official RERA website, <a href=\"https://rera.ap.gov.in\" target=\"_blank\" rel=\"noopener\">rera.ap.gov.in</a>, before booking.</p>"),
        ("No guarantee", "<p>Nothing on this website is a guarantee of financial outcomes or future value.</p>")])

# ------------------------------------------------------------------ homepage (transforms the premium source; visuals preserved)
def build_home():
    t = open(os.path.join(ROOT, 'src/home.src.html'), encoding='utf-8').read()
    def sub(pat, rep, flags=re.S, count=1):
        nonlocal t
        new, n = re.subn(pat, lambda m: rep, t, count=count, flags=flags)
        assert n, 'home transform did not match: ' + pat[:70]
        t = new
    title = f"{NAME} | Real Estate Developer in North Andhra"
    desc = f"{NAME} is a family-led real estate developer in North Andhra Pradesh. Business legacy since {Y0}, real estate since {YR}, led by three generations."
    graph = [website_node(), webpage_node('/', title, desc, about=absu('/#organization')), org_node(True)] + [person_node(p) for p in F['people']]
    graph[1]['@type'] = 'WebPage'
    sub(r'<meta charset="UTF-8">.*?<!-- TODO: paste GTM / Meta Pixel snippet here -->\n', head_html('/', title, desc, graph=graph, prefix=''))
    sub(r'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://api.fontshare.com.*?\n<link href="https://fonts.googleapis.com/css2[^\n]*\n<style>.*?</style>', '')
    t = t.replace('<html lang="en">', '<html lang="en-IN">')
    sub(r'<link rel="stylesheet" href="assets/css/site.css">', '<link rel="preload" as="image" href="img/hero-poster.jpg" fetchpriority="high">\n<link rel="stylesheet" href="assets/css/site.css">', count=1) if False else None
    t = t.replace('<link rel="stylesheet" href="assets/css/site.css">', '<link rel="preload" as="image" href="img/hero-poster.jpg" fetchpriority="high">\n<link rel="stylesheet" href="assets/css/site.css">', 1)
    t = t.replace('href="#projects">Skip to content', 'href="#main">Skip to content')
    sub(r'<nav class="nav" id="nav">.*?</nav>\n<div class="menu" id="menu".*?</div>\n', nav_html(True))
    # hero -> section inside <main>
    t = t.replace('<header class="hero" id="top">', '<main id="main">\n<section class="hero" id="top">').replace('</header>', '</section>', 1)
    t = t.replace('<video class="hero-vid" autoplay muted loop playsinline poster="img/hero-poster.jpg">', '<video class="hero-vid" id="heroVid" autoplay muted loop playsinline preload="metadata" poster="img/hero-poster.jpg">')
    # entity-first intro copy (still editorial)
    sub(r'<p class="reveal">More than five decades.*?</p>', f'<p class="reveal">{NAME} is a family-led real estate developer in North Andhra Pradesh. The family enterprise began in {Y0}, entered real estate in {YR}, and is led today by its third generation &middot; guided by experience, shaped by place and driven by what comes next.</p>')
    sub(r'<div><span class="k">19</span><span class="l">Milestones</span></div>', f'<div><span class="k">{YR}</span><span class="l">In real estate since</span></div>')
    # scenes (generated from facts; draft projects dropped)
    n = len(PROJ)
    bgs = ''.join(f'<div class="bgimg{" on" if i==0 else ""}"><img src="{p["image"]}" alt=""{"" if i==0 else " loading=\"lazy\""}></div>' for i, p in enumerate(PROJ))
    sub(r'<div class="scene-bg" id="bgs">.*?</div>\n      <!-- side labels -->', f'<div class="scene-bg" id="bgs">{bgs}</div>\n      <!-- side labels -->')
    h3 = ''.join(f'<h3{" class=\"on\"" if i==0 else ""}>{E(p["name"])}</h3>' for i, p in enumerate(PROJ))
    pim = ''.join(f'<img{" class=\"on\"" if i==0 else ""} src="{p["image"]}" alt="{E(p.get("imageAlt",""))}"{"" if i==0 else " loading=\"lazy\""}>' for i, p in enumerate(PROJ))
    def sdesc(p): return p['homeDesc'] if p['_pub'] else (p.get('teaserDesc') or '')
    def smeta(p): return p['homeMeta'] if p['_pub'] else (p.get('teaserMeta') or 'Coming soon')
    des = ''.join(f'<p{" class=\"on\"" if i==0 else ""}>{E(sdesc(p))}</p>' for i, p in enumerate(PROJ))
    sub(r'<div class="count">.*?<div class="meta" id="metas">', f'''<div class="count"><span class="now" id="cnow">01</span><span class="bar"><i id="cbar" style="width:{100//n}%"></i></span><span class="total">/ 0{n}</span></div>
        <div class="ttl" id="ttls">{h3}</div>
        <div class="pimg" id="pimgs">{pim}</div>
        <div class="desc" id="descs">{des}</div>
        <div class="meta" id="metas">''')
    sub(r'<span class="mon">Flagship[^<]*</span>', f'<span class="mon">{E(smeta(PROJ[0]))}</span>')
    first = PROJ[0]
    sub(r'<a class="scene-discover" id="sceneDiscover" href="[^"]*">\s*<span class="sd-txt">Discover more</span>', f'<a class="scene-discover" id="sceneDiscover" href="{first["_url"] if first["_pub"] else "#enquire"}">\n            <span class="sd-txt">{"Discover more" if first["_pub"] else "Register interest"}</span>')
    t = t.replace('<div class="scenes" id="scenes">', f'<div class="scenes" id="scenes" style="height:{(n+1)*100}vh">')
    # JS data
    meta_js = json.dumps([smeta(p) for p in PROJ], ensure_ascii=False); url_js = json.dumps([p['_url'] if p['_pub'] else '#enquire' for p in PROJ]); cta_js = json.dumps(['Discover more' if p['_pub'] else 'Register interest' for p in PROJ])
    sub(r'const META=\[.*?\];\nconst SLUG=\[.*?\];', f'const META={meta_js};\nconst URLS={url_js};\nconst CTA={cta_js};')
    t = t.replace('const N=5;', 'const N=META.length;')
    t = t.replace("var disc=document.getElementById('sceneDiscover'); if(disc) disc.href='project.html?p='+SLUG[i];",
                  "var disc=document.getElementById('sceneDiscover'); if(disc){disc.href=URLS[i];var sd=disc.querySelector('.sd-txt');if(sd)sd.textContent=CTA[i];}")
    # milestones
    mj = json.dumps([{"y": m['year'], "tag": m['tag'], "t": m['title'], "d": m['description'], "img": m['image'], **({"major": True} if m.get('major') else {})} for m in MS], ensure_ascii=False, indent=2)
    sub(r'const MILE=\[.*?\n  \];', f'const MILE={mj};')
    N = len(MS)
    t = t.replace('<h3 id="lxtitle">SVN Group founded</h3>', f'<h3 id="lxtitle">{E(MS[0]["title"])}</h3>')
    t = t.replace('<div class="lx-coord" id="lxcoord">01 / 19</div>', f'<div class="lx-coord" id="lxcoord">01 / {N:02d}</div>')
    t = t.replace('<div class="lx" id="lx">', f'<div class="lx" id="lx" style="height:{N*105}vh">')
    ol = f'<ol class="sr-only" aria-label="{NAME} milestones">' + ''.join(f'<li><time datetime="{m["year"]}">{m["year"]}</time> {E(m["title"])}. {E(m["description"])}</li>' for m in MS) + '</ol>\n  '
    t = t.replace('<!-- the scroll-driven spine experience -->', ol + '<!-- the scroll-driven spine experience -->')
    t = t.replace('<h3>The story continues.</h3>', '<h3>The story continues.</h3>\n    <p style="margin-top:22px"><a class="blog-more" href="/legacy/">Read the full record</a></p>')
    # directors
    def dir_card(p):
        pic = (f'<div class="dir-pic"><img src="{p["image"]}" alt="{E(p["imageAlt"])}" loading="lazy"><span class="dir-gen">0{p["generation"]}</span></div>' if p.get('image')
               else f'<div class="dir-pic dir-noimg"><span class="dir-mono">SVN</span><span class="dir-gen">0{p["generation"]}</span></div>')
        nm = '<br>'.join(p['display'].replace('Gudisa ', 'Gudisa|').split('|')) if p['id'] != 'venkateswara-rao' else 'Late Gudisa<br>Venkateswara Rao'
        role = f"{p['role']} · {p['generationLabel']}" 
        blurb = {1: "Laid the foundation of the family enterprise in 1971 on precision, service and long-term relationships. His emphasis on integrity and discipline became the foundation for the generations that followed.",
                 2: "Carried the legacy into real estate in 2003, growing SVN from its early developments into a diversified portfolio spanning layouts, commercial, hospitality and destination projects, defined by steady, responsible growth.",
                 3: "An IIT Madras alumnus with further study at the London School of Economics, bringing a structured, analytical approach to development across multiple districts, and building SVN's next phase of growth."}[p['generation']]
        return f'<article class="dir">{pic}<div class="dir-body"><div class="dir-role">{role}</div><h3>{nm}</h3><p>{blurb}</p><p style="margin-top:14px"><a class="blog-more" href="/leadership/{p["id"]}/">Read profile</a></p></div></article>'
    sub(r'<div class="dirs-row" id="dirsRow">.*?</article>\n    </div>\n  </div>\n</section>', '<div class="dirs-row" id="dirsRow">\n' + '\n'.join(dir_card(p) for p in F['people']) + '\n    </div>\n  </div>\n</section>')
    # journal tiles: not links until stories exist
    a = t.index('<div class="mosaic">'); b = t.index('</section>', a)
    seg = t[a:b].replace('<a class="mtile', '<div class="mtile').replace('href="#" ', '').replace('\n      </a>', '\n      </div>').replace('Read story →', 'In preparation')
    seg = seg.replace('<h3>', '<h3>', 1)
    t = t[:a] + seg + t[b:]
    t = t.replace('<a href="#" class="blog-more reveal">Read all stories →</a>', '')
    # story list rows -> real pages
    arrow = '<svg class="sl-ar" viewBox="0 0 24 24" fill="none" stroke-width="1.5" aria-hidden="true"><path d="M7 17L17 7M17 7H8M17 7V16"/></svg>'
    rows = [("About SVN", "/about/"), ("The Legacy", "/legacy/"), ("Leadership", "/leadership/"), ("Projects", "/projects/"), ("Contact", "/contact/")]
    rh = ''.join(f'<a class="sl-row reveal" href="{u}"><span class="sl-n">0{i+1}</span><span class="sl-t">{n_}</span>{arrow}</a>\n        ' for i, (n_, u) in enumerate(rows))
    sub(r'(<div class="sl-list">).*?(</div>\n    </div>\n  </div>\n</section>)', '<div class="sl-list">\n        ' + rh + '</div>\n    </div>\n  </div>\n</section>')
    t = t.replace('<a href="story.html" class="sl-discover">', '<a href="/about/" class="sl-discover">')
    if not F['site'].get('showJournal', True):
        t, n_ = re.subn(r'<section class="pad blog" id="blog">.*?</section>\n?', '', t, count=1, flags=re.S); assert n_
    # form
    sub(r'<form id="enqForm" novalidate>.*?</form>', form_html(PROJ, home=True))
    # contact CTA
    t = t.replace('<h2>Come and find <em>your place.</em></h2>', '<h2>Come and find <em>your place.</em></h2>')
    # approvals + footer + close main
    sub(r'<section class="approvals" id="approvals">.*?</section>\n\n<footer>.*?</footer>\n', '</main>\n' + approvals_html() + footer_html())
    # scripts: drop inline menu/form (now shared), add shared scripts
    sub(r'\n// ===== MOBILE MENU =====.*?</script>', '\n</script>\n<script src="assets/js/config.js"></script>\n<script src="assets/js/site.js" defer></script>')
    # adaptive video: skip on save-data or very slow connections
    t = t.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap', '<script>(function(){var c=navigator.connection;if(c&&(c.saveData||/(^|-)2g$/.test(c.effectiveType||""))){var v=document.getElementById("heroVid");if(v){v.removeAttribute("autoplay");v.pause&&v.pause();v.querySelectorAll("source").forEach(function(s){s.remove()});v.load&&v.load()}}})();</script>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap', 1)
    # decorative lx plate image
    write('/', t)
    PAGES.append(('/', True, F['site']['lastUpdated']))

# ------------------------------------------------------------------ machine files
def machine_files():
    urls = [(p, m) for p, idx, m in PAGES if idx]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(
        f'  <url><loc>{absu(p)}</loc><lastmod>{m}</lastmod></url>\n' for p, m in sorted(urls)) + '</urlset>\n'
    open(os.path.join(OUT, 'sitemap.xml'), 'w').write(sm)
    open(os.path.join(OUT, 'robots.txt'), 'w').write(f'''# Public crawling is allowed by default, including search and generative-answer crawlers.
# Policy and per-crawler controls: docs/ROBOTS-POLICY.md
User-agent: *
Allow: /

Sitemap: {absu('/sitemap.xml')}

# To restrict a specific crawler later, add a block such as:
# User-agent: GPTBot
# Disallow: /
''')
    # redirects (data-driven: published projects redirect to their page, others to /projects/)
    legacy_slug = {'bay-parck': ['bayparck', 'bay-parck'], 'parckwud': ['parckwud'], 'miraya': ['miraya'], 'ayodhara': ['ayodhara'], 'sapphire': ['sapphire']}
    rd, ht = [], ['RewriteEngine On', '# project.html?p=... -> clean URLs (301)']
    rules = []
    for p in F['projects']:
        dest = p['_url'] if p['_pub'] else '/projects/'
        for s in legacy_slug[p['slug']]:
            rules.append((f'/project.html?p={s}', dest))
            ht.append(f'RewriteCond %{{QUERY_STRING}} (^|&)p={s}(&|$)\nRewriteRule ^project\\.html$ {dest}? [R=301,L]')
        for alt in {f'/{p["slug"].replace("-", "")}/', f'/projects/{p["slug"].replace("-", "")}/'} - {p['_url']}:
            rules.append((alt.rstrip('/'), dest)); rules.append((alt, dest))
    for old, new in [('/story.html', '/about/'), ('/vision.html', '/vision/'), ('/commitment.html', '/commitment/'), ('/pillars.html', '/pillars/'), ('/sustainability.html', '/sustainability/'), ('/index.html', '/')]:
        rules.append((old, new))
    nl = ['# Netlify / Cloudflare-compatible redirects. Query-string rules need Netlify; see _redirects notes in docs/SEO-SETUP.md']
    for old, new in rules:
        if '?p=' in old:
            path, q = old.split('?'); nl.append(f'{path}  {q.replace("p=", "p=")}  {new}  301!')
        else: nl.append(f'{old}  {new}  301')
    for old, new in rules:
        if '?p=' not in old: ht.append(f'RewriteRule ^{old.strip("/").replace(".", chr(92)+".")}/?$ {new} [R=301,L]')
    host = re.sub(r'^https?://', '', SITE)
    if 'DOMAIN.TLD' not in SITE:
        bare = host[4:] if host.startswith('www.') else host
        ht += ['', f'# one canonical host: https://{bare}', f'RewriteCond %{{HTTP_HOST}} ^www\\.{re.escape(bare)}$ [NC]', f'RewriteRule ^(.*)$ https://{bare}/$1 [R=301,L]']
        nl.insert(1, f'https://www.{bare}/*  https://{bare}/:splat  301!')
        nl.insert(1, f'http://{bare}/*  https://{bare}/:splat  301!')
    ht += ['', '# HTTPS', 'RewriteCond %{HTTPS} off\nRewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]', 'ErrorDocument 404 /404.html']
    open(os.path.join(OUT, '_redirects'), 'w').write('\n'.join(nl) + '\n')
    open(os.path.join(OUT, '.htaccess'), 'w').write('\n'.join(ht) + '\n')
    json.dump({"rules": [{"from": a, "to": b} for a, b in rules]}, open(os.path.join(OUT, 'redirect-map.json'), 'w'), indent=1)
    # legacy project.html fallback (client-side, noindex) for hosts without query-string redirects
    leg = {legacy: p['_url'] if p['_pub'] else '/projects/' for p in F['projects'] for legacy in legacy_slug[p['slug']]}
    open(os.path.join(OUT, 'project.html'), 'w').write(f'''<!DOCTYPE html><html lang="en-IN"><head><meta charset="UTF-8"><title>Redirecting</title><meta name="robots" content="noindex,follow"><link rel="canonical" href="{absu('/projects/')}">
<script>var m={json.dumps(leg)};var p=new URLSearchParams(location.search).get("p");location.replace(m[p]||"/projects/");</script>
<noscript><meta http-equiv="refresh" content="0;url=/projects/"></noscript></head><body><a href="/projects/">Projects</a></body></html>''')
    # 404
    open(os.path.join(OUT, '404.html'), 'w').write(f'''<!DOCTYPE html>
<html lang="en-IN"><head>{head_html('/404.html', 'Page not found | ' + NAME, 'The page you were looking for could not be found. Return to the SVN ShivaJyothi Group homepage or browse our projects.', robots='noindex,follow', graph=None)}</head>
<body class="sub"><a class="skip" href="#main">Skip to content</a>{nav_html(False)}<main id="main"><section class="phero"><div class="wrap"><h1>Page not found</h1><p class="lead">This page does not exist or has moved.</p></div></section>
<div class="doc"><div class="wrap narrow"><p><a href="/">Return to the homepage</a> or see our <a href="/projects/">projects</a>.</p></div></div></main>{footer_html()}<script src="/assets/js/config.js"></script><script src="/assets/js/site.js" defer></script></body></html>''')
    # runtime config (no secrets)
    open(os.path.join(OUT, 'assets/js/config.js'), 'w').write(f'window.SVN_CONFIG={json.dumps({"GA4_ID": F["site"]["ga4Id"], "ENQUIRY_ENDPOINT": F["site"]["enquiryEndpoint"], "WHATSAPP": F["site"]["whatsapp"]})};\n')
    # IndexNow key file (key comes from the environment, never from the repo)
    k = os.environ.get('INDEXNOW_KEY')
    if k: open(os.path.join(OUT, f'{k}.txt'), 'w').write(k)

# ------------------------------------------------------------------ completion layer
exec(compile(open(os.path.join(ROOT, "launch_extensions.py"), encoding="utf-8").read(), "launch_extensions.py", "exec"), globals())

# ------------------------------------------------------------------ run
if os.path.isdir(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
shutil.copytree(os.path.join(ROOT, 'assets'), os.path.join(OUT, 'assets'))
if os.path.isdir(os.path.join(ROOT, "downloads")): shutil.copytree(os.path.join(ROOT, "downloads"), os.path.join(OUT,"downloads"))
shutil.copy(os.path.join(ROOT,"favicon.svg"),os.path.join(OUT,"favicon.svg"))
if os.path.isdir(os.path.join(ROOT, 'img')): shutil.copytree(os.path.join(ROOT, 'img'), os.path.join(OUT, 'img'))
build_home(); page_about(); page_legacy(); page_leadership_index()
for p in F['people']: page_person(p)
page_projects_index()
for p in LAUNCHED: page_project(p)
for l in LOCS: page_location(l)
page_contact(); page_faq(); page_legal()
def export_kit():
    ed = os.path.join(ROOT, 'export'); shutil.rmtree(ed, ignore_errors=True); os.makedirs(ed)
    grp = {"name": NAME, "url": absu('/'), "organizationId": absu('/#organization'), "address": addr_line(), "phone": CO['phone'], "email": CO['email'], "offices": CO['offices']}
    for p in LAUNCHED:
        w = p.get('website') or {}; base = (w.get('url') or 'https://PROJECT-DOMAIN.TLD').rstrip('/')
        pub = {k: p.get(k) for k in ('slug','name','fullName','type','locality','district','locationLine','areaAcres','units','unitsNote','plotSizes','parksSqFt','roads','distances','amenityZones','infrastructure','membership','jv','overview','imageAlt')}
        ap_ = p['approvals']; pub['approvals'] = {k: ap_.get(k) for k in ('rera','reraUrl','authority','other','verifyNote') if ap_.get(k)}
        pub['groupPage'] = absu(p['_url']); pub['developer'] = grp
        json.dump(pub, open(os.path.join(ed, f"{p['slug']}.facts.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        place = {"@type": "Place", "@id": base + '/#place', "name": p['fullName'], "url": base + '/', "sameAs": [absu(p['_url'])],
                 "description": ' '.join(p['overview']), "address": {"@type": "PostalAddress", "addressLocality": p.get('locality') or '', "addressRegion": "Andhra Pradesh", "addressCountry": "IN"},
                 "additionalProperty": [{"@type": "PropertyValue", "name": "Developer", "value": p.get('jv') or NAME}]}
        g = [{"@type": "WebSite", "@id": base + '/#website', "url": base + '/', "name": p['fullName'], "publisher": {"@id": absu('/#organization')}},
             place, {"@type": "Organization", "@id": absu('/#organization'), "name": NAME, "url": absu('/')}]
        open(os.path.join(ed, f"{p['slug']}.jsonld"), 'w', encoding='utf-8').write(json.dumps({"@context": "https://schema.org", "@graph": g}, ensure_ascii=False, indent=1))
export_kit()
machine_files()
print(f"built {len(PAGES)} pages -> {OUT}  | site url: {SITE} | today: {TODAY} | launched: {[p['slug'] for p in LAUNCHED]} | teaser: {[p['slug'] for p in PROJ if not p['_pub']]}")
