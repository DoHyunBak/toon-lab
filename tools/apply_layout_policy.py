"""Apply semantic layout JSON to existing artwork; no network/model calls.

python tools/apply_layout_policy.py INPUT.json --output-dir OUTPUT --font FONT.ttf
"""
import argparse,hashlib,json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image
from src.layout_policy import compile_layout
from src.layout_composer import compose_panel,rebase_lettering,geometric_qa
from src.webtoon_stitcher import stitch_episode
from src.layout_lettering import allocate_bands,place_bands

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def write_viewport_previews(output,plan):
 """Render reading stops without marking their visual quality as passed."""
 output=Path(output);qa=output/'viewport_qa'
 if qa.exists():raise FileExistsError('Preserve previous viewport evidence')
 qa.mkdir();cfg=plan['profile'];width=cfg['viewport_width'];height=cfg['viewport_height']
 with Image.open(output/'full_strip.png') as raw:
  master=raw.convert('RGB');ratio=width/master.width
  mobile=master.resize((width,round(master.height*ratio)),Image.Resampling.LANCZOS)
 samples=[]
 for i,d in enumerate(plan['panels']):
  start=max(0,min(max(0,mobile.height-height),round((d['y']+d['height']/2)*ratio-height/2)))
  name=f'viewport_{i+1:03d}.png';mobile.crop((0,start,width,min(mobile.height,start+height))).save(qa/name)
  samples.append(dict(path='viewport_qa/'+name,panel_id=d['id'],mobile_start_y=start,width=width,height=min(height,mobile.height-start),visual_review='not_reviewed'))
 save(output/'viewport_samples.json',dict(source='full_strip.png',samples=samples,scope='rendered stops only; no eye tracking or aesthetic pass'))
 return samples
def run(source,output,font):
 source=Path(source).resolve();output=Path(output).resolve()
 if not output.is_relative_to(ROOT):raise ValueError('Output must stay in this project')
 if output.exists():raise FileExistsError('Preserve prior outputs; choose a fresh destination')
 data=json.loads(source.read_text(encoding='utf-8'))
 if not data.get('expected_ids'):raise ValueError('expected_ids is required to prevent silent manuscript loss')
 if any(p.get('lettering_mode') not in {None,'measured_bands'} for p in data['panels']):raise ValueError('Unknown lettering_mode')
 width=data.get('profile',{}).get('canvas_width',800)
 data['panels']=[allocate_bands(p,font,width) if p.get('lettering_mode')=='measured_bands' else p for p in data['panels']]
 plan=compile_layout(data['panels'],data.get('profile'),expected_ids=data['expected_ids'])
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='layout-',dir=output.parent) as tmp:
  stage=Path(tmp)/'result';stage.mkdir();art=stage/'art';art.mkdir();cuts=[];provenance=[]
  for p,d in zip(data['panels'],plan['panels']):
   image=(source.parent/p['source_image']).resolve()
   with Image.open(image) as im:
    if im.size!=(p['source_width'],p['source_height']):raise ValueError(p['id']+': source dimensions changed')
   d['rule_color']=plan['profile']['rule_color']
   rendered=compose_panel(image,d,clue_marks=p.get('clue_marks'),source_crop=p.get('art_crop'));name=p['id']+'.png';rendered.save(art/name)
   words=(place_bands(p,d,plan['profile']['canvas_width']) if p.get('lettering_mode')=='measured_bands' else rebase_lettering(p.get('dialogue',[]),p['old_geometry'],d,p['old_geometry']['canvas_height'],d['height'],plan['profile']['canvas_width'],p.get('source_canvas_width',800)))
   cut=dict(id=p['id'],page=len(cuts)//4+1,image='art/'+name,description=p.get('description',''),prompt='Existing artwork source; semantic layout derivative, not a new model call',dialogue=words,gap_after=d['gap_after'],reference_ids=p.get('reference_ids',[]),characters=[])
   if d['gap_gradient_after'] is not None:cut['gap_gradient_after']=d['gap_gradient_after']
   cuts.append(cut);provenance.append(dict(id=p['id'],source=str(image),sha256=hashlib.sha256(image.read_bytes()).hexdigest(),annotations=p,decision=d))
  episode=dict(title=data.get('title','Layout candidate'),cuts=cuts);qa=geometric_qa(episode,plan)
  if qa['issues']:raise ValueError('Layout needs review: '+'; '.join(qa['issues']))
  save(stage/'episode.json',episode);save(stage/'layout_plan.json',plan);save(stage/'geometry_qa.json',qa);save(stage/'layout_provenance.json',provenance)
  save(stage/'input_contract.json',dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),profile_source='inline_profile' if 'profile' in data else 'DEFAULT_PROFILE snapshot',profile=plan['profile']))
  stitch_episode(stage/'episode.json',stage,width=plan['profile']['canvas_width'],font_path=font,top_padding=0,bottom_padding=0,max_height=data.get('max_part_height',4000))
  write_viewport_previews(stage,plan)
  # Atomic new directory publication; both paths are verified inside workspace.
  if not stage.resolve().is_relative_to(ROOT):raise ValueError('Unexpected staging root')
  os.replace(stage,output)
 return dict(output=str(output),panels=len(cuts),height=plan['height'],qa=qa)

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('input',type=Path);ap.add_argument('--output-dir',required=True,type=Path);ap.add_argument('--font',required=True,type=Path);a=ap.parse_args()
 print(json.dumps(run(a.input,a.output_dir,a.font),ensure_ascii=False))
if __name__=='__main__':main()
