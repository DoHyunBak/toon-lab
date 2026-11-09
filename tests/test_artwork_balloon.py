import unittest
import math
from PIL import Image
from src.layout_composer import rebase_lettering
from src.layout_composer import composite_clue_marks


class AuthoredClueTests(unittest.TestCase):
 def test_river_layer_renders_all_89_discs_and_preserves_base(self):
  source=Image.new('RGB',(500,400),(20,30,40));before=source.tobytes()
  points=[dict(x=.08+(i%10)*.09,y=.08+(i//10)*.10,radius=.022,on=i<20) for i in range(89)]
  result=composite_clue_marks(source,dict(kind='controlled_lights',symbol='river',source_count=89,points=points))
  self.assertEqual(source.tobytes(),before)
  for p in points:
   x,y=round(p['x']*500),round(p['y']*400)
   self.assertNotEqual(result.getpixel((x,y)),(20,30,40,255))
  self.assertEqual(sum(p['on'] for p in points),20)
  with self.assertRaisesRegex(ValueError,'count'):
   composite_clue_marks(source,dict(kind='controlled_lights',symbol='river',source_count=89,points=points[:-1]))
 def test_thirty_separate_cores_and_one_dark_state_preserve_source(self):
  source=Image.new('RGB',(300,200),(0,0,0));before=source.tobytes()
  points=[dict(x=.5+.4*math.cos(i*math.tau/30),y=.5+.35*math.sin(i*math.tau/30),radius=.008,on=True) for i in range(30)]
  marks=dict(kind='controlled_lights',source_count=30,points=points)
  def cores(image):
   pixels=image.convert('RGB');remaining={(x,y) for y in range(200) for x in range(300) if pixels.getpixel((x,y))==(255,239,198)};count=0
   while remaining:
    count+=1;todo=[remaining.pop()]
    while todo:
     x,y=todo.pop()
     for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
      if q in remaining:remaining.remove(q);todo.append(q)
   return count
  result=composite_clue_marks(source,marks)
  self.assertEqual(cores(result),30);self.assertEqual(source.tobytes(),before)
  self.assertEqual(result.getpixel((150,100)),(0,0,0,255))
  points[0]['on']=False
  self.assertEqual(cores(composite_clue_marks(source,marks)),29)
  self.assertEqual(source.tobytes(),before)
 def test_count_overlap_and_bounds_fail_instead_of_silent_clue_loss(self):
  source=Image.new('RGB',(300,200))
  p=dict(x=.5,y=.5,radius=.02,on=True)
  with self.assertRaisesRegex(ValueError,'count'):composite_clue_marks(source,dict(kind='controlled_lights',source_count=30,points=[p]))
  with self.assertRaisesRegex(ValueError,'Overlapping'):composite_clue_marks(source,dict(kind='controlled_lights',source_count=2,points=[p,p]))
  with self.assertRaisesRegex(ValueError,'outside'):composite_clue_marks(source,dict(kind='controlled_lights',source_count=1,points=[dict(p,x=0)]))
class ArtworkBalloonTests(unittest.TestCase):
 def setUp(self):
  self.old=dict(x=0,top=100,art_width=800,art_height=500)
  self.new=dict(x=100,top=20,art_width=600,art_height=375)
  self.entry=dict(type='normal',box=[0,0,.25,.1],font_size=32,art_anchor=[.5,.1],protected_art_boxes=[[0,0,.4,1]])
 def apply(self,e):return rebase_lettering([e],self.old,self.new,600,450)[0]
 def test_position_tracks_art_but_type_and_body_stay_fixed(self):
  e=self.apply(self.entry);self.assertAlmostEqual(e['box'][0]*800,400);self.assertAlmostEqual(e['box'][1]*450,57.5)
  self.assertAlmostEqual(e['box'][2]*800,200);self.assertAlmostEqual(e['box'][3]*450,60);self.assertEqual(e['font_size'],32)
 def test_protected_subject_is_rejected(self):
  self.entry['art_anchor']=[.1,.1]
  with self.assertRaisesRegex(ValueError,'protected'):self.apply(self.entry)
 def test_overflow_is_rejected_instead_of_shrinking(self):
  self.entry['art_anchor']=[1,1]
  with self.assertRaisesRegex(ValueError,'outside'):self.apply(self.entry)
 def test_legacy_authored_body_stays_unchanged(self):
  self.entry.pop('art_anchor');self.entry['body_placement']='authored'
  self.assertEqual(self.apply(self.entry)['box'][0],0)
if __name__=='__main__':unittest.main()
