"""Authored, supersampled balloon contours and expressive type overlays.

This draws lettering, not scene artwork. Body boxes are measured independently
of tails; text never shrinks or clips to silently fit an unsuitable balloon.
"""
from __future__ import annotations
import math
import unicodedata
from PIL import Image, ImageDraw
from .bubble_renderer import BubbleLayoutError, _load_font, _normalized, _explicit_box
from .font_policy import entry_font

SCALE=4

def _curve(a,b,c,d,steps=30):
    return [((1-t)**3*a[0]+3*(1-t)**2*t*b[0]+3*(1-t)*t*t*c[0]+t**3*d[0],
             (1-t)**3*a[1]+3*(1-t)**2*t*b[1]+3*(1-t)*t*t*c[1]+t**3*d[1])
            for t in (i/steps for i in range(1,steps+1))]

def _ring(body,angle,kind):
    x0,y0,x1,y1=body;cx=(x0+x1)/2;cy=(y0+y1)/2;rx=(x1-x0)/2;ry=(y1-y0)/2
    co,si=math.cos(angle),math.sin(angle)
    # Soft squircle with small asymmetry: more useful text area than an ellipse,
    # without the round-rectangle/button appearance of UI labels.
    n=2 if kind=='measured' else (2.25 if kind!='shout' else 2.05)
    gain=1 if kind=='measured' else 1+.012*math.sin(3*angle+.6)
    if kind=='shout':gain+=.045*math.cos(11*angle)+.018*math.sin(7*angle)
    return (cx+rx*math.copysign(abs(co)**(2/n),co)*gain,
            cy+ry*math.copysign(abs(si)**(2/n),si)*gain)

def _outline(body,kind,tip,measured=False):
    x0,y0,x1,y1=body;cx=(x0+x1)/2;cy=(y0+y1)/2;rx=(x1-x0)/2;ry=(y1-y0)/2
    if kind=='narration':
        return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    contour='measured' if measured and kind!='shout' else kind
    if tip is None or kind in {'thought','narration'}:
        return [_ring(body,2*math.pi*i/180,contour) for i in range(180)]
    angle=math.atan2((tip[1]-cy)/ry,(tip[0]-cx)/rx)
    if ((tip[0]-cx)/rx)**2+((tip[1]-cy)/ry)**2<=1:
        raise BubbleLayoutError('editorial tail must end outside the balloon body')
    # Narrow attachment and restrained curvature keep the tail slender.
    delta=.045
    points=[_ring(body,angle+delta+(2*math.pi-2*delta)*i/160,contour) for i in range(161)]
    a=points[-1];b=points[0];length=math.dist(tip,_ring(body,angle,contour))
    if length>180:raise BubbleLayoutError('editorial tail is too long; place body closer to speaker')
    vx,vy=tip[0]-(a[0]+b[0])/2,tip[1]-(a[1]+b[1])/2
    length0=max(1,math.hypot(vx,vy));nx,ny=-vy/length0,vx/length0
    points+=_curve(a,(a[0]+vx*.35+nx*2.5,a[1]+vy*.35+ny*2.5),
                   (tip[0]-vx*.18+nx*.6,tip[1]-vy*.18+ny*.6),tip)
    points+=_curve(tip,(tip[0]-vx*.20-nx*.6,tip[1]-vy*.20-ny*.6),
                   (b[0]+vx*.32-nx*1.8,b[1]+vy*.32-ny*1.8),b)
    return points

