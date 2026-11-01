#!/usr/bin/env python3
"""Render the checked-in diagram model as editable Excalidraw and portable SVG.

No network or third-party dependency. PNG export is optional, using an SVG renderer.
Both exports use exactly the model's geometry and stable semantic identifiers.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


def render():
    model = json.loads((DOCS / 'architecture-model.json').read_text())
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{model["width"]}" height="{model["height"]}" viewBox="0 0 {model["width"]} {model["height"]}" role="img" aria-labelledby="title description">',
           '<title id="title">OpenBound ownership and evidence boundaries</title>',
           '<desc id="description">One agent owns the task. Private sources are adapted into an isolated public candidate. Inspector and verification produce private evidence. Only the candidate crosses the host-authorized external delivery boundary.</desc>',
           '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#465369" stroke-width="1.4"/></marker></defs>',
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    elements = []
    serial = [0]
    def base(ident, kind, x, y, w, h):
        serial[0] += 1
        return {'id': ident, 'type': kind, 'x': x, 'y': y, 'width': w, 'height': h,
                'angle': 0, 'strokeColor': '#465369', 'backgroundColor': 'transparent',
                'fillStyle': 'solid', 'strokeWidth': 1.5, 'strokeStyle': 'solid',
                'roughness': 0, 'opacity': 100, 'groupIds': [], 'frameId': None,
                'roundness': {'type': 3}, 'seed': serial[0], 'version': 1,
                'versionNonce': serial[0], 'isDeleted': False, 'boundElements': [],
                'updated': 0, 'link': None, 'locked': False}
    def text(ident, x, y, content, size=18, color='#1d2b3d', weight='400'):
        lines = content.split('\n')
        svg.append(f'<text x="{x}" y="{y+size}" font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">')
        for i,line in enumerate(lines):
            svg.append(f'<tspan x="{x}" dy="{0 if i==0 else size*1.4}">{escape(line)}</tspan>')
        svg.append('</text>')
        element = base(ident, 'text', x, y, max(map(len, lines)) * size * .59, len(lines) * size * 1.4)
        element.update({'text': content, 'originalText': content, 'fontSize': size,
                        'fontFamily': 2, 'textAlign': 'left', 'verticalAlign': 'top',
                        'containerId': None, 'lineHeight': 1.4, 'autoResize': True,
                        'strokeColor': color, 'baseline': size})
        elements.append(element)
    text('title', 55, 25, model['title'], 32, weight='700')
    text('subtitle', 57, 70, model['subtitle'], 17, '#526275')
    for region in model['regions']:
        x,y,w,h = [region[k] for k in ('x','y','w','h')]
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{region["color"]}" stroke="#d9e0e8"/>')
        e = base(region['id'], 'rectangle',x,y,w,h)
        e.update({'backgroundColor':region['color'],'strokeColor':'#d9e0e8'})
        elements.append(e)
        text(region['id']+'-label',x+22,y+12,region['label'],15,'#465369','700')
    for edge in model['edges']:
        points=edge['points']
        dashed=' stroke-dasharray="7 4"' if edge.get('kind')=='evidence' else ''
        coords=' '.join(str(x)+','+str(y) for x,y in points)
        svg.append(f'<polyline points="{coords}" fill="none" stroke="#465369" stroke-width="1.8"{dashed} marker-end="url(#arrow)"/>')
        x,y=points[0]
        e=base(edge['id'],'arrow',x,y,max(p[0] for p in points)-min(p[0] for p in points),max(p[1] for p in points)-min(p[1] for p in points))
        e.update({'points':[[px-x,py-y] for px,py in points], 'startArrowhead':None,
                  'endArrowhead':'arrow','lastCommittedPoint':None,
                  'startBinding':{'elementId':edge['from'],'focus':0,'gap':0},
                  'endBinding':{'elementId':edge['to'],'focus':0,'gap':0},
                  'strokeStyle':'dashed' if edge.get('kind')=='evidence' else 'solid'})
        elements.append(e)
        if edge.get('label'):
            text(edge['id']+'-label',*edge['labelAt'],edge['label'],13,'#465369')
    for node in model['nodes']:
        x,y,w,h=[node[k] for k in ('x','y','w','h')]
        color='#fffdf8' if node['id'] in ('gate','remote') else '#ffffff'
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{color}" stroke="#8393aa" stroke-width="1.5"/>')
        e=base(node['id'],'rectangle',x,y,w,h)
        e.update({'backgroundColor':color,'strokeColor':'#8393aa','customData':{'evidenceStatus':node['status']}})
        e['boundElements']=[{'id':edge['id'],'type':'arrow'} for edge in model['edges'] if node['id'] in (edge['from'],edge['to'])]
        elements.append(e)
        text(node['id']+'-title',x+18,y+14,node['title'],21,weight='700')
        text(node['id']+'-body',x+18,y+50,'\n'.join(node['lines']),16,'#415268')
    svg.append('</svg>')
    (DOCS/'architecture.svg').write_text('\n'.join(svg)+'\n')
    scene={'type':'excalidraw','version':2,'source':'OpenBound local model renderer',
           'elements':elements,'appState':{'viewBackgroundColor':'#ffffff','gridSize':None},'files':{}}
    (DOCS/'architecture.excalidraw').write_text(json.dumps(scene,indent=2)+'\n')
    print('Rendered local SVG and editable Excalidraw from one geometry model.')


if __name__=='__main__':
    render()
