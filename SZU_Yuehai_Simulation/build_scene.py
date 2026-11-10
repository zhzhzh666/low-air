"""blender -b -P build_scene.py -- /absolute/path/to/szu_sim"""
import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector
root=Path(sys.argv[sys.argv.index('--')+1]);m=json.loads((root/'data/map.json').read_text()); orders=json.loads((root/'data/orders.json').read_text());run=json.loads((root/'results/gust.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
def mat(n,c):
 x=bpy.data.materials.new(n);x.diffuse_color=(*c,1);x.use_nodes=True
 nt=x.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission');geom=nt.nodes.new('ShaderNodeNewGeometry');dot=nt.nodes.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(.28,-.36,.75)
 level=nt.nodes.new('ShaderNodeMath');level.operation='MULTIPLY_ADD';level.inputs[1].default_value=.42;level.inputs[2].default_value=.79
 nt.links.new(geom.outputs['Normal'],dot.inputs[0]);nt.links.new(dot.outputs['Value'],level.inputs[0]);nt.links.new(level.outputs[0],em.inputs['Strength']);em.inputs['Color'].default_value=(*c,1);nt.links.new(em.outputs[0],out.inputs['Surface']);return x
ground=mat('Ground • local datum',(0.17,.28,.27));water=mat('Water',(.16,.50,.60));green=mat('Vegetation',(.24,.46,.32));road=mat('Road',(.44,.46,.43));light=mat('OSM height',(.79,.78,.69));estimate=mat('Estimated height',(.62,.69,.69));blue=mat('Truck',(.04,.35,.73));orange=mat('Drone',(.95,.28,.035));dk=mat('Chassis',(.03,.05,.07));marker=mat('Pickup location',(.95,.68,.12))
def mesh(name,v,f,ma):
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);scene.collection.objects.link(o);me.materials.append(ma);return o
def prism(name,items,ma):
 verts=[];faces=[]
 for pts,h in items:
  n=len(pts)
  if n<3:continue
  k=len(verts);verts.extend([(x,y,z) for z in [0,h] for x,y in pts]);faces.append(tuple(k+n+i for i in range(n)));faces.extend((k+i,k+(i+1)%n,k+n+(i+1)%n,k+n+i) for i in range(n))
 return mesh(name,verts,faces,ma)
prism('Site | 4.116 × 3.988 km',[([(-2058,-1994),(2058,-1994),(2058,1994),(-2058,1994)],-3)],ground)
for typ,ma in [('water',water),('green',green)]:prism(typ,[(p,.20 if typ=='water' else .10) for p,t in m['land'] if t==typ],ma)
for est,ma in [(True,estimate),(False,light)]:prism('Buildings | '+ma.name,[(b[0],b[1]) for b in m['buildings'] if (b[2]=='type estimate')==est],ma)
v=[];f=[]
for ids,cl,*_ in m['roads']:
 width={'service':4,'residential':6,'primary':12,'secondary':10,'trunk':13,'motorway':14}.get(cl,6)
 for a,b in zip(ids,ids[1:]):
  x,y=m['nodes'][a];X,Y=m['nodes'][b];dx=X-x;dy=Y-y;l=math.hypot(dx,dy)
  if not l:continue
  u=-dy/l*width/2;w=dx/l*width/2;k=len(v);v.extend([(x+u,y+w,.3),(x-u,y-w,.3),(X-u,Y-w,.3),(X+u,Y+w,.3)]);f.append(tuple(range(k,k+4)))
mesh('Directed road surface',v,f,road)
def box(n,xyz,scale,ma,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=xyz);o=bpy.context.object;o.name=n;o.dimensions=scale;o.data.materials.append(ma);o.parent=parent;return o
def empty(n):
 o=bpy.data.objects.new(n,None);scene.collection.objects.link(o);return o
truck=empty('TRUCK • animated');drone=empty('UAV • animated')
box('Cargo box',(-.7,0,2),(4.3,2.25,2.5),blue,truck);box('Cab',(2.2,0,1.6),(1.5,2.2,1.9),blue,truck);box('Windshield',(2.8,0,2.1),(.35,1.8,.7),dk,truck)
for x in [-2,1.9]:
 for y in [-1.05,1.05]:
  bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.45,depth=.28,location=(x,y,.6),rotation=(math.pi/2,0,0));o=bpy.context.object;o.parent=truck;o.data.materials.append(dk)
