"""Explicit assumptions and geographical anchors, independent of the solver."""
from __future__ import annotations

# Chennai operating zones. Every zone is served by the same imported Chennai road
# package (data/networks/TN.json); the zone is an operational grouping used for
# dispatch, mutual aid and filtering.
REGION_ROWS = [
    ('CHN-N', 'North Chennai', 'George Town', 13.1050, 80.2850, 'urban'),
    ('CHN-C', 'Central Chennai', 'Egmore', 13.0780, 80.2650, 'urban'),
    ('CHN-W', 'West Chennai', 'Anna Nagar', 13.0850, 80.2200, 'urban'),
    ('CHN-NW', 'Northwest Chennai', 'Perambur', 13.1080, 80.2350, 'urban'),
    ('CHN-S', 'T Nagar & South', 'T Nagar', 13.0400, 80.2350, 'urban'),
    ('CHN-SW', 'Southwest Chennai', 'Saidapet', 13.0340, 80.2230, 'urban'),
    ('CHN-E', 'Mylapore & East Coast', 'Mylapore', 13.0330, 80.2750, 'urban'),
    ('CHN-SE', 'Southeast Chennai', 'Alwarpet', 13.0370, 80.2580, 'urban'),
]
REGIONS = [dict(id=r[0], name=r[1], city=r[2], lat=r[3], lon=r[4], terrain=r[5]) for r in REGION_ROWS]
REGION_BY_ID = {r['id']: r for r in REGIONS}