def render_editorial(image,entries,*,font_path,font_size,min_font_size):
    w,h=image.size;ss=SCALE
    overlay=Image.new('RGBA',(w*ss,h*ss),(0,0,0,0));d=ImageDraw.Draw(overlay)
    occupied=[]
    for e in entries:
        if e.get('style')!='editorial':raise BubbleLayoutError('Do not mix editorial and legacy lettering in one image')
        text=e.get('text');kind=e.get('type','normal');size=e.get('font_size',font_size)
        if not isinstance(text,str) or not text.strip():raise BubbleLayoutError('text must be nonempty')
        if any(unicodedata.category(c)=='Cc' and c not in '\n\r' for c in text):
            raise BubbleLayoutError('text contains unsupported control characters')
        if kind not in {'normal','thought','shout','narration','sfx'}:raise BubbleLayoutError('unknown editorial type')
        if type(size) is not int or not min_font_size<=size<=512:raise BubbleLayoutError('invalid editorial font_size')
        body=_explicit_box(e['box'],w,h)
        chosen=entry_font(e,font_path)
        font=_load_font(chosen,size*ss,text)
        measured=None
        if 'balloon_variant' in e:
            if kind in {'narration','sfx'}:raise BubbleLayoutError('B/C sizing applies only to balloons')
            from .balloon_sizing import measure_balloon
            measured=measure_balloon(text,font_path=chosen,font_size=size,variant=e['balloon_variant'])
            if (body[2]-body[0],body[3]-body[1])!=(measured.width,measured.height):
                raise BubbleLayoutError('Authored body differs from B/C measured dimensions')
        ink=e.get('ink','#242126')
        if kind=='sfx':
            if '\n' in text:raise BubbleLayoutError('editorial sfx must be a single line')
            angle=e.get('angle',0)
            if isinstance(angle,bool) or not isinstance(angle,(int,float)) or not math.isfinite(angle) or abs(angle)>45:
                raise BubbleLayoutError('sfx angle must be finite and within 45 degrees')
            tracking=e.get('tracking',0)*ss
            advance=sum(font.getlength(c) for c in text)+tracking*(len(text)-1)
            stroke=max(0,round(e.get('halo',1.0)*ss));pad=round((size*.35+5)*ss)
            tile=Image.new('RGBA',(math.ceil(advance+pad*2),size*ss*2+pad*2),(0,0,0,0));td=ImageDraw.Draw(tile)
            x=pad
            for char in text:
                td.text((x,pad),char,font=font,fill=ink,stroke_width=stroke,stroke_fill=e.get('halo_ink','white'),anchor='lt')
                x+=font.getlength(char)+tracking
            bb=tile.getbbox();tile=tile.crop(bb).rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
            if tile.width>(body[2]-body[0])*ss or tile.height>(body[3]-body[1])*ss:
                raise BubbleLayoutError('SFX does not fit authored area; enlarge box or change font size')
            x=round(((body[0]+body[2])*ss-tile.width)/2);y=round(((body[1]+body[3])*ss-tile.height)/2)
            overlay.alpha_composite(tile,(x,y));foot=(x/ss,y/ss,(x+tile.width)/ss,(y+tile.height)/ss)
        else:
            tip=None
            if e.get('tail') is not None:
                tx,ty=_normalized(e['tail'],2,'tail');tip=(tx*w,ty*h)
            points=_outline(body,kind,tip,measured=measured is not None)
            foot=(min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points))
            if tip and kind=='thought':
                cx=(body[0]+body[2])/2;cy=(body[1]+body[3])/2
                angle=math.atan2((tip[1]-cy)/((body[3]-body[1])/2),(tip[0]-cx)/((body[2]-body[0])/2))
                start=_ring(body,angle,'measured' if measured else kind)
                for t,r in ((.36,4.2),(.66,2.9),(.91,1.8)):
                    x=start[0]+(tip[0]-start[0])*t;y=start[1]+(tip[1]-start[1])*t
                    d.ellipse(((x-r)*ss,(y-r)*ss,(x+r)*ss,(y+r)*ss),fill='white',outline='#222222',width=round(1.1*ss))
                    foot=(min(foot[0],x-r),min(foot[1],y-r),max(foot[2],x+r),max(foot[3],y+r))
            line=max(1,round(e.get('line_width',1.5)*ss))
            p=[(round(x*ss),round(y*ss)) for x,y in points]
            d.polygon(p,fill='#fffefa');d.line(p+[p[0]],fill='#222222',width=line,joint='curve')
            lines=text.split('\n');spacing=measured.line_gap*ss if measured else round(size*.23*ss)
            boxes=[font.getbbox(t) for t in lines];widths=[b[2]-b[0] for b in boxes];heights=[b[3]-b[1] for b in boxes]
            total=sum(heights)+spacing*(len(lines)-1)
            if max(widths)>(body[2]-body[0]-32)*ss or total>(body[3]-body[1]-28)*ss:
                raise BubbleLayoutError('Text exceeds editorial body padding; change the authored body, not the text')
            y=((body[1]+body[3])*ss-total)/2-ss
            if measured:y=(body[1]+measured.text_boxes[0][1])*ss
            for text_line,bb,tw,th in zip(lines,boxes,widths,heights):
                x=((body[0]+body[2])*ss-tw)/2-bb[0]
                d.text((round(x),round(y-bb[1])),text_line,font=font,fill=ink)
                y+=th+spacing
        if foot[0]<0 or foot[1]<0 or foot[2]>w or foot[3]>h:raise BubbleLayoutError('editorial lettering exceeds canvas')
        if any(not(foot[2]+3<=o[0] or o[2]+3<=foot[0] or foot[3]+3<=o[1] or o[3]+3<=foot[1]) for o in occupied):
            raise BubbleLayoutError('editorial lettering footprints overlap')
        occupied.append(foot)
    mode='RGBA' if image.mode in {'RGBA','LA','PA'} or 'transparency' in image.info else 'RGB'
    return Image.alpha_composite(image.convert('RGBA'),overlay.resize(image.size,Image.Resampling.LANCZOS)).convert(mode)