box('UAV body',(0,0,.22),(.65,.45,.3),orange,drone)
for a in [45,135,225,315]:
 r=math.radians(a);c,s=math.cos(r),math.sin(r);o=box('Arm',(.36*c,.36*s,.2),(.8,.08,.08),dk,drone);o.rotation_euler.z=r
 bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.25,depth=.025,location=(.72*c,.72*s,.3));o=bpy.context.object;o.parent=drone;o.data.materials.append(orange)
for o in orders:
 x,y=o['xy'];b=box('Depot' if not o['id'] else 'Pickup %02d'%o['id'],(x,y,1.2),(5,5,2),marker);b['order_id']=o['id']
def motion(o,rows):
 # Replay maps ten simulation seconds to one animation frame; retain subframes.
 prev=None
 for t,x,y,z in rows:
  fr=1+t/10;o.location=(x,y,z);o.keyframe_insert(data_path='location',frame=fr)
  if prev and math.hypot(x-prev[0],y-prev[1])>.1:
   ang=math.atan2(y-prev[1],x-prev[0]);o.rotation_euler.z=ang;o.keyframe_insert(data_path='rotation_euler',frame=fr)
  prev=x,y
 if o.animation_data:
  for c in o.animation_data.action.fcurves:
   for k in c.keyframe_points:k.interpolation='LINEAR'
motion(truck,run['truck']);motion(drone,run['drone'])
def line(n,rows,ma,r):
 cu=bpy.data.curves.new(n,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=1
 for pts in rows:
  if len(pts)<2:continue
  sp=cu.splines.new('POLY');sp.points.add(len(pts)-1)
  for a,p in zip(sp.points,pts):a.co=(*p,1)
 o=bpy.data.objects.new(n,cu);scene.collection.objects.link(o);cu.materials.append(ma)
line('Truck itinerary',[[[x,y,1.2] for _,x,y,z in run['truck']]],blue,1.7)
flights=[];rows=run['drone']
for a,b in zip(rows,rows[1:]):
 if max(a[3],b[3])>5:flights.append([a[1:],b[1:]])
line('UAV air corridors',flights,orange,1.5)
cam_data=bpy.data.cameras.new('Overview');cam=bpy.data.objects.new('Overview',cam_data);scene.collection.objects.link(cam);cam.location=(2650,-4800,3800);cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam_data.type='ORTHO';cam_data.ortho_scale=6400;cam_data.clip_end=18000;scene.camera=cam
bpy.ops.object.light_add(type='SUN',rotation=(.5,-.6,-.4));bpy.context.object.data.energy=3
scene.world=bpy.data.worlds.new('Daylight');scene.world.color=(.55,.59,.63)
scene.frame_end=math.ceil(run['summary']['minutes']*6)+1;scene.render.fps=12;scene.frame_set(1);scene.unit_settings.system='METRIC'
scene.render.engine='CYCLES';scene.cycles.samples=4;scene.cycles.use_denoising=False;scene.render.resolution_x=1350;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
for ar in bpy.context.screen.areas:
 if ar.type=='VIEW_3D':
  sp=ar.spaces.active;sp.clip_end=25000;sp.region_3d.view_distance=5400;sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.shading.color_type='MATERIAL'
for e in run['events']:
 if e[2]=='land_hold_pickup_by_truck':scene.timeline_markers.new('Ground hold | pickup '+str(e[1]),frame=round(1+e[0]/10))
scene['Source']='OSM contributors, ODbL. Local flat terrain, inferred heights distinguished by material. Synthetic operational conditions.'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'SZU_Yuehai.blend'))
scene.render.filepath=str(root/'overview.png');bpy.ops.render.render(write_still=True)
