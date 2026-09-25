#!/usr/bin/env python3
'''Refresh the exported GitSkins SVGs with current GitHub profile data.'''
import json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'; DATA=ROOT/'data'
USER=os.environ.get('GITHUB_USER','Ki-Will'); TOKEN=os.environ.get('GITHUB_TOKEN','')
HEADERS={'Accept':'application/vnd.github+json','User-Agent':'Ki-Will-animated-profile'}
if TOKEN: HEADERS['Authorization']=f'Bearer {TOKEN}'

def api(url, method='GET', body=None):
    headers=dict(HEADERS); payload=None
    if body is not None:
        payload=json.dumps(body).encode(); headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=payload,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=45) as r: return json.load(r)

def gql(query, variables): return api('https://api.github.com/graphql','POST',{'query':query,'variables':variables})

def text_node(svg, old, new):
    '''Replace only exact visible SVG text nodes, never IDs/animation code/path data.'''
    pattern=re.compile(r'(<text\b[^>]*>)'+re.escape(old)+r'(</text>)')
    return pattern.sub(lambda m:m.group(1)+escape(str(new))+m.group(2),svg, count=1)

def all_text_nodes(svg, old, new):
    pattern=re.compile(r'(<text\b[^>]*>)'+re.escape(old)+r'(</text>)')
    return pattern.sub(lambda m:m.group(1)+escape(str(new))+m.group(2),svg)

def write(name, content): (ASSETS/name).write_text(content,encoding='utf-8')
def fmt(n): return f'{int(n):,}'

profile=api(f'https://api.github.com/users/{USER}')
repos=[]
for page in range(1,11):
    batch=api(f'https://api.github.com/users/{USER}/repos?per_page=100&page={page}&sort=pushed')
    repos.extend(batch)
    if len(batch)<100: break

now=datetime.now(timezone.utc); start=now-timedelta(days=365)
query='''query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){totalCommitContributions totalIssueContributions totalPullRequestContributions contributionCalendar{totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}'''
gres=gql(query,{'login':USER,'from':start.isoformat(),'to':now.isoformat()})
if 'errors' in gres: raise RuntimeError('GitHub GraphQL error: '+json.dumps(gres['errors']))
collection=gres['data']['user']['contributionsCollection']; calendar=collection['contributionCalendar']
days=[d for w in calendar['weeks'] for d in w['contributionDays']]

stars=sum(r.get('stargazers_count',0) for r in repos)
active_days=sum(1 for d in days if d['contributionCount']>0)
# Repository primary-language weighting. This stays dependency-free for Actions.
lang_weight={}
for r in repos:
    lang=r.get('language')
    if lang: lang_weight[lang]=lang_weight.get(lang,0)+max(1,int(r.get('size') or 1))
top=sorted(lang_weight.items(),key=lambda x:x[1],reverse=True)[:5]
total=sum(v for _,v in top) or 1
stack=[{'name':n,'percent':round(v/total*100)} for n,v in top]

projects=[r for r in repos if not r.get('fork')]
projects.sort(key=lambda r:r.get('pushed_at') or '',reverse=True)
projects=projects[:2]

payload={
 'login':USER,'name':profile.get('name') or USER,'bio':profile.get('bio') or 'Software Engineer',
 'followers':profile.get('followers',0),'following':profile.get('following',0),'public_repos':profile.get('public_repos',0),
 'stars':stars,'contributions':calendar['totalContributions'],'active_days':active_days,
 'commit_contributions':collection['totalCommitContributions'],'issue_contributions':collection['totalIssueContributions'],'pr_contributions':collection['totalPullRequestContributions'],
 'generated_at':now.isoformat(),'stack':stack,'projects':[
   {'name':r['name'],'description':(r.get('description') or 'Open-source project.')[:85],'language':r.get('language') or 'code','stars':r.get('stargazers_count',0),'url':r.get('html_url'),'pushed_at':r.get('pushed_at')}
   for r in projects], 'days':days}
(DATA/'profile.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')

# HERO
s=(ASSETS/'hero.svg').read_text(encoding='utf-8')
s=text_node(s,'12',fmt(stars)); s=text_node(s,'@ki-will','@'+USER.lower()); s=text_node(s,'Prince Bonheur',payload['name'])
for old,item in zip(['TypeScript','HTML','Dart','Java'],stack[:4]): s=text_node(s,old,item['name'])
write('hero.svg',s)

# SYSTEM SCAN
s=(ASSETS/'system-scan.svg').read_text(encoding='utf-8')
for old,new in [('Prince Bonheur',payload['name']),('@ki-will','@'+USER.lower()),('24',payload['public_repos']),('2,404',fmt(payload['contributions'])),('12',fmt(stars)),('7',payload['followers']),('127',active_days),('TypeScript, HTML, Dart, Java',', '.join(x['name'] for x in stack[:4]))]:
    s=text_node(s,old,new)
write('system-scan.svg',s)

# PROJECTS: update the two latest non-fork repositories while preserving the exported animation.
s=(ASSETS/'projects.svg').read_text(encoding='utf-8')
s=text_node(s,'2 pinned','LATEST // 2')

def replace_first(pattern, replacement, source):
    return re.sub(pattern, replacement, source, count=1, flags=re.S)

