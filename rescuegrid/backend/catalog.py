"""Explicit assumptions and geographical anchors, independent of the solver."""
from __future__ import annotations

REGION_ROWS = [
    ('AN','Andaman and Nicobar Islands','Port Blair',11.6234,92.7265,'island'),
    ('AP','Andhra Pradesh','Vijayawada',16.5062,80.6480,'coastal'),
    ('AR','Arunachal Pradesh','Itanagar',27.0844,93.6053,'mountain'),
    ('AS','Assam','Guwahati',26.1445,91.7362,'river'),
    ('BR','Bihar','Patna',25.5941,85.1376,'river'),
    ('CH','Chandigarh','Chandigarh',30.7333,76.7794,'urban'),
    ('CG','Chhattisgarh','Raipur',21.2514,81.6296,'rural'),
    ('DN','Dadra and Nagar Haveli and Daman and Diu','Daman',20.3974,72.8328,'coastal'),
    ('DL','Delhi','New Delhi',28.6139,77.2090,'urban'),
    ('GA','Goa','Panaji',15.4909,73.8278,'coastal'),
    ('GJ','Gujarat','Ahmedabad',23.0225,72.5714,'urban'),
    ('HR','Haryana','Gurugram',28.4595,77.0266,'urban'),
    ('HP','Himachal Pradesh','Shimla',31.1048,77.1734,'mountain'),
    ('JK','Jammu and Kashmir','Srinagar',34.0837,74.7973,'mountain'),
    ('JH','Jharkhand','Ranchi',23.3441,85.3096,'rural'),
    ('KA','Karnataka','Bengaluru',12.9716,77.5946,'urban'),
    ('KL','Kerala','Kochi',9.9312,76.2673,'coastal'),
    ('LA','Ladakh','Leh',34.1526,77.5771,'mountain'),
    ('LD','Lakshadweep','Kavaratti',10.5667,72.6417,'island'),
    ('MP','Madhya Pradesh','Bhopal',23.2599,77.4126,'rural'),
    ('MH','Maharashtra','Mumbai',19.0760,72.8777,'urban'),
    ('MN','Manipur','Imphal',24.8170,93.9368,'mountain'),
    ('ML','Meghalaya','Shillong',25.5788,91.8933,'mountain'),
    ('MZ','Mizoram','Aizawl',23.7271,92.7176,'mountain'),
    ('NL','Nagaland','Kohima',25.6751,94.1086,'mountain'),
    ('OD','Odisha','Bhubaneswar',20.2961,85.8245,'coastal'),
    ('PY','Puducherry','Puducherry',11.9416,79.8083,'coastal'),
    ('PB','Punjab','Ludhiana',30.9010,75.8573,'rural'),
    ('RJ','Rajasthan','Jaipur',26.9124,75.7873,'rural'),
    ('SK','Sikkim','Gangtok',27.3389,88.6065,'mountain'),
    ('TN','Tamil Nadu','Chennai',13.0827,80.2707,'coastal'),
    ('TS','Telangana','Hyderabad',17.3850,78.4867,'urban'),
    ('TR','Tripura','Agartala',23.8315,91.2868,'rural'),
    ('UP','Uttar Pradesh','Lucknow',26.8467,80.9462,'rural'),
    ('UK','Uttarakhand','Dehradun',30.3165,78.0322,'mountain'),
    ('WB','West Bengal','Kolkata',22.5726,88.3639,'river'),
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
    dict(id='national', name='National readiness exercise', region='ALL', hazard='mixed', description='Twelve concurrent emergencies across India. Coordinate scarce resources and compare treatment delays.', icon='globe', count=12),
    dict(id='chennai', name='Chennai · highway collision', region='TN', hazard='road', description='Competing road incidents, extrication and limited trauma capacity along the Chennai corridor.', icon='road', count=5),
    dict(id='assam', name='Assam · rising water', region='AS', hazard='flood', description='Stranded patients and evacuation groups need boats, transfer points and medical transport.', icon='water', count=5),
    dict(id='odisha', name='Odisha · cyclone landfall', region='OD', hazard='cyclone', description='Evacuation, rescue and shelter capacity under severe congestion.', icon='wind', count=5),
    dict(id='rail', name='Odisha · rail emergency', region='OD', hazard='rail', description='Multiple carriage-access tasks and critical patients compete for heavy rescue and advanced ambulances.', icon='train', count=4),
    dict(id='himalaya', name='Uttarakhand · blocked access', region='UK', hazard='landslide', description='Mountain rescue, access clearance and long response journeys.', icon='mountain', count=4),
    dict(id='gujarat', name='Gujarat · earthquake', region='GJ', hazard='earthquake', description='Extraction-dependent casualties and treatment queues after a simulated earthquake.', icon='activity', count=5),
    dict(id='mumbai', name='Mumbai · industrial incident', region='MH', hazard='chemical', description='Decontamination and isolation-capable receiving facilities.', icon='flame', count=4),
    dict(id='islands', name='Islands · coastal evacuation', region='AN', hazard='tsunami', description='Water rescue, inland shelters and an explicit sea/air mutual-aid connection.', icon='waves', count=4),
    dict(id='heatwave', name='Rajasthan · heatwave', region='RJ', hazard='heatwave', description='Medical teams and hospital capacity under sustained demand.', icon='sun', count=5),
    dict(id='compound', name='Kerala · cascading emergency', region='KL', hazard='flood', description='Flooding is followed by a facility outage and a road-corridor closure.', icon='layers', count=5),
    dict(id='capacity', name='Chennai · hospital saturation', region='TN', hazard='road', description='Constructed bottleneck case: the nearest trauma facility is full, while a farther facility has capacity.', icon='hospital', count=3),
]

ASSUMPTIONS = [
    'Research simulation. Vehicle availability, staffing, casualties and facility capacities are synthetic.',
    'One patient per ambulance trip. Evacuation buses carry up to 20 people per trip.',
    'Every asset includes its assigned crew. Asset and crew are reserved together.',
    'Scenario rescue durations represent the listed sequential prerequisites, not physical hazard forecasts.',
    'Treatment-bay occupancy represents emergency treatment, not the total number of hospital beds.',
    'Routine handover and vehicle turnaround take 4 and 5 simulated minutes respectively.',
    'A vehicle finishes its current travel leg; changed road conditions are applied to subsequent legs and pending dispatches.',
    'Generated local transport graphs and water corridors are illustrative. Imported OSM road packages are labelled separately.',
    'National assistance uses explicit estimated transfer links. Island transfers require a simulated air or sea connection.',
    'A public warning is not a confirmed casualty report. Experiment inputs are frozen independently of public feeds.',
]
