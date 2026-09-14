"""Small deterministic SVG renderer. No eval, sympify, HTML or model SVG."""
import ast
import math
from html import escape
from .exceptions import AIResponseError


def number(x):
    if isinstance(x, bool):
        raise ValueError('boolean coordinate')
    x = float(x)
    if not math.isfinite(x) or abs(x) > 1e6:
        raise ValueError('coordinate out of range')
    return x


def expression(source):
    source = str(source).replace('^', '**')
    if len(source) > 240:
        raise ValueError('expression too long')
    tree = ast.parse(source, mode='eval').body
    functions = {'exp': math.exp, 'ln': math.log, 'log': math.log,
                 'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'abs': abs}
    def check(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            number(n.value)
        elif isinstance(n, ast.Name) and n.id in ('x', 'e', 'pi'):
            pass
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            check(n.operand)
        elif isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            check(n.left); check(n.right)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in functions and len(n.args) == 1 and not n.keywords:
            check(n.args[0])
        else:
            raise ValueError('unsupported expression')
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError('expression too complex')
    check(tree)
    def run(n, x):
        if isinstance(n, ast.Constant): return float(n.value)
        if isinstance(n, ast.Name): return {'x': x, 'e': math.e, 'pi': math.pi}[n.id]
        if isinstance(n, ast.UnaryOp): return (-1 if isinstance(n.op, ast.USub) else 1)*run(n.operand, x)
        if isinstance(n, ast.Call): return functions[n.func.id](run(n.args[0], x))
        a, b = run(n.left, x), run(n.right, x)
        if isinstance(n.op, ast.Add): return a+b
        if isinstance(n.op, ast.Sub): return a-b
        if isinstance(n.op, ast.Mult): return a*b
        if isinstance(n.op, ast.Div): return a/b
        if abs(b) > 100: raise ValueError('exponent too large')
        return math.pow(a, b)
    return lambda x: run(tree, x)


def text(x, y, value, size=16):
    return f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Arial, sans-serif" font-size="{size}" fill="#172033">{escape(str(value))}</text>'


def line(x1, y1, x2, y2, color='#94a3b8', dash=False, arrow=False):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5"'+(' stroke-dasharray="6 5"' if dash else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>'


def wrap(parts, width, height):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="#172033"/></marker></defs><rect width="100%" height="100%" fill="white"/>'+''.join(parts)+'</svg>'


def graph(v):
    xmin, xmax = map(number, v['x_domain']); ymin, ymax = map(number, v['y_domain'])
    if not (1 <= xmax-xmin <= 60 and 1 <= ymax-ymin <= 60):
        raise ValueError('graph spans must be between 1 and 60')
    scale = min(640/(xmax-xmin), 540/(ymax-ymin))
    w, h = round((xmax-xmin)*scale+100), round((ymax-ymin)*scale+100)
    X = lambda x: 50+(x-xmin)*scale
    Y = lambda y: 50+(ymax-y)*scale
    p=[]
    for x in range(math.ceil(xmin), math.floor(xmax)+1):
        p.append(line(X(x),50,X(x),h-50,'#e2e8f0'))
        p.append(text(X(x),h-27,x,12))
    for y in range(math.ceil(ymin), math.floor(ymax)+1):
        p.append(line(50,Y(y),w-50,Y(y),'#e2e8f0'))
        p.append(text(27,Y(y)+4,y,12))
    if ymin <= 0 <= ymax: p.append(line(50,Y(0),w-45,Y(0),'#172033',arrow=True))
    if xmin <= 0 <= xmax: p.append(line(X(0),h-50,X(0),45,'#172033',arrow=True))
    p.extend([text(w-30,Y(0) if ymin <= 0 <= ymax else h-30,'x'),text(X(0) if xmin <= 0 <= xmax else 30,30,'y')])
    for a in v.get('asymptotes', [])[:8]:
        val=number(a['value'])
        if a['axis']=='x' and xmin <= val <= xmax: p.append(line(X(val),50,X(val),h-50,'#d97706',True))
        if a['axis']=='y' and ymin <= val <= ymax: p.append(line(50,Y(val),w-50,Y(val),'#d97706',True))
    series=v.get('series', [])
    if not isinstance(series,list) or not 1 <= len(series) <= 4: raise ValueError('missing series')
    for i,s in enumerate(series):
        fn=expression(s['expression']); excluded=sorted(number(t) for t in s.get('exclude',[]))
        path=[]; prev=None; visible=0
        for j in range(1601):
            x=xmin+(xmax-xmin)*j/1600
            try:
                y=fn(x)
                valid=math.isfinite(y) and ymin <= y <= ymax and all(abs(x-a)>1e-9 for a in excluded)
            except (ValueError, OverflowError, ZeroDivisionError, TypeError): valid=False
            if not valid: prev=None; continue
            connected=prev is not None and abs(y-prev[1])*scale < 100 and not any(prev[0] <= a <= x for a in excluded)
            path.append(f'{"L" if connected else "M"}{X(x):.2f},{Y(y):.2f}')
            prev=(x,y); visible+=1
        if visible < 2: raise ValueError('no visible curve; adjust domains')
        color=['#2563eb','#dc2626','#059669','#9333ea'][i]
        p.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        p.append(text(90+i*150,18,s.get('label',f'C{i+1}'),13))
    return wrap(p,w,h)


def variation(v):
    xs=v['x_values']; intervals=v['intervals']
    if not isinstance(xs,list) or not 2 <= len(xs) <= 12 or len(intervals)!=len(xs)-1:
        raise ValueError('variation dimensions')
    w=140+180*len(intervals); h=270; p=[]
    p.extend([line(20,35,w-20,35),line(20,90,w-20,90),line(20,145,w-20,145),line(20,250,w-20,250),line(95,35,95,250)])
    p.extend([text(55,70,'x'),text(55,125,v.get('derivative_label',"f′(x)")),text(55,205,v.get('function_label','f(x)'))])
    def pos(i): return 120+180*i
    for i,x in enumerate(xs):
        p.append(text(pos(i),70,x))
        if i in v.get('undefined_indices',[]):
            p.append(line(pos(i)-3,90,pos(i)-3,250,'#172033'))
            p.append(line(pos(i)+3,90,pos(i)+3,250,'#172033'))
        elif 0<i<len(xs)-1:
            p.append(line(pos(i),90,pos(i),250,'#cbd5e1',True))
            p.append(text(pos(i),125,v.get('critical_signs',{}).get(str(i),'0')))
    for i,entry in enumerate(intervals):
        sign=entry['sign']; trend=entry['trend']
        if sign not in ('+','-','0') or trend not in ('up','down','constant'):
            raise ValueError('invalid signs or arrows')
        if {'+':'up','-':'down','0':'constant'}[sign]!=trend: raise ValueError('sign contradicts arrow')
        a,b=(229,169) if trend=='up' else (169,229) if trend=='down' else (200,200)
        p.extend([text((pos(i)+pos(i+1))/2,125,sign),text(pos(i)+27,a,entry['left'],14),text(pos(i+1)-27,b,entry['right'],14),line(pos(i)+55,a-5,pos(i+1)-55,b-5,'#172033',arrow=trend!='constant')])
    return wrap(p,w,h)


def render_visuals(value):
    if value is None: return []
    if not isinstance(value,list) or len(value)>8: raise AIResponseError('visuals يجب أن تكون قائمة صغيرة.')
    out=[]
    for i,v in enumerate(value):
        if not isinstance(v,dict): raise AIResponseError('بيانات الرسم غير صالحة.')
        v=dict(v); v.pop('svg',None); v.pop('renderer',None)
        try:
            if v.get('type') in ('circuit','forces','physics_graph'):
                from .physics_visuals import render
                svg=render(v)
            elif v.get('type')=='graph': svg=graph(v)
            elif v.get('type')=='variation_table': svg=variation(v)
            elif v.get('type') in ('diagram','table'):
                out.append(v); continue
            else: raise ValueError('unsupported visual type')
        except (ValueError,KeyError,TypeError,SyntaxError,OverflowError,AttributeError) as exc:
            raise AIResponseError(f'بيانات الرسم تحتاج تصحيحًا: {exc}') from exc
        v.update(id=str(v.get('id',f'v{i+1}')),renderer='server-math-v1',svg=svg)
        out.append(v)
    return out


def without_svg(value):
    if isinstance(value,dict): return {k:without_svg(v) for k,v in value.items() if k not in ('svg','renderer')}
    if isinstance(value,list): return [without_svg(v) for v in value]
    return value