def update_project_card(card, project, second=False):
    # Repository link
    card=re.sub(r'<a href="[^"]+" target="_blank">', lambda m: f'<a href="{project["url"]}" target="_blank">', card, count=1)
    name=escape(project['name'])
    desc=escape(project['description'])
    stars=fmt(project['stargazers_count'])
    # Header label
    card=replace_first(r'(<text x="16" y="19\.5"[^>]*>).*?(</text>)',
                       rf'\1<tspan fill="#00ff00">&#8226;</tspan> {name}\2', card)
    # Main title, retaining the animated cursor
    card=replace_first(r'(<text x="18" y="58"[^>]*>).*?(</text>)',
                       rf'\1{name}<tspan fill="#00ff00"> _<animate attributeName="opacity" values="1;0;1" dur="1.2s" repeatCount="indefinite"/></tspan>\2', card)
    # Description: use up to two lines so long descriptions remain inside the card.
    words=project['description'].split()
    line1=escape(' '.join(words[:11]))
    line2=escape(' '.join(words[11:22]))
    card=replace_first(r'<text x="18" y="79"[^>]*>.*?</text>',
                       f'<text x="18" y="79" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11.5" fill="#4ade80">{line1}</text>', card)
    if line2:
        card=replace_first(r'<text x="18" y="95"[^>]*>.*?</text>',
                           f'<text x="18" y="95" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11.5" fill="#4ade80">{line2}</text>', card)
    else:
        card=re.sub(r'\s*<text x="18" y="95"[^>]*>.*?</text>', '', card, count=1, flags=re.S)
    # Star count
    card=replace_first(r'<text x="18" y="150"[^>]*>.*?</text>',
                       f'<text x="18" y="150" font-family="ui-monospace,\'SF Mono\',SFMono-Regular,Menlo,Consolas,monospace" font-size="11" fill="#4ade80"><tspan fill="#4b8cd2">&#9733;</tspan> {stars}<tspan fill="#4ade80" fill-opacity="0.7" dx="12">updated {project.get("pushed_at","")[:10]}</tspan></text>', card)
    return card

if projects:
    p1=projects[0]
    p2=projects[1] if len(projects)>1 else projects[0]
    cards=list(re.finditer(r'<a href="[^"]+" target="_blank">\s*<g opacity="0" transform="translate\([^)]*\)">.*?</g>\s*</a>', s, flags=re.S))
    if len(cards)>=2:
        first=cards[0]
        second=cards[1]
        updated1=update_project_card(first.group(0),p1)
        # Re-find the second card after the first replacement is prepared.
        s=s[:first.start()]+updated1+s[first.end():]
        offset=len(updated1)-(first.end()-first.start())
        second_start=second.start()+offset
        second_end=second.end()+offset
        updated2=update_project_card(s[second_start:second_end],p2,second=True)
        s=s[:second_start]+updated2+s[second_end:]

write('projects.svg',s)

# STACK
s=(ASSETS/'stack.svg').read_text(encoding='utf-8')
for i,item in enumerate(stack):
    if i < 5:
        old_lang=['TypeScript','HTML','Dart','Java','JavaScript'][i]
        old_pct=['58%','16%','7%','7%','5%'][i]
        s=text_node(s,old_lang,item['name']); s=text_node(s,old_pct,f"{item['percent']}%")
write('stack.svg',s)

# LIVE CONTRIBUTION HEATMAP. The exported artwork has 371 animated cell groups in column-major order.
s=(ASSETS/'heatmap.svg').read_text(encoding='utf-8')
s=text_node(s,'2,404 contributions in the last year',f"{fmt(payload['contributions'])} contributions in the last year")
levels={'NONE':0.07,'FIRST':0.26,'SECOND':0.48,'THIRD':0.72,'FOURTH':1.0}
# Match the contribution-cell groups by their translate coordinates, not decorative legend cells.
pat=re.compile(r'(<g transform="translate\([^)]*\)">\s*<rect[^>]*fill="#[0-9a-fA-F]+" fill-opacity=")([0-9.]+)("[^>]*>\s*<animate attributeName="fill-opacity" values=")([^\"]+)(")')
idx=0

def cell_repl(m):
    global idx
    if idx>=len(days): return m.group(0)
    d=days[idx]; idx+=1
    op=levels.get(d['contributionLevel'],0.07)
    peak=min(1.0,op+0.18)
    return m.group(1)+f'{op:.2f}'+m.group(3)+f'0;{peak:.2f};{op:.2f}'+m.group(5)
# Only groups with translate values in the actual grid are matched by the fixed rect/animate pattern.
s=pat.sub(cell_repl,s)
write('heatmap.svg',s)

# README cache-buster. The query changes each workflow run so GitHub's image CDN fetches the new SVGs.
run=os.environ.get('GITHUB_RUN_NUMBER','local')
readme=f'''<div align="center">\n\n<img src="./assets/hero.svg?v={run}" alt="Prince Bonheur GitHub profile" width="860">\n\n<img src="./assets/system-scan.svg?v={run}" alt="Live GitHub profile system scan" width="1180">\n\n<img src="./assets/projects.svg?v={run}" alt="Live projects" width="860">\n\n<img src="./assets/stack.svg?v={run}" alt="Live language stack" width="860">\n\n<img src="./assets/heatmap.svg?v={run}" alt="Live contribution activity" width="860">\n\n</div>\n'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
print(f"Updated @{USER}: {payload['contributions']:,} contributions | {payload['public_repos']} repos | {payload['followers']} followers | {payload['stars']} stars | {active_days} active days")
