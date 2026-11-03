"""Import an OSM road package for any selected region; run while the server is stopped.
Example: python scripts/import_osm.py --region TN --radius 5500
A package changes scenario node IDs. Reset existing workspaces after installing it.
"""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
import httpx
import networkx as nx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.catalog import REGION_BY_ID

p=argparse.ArgumentParser();p.add_argument('--region',required=True,choices=REGION_BY_ID);p.add_argument('--radius',type=int,default=5500);p.add_argument('--lat',type=float);p.add_argument('--lon',type=float);args=p.parse_args()
if not 1000<=args.radius<=20000:p.error('Radius must be between 1000 and 20000 metres')
r=REGION_BY_ID[args.region];lat=args.lat if args.lat is not None else r['lat'];lon=args.lon if args.lon is not None else r['lon']
query=f'[out:json][timeout:55];way(around:{args.radius},{lat},{lon})[highway~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|.*_link)$"][access!~"private|no"];(._;>;);out body;'
error=None
for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        response=httpx.post(endpoint,data={'data':query},timeout=90,headers={'User-Agent':'RescueGrid-Research-Prototype/1.0'});response.raise_for_status();data=response.json();break
    except Exception as exc:error=exc
else:raise SystemExit(f'OSM import unavailable: {error}. Existing packages have not changed.')
nodes={str(e['id']):dict(id=str(e['id']),lon=e['lon'],lat=e['lat']) for e in data['elements'] if e['type']=='node'}
edges=[];g=nx.DiGraph()
for way in data['elements']:
    if way['type']!='way':continue
    tags=way.get('tags',{});ns=[str(n) for n in way['nodes']];oneway=tags.get('oneway')
    if oneway=='-1':ns.reverse()
    speed={'motorway':65,'trunk':55,'primary':40,'secondary':35}.get(tags.get('highway'),25)
    for a,b in zip(ns,ns[1:]):
        if a not in nodes or b not in nodes:continue
        edges.append(dict(**{'from':a,'to':b},speed=speed));g.add_edge(a,b)
        if oneway not in ('yes','1','true','-1') and tags.get('junction')!='roundabout':
            edges.append(dict(**{'from':b,'to':a},speed=speed));g.add_edge(b,a)
if not g:raise SystemExit('No routable roads returned')
component=max(nx.strongly_connected_components(g),key=len)
pack=dict(region=args.region,source='OpenStreetMap contributors',license='ODbL 1.0',attribution='© OpenStreetMap contributors',retrieved=datetime.now(timezone.utc).isoformat(),center=[lon,lat],
          nodes=[nodes[n] for n in sorted(component)],edges=[e for e in edges if e['from'] in component and e['to'] in component],
          assumptions='Road-class speeds are assumed; turn restrictions and live traffic are not modelled.')
path=ROOT/'data'/'networks'/f'{args.region}.json';path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(pack,separators=(',',':')),encoding='utf-8')
print(f'{args.region}: {len(pack["nodes"])} nodes, {len(pack["edges"])} directed road segments imported')
