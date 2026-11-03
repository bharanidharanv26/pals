"""CAP/RSS adapter. No casualty inference, external entities or arbitrary URL fetches."""
import os
import time
from datetime import datetime,timezone
from urllib.parse import urlparse
import httpx
from defusedxml.ElementTree import fromstring

_cache={'etag':None,'data':None,'retrieved':None}
_seismic={'checked':0,'result':None}

def earthquakes():
    """Public observations around India, distinct from the simulated incident queue."""
    if _seismic['result'] is not None and time.monotonic()-_seismic['checked']<900:
        return {**_seismic['result'],'status':'cached'}
    url='https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson'
    try:
        response=httpx.get(url,timeout=12,headers={'User-Agent':'RescueGrid-Research-Prototype/1.0'})
        response.raise_for_status();data=response.json();items=[]
        for feature in data['features']:
            lon,lat,*_=feature['geometry']['coordinates']
            if not (6<=lat<=38 and 68<=lon<=98):continue
            p=feature['properties']
            items.append(dict(id=feature['id'],headline=p.get('title') or p.get('place'),description='Observed seismic event. No casualties or response demand inferred.',
                severity=f"Magnitude {p.get('mag')}",area=p.get('place'),sent=datetime.fromtimestamp(p['time']/1000,timezone.utc).isoformat(),
                url=p.get('url'),status='Observation',source='USGS Earthquake Hazards Program',position=[lon,lat]))
        result=dict(status='connected',items=items,source='USGS · India and neighbouring seismic activity',portal=url,retrieved_at=datetime.now(timezone.utc).isoformat(),
                    message='Public magnitude 2.5+ observations from the past week within 6–38° N, 68–98° E. This geographic window includes neighbouring countries. Observations do not create simulated incidents.')
        _seismic.update(checked=time.monotonic(),result=result)
        return result
    except Exception as exc:
        return dict(status='unavailable',items=(_seismic['result'] or {}).get('items',[]),source='USGS Earthquake Hazards Program',message=str(exc),retrieved_at=(_seismic['result'] or {}).get('retrieved_at'))

def parse_cap(xml):
    root=fromstring(xml)
    if root.tag.split('}')[-1]=='alert':
        def get(parent,name):
            return next((e.text for e in parent.iter() if e.tag.split('}')[-1]==name),None)
        result=[]
        for info in [e for e in root.iter() if e.tag.split('}')[-1]=='info']:
            polygon=get(info,'polygon');coords=[]
            if polygon:
                for point in polygon.split():
                    lat,lon=map(float,point.split(','));coords.append([lon,lat])
            result.append(dict(id=get(root,'identifier'),headline=get(info,'headline') or get(info,'event'),description=get(info,'description'),
                severity=get(info,'severity'),area=get(info,'areaDesc'),sent=get(root,'sent'),expires=get(info,'expires'),
                sender=get(root,'sender'),status=get(root,'status'),language=get(info,'language'),polygon=coords,source='Imported CAP document'))
        return result
    items=[]
    for item in root.iter('item'):
        items.append(dict(id=item.findtext('guid') or item.findtext('link'),headline=item.findtext('title'),description=item.findtext('description'),
            sent=item.findtext('pubDate'),url=item.findtext('link'),source='Public RSS feed',severity='Unknown',status='Public feed'))
    return items

def fetch_alerts():
    url=os.environ.get('SACHET_FEED_URL','')
    if not url:
        return dict(status='not_configured',items=[],source='NDMA SACHET',portal='https://sachet.ndma.gov.in/CapFeed',
                    message='Public-source adapter ready. Configure the current published SACHET feed URL or import a CAP XML document. Operational scenarios remain synthetic.',retrieved_at=None)
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='sachet.ndma.gov.in':
        return dict(status='unavailable',items=[],message='SACHET_FEED_URL must be an HTTPS URL on sachet.ndma.gov.in')
    try:
        headers={'User-Agent':'RescueGrid-Research-Prototype/1.0'}
        if _cache['etag']:headers['If-None-Match']=_cache['etag']
        with httpx.Client(timeout=12,follow_redirects=False) as client:
            response=client.get(url,headers=headers)
        if response.status_code==304 and _cache['data'] is not None:
            return dict(status='cached',items=_cache['data'],retrieved_at=_cache['retrieved'],source='NDMA SACHET')
        response.raise_for_status()
        if len(response.content)>2_000_000:raise ValueError('Feed exceeds the prototype size limit')
        items=parse_cap(response.content)
        _cache.update(etag=response.headers.get('etag'),data=items,retrieved=datetime.now(timezone.utc).isoformat())
        return dict(status='connected',items=items,retrieved_at=_cache['retrieved'],source='NDMA SACHET')
    except Exception as exc:
        return dict(status='unavailable',items=_cache['data'] or [],retrieved_at=_cache['retrieved'],message=str(exc),source='NDMA SACHET')
