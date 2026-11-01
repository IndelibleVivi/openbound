#!/usr/bin/env python3
"""Render both language editions as editable Excalidraw and portable SVG.

No network or third-party dependency. PNG export is optional, using an SVG renderer.
One model owns topology, translations and language-specific layouts.
"""
from copy import deepcopy
import json
from pathlib import Path
import unicodedata
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


def localized(model, language):
    result = deepcopy(model)
    if language == 'en':
        return result
    translation = model['translations'][language]
    for key in ('title', 'subtitle', 'accessibility', 'width', 'height'):
        result[key] = translation.get(key, model[key])
    for section in ('regions', 'nodes', 'edges'):
        updates = translation[section]
        expected = {item['id'] for item in model[section]}
        if set(updates) != expected:
            raise ValueError(f'{language}: incomplete {section} translation')
        for item in result[section]:
            item.update(updates.get(item['id'], {}))
    return result


def render_edition(model, language, stem):
    chinese = language == 'zh-CN'
    font = ('PingFang SC, Noto Sans CJK SC, Microsoft YaHei, DejaVu Sans, sans-serif'
            if chinese else 'DejaVu Sans, Arial, sans-serif')
    line_height = 1.25 if chinese else 1.4
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{model["width"]}" height="{model["height"]}" viewBox="0 0 {model["width"]} {model["height"]}" role="img" lang="{language}" aria-labelledby="diagram-title diagram-description">',
           f'<title id="diagram-title">{escape(model["accessibility"]["title"])}</title>',
           f'<desc id="diagram-description">{escape(model["accessibility"]["description"])}</desc>',
           '<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#465369" stroke-width="1.4"/></marker></defs>',
           f'<rect width="{model["width"]}" height="{model["height"]}" fill="#ffffff"/>']
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
    def text(ident, x, y, content, size=18, color='#1d2b3d', weight='400', role='body'):
        lines = content.split('\n')
        for i,line in enumerate(lines):
            # Explicit coordinates also work in native renderers that do not
            # implement relative tspan offsets or percentage-sized backgrounds.
            baseline = y + size + i * size * line_height
            svg.append(f'<text x="{x}" y="{baseline}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{color}" data-readability="{role}">{escape(line)}</text>')
        width = max(sum(1 if unicodedata.east_asian_width(char) in ('W', 'F') else .59
                        for char in line) for line in lines) * size
        element = base(ident, 'text', x, y, width, len(lines) * size * line_height)
        element.update({'text': content, 'originalText': content, 'fontSize': size,
                        'fontFamily': 2, 'textAlign': 'left', 'verticalAlign': 'top',
                        'containerId': None, 'lineHeight': line_height, 'autoResize': True,
                        'strokeColor': color, 'baseline': size})
        elements.append(element)
    svg.append('<g id="heading">')
    text('title', 55, 25, model['title'], 38 if chinese else 32, weight='700', role='critical')
    text('subtitle', 57, 85 if chinese else 70, model['subtitle'], 22 if chinese else 17, '#526275')
    svg.append('</g>')
    for region in model['regions']:
        x,y,w,h = [region[k] for k in ('x','y','w','h')]
        svg.append(f'<g id="{region["id"]}" data-readability-background="{region["color"]}">')
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{region["color"]}" stroke="#d9e0e8"/>')
        e = base(region['id'], 'rectangle',x,y,w,h)
        e.update({'backgroundColor':region['color'],'strokeColor':'#d9e0e8'})
        elements.append(e)
        text(region['id']+'-label',x+22,y+12,region['label'],20 if chinese else 15,'#465369','700',role='supporting')
        svg.append('</g>')
    for edge in model['edges']:
        svg.append(f'<g id="{edge["id"]}">')
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
            x, y = edge['labelAt']
            text(edge['id']+'-label',x,y,edge['label'],18 if chinese else 13,'#465369',role='supporting')
        svg.append('</g>')
    for node in model['nodes']:
        x,y,w,h=[node[k] for k in ('x','y','w','h')]
        color=node.get('color', '#fffdf8' if node['id'] in ('gate','remote') else '#ffffff')
        border=node.get('border', '#8393aa')
        svg.append(f'<g id="{node["id"]}" data-readability-background="{color}">')
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{color}" stroke="{border}" stroke-width="1.5"/>')
        e=base(node['id'],'rectangle',x,y,w,h)
        e.update({'backgroundColor':color,'strokeColor':border,'customData':{'evidenceStatus':node['status']}})
        e['boundElements']=[{'id':edge['id'],'type':'arrow'} for edge in model['edges'] if node['id'] in (edge['from'],edge['to'])]
        elements.append(e)
        text(node['id']+'-title',x+18,y+14,node['title'],26 if chinese else 21,weight='700',role='critical')
        text(node['id']+'-body',x+18,y+node.get('bodyOffset', 58 if chinese else 50),'\n'.join(node['lines']),20 if chinese else 16,'#415268')
        svg.append('</g>')
    svg.append('</svg>')
    (DOCS/(stem+'.svg')).write_text('\n'.join(svg)+'\n', encoding='utf-8')
    scene={'type':'excalidraw','version':2,'source':'OpenBound local model renderer',
           'elements':elements,'appState':{'viewBackgroundColor':'#ffffff','gridSize':None},'files':{}}
    (DOCS/(stem+'.excalidraw')).write_text(json.dumps(scene,indent=2,ensure_ascii=False)+'\n', encoding='utf-8')


def render():
    model = json.loads((DOCS / 'architecture-model.json').read_text(encoding='utf-8'))
    for language, stem in (('en', 'architecture'), ('zh-CN', 'architecture.zh-CN')):
        render_edition(localized(model, language), language, stem)
    print('Rendered English and Chinese SVG/Excalidraw from one shared model.')


if __name__=='__main__':
    render()
