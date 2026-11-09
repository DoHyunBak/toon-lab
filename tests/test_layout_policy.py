"""Semantic contracts and rendering invariants; never an automatic aesthetic score."""
import copy,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from src.layout_policy import compile_layout
from src.layout_composer import compose_panel,rebase_lettering,geometric_qa

def panel(cid='p',**kw):
 p=dict(id=cid,role='emotion',time_layer='present',source_width=800,source_height=500,header_height=100,footer_height=0,link_after='beat',edge_safe_box=[.1,.1,.8,.8]);p.update(kw);return p

class PolicyTests(unittest.TestCase):
 def test_renaming_panels_does_not_change_design(self):
  a=compile_layout([panel('alpha')])['panels'][0];b=compile_layout([panel('beta')])['panels'][0]
  for k in ['art_width','art_height','edge','gap_after','paper']:self.assertEqual(a[k],b[k])
 def test_no_universal_black_frame(self):
  d=compile_layout([panel()])['panels'][0];self.assertEqual(d['rule_width'],0);self.assertEqual(d['edge'],'none')
 def test_explicit_contact_rule(self):
  d=compile_layout([panel(role='impact',emphasis='contact')])['panels'][0];self.assertGreater(d['rule_width'],0)
 def test_memory_entry_and_return(self):
  ds=compile_layout([panel('a'),panel('b',time_layer='memory',memory_group='childhood'),panel('c')])['panels']
  self.assertEqual(ds[0]['transition_after'],'memory_enter');self.assertEqual(ds[1]['transition_after'],'memory_exit');self.assertEqual(ds[1]['edge'],'soft');self.assertEqual(ds[0]['gap_gradient_after'][1],ds[1]['paper'])
 def test_memory_can_explicitly_disable_fade_for_boundary_art(self):
  ds=compile_layout([panel('a'),panel('b',time_layer='memory',memory_group='m',edge_safe_box=[0,0,1,1]),panel('c')],{'memory_edge_ratio':0})['panels']
  self.assertEqual(ds[0]['transition_after'],'memory_enter');self.assertEqual(ds[1]['transition_after'],'memory_exit')
  self.assertEqual(ds[1]['warnings'],[]);self.assertEqual(ds[1]['edge_pixels'],0)
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   source=Path(tmp)/'edge.png';Image.new('RGB',(800,500),(30,90,150)).save(source);im=compose_panel(source,ds[1])
   x,y=ds[1]['x'],ds[1]['top'];self.assertEqual(im.getpixel((x,y)),(30,90,150));self.assertEqual(im.getpixel((x+ds[1]['art_width']-1,y+ds[1]['art_height']-1)),(30,90,150))
 def test_rejects_unclosed_memory(self):
  with self.assertRaisesRegex(ValueError,'Unclosed'):compile_layout([panel(time_layer='memory',memory_group='m')])
 def test_rejects_missing_duplicate_or_reordered_scenes(self):
  for panels,expected in [([panel('a')],['a','b']),([panel('a'),panel('a')],None),([panel('b'),panel('a')],['a','b'])]:
   with self.assertRaises(ValueError):compile_layout(panels,expected_ids=expected)
 def test_rejects_unknown_semantics_and_invalid_numbers(self):
  for kw in [dict(role='random'),dict(time_layer='guess'),dict(link_after='random'),dict(source_width=0),dict(source_height=float('nan')),dict(role='impact',emphasis='black_band')]:
   with self.assertRaises(ValueError):compile_layout([panel(**kw)])
 def test_protects_critical_content_at_edge(self):
  ds=compile_layout([panel('m',time_layer='memory',memory_group='m',edge_safe_box=[0,0,.8,.8]),panel('p')])['panels']
  self.assertEqual(ds[0]['edge_pixels'],0);self.assertTrue(ds[0]['warnings'])
 def test_unknown_profile_option_does_not_silently_apply(self):
  with self.assertRaises(ValueError):compile_layout([panel()],{'black_frame_everywhere':True})
 def test_panel_id_cannot_escape_output_directory(self):
  with self.assertRaises(ValueError):compile_layout([panel('../../other')])
 def test_narrative_transition_is_not_same_as_action_gap(self):
  a=compile_layout([panel('a',link_after='continuous'),panel('b')]);b=compile_layout([panel('a',link_after='scene_change'),panel('b')]);self.assertGreater(b['panels'][0]['gap_after'],a['panels'][0]['gap_after'])
 def test_reveal_constraint_preserves_stopping_window(self):
  d=compile_layout([panel('a'),panel('b',role='reveal',reveal_requires_scroll=True,reveal_after='a')]);a=d['panels'][0];h=844*800/390;self.assertGreaterEqual(a['height']/2+a['gap_after'],h/2)
 def test_missing_reveal_dependency_rejected(self):
  with self.assertRaises(ValueError):compile_layout([panel('a'),panel('b',reveal_requires_scroll=True,reveal_after='other')])
 def test_render_protects_interior_and_uses_configured_canvas(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   p=Path(tmp)/'source.png';Image.new('RGB',(800,500),(30,90,150)).save(p)
   plan=compile_layout([panel('m',time_layer='memory',memory_group='m'),panel('n')],{'canvas_width':400})
   d=plan['panels'][0];im=compose_panel(p,d)
   self.assertEqual(im.width,400);self.assertEqual(im.getpixel((d['x']+d['art_width']//2,d['top']+d['art_height']//2)),(30,90,150))
   self.assertNotEqual(im.getpixel((d['x'],d['top'])),(30,90,150))
 def test_lettering_rebased_without_font_shrink(self):
  old=dict(art_width=600,art_height=400,x=100,top=100);new=dict(art_width=700,art_height=467,x=50,top=100)
  e=[dict(text='예시',font_size=32,type='normal',box=[.2,.02,.3,.12],tail=[.5,.20])]
  r=rebase_lettering(e,old,new,500,567)
  self.assertEqual(r[0]['font_size'],32);self.assertAlmostEqual(r[0]['box'][2]*800,.3*800);self.assertEqual(e[0]['box'][1],.02)
 def test_transparent_art_uses_paper_instead_of_black(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   source=Path(tmp)/'transparent.png';Image.new('RGBA',(800,500),(0,0,0,0)).save(source)
   d=compile_layout([panel()])['panels'][0];im=compose_panel(source,d)
   self.assertEqual(im.getpixel((400,d['top']+20)),(255,255,255))
 def test_authored_balloon_body_is_not_repositioned_by_tail(self):
  old=dict(art_width=800,art_height=400,x=0,top=200);new=dict(art_width=688,art_height=344,x=56,top=200)
  entries=[dict(text='맡아 주렴.',type='normal',font_size=34,body_placement='authored',box=[.52,.02,.37,.26],tail=[.45,.4])]
  result=rebase_lettering(entries,old,new,600,544)[0]
  self.assertAlmostEqual(result['box'][0],.52)
  self.assertAlmostEqual(result['box'][1]*544,.02*600)
  self.assertAlmostEqual(result['tail'][0]*800,56+.45*800*.86)
  self.assertEqual(result['font_size'],34)
 def test_geometry_reports_out_of_canvas_without_quality_claim(self):
  plan=compile_layout([panel()]);qa=geometric_qa({'cuts':[dict(id='p',dialogue=[dict(box=[.9,0,.3,.2],font_size=32)])]},plan)
  self.assertEqual(qa['status'],'needs_review');self.assertEqual(qa['visual_quality'],'not_assessed')
 def test_failed_composition_does_not_publish_partial_episode(self):
  from tools.apply_layout_policy import run
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   work=Path(tmp);im=work/'art.png';Image.new('RGB',(800,400),'red').save(im)
   p=panel();p.update(source_image=str(im),old_geometry=dict(art_width=800,art_height=500,x=0,top=0,canvas_height=500),dialogue=[])
   src=work/'input.json';src.write_text(json.dumps(dict(expected_ids=['p'],panels=[p])),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'source dimensions changed'):run(src,work/'out',None)
   self.assertFalse((work/'out').exists())
 def test_cli_path_publishes_complete_manuscript_and_reports_only_geometry(self):
  from tools.apply_layout_policy import run
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   work=Path(tmp);im=work/'art.png';Image.new('RGB',(800,500),(30,90,150)).save(im)
   p=panel();p.update(source_image=str(im),old_geometry=dict(art_width=800,art_height=500,x=0,top=0,canvas_height=500),dialogue=[])
   src=work/'input.json';src.write_text(json.dumps(dict(expected_ids=['p'],panels=[p])),encoding='utf-8')
   result=run(src,work/'out',None)
   self.assertTrue((work/'out/full_strip.png').is_file());self.assertTrue((work/'out/manifest.json').is_file())
   self.assertEqual(result['qa']['status'],'geometry_passed');self.assertEqual(result['qa']['visual_quality'],'not_assessed')

if __name__=='__main__':unittest.main()
