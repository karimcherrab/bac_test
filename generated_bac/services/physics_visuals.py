"""Deterministic school-physics SVG: node circuits, force vectors and numeric plots."""
import math
from html import escape
from .math_visuals import expression, text, line as base_line, wrap

def line(x1,y1,x2,y2,color="#94a3b8",dash=False,arrow=False):
    result=base_line(x1,y1,x2,y2,color,dash,False)
    if arrow:
        angle=math.atan2(y2-y1,x2-x1)
        for side in (-1,1):
            a=angle+side*0.48
            result+=base_line(x2,y2,x2-11*math.cos(a),y2-11*math.sin(a),color)
    return result



def num(v):
    if isinstance(v,bool): raise ValueError('boolean coordinate')
    n=float(v)
    if not math.isfinite(n) or abs(n)>1e15: raise ValueError('invalid coordinate')
    return n


def label(x,y,s): return text(x,y,str(s)[:70],15)


def circuit(v):
    nodes={}
    for n in v['nodes']:
        if n['id'] in nodes: raise ValueError('duplicate node')
        x,y=num(n['x']),num(n['y'])
        if not (30<=x<=730 and 40<=y<=410): raise ValueError('node outside drawing')
        nodes[n['id']]=(x,y)
    components=v['components']
    if not 2<=len(nodes)<=30 or not 1<=len(components)<=40: raise ValueError('circuit size')
    # Check connectivity of the declared topology, not electrical solvability.
    adjacency={key:set() for key in nodes}
    wires={frozenset((c['from'],c['to'])) for c in components if c['kind']=='wire'}
    for c in components:
        a,b=c['from'],c['to']
        if a==b or a not in nodes or b not in nodes:raise ValueError('invalid component terminals')
        if c['kind']!='wire' and frozenset((a,b)) in wires:raise ValueError('wire shorts a component')
        adjacency[a].add(b);adjacency[b].add(a)
    visited=set();todo=[next(iter(nodes))]
    while todo:
        key=todo.pop()
        if key not in visited:visited.add(key);todo.extend(adjacency[key]-visited)
    if visited!=set(nodes):raise ValueError('disconnected circuit nodes')
    p=[]; seen=set()
    for c in components:
        if c['id'] in seen: raise ValueError('duplicate component')
        seen.add(c['id'])
        a,b=nodes[c['from']],nodes[c['to']]; dx,dy=b[0]-a[0],b[1]-a[1]
        length=math.hypot(dx,dy); angle=math.degrees(math.atan2(dy,dx)); kind=c['kind']
        if length<20: raise ValueError('component too short')
        if kind=='wire': p.append(line(*a,*b,'#334155'));continue
        if length<85: raise ValueError('leave at least 85px for component')
        mid=length/2; left,right=mid-28,mid+28
        part=[line(0,0,left,0,'#172033'),line(right,0,length,0,'#172033')]
        if kind=='resistor': part.append(f'<rect x="{left}" y="-10" width="56" height="20" fill="white" stroke="#172033" stroke-width="2"/>')
        elif kind=='capacitor':
            part=[line(0,0,mid-6,0),line(mid+6,0,length,0),line(mid-6,-22,mid-6,22,'#172033'),line(mid+6,-22,mid+6,22,'#172033')]
        elif kind=='inductor':
            d=f'M{left} 0'+''.join(' q7 -28 14 0' for _ in range(4))
            part.append(f'<path d="{d}" fill="none" stroke="#172033" stroke-width="2"/>')
        elif kind in ('source','ammeter','voltmeter'):
            part.append(f'<circle cx="{mid}" cy="0" r="28" fill="white" stroke="#172033" stroke-width="2"/>')
            if kind=='source': pass
            else: part.append(text(mid,6,'A' if kind=='ammeter' else 'V',20))
        elif kind=='switch':
            if c.get('state','closed') not in ('open','closed'): raise ValueError('switch state')
            part.append(line(left,0,right,-18 if c.get('state')=='open' else 0,'#172033'))
            for x in (left,right):part.append(f'<circle cx="{x}" cy="0" r="3" fill="white" stroke="#172033"/>')
        else: raise ValueError('unknown circuit symbol')
        p.append(f'<g transform="translate({a[0]} {a[1]}) rotate({angle})">'+''.join(part)+'</g>')
        if kind=='source':
            for offset,sign in [(-12,'+'),(12,'−')]:
                p.append(text(a[0]+(mid+offset)*dx/length,a[1]+(mid+offset)*dy/length+5,sign,15))
        # Horizontal text even for vertical components.
        mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2
        p.append(label(mx if abs(dx)>=abs(dy) else mx+48,my-36 if abs(dx)>=abs(dy) else my-8,c.get('label',c['id'])))
    for n in v['nodes']:
        x,y=nodes[n['id']];p.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#172033"/>')
        if n.get('label'): p.append(label(x+10,y-10,n['label']))
    return wrap(p,760,450)


