"""Allocate measured dialogue bands separately from artwork, without shrinking type.

Role/link annotations remain editorial input. This module only packs the actual
text and maps existing artwork-relative SFX; it does not identify faces or speakers.
"""
import copy
from .balloon_sizing import measure_balloon
from .layout_composer import rebase_lettering


def allocate_bands(panel,font_path,canvas_width=800):
    p=copy.deepcopy(panel);old=p['old_geometry'];old_width=p.get('source_canvas_width',800)
    width=canvas_width;pad=24;gap=28;tail_room=32
    bands={'header':[],'footer':[]};sfx_seen=False;footer_seen=False
    for index,e in enumerate(p.get('dialogue',[])):
        if e.get('type')=='sfx':
            if footer_seen:raise ValueError('Interleaved SFX after footer speech needs authored placement')
            sfx_seen=True;continue
        band='footer' if sfx_seen else 'header';footer_seen|=sfx_seen
        if 'balloon_variant' in e:
            from .font_policy import entry_font
            m=measure_balloon(e['text'],font_path=entry_font(e,font_path),font_size=e['font_size'],variant=e['balloon_variant'])
            w,h=m.width,m.height
        else:
            w=round(e['box'][2]*old_width);h=round(e['box'][3]*old['canvas_height'])
        if w>width-2*pad:raise ValueError('Text too wide for dialogue band; revise line breaks without shrinking type')
        bands[band].append(dict(entry=index,width=w,height=h))
    for name,slots in bands.items():
        x=pad;y=pad;row_height=0
        for slot in slots:
            if x!=pad and x+slot['width']>width-pad:
                x=pad;y+=row_height+gap;row_height=0
            slot.update(x=x,y=y);x+=slot['width']+gap;row_height=max(row_height,slot['height'])
        p[name+'_height']=y+row_height+pad+tail_room if slots else 0
    p['lettering_bands']=bands
    return p


def place_bands(panel,decision,canvas_width=800):
    old=panel['old_geometry']
    words=rebase_lettering(panel.get('dialogue',[]),old,decision,old['canvas_height'],decision['height'],canvas_width,panel.get('source_canvas_width',800))
    for band,slots in panel['lettering_bands'].items():
        for slot in slots:
            e=words[slot['entry']];x=slot['x'];y=slot['y']
            if band=='footer':y+=decision['top']+decision['art_height']
            w=slot['width'];h=slot['height'];e['box']=[x/canvas_width,y/decision['height'],w/canvas_width,h/decision['height']]
            # A restrained directional tail stays in the reserved white band.
            # It is not an automatic mouth/face anchor.
            e.pop('tail',None)
            if e.get('type') in {'normal','shout'} and slot is slots[-1]:
                tip_y=y+h+22 if band=='header' else y-18
                e['tail']=[(x+w*.65)/canvas_width,tip_y/decision['height']]
            e['body_placement']='authored'
    return words
