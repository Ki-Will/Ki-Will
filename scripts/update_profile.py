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

# PROJECTS: preserve the exact cards and animation, update names, copy, stars, and links.
s=(ASSETS/'projects.svg').read_text(encoding='utf-8')
if projects:
    p1=projects[0]; p2=projects[1] if len(projects)>1 else projects[0]
    s=text_node(s,'awesome-project',p1['name']); s=text_node(s,'A standout open-source project.',p1['description']); s=text_node(s,'toolkit',p2['name']); s=text_node(s,'Reusable building blocks and',p2['description'])
    s=s.replace('https://github.com/awesome-project',p1['url']).replace('https://github.com/toolkit',p2['url'])
    # These strings are part of the card labels; limit replacements to text nodes.
    s=text_node(s,'&#9733; 0updated just now',f"&#9733; {p1['stars']}updated just now"); s=text_node(s,'&#9733; 0updated n/a',f"&#9733; {p2['stars']}updated just now")
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
