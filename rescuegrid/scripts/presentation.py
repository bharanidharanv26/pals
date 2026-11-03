"""Build a PALS-aligned project deck from the supplied IT presentation template."""
import io,json,statistics,sys,zipfile,shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_SHAPE_TYPE
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'
TEMPLATE=ROOT.parent/'PALS THINK2IPACT_CORE-IT SOLUTION TEMPLATE.zip'

def build():
    if not TEMPLATE.exists():raise SystemExit(f'Supplied template not found: {TEMPLATE}')
    with zipfile.ZipFile(TEMPLATE) as z:
        filename=next(n for n in z.namelist() if n.endswith('T2I. IT Projects Presentation.pptx'))
        deck=Presentation(io.BytesIO(z.read(filename)))
    report=json.loads((OUT/'benchmark-results.json').read_text(encoding='utf-8'))
    def value(scenario,policy,key):
        vals=[r[key] for r in report['records'] if r['scenario']==scenario and r['policy']==policy and r[key] is not None]
        return statistics.mean(vals) if vals else 0
    sat_base=value('capacity','nearest','mean_care_minutes');sat_opt=value('capacity','optimized','mean_care_minutes')
    crit_base=value('chennai','nearest','critical_care_minutes');crit_opt=value('chennai','optimized','critical_care_minutes')
    slides=[
      ('RescueGrid India',[
        'Intelligent Emergency Rescue and Medical Response Optimisation',
        'PALS Think2Impact · ITPRBLM–B',
        'Nationwide multi-disaster decision support and simulation',
        'College: [add your college name]',
        'Team members: [add names and registration details]',
      ]),
      ('Problem and objectives',[
        'Coordinate scarce rescue teams, ambulances, routes and receiving facilities.',
        'Model the complete chain from incident reporting to appropriate medical treatment.',
        'Identify delays caused by access, resource availability, rescue work and hospital queues.',
        'Compare response strategies under identical, reproducible scenario conditions.',
      ]),
      ('Benefits and research questions',[
        'Beneficiaries: response planners, dispatch analysts, rescue coordinators and hospital managers.',
        'When does a farther compatible hospital provide earlier appropriate care?',
        'Which additional resource most reduces the dominant bottleneck?',
        'What does prioritising critical patients cost other patients or supplying regions?',
        'Report time, capacity pressure and unmet demand together.',
      ]),
      ('India-wide and multi-disaster scope',[
        '36 state/UT resource packages; 612 synthetic assets and 144 synthetic facilities.',
        'Core: road accidents, train accidents, floods and cyclones.',
        'Extensions: collapse, landslide, fire, chemical incidents, tsunami, heatwave and public-health pressure.',
        '12 playbooks across 10 disaster families; configurable regional exercises.',
        'Detailed OSM roads: Chennai and Guwahati; other packages use labelled generated networks.',
      ]),
      ('Functional requirements',[
        'Record incident location, severity, patient demand and evacuation groups.',
        'Track resources, capabilities, access restrictions and receiving capacity.',
        'Calculate explainable rescue, ambulance and hospital recommendations.',
        'Reserve resources, advance the response and adapt subsequent legs to disruptions.',
        'Compare policies, replay decisions, export results and plan regional assistance.',
      ]),
      ('Non-functional requirements',[
        'Reproducibility: seeds, input versions, source hashes and recorded decisions.',
        'Reliability: revision checks, exclusive resources and capacity conservation.',
        'Performance: bounded candidate models, cached routing and a separate experiment process.',
        'Usability: map-led workflows and English/Hindi/Tamil interface labels.',
        'Traceability: clear distinction between reference geography and simulated operations.',
      ]),
      ('Technical architecture',[
        'React + TypeScript → FastAPI → versioned workspace state.',
        'MapLibre renders local reference geometry, road packages and response routes.',
        'NetworkX computes travel paths; OR-Tools allocates and schedules resources.',
        'SimPy executes response events; a bounded process runs controlled experiments.',
        'SQLAlchemy persists state and experiments in SQLite or PostgreSQL.',
      ]),
      ('System workflow',[
        'Incident → report → specialist rescue assignment → rescue prerequisites.',
        'Rescue / transfer readiness → suitable ambulance → compatible hospital.',
        'Hospital queue → treatment → release of treatment capacity.',
        'Vehicle handover and turnaround → resource available for another mission.',
        'Observe changed conditions → re-optimise pending demand and later legs.',
      ]),
      ('Use cases',[
        'Dispatcher: enter an incident, inspect a recommendation and commit a response plan.',
        'Coordinator: change resource or facility availability and inspect queued demand.',
        'Planner: request regional assistance while retaining donor coverage.',
        'Researcher: compare three policies with paired seeds and export evidence.',
        'Presenter: load a prepared exercise and replay the response timeline.',
      ]),
      ('Detailed design: routing and rescue',[
        'Directed shortest-travel-time road graph with explicit blocked edges.',
        'Disaster playbooks define specialist capabilities and sequential service tasks.',
        'Boat / air scenarios include capacity-limited trips and ground transfer points.',
        'Medical and evacuation groups have separate readiness times.',
        'Infeasible access or missing capabilities produce explicit queued demand.',
      ]),
      ('Detailed design: allocation',[
        'Stage 1: severity-weighted rescue/resource matching using CP-SAT.',
        'Stage 2: candidate patient–ambulance–hospital assignments.',
        'One patient per ambulance; critical patients require ALS capability.',
        'Optional treatment intervals and cumulative constraints enforce hospital capacity.',
        'Bounded candidate model; solver status and fallback use remain visible.',
      ]),
      ('Regional coordination',[
        'CP-SAT minimises estimated transfer time for a desired receiving-region fleet.',
        'Donor reserve constraints prevent the model from removing configured local coverage.',
        'Mobilisation and road/sea travel consume simulated time.',
        'Transferred resources are unavailable until arrival.',
        'Links are explicit scenario estimates, not nationwide turn-by-turn routing.',
      ]),
      ('User interface: command centre',[], 'overview-desktop.png'),
      ('User interface: simulation laboratory',[], 'simulation-results.png'),
      ('Data model and provenance',[
        'Region → incident → patients / evacuation demand → missions.',
        'Resource + dedicated crew → mission → receiving facility reservation.',
        'Workspace: configuration, clock, revision, events and decision trace.',
        'Reference boundaries retain source year; the district index has 735 historical records.',
        'Public CAP/USGS observations are separate from synthetic casualty demand.',
      ]),
      ('Evaluation method',[
        f"{len(report['records'])} measured runs: five scenarios, three policies, {report['repetitions']} paired seeds.",
        f"Each run covers {report['horizon']} simulated minutes with identical exogenous inputs.",
        'Policies: nearest suitable, severity-first greedy and coordinated optimisation.',
        'Measure mean/P90 care time, response time, unserved patients and evacuation.',
        'Inspect critical-patient outcomes and bottlenecks; no fixed improvement claim.',
      ]),
      ('Measured outcomes and trade-offs',[
        f'Constructed saturation case: mean care {sat_base:.1f} → {sat_opt:.1f} minutes (nearest → optimised).',
        f'Chennai critical-patient mean care: {crit_base:.1f} → {crit_opt:.1f} minutes across paired runs.',
        'Severity prioritisation can increase the overall mean or leave more lower-priority demand at the horizon.',
        'The optimiser is myopic and staged; results vary by scenario and assumptions.',
        'Full results: docs/EVALUATION.md and benchmark-results.csv / .json.',
      ]),
      ('Validation and infrastructure',[
        '38 engine/API tests cover workflows, capacity, isolation, stale steps and interrupted jobs.',
        '10 browser tests cover the interface, sustained playback, real server restart and recovery.',
        'Local target: Python 3.11+, Node.js 22/24 and an approximately 8 GB laptop.',
        'Windows launcher; Docker/Compose and hosted-service configuration included.',
        'Native production build tested; Docker execution and hosted publication require their environments.',
      ]),
      ('Assumptions and implementation path',[
        'All operational availability, casualties and hospital capacity are simulated.',
        'Travel speeds, service times and severity weights are stated research assumptions.',
        'Current travel legs finish; later legs use updated access and facility conditions.',
        'Next validation: current district data, practitioner-reviewed durations and authorised operational integrations.',
        'Research prototype; no real emergency-dispatch or clinical diagnosis integration.',
      ]),
      ('Demonstration and discussion',[
        'Launch START_RESCUEGRID.bat → http://127.0.0.1:8000',
        'Load saturation exercise → calculate → explain → dispatch → advance.',
        'Compare policies → inspect critical outcomes and unmet demand → export.',
        'Demonstrate flood transfers and reserve-constrained regional assistance.',
        'Which resource change best reduces the limiting delay in this scenario?',
      ]),
    ]
    # Retain the supplied presentation package, theme and footer artwork.
    while len(deck.slides)>len(slides):
        slide_id=deck.slides._sldIdLst[-1];deck.part.drop_rel(slide_id.rId);deck.slides._sldIdLst.remove(slide_id)
    width=deck.slide_width/914400;height=deck.slide_height/914400
    for index,(slide,content) in enumerate(zip(deck.slides,slides)):
        for shape in list(slide.shapes):
            footer=shape.top>deck.slide_height*.86
            keep=footer and (shape.shape_type==MSO_SHAPE_TYPE.PICTURE or (shape.has_text_frame and 'association' in shape.text.lower()))
            if not keep:shape._element.getparent().remove(shape._element)
        fill=slide.background.fill;fill.solid();fill.fore_color.rgb=RGBColor(250,251,248)
        bar=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(.4),Inches(.55),Inches(.07),Inches(.48));bar.fill.solid();bar.fill.fore_color.rgb=RGBColor(116,143,58);bar.line.fill.background()
        title=slide.shapes.add_textbox(Inches(.65),Inches(.45),Inches(width-1.2),Inches(.85))
        tf=title.text_frame;tf.word_wrap=True;p=tf.paragraphs[0];p.text=content[0];p.font.name='Aptos Display';p.font.size=Pt(29 if len(content[0])<38 else 25);p.font.bold=True;p.font.color.rgb=RGBColor(30,45,36)
        if len(content)==3:
            source=ROOT/'frontend'/'test-results'/content[2]
            if source.exists():
                dest=OUT/content[2];shutil.copyfile(source,dest)
                with Image.open(source) as im:ratio=im.width/im.height
                h=min(height-2,5.4);w=h*ratio
                if w>width-1.2:w=width-1.2;h=w/ratio
                slide.shapes.add_picture(str(source),Inches((width-w)/2),Inches(1.35),width=Inches(w),height=Inches(h))
        else:
            box=slide.shapes.add_textbox(Inches(.8),Inches(1.5),Inches(width-1.6),Inches(height-2.3));tf=box.text_frame;tf.word_wrap=True
            for j,line in enumerate(content[1]):
                p=tf.paragraphs[0] if j==0 else tf.add_paragraph();p.text=line;p.font.name='Aptos';p.font.size=Pt(20 if width>=12 else 18);p.font.color.rgb=RGBColor(54,66,55);p.space_after=Pt(20);p.line_spacing=1.15
        foot=slide.shapes.add_textbox(Inches(.7),Inches(height-.42),Inches(width-1.4),Inches(.25))
        p=foot.text_frame.paragraphs[0];p.text=f'RescueGrid India  |  PALS ITPRBLM–B  |  Research simulation                         {index+1:02d}';p.font.size=Pt(8);p.font.color.rgb=RGBColor(112,125,103)
    destination=OUT/'PALS_RescueGrid_India.pptx';deck.save(destination)
    # Re-open and confirm that every generated content slide is present.
    check=Presentation(destination)
    assert len(check.slides)==len(slides)
    assert all(any(shape.has_text_frame and content[0] in shape.text for shape in slide.shapes) for slide,content in zip(check.slides,slides))
    print(f'Created and verified {len(slides)} slides: {destination}')

if __name__=='__main__':build()
