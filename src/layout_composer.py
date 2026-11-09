"""Apply a compiled layout plan to raw panel art and separate lettering layers."""
from __future__ import annotations
import copy
import math
from PIL import Image,ImageDraw,ImageChops,ImageFilter

def _smooth(v):return v*v*(3-2*v)

def composite_clue_marks(source,marks):
 """Authored count-critical light layer; preserve AI base bytes and explicit states."""
 if marks.get('kind')!='controlled_lights':raise ValueError('Unknown authored clue layer')
 points=marks.get('points');count=marks.get('source_count')
 if type(count) is not int or not 1<=count<=128 or not isinstance(points,list) or len(points)!=count:
  raise ValueError('Clue light count differs from declared source count')
 raw=source.convert('RGBA');w,h=raw.size;geometry=[]
 for point in points:
  values=[point.get(k) for k in ('x','y','radius')]
  if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values) or type(point.get('on')) is not bool:
   raise ValueError('Invalid clue light geometry/state')
  x,y,r=values;x*=w;y*=h;r*=w
  if r<1 or x-r<0 or x+r>w or y-r<0 or y+r>h:raise ValueError('Clue light outside art')
  if any(math.hypot(x-a,y-b)<=r+c for a,b,c,_ in geometry):raise ValueError('Overlapping clue lights')
  geometry.append((x,y,r,point['on']))
 if marks.get('symbol')=='river':
  # Same counted layer as the pressure lights, with a river-wave emblem.
  layer=Image.new('RGBA',raw.size);draw=ImageDraw.Draw(layer)
  for i in range(2200):
   x=(.07+((i*137)%2200)/2200*.86)*w;y=(.07+((i*733)%2200)/2200*.82)*h
   draw.ellipse((x-1,y-1,x+1,y+1),fill=(92,211,236,85))
  for x,y,r,on in geometry:
   if on:draw.ellipse((x-r*1.3,y-r*1.3,x+r*1.3,y+r*1.3),fill=(35,196,241,130))
  raw=Image.alpha_composite(raw,layer.filter(ImageFilter.GaussianBlur(5)))
  layer=Image.new('RGBA',raw.size);draw=ImageDraw.Draw(layer)
  for x,y,r,on in geometry:
   color=(134,245,255,255) if on else (83,130,150,255)
   draw.ellipse((x-r,y-r,x+r,y+r),fill=(4,25,37,190),outline=color,width=max(2,round(r*.10)))
   for offset in [-.23,0,.23]:
    line=[(x+r*t,y+r*(offset+.15*math.sin(t*math.pi*1.4))) for t in [j/20 for j in range(-14,15)]]
    draw.line(line,fill=color,width=max(2,round(r*.07)))
  return Image.alpha_composite(raw,layer)
 glow=Image.new('RGBA',raw.size);draw=ImageDraw.Draw(glow)
 for x,y,r,on in geometry:
  if on:draw.ellipse((x-r*1.8,y-r*1.8,x+r*1.8,y+r*1.8),fill=(255,48,22,145))
 glow=glow.filter(ImageFilter.GaussianBlur(max(g[2] for g in geometry)*.7))
 raw=Image.alpha_composite(raw,glow);draw=ImageDraw.Draw(raw)
 for x,y,r,on in geometry:
  draw.ellipse((x-r,y-r,x+r,y+r),fill=(55,22,20,255),outline=(128,57,39,255),width=max(1,round(r*.13)))
  if on:
   draw.ellipse((x-r*.76,y-r*.76,x+r*.76,y+r*.76),fill=(255,91,39,255))
   draw.ellipse((x-r*.46,y-r*.46,x+r*.46,y+r*.46),fill=(255,239,198,255))
  else:
   draw.ellipse((x-r*.73,y-r*.73,x+r*.73,y+r*.73),fill=(19,15,17,255))
 return raw


def compose_panel(source,decision,*,clue_marks=None,source_crop=None):
 """Only scene edge effects; never blur or regenerate protected subject regions."""
 raw=Image.open(source).convert('RGBA')
 if clue_marks is not None:raw=composite_clue_marks(raw,clue_marks)
 if source_crop is not None:
  if (not isinstance(source_crop,list) or len(source_crop)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in source_crop)):
   raise ValueError('Invalid authored art crop')
  cx,cy,cw,ch=source_crop
  if min(cx,cy)<0 or min(cw,ch)<=0 or cx+cw>1 or cy+ch>1 or abs(cw/ch-1)>.01:
   raise ValueError('Art crop must stay inside and retain source aspect')
  rw,rh=raw.size;raw=raw.crop((round(cx*rw),round(cy*rh),round((cx+cw)*rw),round((cy+ch)*rh)))
 w=decision['art_width'];h=decision['art_height'];x=decision['x'];top=decision['top']
 art=raw.resize((w,h),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(decision.get('canvas_width',800),decision['height']),decision['paper'])
 mask=None
 if decision['edge']=='soft' and decision['edge_pixels']:
  edge=decision['edge_pixels'];mask=Image.new('L',(w,h),255);draw=ImageDraw.Draw(mask)
  for i in range(edge+1):draw.rectangle((i,i,w-1-i,h-1-i),fill=round(255*_smooth(i/edge)))
 elif decision['edge']=='ending_soft' and decision['bottom_fade_pixels']:
  edge=decision['bottom_fade_pixels'];mask=Image.new('L',(w,h),255);draw=ImageDraw.Draw(mask)
  for row in range(h-edge,h):draw.line((0,row,w-1,row),fill=round(255*(1-_smooth((row-h+edge)/max(1,edge-1)))))
 alpha=art.getchannel('A')
 if mask is not None:alpha=ImageChops.multiply(alpha,mask)
 canvas.paste(art,(x,top),alpha)
 if decision['rule_width']:ImageDraw.Draw(canvas).rectangle((x,top,x+w-1,top+h-1),outline=decision.get('rule_color','#292724'),width=decision['rule_width'])
 return canvas

