"""Download attributed, versioned boundary data and derive a searchable district index.
Run once at setup. No download is needed to operate the packaged application.
"""
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
import httpx
from shapely.geometry import shape,mapping

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.catalog import REGIONS
from backend.routing import distance

OUT=ROOT/'data'/'geography'
OUT.mkdir(parents=True,exist_ok=True)
ALIASES={'Orissa':'OD','Uttaranchal':'UK','NCT of Delhi':'DL','Delhi':'DL','Andaman & Nicobar':'AN',
         'Andaman and Nicobar':'AN','Pondicherry':'PY','Dadra and Nagar Haveli':'DN','Daman and Diu':'DN','Chattisgarh':'CG','Jammu & Kashmir':'JK'}
def identify(name,point):
    for r in REGIONS:
        if r['name'].lower()==name.lower():return r['id']
    if name in ALIASES:return ALIASES[name]
    return min(REGIONS,key=lambda r:distance(point,[r['lon'],r['lat']]))['id']

sources=[];state_shapes=[]
with httpx.Client(timeout=90,follow_redirects=True,headers={'User-Agent':'RescueGrid-Research-Prototype/1.0'}) as client:
    for level in ['ADM1','ADM2']:
        meta=client.get(f'https://www.geoboundaries.org/api/current/gbOpen/IND/{level}/');meta.raise_for_status();meta=meta.json()
        url=meta['simplifiedGeometryGeoJSON'].replace('https://github.com/wmgeolab/geoBoundaries/raw/','https://raw.githubusercontent.com/wmgeolab/geoBoundaries/')
        response=client.get(url);response.raise_for_status()
        if response.text.startswith('version https://git-lfs'):
            url=url.replace('https://raw.githubusercontent.com/','https://media.githubusercontent.com/media/')
            response=client.get(url);response.raise_for_status()
        data=response.json()
        features=[];districts=[]
        for idx,feature in enumerate(data['features']):
            geom=shape(feature['geometry']).simplify(.012 if level=='ADM1' else .009,preserve_topology=True)
            point=geom.representative_point();pos=[point.x,point.y];name=feature['properties']['shapeName']
            if level=='ADM1':
                rid=identify(name,pos);state_shapes.append((geom,rid))
            else:
                rid=next((rid for geom,rid in state_shapes if geom.covers(point)),None) or identify('',pos)
                districts.append(dict(id=feature['properties'].get('shapeID',str(idx)),name=name,region=rid,position=pos,year=meta['boundaryYearRepresented']))
            features.append(dict(type='Feature',properties=dict(name=name,region=rid,id=idx),geometry=mapping(geom)))
        name='states' if level=='ADM1' else 'district-boundaries'
        (OUT/f'{name}.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),separators=(',',':')),encoding='utf-8')
        if districts:(OUT/'districts.json').write_text(json.dumps(districts,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        sources.append(dict(dataset=name,url=url,provider=meta['boundarySource'],license=meta['boundaryLicense'],year=meta['boundaryYearRepresented'],count=len(features),retrieved_at=datetime.now(timezone.utc).isoformat(),note='Historical reference boundaries; not a current authoritative administrative register.'))
        print(f'{name}: {len(features)} features prepared')
(OUT/'sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