HAZARDS = {
    'road': dict(name='Road accident', family='Transport', rescue='rescue', duration=12, care='trauma', mode='road', colour='#e7a757', steps=['Scene access','Vehicle extrication','Stabilisation']),
    'rail': dict(name='Rail accident', family='Transport', rescue='heavy_rescue', duration=24, care='trauma', mode='road', colour='#a6a1ee', steps=['Rail access','Carriage extraction','Casualty collection']),
    'flood': dict(name='Flood', family='Hydrological', rescue='boat', duration=18, care='general', mode='water', colour='#5ab5df', steps=['Water access','Boat rescue','Transfer to road transport']),
    'cyclone': dict(name='Cyclone', family='Meteorological', rescue='rescue', duration=16, care='trauma', mode='road', colour='#84a4ff', steps=['Safe access','Rescue and collection','Shelter evacuation']),
    'earthquake': dict(name='Earthquake / collapse', family='Geological', rescue='heavy_rescue', duration=30, care='trauma', mode='road', colour='#d9a982', steps=['Site assessment','Debris clearance','Trapped-person extraction']),
    'landslide': dict(name='Landslide / avalanche', family='Geological', rescue='mountain_rescue', duration=28, care='trauma', mode='road', colour='#b7b591', steps=['Access restoration','Mountain rescue','Transfer to transport']),
    'fire': dict(name='Fire / explosion', family='Industrial', rescue='fire_engine', duration=20, care='burns', mode='road', colour='#f28369', steps=['Fire access control','Extraction','Burns transport']),
    'chemical': dict(name='Chemical incident', family='Industrial', rescue='hazmat', duration=25, care='isolation', mode='road', colour='#bba0d8', steps=['Exclusion-zone access','Decontamination','Specialist transport']),
    'tsunami': dict(name='Tsunami / coastal flooding', family='Hydrological', rescue='boat', duration=20, care='trauma', mode='water', colour='#55c1bb', steps=['Coastal rescue','Water-to-road transfer','Inland evacuation']),
    'heatwave': dict(name='Heatwave', family='Meteorological', rescue='medical_team', duration=8, care='general', mode='road', colour='#e7bb62', steps=['Field assessment','Cooling and stabilisation','Medical transport']),
    'epidemic': dict(name='Medical demand surge', family='Public health', rescue='medical_team', duration=10, care='isolation', mode='road', colour='#d08eb0', steps=['Field assessment','Medical-team support','Isolation-capable care']),
    'drought': dict(name='Drought-related emergency', family='Public health', rescue='supply_truck', duration=20, care='general', mode='road', colour='#c5ae7d', steps=['Supply delivery','Field medical support','Patient transport']),
}
RESOURCE_TYPES = {
    'als': 'Advanced ambulance', 'bls': 'Basic ambulance', 'rescue': 'Rescue team',
    'heavy_rescue': 'Heavy rescue team', 'boat': 'Rescue boat + crew',
    'mountain_rescue': 'Mountain rescue team', 'fire_engine': 'Fire response unit',
    'hazmat': 'Hazmat team', 'medical_team': 'Mobile medical team',
    'supply_truck': 'Medical supply unit', 'bus': 'Evacuation bus', 'helicopter': 'Rescue helicopter',
}
SEVERITY = {'critical': 9, 'serious': 4, 'minor': 1}
PRESETS = [
    dict(id='chennai_city', name='Chennai · City road accident', region='CHN-C', hazard='road', description='A multi-vehicle collision on Anna Salai / Mount Road during peak hours. Coordinate ambulances, rescue teams and nearby trauma hospitals.', icon='road', count=4),
    dict(id='chennai_highway', name='Chennai · Saidapet highway crash', region='CHN-SW', hazard='road', description='A serious accident on the Anna Salai–GST Road corridor near Saidapet. Long rescue and transport times to city hospitals.', icon='road', count=3),
    dict(id='chennai_multi', name='Chennai · Multiple simultaneous accidents', region='ALL', hazard='road', description='Six accidents across the city at the same time. Scarce ambulances must be shared carefully between zones.', icon='road', count=6),
    dict(id='chennai_capacity', name='Chennai · Hospital full (bottleneck)', region='CHN-S', hazard='road', description='The nearest trauma centre in T Nagar is full; a farther hospital has capacity. Tests whether the system picks the right destination.', icon='hospital', count=3),
    dict(id='chennai_flood', name='Chennai · Local flooding', region='CHN-S', hazard='flood', description='Heavy rain floods low-lying areas of south Chennai. Boats and road ambulances work together to reach stranded patients.', icon='water', count=4),
    dict(id='chennai_fire', name='Chennai · Building fire', region='CHN-S', hazard='fire', description='A commercial building fire in T Nagar. Fire engine, rescue team and burns-capable hospital response.', icon='flame', count=3),
    dict(id='chennai_rail', name='Chennai · Railway crossing accident', region='CHN-C', hazard='rail', description='A vehicle stuck at a railway crossing near Egmore. Heavy rescue and ambulance coordination needed.', icon='train', count=2),
    dict(id='chennai_cyclone', name='Chennai · Cyclone landfall', region='CHN-E', hazard='cyclone', description='Cyclone conditions along the east coast. Evacuation buses, shelters and trauma care compete for the same crews.', icon='water', count=3),
]

ASSUMPTIONS = [
    'Chennai city is the only operating area. Incidents, assets and facilities are synthetic demonstrations placed near eight Chennai zone anchors.',
    'Research simulation. Vehicle availability, staffing, casualties and facility capacities are synthetic.',
    'One patient per ambulance trip. Evacuation buses carry up to 20 people per trip.',
    'Every asset includes its assigned crew. Asset and crew are reserved together.',
    'Scenario rescue durations represent the listed sequential prerequisites, not physical hazard forecasts.',
    'Treatment-bay occupancy represents emergency treatment, not the total number of hospital beds.',
    'Routine handover and vehicle turnaround take 4 and 5 simulated minutes respectively.',
    'A vehicle finishes its current travel leg; changed road conditions are applied to subsequent legs and pending dispatches.',
    'Road routing uses a bounded OpenStreetMap extract of Chennai. Zone transfers use explicit estimated links, not turn-by-turn routing.',
    'A public warning is not a confirmed casualty report. Experiment inputs are frozen independently of public feeds.',
]
