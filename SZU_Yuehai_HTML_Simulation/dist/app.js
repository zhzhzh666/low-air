const CASE_META = {
  truck: { label: "纯卡车", row: "纯卡车" },
  normal: { label: "常规风况 · 逐站分配", row: "常规风况，逐站分配" },
  gust: { label: "突发强风 · 逐站分配", row: "突发强风，逐站分配" },
  gust_milp: { label: "突发强风 · 滚动整数规划", row: "突发强风，滚动整数规划" }
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const canvas = $("#map-canvas");
const gl = canvas.getContext("webgl", { antialias: false, alpha: false, depth: true, powerPreference: "default" });

const state = {
  map: null, orders: [], cases: {}, currentCase: "gust", time: 0,
  playing: true, suspended: false, speed: 180, loopCount: 0,
  lastFrame: performance.now(), lastRender: 0, lastUiUpdate: 0,
  geometry: {}, routeBuffers: {}, camera: { yaw: .57, pitch: .72, distance: 5600, target: [0, 0, 0], follow: false },
  pointer: { active: false, x: 0, y: 0 }
};

if (!gl) {
  $("#event-toast strong").textContent = "当前浏览器未启用 WebGL，无法显示三维场景。";
  throw new Error("WebGL unavailable");
}

const VERTEX_SHADER = `
attribute vec3 a_position;
attribute vec3 a_normal;
uniform mat4 u_model;
uniform mat4 u_viewProjection;
uniform vec3 u_camera;
varying vec3 v_normal;
varying float v_distance;
void main() {
  vec4 world = u_model * vec4(a_position, 1.0);
  v_normal = mat3(u_model) * a_normal;
  v_distance = distance(world.xyz, u_camera);
  gl_Position = u_viewProjection * world;
}`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform vec4 u_color;
uniform float u_unlit;
uniform vec3 u_fogColor;
varying vec3 v_normal;
varying float v_distance;
void main() {
  vec3 normal = normalize(v_normal);
  vec3 lightDir = normalize(vec3(-0.35, 0.82, 0.42));
  float diffuse = max(dot(normal, lightDir), 0.0);
  float lighting = mix(0.58 + diffuse * 0.42, 1.0, u_unlit);
  vec3 rgb = u_color.rgb * lighting;
  float fog = smoothstep(4300.0, 9000.0, v_distance);
  gl_FragColor = vec4(mix(rgb, u_fogColor, fog), u_color.a);
}`;

function compileShader(type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source); gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}

function createProgram() {
  const p = gl.createProgram();
  gl.attachShader(p, compileShader(gl.VERTEX_SHADER, VERTEX_SHADER));
  gl.attachShader(p, compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}

const program = createProgram();
const loc = {
  position: gl.getAttribLocation(program, "a_position"), normal: gl.getAttribLocation(program, "a_normal"),
  model: gl.getUniformLocation(program, "u_model"), viewProjection: gl.getUniformLocation(program, "u_viewProjection"),
  camera: gl.getUniformLocation(program, "u_camera"), color: gl.getUniformLocation(program, "u_color"),
  unlit: gl.getUniformLocation(program, "u_unlit"), fogColor: gl.getUniformLocation(program, "u_fogColor")
};

function identity() { return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]); }
function multiply(a,b) { const o=new Float32Array(16); for(let c=0;c<4;c++)for(let r=0;r<4;r++)o[c*4+r]=a[r]*b[c*4]+a[4+r]*b[c*4+1]+a[8+r]*b[c*4+2]+a[12+r]*b[c*4+3]; return o; }
function perspective(fov,aspect,near,far) { const f=1/Math.tan(fov/2),nf=1/(near-far); return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0]); }
function normalize(v) { const l=Math.hypot(v[0],v[1],v[2])||1; return [v[0]/l,v[1]/l,v[2]/l]; }
function cross(a,b) { return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]; }
function subtract(a,b) { return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]; }
function lookAt(eye,target,up) { const z=normalize(subtract(eye,target)),x=normalize(cross(up,z)),y=cross(z,x); return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-(x[0]*eye[0]+x[1]*eye[1]+x[2]*eye[2]),-(y[0]*eye[0]+y[1]*eye[1]+y[2]*eye[2]),-(z[0]*eye[0]+z[1]*eye[1]+z[2]*eye[2]),1]); }
function modelMatrix(position=[0,0,0],scale=[1,1,1],yaw=0) { const c=Math.cos(yaw),s=Math.sin(yaw); return new Float32Array([c*scale[0],0,-s*scale[0],0,0,scale[1],0,0,s*scale[2],0,c*scale[2],0,position[0],position[1],position[2],1]); }
function worldPoint(x,y,z=0) { return [x,z,-y]; }

function addTriangle(target,a,b,c,normal) { target.vertices.push(...a,...b,...c); target.normals.push(...normal,...normal,...normal); }
function polygonTop(target,points,height) { if(!points||points.length<3)return; const center=points.reduce((a,p)=>[a[0]+p[0],a[1]+p[1]],[0,0]).map(v=>v/points.length),c=worldPoint(center[0],center[1],height); for(let i=0;i<points.length;i++){const a=worldPoint(points[i][0],points[i][1],height),b=worldPoint(points[(i+1)%points.length][0],points[(i+1)%points.length][1],height);addTriangle(target,c,b,a,[0,1,0]);} }
function extrudePolygon(target,points,height,base=.35) { polygonTop(target,points,height); for(let i=0;i<points.length;i++){const p=points[i],q=points[(i+1)%points.length],a=worldPoint(p[0],p[1],base),b=worldPoint(q[0],q[1],base),c=worldPoint(q[0],q[1],height),d=worldPoint(p[0],p[1],height),n=normalize(cross(subtract(b,a),subtract(d,a)));addTriangle(target,a,b,c,n);addTriangle(target,a,c,d,n);} }
function roadQuad(target,p,q,width) { const dx=q[0]-p[0],dy=q[1]-p[1],len=Math.hypot(dx,dy);if(!len)return;const ox=-dy/len*width/2,oy=dx/len*width/2,a=worldPoint(p[0]+ox,p[1]+oy,.42),b=worldPoint(p[0]-ox,p[1]-oy,.42),c=worldPoint(q[0]-ox,q[1]-oy,.42),d=worldPoint(q[0]+ox,q[1]+oy,.42);addTriangle(target,a,b,c,[0,1,0]);addTriangle(target,a,c,d,[0,1,0]); }

function createBufferGeometry(vertices,normals,mode=gl.TRIANGLES,dynamic=false) { const g={mode,count:vertices.length/3,position:gl.createBuffer(),normal:gl.createBuffer()};gl.bindBuffer(gl.ARRAY_BUFFER,g.position);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),dynamic?gl.DYNAMIC_DRAW:gl.STATIC_DRAW);gl.bindBuffer(gl.ARRAY_BUFFER,g.normal);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(normals),dynamic?gl.DYNAMIC_DRAW:gl.STATIC_DRAW);return g; }
function updateGeometry(g,vertices) { g.count=vertices.length/3;const normals=new Float32Array(vertices.length);for(let i=1;i<normals.length;i+=3)normals[i]=1;gl.bindBuffer(gl.ARRAY_BUFFER,g.position);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.DYNAMIC_DRAW);gl.bindBuffer(gl.ARRAY_BUFFER,g.normal);gl.bufferData(gl.ARRAY_BUFFER,normals,gl.DYNAMIC_DRAW); }
function cubeGeometry() { const t={vertices:[],normals:[]},f=[[[ -1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],[0,0,1]],[[1,-1,-1],[-1,-1,-1],[-1,1,-1],[1,1,-1],[0,0,-1]],[[-1,1,1],[1,1,1],[1,1,-1],[-1,1,-1],[0,1,0]],[[-1,-1,-1],[1,-1,-1],[1,-1,1],[-1,-1,1],[0,-1,0]],[[1,-1,1],[1,-1,-1],[1,1,-1],[1,1,1],[1,0,0]],[[-1,-1,-1],[-1,-1,1],[-1,1,1],[-1,1,-1],[-1,0,0]]];f.forEach(([a,b,c,d,n])=>{addTriangle(t,a,b,c,n);addTriangle(t,a,c,d,n);});return createBufferGeometry(t.vertices,t.normals); }

function buildSceneGeometry() {
  const known={vertices:[],normals:[]},estimated={vertices:[],normals:[]},road={vertices:[],normals:[]},green={vertices:[],normals:[]},water={vertices:[],normals:[]};
  state.map.buildings.forEach(b=>extrudePolygon(b[2]==="type estimate"?estimated:known,b[0],Math.max(3,Number(b[1])||10)));
  state.map.land.forEach(([poly,type])=>polygonTop(type==="water"?water:green,poly,type==="water"?.12:.2));
  const widths={service:4,residential:6,primary:12,secondary:10,trunk:13,motorway:14};
  state.map.roads.forEach(([ids,cls])=>{for(let i=1;i<ids.length;i++){const p=state.map.nodes[ids[i-1]],q=state.map.nodes[ids[i]];if(p&&q)roadQuad(road,p,q,widths[cls]||6);}});
  const ground={vertices:[],normals:[]};polygonTop(ground,[[-2100,-2040],[2100,-2040],[2100,2040],[-2100,2040]],0);
  state.geometry.ground=createBufferGeometry(ground.vertices,ground.normals);state.geometry.green=createBufferGeometry(green.vertices,green.normals);state.geometry.water=createBufferGeometry(water.vertices,water.normals);state.geometry.roads=createBufferGeometry(road.vertices,road.normals);state.geometry.estimated=createBufferGeometry(estimated.vertices,estimated.normals);state.geometry.known=createBufferGeometry(known.vertices,known.normals);state.geometry.cube=cubeGeometry();
}

function bindGeometry(g) { gl.bindBuffer(gl.ARRAY_BUFFER,g.position);gl.enableVertexAttribArray(loc.position);gl.vertexAttribPointer(loc.position,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ARRAY_BUFFER,g.normal);gl.enableVertexAttribArray(loc.normal);gl.vertexAttribPointer(loc.normal,3,gl.FLOAT,false,0,0); }
function drawGeometry(g,color,model=identity(),unlit=0) { if(!g?.count)return;bindGeometry(g);gl.uniformMatrix4fv(loc.model,false,model);gl.uniform4fv(loc.color,color);gl.uniform1f(loc.unlit,unlit);gl.drawArrays(g.mode,0,g.count); }
async function loadJSON(path) { const r=await fetch(path);if(!r.ok)throw new Error(`${path}: ${r.status}`);return r.json(); }
function fmtClock(seconds,compact=false) { const s=Math.max(0,Math.floor(seconds)),h=Math.floor(s/3600),m=Math.floor((s%3600)/60),r=s%60;return compact&&h===0?`${String(m).padStart(2,"0")}:${String(r).padStart(2,"0")}`:`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(r).padStart(2,"0")}`; }
function lerp(a,b,t){return a+(b-a)*t;}
function sampleTrack(track,time){if(!track?.length)return[time,0,0,0];if(time<=track[0][0])return track[0];if(time>=track.at(-1)[0])return track.at(-1);let lo=0,hi=track.length-1;while(lo+1<hi){const mid=(lo+hi)>>1;if(track[mid][0]<=time)lo=mid;else hi=mid;}const a=track[lo],b=track[hi],p=(time-a[0])/Math.max(.001,b[0]-a[0]);return[time,lerp(a[1],b[1],p),lerp(a[2],b[2],p),lerp(a[3]||0,b[3]||0,p)];}
function sampleBattery(track,time){if(!track?.length)return 756;if(time<=track[0][0])return track[0][1];if(time>=track.at(-1)[0])return track.at(-1)[1];let i=1;while(i<track.length&&track[i][0]<time)i++;const a=track[i-1],b=track[i];return lerp(a[1],b[1],(time-a[0])/Math.max(.001,b[0]-a[0]));}
function trackYaw(track,time){if(!track?.length)return 0;let i=1;while(i<track.length&&track[i][0]<time)i++;const a=track[Math.max(0,i-1)],b=track[Math.min(track.length-1,i)];return Math.atan2(-(b[2]-a[2]),b[1]-a[1]);}

function makeRouteGeometry(track,isDrone=false){const vertices=[],normals=[];track.forEach(p=>{vertices.push(...worldPoint(p[1],p[2],isDrone?Math.max(2,p[3]):1.1));normals.push(0,1,0);});const geometry=createBufferGeometry(vertices,normals,gl.LINE_STRIP,false);geometry.times=track.map(p=>p[0]);geometry.fullCount=geometry.count;return geometry;}
function buildRouteBuffers(){Object.entries(state.cases).forEach(([name,result])=>{state.routeBuffers[name]={truck:makeRouteGeometry(result.truck,false),drone:makeRouteGeometry(result.drone,true)};});}
function setVisibleRoute(geometry,time){const times=geometry.times;if(!times.length){geometry.count=0;return;}let lo=0,hi=times.length;while(lo<hi){const mid=(lo+hi)>>1;if(times[mid]<=time)lo=mid+1;else hi=mid;}geometry.count=Math.max(1,Math.min(geometry.fullCount,lo));}
function resizeCanvas(){const r=canvas.getBoundingClientRect(),dpr=1,w=Math.max(1,Math.round(r.width*dpr)),h=Math.max(1,Math.round(r.height*dpr));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}}
function drawTruck(p,yaw){drawGeometry(state.geometry.cube,[.98,.39,.11,1],modelMatrix([p[0],p[1]+2.1,p[2]],[4.5,1.25,1.25],yaw),1);const o=[Math.cos(yaw)*3.8,0,-Math.sin(yaw)*3.8];drawGeometry(state.geometry.cube,[1,.55,.18,1],modelMatrix([p[0]+o[0],p[1]+1.7,p[2]+o[2]],[1.5,1.65,1.2],yaw),1);}
function drawDrone(p,yaw){drawGeometry(state.geometry.cube,[.15,.82,1,1],modelMatrix([p[0],p[1]+1.2,p[2]],[1.7,.45,1.15],yaw),1);drawGeometry(state.geometry.cube,[.7,.93,1,1],modelMatrix([p[0],p[1]+1.25,p[2]],[3.1,.10,.13],yaw+.785),1);drawGeometry(state.geometry.cube,[.7,.93,1,1],modelMatrix([p[0],p[1]+1.25,p[2]],[3.1,.10,.13],yaw-.785),1);}
function cameraEye(){const c=state.camera,h=c.distance*Math.cos(c.pitch);return[c.target[0]+h*Math.sin(c.yaw),c.target[1]+c.distance*Math.sin(c.pitch),c.target[2]+h*Math.cos(c.yaw)];}

function render3D(){
  if(!state.map)return;resizeCanvas();const result=state.cases[state.currentCase],truck=sampleTrack(result.truck,state.time),drone=sampleTrack(result.drone,state.time),tw=worldPoint(truck[1],truck[2],0),dw=worldPoint(drone[1],drone[2],Math.max(2,drone[3]));
  if(state.camera.follow){state.camera.target[0]+=(tw[0]-state.camera.target[0])*.05;state.camera.target[2]+=(tw[2]-state.camera.target[2])*.05;state.camera.target[1]+=(18-state.camera.target[1])*.05;}
  const eye=cameraEye(),vp=multiply(perspective(Math.PI/4,canvas.width/canvas.height,2,15000),lookAt(eye,state.camera.target,[0,1,0]));
  gl.enable(gl.DEPTH_TEST);gl.disable(gl.BLEND);gl.clearColor(.027,.063,.09,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);gl.uniformMatrix4fv(loc.viewProjection,false,vp);gl.uniform3fv(loc.camera,eye);gl.uniform3fv(loc.fogColor,[.027,.063,.09]);
  drawGeometry(state.geometry.ground,[.055,.105,.12,1]);drawGeometry(state.geometry.green,[.14,.28,.18,1]);drawGeometry(state.geometry.water,[.08,.28,.38,1]);drawGeometry(state.geometry.roads,[.31,.36,.38,1]);drawGeometry(state.geometry.estimated,[.31,.43,.46,1]);drawGeometry(state.geometry.known,[.56,.59,.52,1]);
  const routes=state.routeBuffers[state.currentCase];setVisibleRoute(routes.truck,state.time);setVisibleRoute(routes.drone,state.time);gl.disable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);drawGeometry(routes.truck,[1,.42,.13,.95],identity(),1);if(state.currentCase!=="truck")drawGeometry(routes.drone,[.15,.82,1,.95],identity(),1);gl.disable(gl.BLEND);gl.enable(gl.DEPTH_TEST);drawTruck(tw,trackYaw(result.truck,state.time));if(state.currentCase!=="truck")drawDrone(dw,trackYaw(result.drone,state.time));
}

function latestAudit(result,time){let v=null;result.audit.forEach(x=>{if(x.t_s<=time)v=x;});return v;}
function latestEvent(result,time){let v=null;result.events.forEach(x=>{if(x[0]<=time)v=x;});return v;}
function latestWeather(result,time){let v=null;(result.weather_observations||[]).forEach(x=>{if(x.t_s<=time)v=x;});return v;}
const decisionText={launch:["任务通过起飞筛选","五个预测情景满足载荷、建筑净空、14 m/s 风速上限和完整任务电量约束。"],return_energy:["电量裕度不足，交给卡车","扣除 20% 安全电量后，剩余电量不足以覆盖完整任务。"],distance_reserve:["安全航程不足，交给卡车","最坏地速下的起飞点、客户点和回收点总距离超过当前安全距离上限。"],wind_threshold_truck:["风速达到纯卡车阈值","本节点仅执行卡车任务。"],truck_faster:["卡车直接服务更快","候选飞行可行，但并行方案没有缩短当前计划时间。"],milp_ground:["滚动规划选择卡车","当前窗口内由卡车服务的综合成本更低。"],ground:["卡车执行当前订单","本路段未分配无人机任务。"],weather_or_clearance:["天气或净空条件拒绝","至少一个预测风况或建筑净空条件不满足。"],launch_unavailable:["起飞检查未通过","执行时的风况或净空不满足起飞要求。"]};

function updateUI(force=false){
  const now=performance.now();if(!force&&now-state.lastUiUpdate<120)return;state.lastUiUpdate=now;
  const result=state.cases[state.currentCase],params=result.config_snapshot||{battery_Wh:756,reserve_Wh:151.2},duration=result.truck.at(-1)[0],battery=sampleBattery(result.battery,state.time);
  let dist=0,prev=result.truck[0];for(const p of result.truck){if(p[0]>state.time)break;dist+=Math.hypot(p[1]-prev[1],p[2]-prev[2]);prev=p;}
  const audit=latestAudit(result,state.time),event=latestEvent(result,state.time),weather=latestWeather(result,state.time)||{speed_mps:0,direction:"静风",weather_class:"normal"},copy=decisionText[audit?.decision||"ground"]||decisionText.ground;
  const modeLabel={normal:"常规风况",gust:"突发强风",truck_only:"纯卡车"}[weather.weather_class]||weather.weather_class;
  const swapCount=(result.battery_swaps||[]).filter(x=>x.t_s<=state.time).length;
  $("#sim-clock").textContent=`T+${fmtClock(state.time)}`;$("#battery-value").textContent=battery.toFixed(2);$("#available-value").textContent=`${Math.max(0,battery-params.reserve_Wh).toFixed(2)} Wh`;$("#battery-fill").style.width=`${Math.max(0,Math.min(100,battery/params.battery_Wh*100))}%`;$("#wind-value").textContent=Number(weather.speed_mps).toFixed(2);$("#wind-direction").textContent=weather.direction;$("#distance-value").textContent=(dist/1000).toFixed(2);$("#swap-value").textContent=String(swapCount);$("#timeline").value=Math.round(state.time/Math.max(1,duration)*1000);$("#timeline-current").textContent=fmtClock(state.time,true);$("#timeline-total").textContent=fmtClock(duration,true);$("#case-label").textContent=`${CASE_META[state.currentCase].label} · ${modeLabel}`;$("#decision-title").textContent=copy[0];
  if(audit){const forecast=audit.max_forecast_Wh==null?"当前没有完整可行的无人机任务":`五情景最高预测耗电 ${audit.max_forecast_Wh.toFixed(2)} Wh`;$("#decision-detail").textContent=`订单 ${audit.customer}：${audit.observed_wind_direction}风 ${audit.observed_wind_mps.toFixed(2)} m/s，安全距离 ${audit.safe_distance_budget_m.toFixed(0)} m，${forecast}。${copy[1]}`;}else $("#decision-detail").textContent=copy[1];
  let eventCopy="卡车到达节点后重新观测天气并更新调度";if(event){const labels={sortie:`订单 ${event[1]}：无人机起飞执行取件`,truck_faster:`订单 ${event[1]}：卡车直接服务更快`,land_hold_pickup_by_truck:`订单 ${event[1]}：强风超限，无人机落地等待卡车接回`,distance_reserve:`订单 ${event[1]}：安全距离不足，改由卡车`,wind_threshold_truck:`节点 ${event[1]}：风速达到纯卡车阈值`,battery_swap:`节点 ${event[1]}：电量达到 20% 阈值，完成换电`,ground:`订单 ${event[1]}：由卡车完成取件`};eventCopy=labels[event[2]]||`订单 ${event[1]}：${event[2]}`;}$("#event-toast strong").textContent=eventCopy;
}

function resetCamera(){Object.assign(state.camera,{yaw:.57,pitch:.72,distance:5600,target:[0,0,0],follow:false});$("#view-follow").setAttribute("aria-pressed","false");}
function setCase(name,keep=false){const old=state.cases[state.currentCase],ratio=old?state.time/old.truck.at(-1)[0]:0;state.currentCase=name;state.time=keep?ratio*state.cases[name].truck.at(-1)[0]:0;$$('.case-switch button').forEach(b=>b.classList.toggle('active',b.dataset.case===name));updateUI(true);}
function jumpTo(time,caseName="gust"){if(state.currentCase!==caseName)setCase(caseName);state.time=Math.min(time,state.cases[caseName].truck.at(-1)[0]);state.playing=false;$("#play-button").innerHTML="<span>▶</span> 播放";updateUI(true);document.querySelector('.sim-shell').scrollIntoView({behavior:'smooth',block:'start'});}
function renderStoryJumps(){const gustObs=(state.cases.gust.weather_observations||[]).find(x=>x.weather_class==='gust')||state.cases.gust.weather_observations?.[0];const swapCase=Object.keys(state.cases).find(k=>state.cases[k].battery_swaps?.length);const weatherButton=$("#jump-weather"),swapButton=$("#jump-swap");weatherButton.dataset.time=String(gustObs?.t_s||0);weatherButton.dataset.case="gust";weatherButton.querySelector('strong').textContent=gustObs?`${gustObs.direction}风 ${gustObs.speed_mps.toFixed(2)} m/s · ${gustObs.weather_class==='gust'?'突发强风':'常规风况'}`:"逐节点天气重判";weatherButton.querySelector('small').textContent=`跳转至 T+${fmtClock(gustObs?.t_s||0)}`;if(swapCase){const swap=state.cases[swapCase].battery_swaps[0];swapButton.dataset.time=String(swap.t_s);swapButton.dataset.case=swapCase;swapButton.querySelector('strong').textContent=`电量 ${swap.before_Wh.toFixed(2)} Wh · 节点换电`;swapButton.querySelector('small').textContent=`跳转至 T+${fmtClock(swap.t_s)}`;}else{const low=state.cases.gust.battery.reduce((a,b)=>b[1]<a[1]?b:a);swapButton.dataset.time=String(low[0]);swapButton.dataset.case="gust";swapButton.querySelector('strong').textContent="当前算例未触发换电";swapButton.querySelector('small').textContent=`最低电量 ${low[1].toFixed(2)} Wh，规则仍保持启用`;}}
function renderTable(){const body=$("#results-body");body.innerHTML=Object.entries(CASE_META).map(([key,meta])=>{const s=state.cases[key].summary;return `<tr class="${key==='gust_milp'?'highlight':''}"><td>${meta.row}</td><td>${s.drone_collections} 单</td><td>${s.truck_km.toFixed(2)} km</td><td>${s.minutes.toFixed(2)} min</td><td>${Number(s.energy_Wh).toFixed(2)} Wh</td><td>${s.ground_recoveries} 次</td><td>${s.battery_swaps} 次</td></tr>`;}).join('');const g=state.cases.gust.summary,m=state.cases.gust_milp.summary,dO=m.drone_collections-g.drone_collections,dK=g.truck_km-m.truck_km,dM=g.minutes-m.minutes,dW=m.energy_Wh-g.energy_Wh;$("#comparison-copy").textContent=`滚动规划${dO<0?`少派 ${Math.abs(dO)} 单无人机`:`多派 ${dO} 单无人机`}，卡车少走 ${dK.toFixed(2)} km，总作业时间缩短 ${dM.toFixed(2)} min，无人机耗电${dW>=0?'增加':'减少'} ${Math.abs(dW).toFixed(2)} Wh。`;}

function bindControls(){
  $$('.case-switch button').forEach(b=>b.addEventListener('click',()=>setCase(b.dataset.case,true)));$("#play-button").addEventListener('click',()=>{state.playing=!state.playing;$("#play-button").innerHTML=state.playing?"<span>Ⅱ</span> 暂停":"<span>▶</span> 播放";});$("#speed-select").addEventListener('change',e=>state.speed=Number(e.target.value));$("#timeline").addEventListener('input',e=>{const r=state.cases[state.currentCase];state.time=Number(e.target.value)/1000*r.truck.at(-1)[0];updateUI(true);});[$("#jump-weather"),$("#jump-swap")].forEach(b=>b.addEventListener('click',()=>jumpTo(Number(b.dataset.time||0),b.dataset.case||"gust")));$("#view-reset").addEventListener('click',resetCamera);$("#view-follow").addEventListener('click',()=>{state.camera.follow=!state.camera.follow;state.camera.distance=state.camera.follow ? 1250 : 5600;state.camera.pitch=state.camera.follow ? .46 : .72;$("#view-follow").setAttribute('aria-pressed',String(state.camera.follow));});
  canvas.addEventListener('pointerdown',e=>{state.pointer={active:true,x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);state.camera.follow=false;$("#view-follow").setAttribute('aria-pressed','false');});canvas.addEventListener('pointermove',e=>{if(!state.pointer.active)return;const dx=e.clientX-state.pointer.x,dy=e.clientY-state.pointer.y;state.pointer.x=e.clientX;state.pointer.y=e.clientY;state.camera.yaw-=dx*.006;state.camera.pitch=Math.max(.12,Math.min(1.38,state.camera.pitch+dy*.005));});canvas.addEventListener('pointerup',()=>state.pointer.active=false);canvas.addEventListener('pointercancel',()=>state.pointer.active=false);canvas.addEventListener('wheel',e=>{e.preventDefault();state.camera.distance=Math.max(420,Math.min(9000,state.camera.distance*Math.exp(e.deltaY*.001)));},{passive:false});canvas.addEventListener('dblclick',resetCamera);window.addEventListener('resize',resizeCanvas);
  document.addEventListener('visibilitychange',()=>{state.suspended=document.hidden;state.lastFrame=performance.now();});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();state.suspended=true;state.playing=false;$("#event-toast strong").textContent="三维显卡上下文已释放，请刷新当前页面恢复仿真。";});
}

function animate(now){requestAnimationFrame(animate);if(state.suspended||now-state.lastRender<40)return;const dt=Math.min(.12,(now-state.lastFrame)/1000);state.lastFrame=now;state.lastRender=now;const result=state.cases[state.currentCase];if(state.playing&&result){const duration=Math.max(1,result.truck.at(-1)[0]),next=state.time+dt*state.speed;if(next>=duration){state.loopCount+=Math.floor(next/duration);document.documentElement.dataset.loopCount=String(state.loopCount);}state.time=next%duration;}render3D();updateUI();}
async function init(){try{$("#event-toast strong").textContent="正在生成 2,106 栋建筑与道路三维网格…";const [map,orders,truck,normal,gust,milp]=await Promise.all([loadJSON('data/map.json'),loadJSON('data/orders.json'),loadJSON('results/truck.json'),loadJSON('results/normal.json'),loadJSON('results/gust.json'),loadJSON('results/gust_milp.json')]);state.map=map;state.orders=orders;state.cases={truck,normal,gust,gust_milp:milp};const qaSpeed=Number(new URLSearchParams(location.search).get('speed'));if(Number.isFinite(qaSpeed)&&qaSpeed>0)state.speed=qaSpeed;buildSceneGeometry();buildRouteBuffers();bindControls();renderTable();renderStoryJumps();updateUI(true);requestAnimationFrame(animate);}catch(error){console.error(error);$("#event-toast strong").textContent=`三维场景加载失败：${error.message}`;}}
init();
