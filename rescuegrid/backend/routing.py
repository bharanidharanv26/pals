from __future__ import annotations
import json
import hashlib
import math
from functools import lru_cache
from pathlib import Path
import networkx as nx
from .catalog import REGION_BY_ID

ROOT = Path(__file__).resolve().parents[1]

def distance(a, b):
    """Haversine km; coordinates are [longitude, latitude]."""
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))

@lru_cache(maxsize=48)
def network(region):
    path = ROOT / 'data' / 'networks' / f'{region}.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        g = nx.DiGraph()
        for n in data['nodes']:
            g.add_node(str(n['id']), pos=[n['lon'], n['lat']])
        for e in data['edges']:
            a,b = str(e['from']),str(e['to'])
            coords=e.get('geometry',[g.nodes[a]['pos'],g.nodes[b]['pos']])
            km=sum(distance(x,y) for x,y in zip(coords,coords[1:]))
            minutes=e.get('minutes',max(.05, km/e.get('speed',30)*60))
            if not g.has_edge(a,b) or minutes<g[a][b]['minutes']:
                g.add_edge(a,b, km=km, minutes=minutes, edge_id=f'{a}:{b}',geometry=coords)
        g.graph.update(source='OpenStreetMap regional extract', mode='osm', imported=data.get('retrieved'),fingerprint=hashlib.sha256(path.read_bytes()).hexdigest())
        return g
    r = REGION_BY_ID[region]
    g = nx.DiGraph()
    # A bounded, explicitly synthetic transport graph anchored to real coordinates.
    for y in range(7):
        for x in range(7):
            g.add_node(str(y*7+x), pos=[r['lon']+(x-3)*.018/max(.5,math.cos(math.radians(r['lat']))), r['lat']+(y-3)*.018])
    for y in range(7):
        for x in range(7):
            a = str(y*7+x)
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                if 0<=x+dx<7 and 0<=y+dy<7:
                    b=str((y+dy)*7+x+dx)
                    km=distance(g.nodes[a]['pos'],g.nodes[b]['pos'])
                    speed=26 if r['terrain']=='mountain' else (52 if x==3 or y==3 else 32)
                    g.add_edge(a,b,km=km,minutes=km/speed*60,edge_id=f'{a}:{b}')
    g.graph.update(source='Generated demonstration network',mode='synthetic',fingerprint='generated-grid-v1')
    return g

def node_position(region, node):
    return network(region).nodes[str(node)]['pos']

def nearest(region, point):
    g=network(region)
    return min(g.nodes,key=lambda n: distance(point,g.nodes[n]['pos']))

def route(region, start, end, conditions, mode='road'):
    return _route(region,str(start),str(end),float(conditions.get('traffic',1.25)),conditions.get('weather','normal'),tuple(sorted(conditions.get('closed_edges',{}).get(region,[]))),mode)

@lru_cache(maxsize=20000)
def _route(region,start,end,traffic,weather,closed,mode):
    g=network(region)
    start,end=str(start),str(end)
    if start not in g or end not in g:
        return None
    if mode in ('water','air'):
        if weather=='severe':
            return None
        a,b=g.nodes[start]['pos'],g.nodes[end]['pos']
        km=distance(a,b)
        # These are scenario transport links, never presented as navigable waterways.
        return dict(minutes=round(km/(16 if mode=='water' else 140)*60+2,2),km=round(km,2),coordinates=[a,b],nodes=[start,end],mode=mode,source='Simulated transfer corridor')
    blocked=set(closed)
    view=nx.subgraph_view(g,filter_edge=lambda a,b: f'{a}:{b}' not in blocked)
    try:
        path=nx.shortest_path(view,start,end,weight='minutes')
    except (nx.NetworkXNoPath,nx.NodeNotFound):
        return None
    km=sum(g[a][b]['km'] for a,b in zip(path,path[1:]))
    minutes=sum(g[a][b]['minutes'] for a,b in zip(path,path[1:]))*traffic
    coordinates=[]
    for a,b in zip(path,path[1:]):
        segment=g[a][b].get('geometry',[g.nodes[a]['pos'],g.nodes[b]['pos']])
        coordinates.extend(segment if not coordinates else segment[1:])
    return dict(minutes=round(max(.5,minutes),2),km=round(km,2),coordinates=coordinates or [g.nodes[start]['pos']],nodes=path,mode='road',source=g.graph['source'])

def network_geojson(region):
    g=network(region)
    return dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(id=d['edge_id'],minutes=d['minutes'],source=g.graph['mode']),geometry=dict(type='LineString',coordinates=d.get('geometry',[g.nodes[a]['pos'],g.nodes[b]['pos']]))) for a,b,d in g.edges(data=True)])