def forces(v):
    p=[]; bodies={}
    for b in v.get('bodies',[]):
        x,y=num(b['x']),num(b['y']);r=num(b.get('radius',24))
        if b['id'] in bodies or not (50<=x<=710 and 50<=y<=400 and 5<=r<=60):raise ValueError('body geometry')
        bodies[b['id']]=(x,y)
        p.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#eff6ff" stroke="#2563eb" stroke-width="2"/>')
        p.append(label(x-r-18,y-8,b.get('label',b['id'])))
    if not bodies: raise ValueError('missing body')
    for s in v.get('surfaces',[]):
        coords=[num(s[k]) for k in ('x1','y1','x2','y2')]
        if any(t<10 or t>740 for t in coords):raise ValueError('surface geometry')
        p.append(line(*coords,'#64748b'))
    vectors=v.get('vectors',[])
    if not 1<=len(vectors)<=12: raise ValueError('missing or too many vectors')
    for q in vectors:
        x,y=bodies[q['body']];dx,dy=num(q['dx']),num(q['dy'])
        # Cartesian components: positive dy means upwards.
        ex,ey=x+dx,y-dy
        if not (25<=ex<=735 and 30<=ey<=415) or math.hypot(dx,dy)<15: raise ValueError('force outside frame or too short')
        p.append(line(x,y,ex,ey,'#172033',arrow=True))
        p.append(label(ex+(15 if dx>=0 else -15),ey-12,q['label']))
    return wrap(p,760,450)


def physics_graph(v):
    xmin,xmax=map(num,v['x_domain']);ymin,ymax=map(num,v['y_domain'])
    if xmax<=xmin or ymax<=ymin: raise ValueError('invalid axis range')
    X=lambda x:80+600*(x-xmin)/(xmax-xmin)
    Y=lambda y:370-310*(y-ymin)/(ymax-ymin)
    p=[]
    def ticks(lo,hi):
        raw=(hi-lo)/6; power=10**math.floor(math.log10(raw))
        step=next(k*power for k in (1,2,5,10) if k*power>=raw)
        return [i*step for i in range(math.ceil(lo/step),math.floor(hi/step)+1)]
    for x in ticks(xmin,xmax):
        p.extend([line(X(x),60,X(x),370,'#e2e8f0'),label(X(x),395,f'{x:.3g}')])
    for y in ticks(ymin,ymax):
        p.extend([line(80,Y(y),680,Y(y),'#e2e8f0'),label(42,Y(y)+4,f'{y:.3g}')])
    p.extend([line(80,370,700,370,'#172033',arrow=True),line(80,370,80,40,'#172033',arrow=True),label(630,435,v.get('x_label','t (s)')),label(150,22,v.get('y_label','y'))])
    series=v['series']
    if not 1<=len(series)<=5:raise ValueError('series count')
    for i,s in enumerate(series):
        if s.get('expression'):
            fn=expression(s['expression']); points=[]
            for j in range(801):
                x=xmin+(xmax-xmin)*j/800
                try:y=fn(x)
                except (ValueError,OverflowError,ZeroDivisionError):y=float('nan')
                points.append({'x':x,'y':y})
        else:
            points=s.get('data',[])
            if not 2<=len(points)<=1000:raise ValueError('missing graph data')
            points=[{'x':num(q['x']),'y':num(q['y'])} for q in points]
            if any(points[j]['x']>=points[j+1]['x'] for j in range(len(points)-1)):raise ValueError('x data must increase')
        path=[];prev=False; visible=0
        for q in points:
            x,y=q['x'],q['y']
            if not math.isfinite(y) or not xmin<=x<=xmax or not ymin<=y<=ymax:prev=False;continue
            path.append(f'{"L" if prev else "M"}{X(x):.2f},{Y(y):.2f}');prev=True;visible+=1
        if visible<2:raise ValueError('no visible data')
        color=['#2563eb','#dc2626','#059669','#9333ea','#d97706'][i]
        p.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2"/>')
        p.append(label(300+i*90,22,s.get('label',f's{i+1}')))
    return wrap(p,760,450)


def render(v):
    return {'circuit':circuit,'forces':forces,'physics_graph':physics_graph}[v['type']](v)
