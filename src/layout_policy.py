"""Deterministic semantic layout planning; no inferred story or automatic art score.

Editorial profile values are project choices. Their research rationale is tracked
separately in workspace/research/layout_assembly_2026_10_21/.
"""
from __future__ import annotations
import copy
import math
import re
from PIL import ImageColor

ROLES={'card','establish','wide','action','reaction','emotion','insert','impact','relationship','reveal'}
DEFAULT_PROFILE={
 'canvas_width':800,'viewport_width':390,'viewport_height':844,
 'width_ratios':{'card':1,'establish':1,'wide':1,'action':.95,'reaction':.86,'emotion':.86,'insert':.74,'impact':.82,'relationship':.96,'reveal':1},
 'max_art_viewport_ratios':None,
 'gap_viewport_ratios':{'continuous':.035,'beat':.065,'scene_change':.18,'memory_enter':.18,'memory_exit':.18,'ending':.10},
 'present_paper':'#ffffff','memory_paper':'#f7eee2','rule_color':'#292724','rule_width_ratio':.0025,'memory_edge_ratio':.035,'ending_edge_ratio':.05,
}

def _number(value,name,lo,hi):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError(f'{name} out of range')
 return value

def _box(box,name):
 if not isinstance(box,(list,tuple)) or len(box)!=4:raise ValueError(f'{name} needs [x,y,width,height]')
 x,y,w,h=[_number(v,name,0,1) for v in box]
 if w<=0 or h<=0 or x+w>1+1e-9 or y+h>1+1e-9:raise ValueError(f'{name} outside normalized bounds')
 return [x,y,w,h]

