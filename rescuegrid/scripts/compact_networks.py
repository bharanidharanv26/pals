"""Contract degree-two road geometry without removing junctions or directionality."""
import json,sys
from pathlib import Path
import networkx as nx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.routing import distance

for path in (ROOT/'data'/'networks').glob('*.json'):
    pack=json.loads(path.read_text(encoding='utf-8'))
    if pack.get('compacted'):continue
    nodes={n['id']:n for n in pack['nodes']};g=nx.DiGraph()
    for e in pack['edges']:
        a,b=e['from'],e['to'];pa=[nodes[a]['lon'],nodes[a]['lat']];pb=[nodes[b]['lon'],nodes[b]['lat']]
        g.add_edge(a,b,minutes=distance(pa,pb)/e.get('speed',30)*60)
    keep={n for n in g if len(set(g.predecessors(n))|set(g.successors(n)))!=2 or g.in_degree(n)==0 or g.out_degree(n)==0}
    if not keep:keep.add(next(iter(g)))
    result=[]
    for a in sorted(keep):
        for nxt in g.successors(a):
            seq=[a,nxt];total=g[a][nxt]['minutes'];prev=a;cur=nxt
            while cur not in keep:
                candidates=[n for n in g.successors(cur) if n!=prev]
                if len(candidates)!=1:break
                following=candidates[0]
                if following in seq:break
                total+=g[cur][following]['minutes'];seq.append(following);prev,cur=cur,following
            if cur not in keep:keep.add(cur)
            if a!=cur:result.append(dict(**{'from':a,'to':cur},minutes=total,geometry=[[nodes[n]['lon'],nodes[n]['lat']] for n in seq]))
    used={e[k] for e in result for k in ['from','to']}
    pack.update(nodes=[nodes[n] for n in sorted(used)],edges=result,compacted=True)
    path.write_text(json.dumps(pack,separators=(',',':')),encoding='utf-8')
    print(f'{path.stem}: {len(nodes)} -> {len(used)} routing junctions; {len(result)} directed edges, original road geometry retained')