def rebase_lettering(entries,old_art,new_art,old_height,new_height,canvas_width=800,old_canvas_width=800):
 """Retain font sizes; rebase artwork-relative marks and speaker anchors.

Text exceeding an authored allocation is still rejected by editorial_lettering.
No automatic text shrinking or scene reordering is performed.
"""
 result=copy.deepcopy(entries);ratio=new_art['art_width']/old_art['art_width']
 old_top=old_art['top'];new_top=new_art['top'];old_h=old_art['art_height'];new_h=new_art['art_height']
 for e in result:
  bx,by,bw,bh=e['box'];bx*=old_canvas_width;bw*=old_canvas_width;by*=old_height;bh*=old_height
  if bw>canvas_width-24:raise ValueError('Text allocation wider than canvas; edit lettering, do not shrink type')
  if e.get('art_anchor') is not None:
   # Explicit artwork-relative body position; measured text dimensions stay fixed.
   ax,ay=e['art_anchor']
   if not (0<=ax<=1 and 0<=ay<=1):raise ValueError('Invalid art_anchor')
   bx=new_art['x']+ax*new_art['art_width'];by=new_top+ay*new_h
   if bx<12 or bx+bw>canvas_width-12 or by<4 or by+bh>new_height-4:raise ValueError('Artwork balloon allocation outside canvas')
   for zone in e.get('protected_art_boxes',[]):
    zx,zy,zw,zh=zone
    if min(zx,zy)<0 or min(zw,zh)<=0 or zx+zw>1 or zy+zh>1:raise ValueError('Invalid protected artwork box')
    left=new_art['x']+zx*new_art['art_width'];top=new_top+zy*new_h
    if bx<left+zw*new_art['art_width'] and bx+bw>left and by<top+zh*new_h and by+bh>top:raise ValueError('Balloon overlaps protected artwork')
  elif e.get('type')=='sfx':
   bx=new_art['x']+(bx-old_art['x'])*ratio;by=new_top+(by-old_top)*ratio
   bx=max(4,min(canvas_width-bw-4,bx));by=max(new_top,min(new_height-bh-4,by))
  elif by>=old_top+old_h-1:by+=new_h-old_h
  elif e.get('tail') is not None and e.get('body_placement')!='authored':
   tx,ty=e['tail'];target=new_art['x']+(tx*old_canvas_width-old_art['x'])*ratio
   bx=max(12,min(canvas_width-bw-12,target-bw*.62))
  if e.get('tail') is not None:
   tx,ty=e['tail'];tx=new_art['x']+(tx*old_canvas_width-old_art['x'])*ratio
   ty=new_top+(ty*old_height-old_top)*ratio
   e['tail']=[max(0,min(1,tx/canvas_width)),max(0,min(1,ty/new_height))]
  e['box']=[bx/canvas_width,by/new_height,bw/canvas_width,bh/new_height]
 return result

def geometric_qa(episode,plan):
 """Engineering checks only. Composition/acting/reader acceptance require eyes."""
 issues=[];decisions={d['id']:d for d in plan['panels']}
 if [c['id'] for c in episode['cuts']]!=plan['expected_ids']:issues.append('episode order differs from plan')
 for c in episode['cuts']:
  d=decisions[c['id']]
  if d['x']<0 or d['x']+d['art_width']>plan['profile']['canvas_width']:issues.append(c['id']+': art outside canvas')
  for e in c.get('dialogue',[]):
   x,y,w,h=e['box']
   if min(x,y)<0 or min(w,h)<=0 or x+w>1.000001 or y+h>1.000001:issues.append(c['id']+': lettering outside canvas')
   if e.get('font_size',0)<=0:issues.append(c['id']+': invalid text size')
  if d['warnings']:issues.extend(c['id']+': '+w for w in d['warnings'])
 return dict(status='needs_review' if issues else 'geometry_passed',issues=issues,visual_quality='not_assessed',research_effectiveness='not_measured')