def compile_layout(panels,profile=None,*,expected_ids=None):
 """Keep order, derive widths/ends/transitions, and preserve every story identity.

Requires editorial role/time/link annotations. It cannot derive them from images.
Cards do not count as story scenes. Numeric choices never prove visual quality.
"""
 cfg=copy.deepcopy(DEFAULT_PROFILE)
 if profile:
  unknown=set(profile)-set(cfg)
  if unknown:raise ValueError('Unknown profile fields: '+','.join(sorted(unknown)))
  for k,v in profile.items():cfg[k]=copy.deepcopy(v)
 width=cfg['canvas_width'];vw=cfg['viewport_width'];vh=cfg['viewport_height']
 for name,v in [('canvas_width',width),('viewport_width',vw),('viewport_height',vh)]:
  if type(v) is not int or not 32<=v<=16000:raise ValueError(name+' must be a positive integer size')
 if set(cfg['width_ratios'])!=ROLES:raise ValueError('width_ratios must specify every known role')
 for k,v in cfg['width_ratios'].items():_number(v,k,.45,1)
 limits=cfg['max_art_viewport_ratios']
 if limits is not None:
  if not isinstance(limits,dict) or set(limits)!=ROLES:raise ValueError('height limits must specify every known role')
  for k,v in limits.items():_number(v,k,.15,2)
 kinds={'continuous','beat','scene_change','memory_enter','memory_exit','ending'}
 if set(cfg['gap_viewport_ratios'])!=kinds:raise ValueError('gap profile keys differ')
 for k,v in cfg['gap_viewport_ratios'].items():_number(v,k,0,1)
 for k in ['rule_width_ratio','memory_edge_ratio','ending_edge_ratio']:_number(cfg[k],k,0,.1)
 for k in ['present_paper','memory_paper','rule_color']:ImageColor.getrgb(cfg[k])
 if not isinstance(panels,list) or not panels:raise ValueError('Need ordered panels')
 if any(not isinstance(p,dict) for p in panels):raise ValueError('Each panel must be an object')
 ids=[p.get('id') for p in panels]
 if any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Panel IDs must be unique safe filenames')
 if expected_ids is not None and ids!=list(expected_ids):raise ValueError('Panel order/coverage changed')
 story=[p for p in panels if p.get('role')!='card']
 if not story:raise ValueError('No story panels')
 if story[-1].get('time_layer')!='present':raise ValueError('Unclosed memory; explicit return required')
 decisions=[];master_view_height=vh*width/vw
 for index,p in enumerate(panels):
  role=p.get('role');time=p.get('time_layer')
  if role not in ROLES:raise ValueError('Unknown narrative role')
  if time not in {'present','memory'}:raise ValueError('Missing time_layer')
  if time=='memory' and not p.get('memory_group'):raise ValueError('Memory requires a group')
  link=p.get('link_after')
  if link not in {'continuous','beat','scene_change','ending'}:raise ValueError('Unknown link_after')
  align=p.get('alignment','center')
  if align not in {'left','center','right'}:raise ValueError('Unknown alignment')
  emphasis=p.get('emphasis','none')
  if emphasis not in {'none','contact','shock'}:raise ValueError('Unknown emphasis')
  sw=_number(p.get('source_width'),'source_width',1,50000);sh=_number(p.get('source_height'),'source_height',1,50000)
  role_width=round(width*cfg['width_ratios'][role]);aw=role_width
  # Fit the whole source within an explicit mobile reading budget. No crop,
  # stretch, or inferred camera change; legacy profiles retain their old output.
  if limits is not None and role!='card':aw=min(aw,max(1,math.floor(master_view_height*limits[role]*sw/sh)))
  ah=max(1,round(sh*aw/sw));x=0 if align=='left' else width-aw if align=='right' else (width-aw)//2
  top=p.get('header_height',0);bottom=p.get('footer_height',0)
  if any(type(v) is not int or v<0 for v in [top,bottom]):raise ValueError('Header/footer allocations must be nonnegative integers')
  warnings=[];paper=cfg['memory_paper'] if time=='memory' else cfg['present_paper']
  edge='soft' if time=='memory' and cfg['memory_edge_ratio']>0 else 'hairline' if emphasis in {'contact','shock'} else 'none'
  fade=round(aw*cfg['memory_edge_ratio']) if edge=='soft' else 0
  safe=p.get('edge_safe_box')
  if safe is not None:_box(safe,'edge_safe_box')
  if edge=='soft':
   if safe is None:fade=0;warnings.append('edge_softening_requires_reviewed_safe_box')
   else:
    sx,sy,bw,bh=_box(safe,'edge_safe_box')
    clearance=min(sx*aw,sy*ah,(1-sx-bw)*aw,(1-sy-bh)*ah)
    fade=min(fade,max(0,math.floor(clearance)))
    if fade==0:warnings.append('edge_softening_disabled_to_protect_boundary_content')
  nxt=panels[index+1] if index+1<len(panels) else None
  transition=link
  if nxt and role!='card' and nxt.get('role')!='card' and time!=nxt.get('time_layer'):
   transition='memory_enter' if nxt.get('time_layer')=='memory' else 'memory_exit'
  elif nxt and time=='memory' and nxt.get('time_layer')=='memory' and p.get('memory_group')!=nxt.get('memory_group'):transition='scene_change'
  gap=round(master_view_height*cfg['gap_viewport_ratios'][transition]) if nxt else 0
  next_paper=(cfg['memory_paper'] if nxt.get('time_layer')=='memory' else cfg['present_paper']) if nxt else paper
  gradient=[paper,next_paper] if nxt and paper!=next_paper else [paper,paper] if time=='memory' and nxt else None
  bottom_fade=0
  if link=='ending' and role=='reveal':
   bottom_fade=round(aw*cfg['ending_edge_ratio']);edge='ending_soft'
   if safe is not None:
    sy=_box(safe,'edge_safe_box')[1];bh=safe[3];bottom_fade=min(bottom_fade,max(0,math.floor((1-sy-bh)*ah)))
   else:bottom_fade=0;warnings.append('ending_softening_requires_reviewed_safe_box')
  decisions.append(dict(id=p['id'],role=role,time_layer=time,paper=paper,canvas_width=width,rule_color=cfg['rule_color'],art_width=aw,art_height=ah,x=x,top=top,height=max(260,top+ah+bottom) if role!='card' else top+ah+bottom,
      edge=edge,edge_pixels=fade,bottom_fade_pixels=bottom_fade,rule_width=max(1,round(aw*cfg['rule_width_ratio'])) if edge=='hairline' else 0,
      transition_after=transition,gap_after=gap,gap_gradient_after=gradient,warnings=warnings,
      evidence_rules=['L01','L02','L03','L04'],reason=f'role={role}; time={time}; emphasis={emphasis}; next_transition={transition}; width={aw}/{role_width}; full_source_preserved'))
 # Optional suspense constraint is explicit story intent, not a universal rhythm.
 for i,p in enumerate(panels[1:],1):
  if p.get('reveal_requires_scroll'):
   if p.get('reveal_after')!=panels[i-1]['id']:raise ValueError('Reveal dependency must be the preceding panel')
   before=decisions[i-1];minimum=math.ceil(master_view_height/2-before['height']/2+32)
   before['gap_after']=max(before['gap_after'],minimum)
   before['reason']+='; preserve explicit reveal stopping window'
 y=0
 for d in decisions:d['y']=y;y+=d['height']+d['gap_after']
 return dict(schema_version=1,profile=cfg,panels=decisions,height=y,expected_ids=ids,automatic_visual_quality='not_assessed',human_approval='pending')
