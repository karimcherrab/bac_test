"""Compact source without deleting givens or sending entire worked solutions."""
import xml.etree.ElementTree as ET

DROP={'solution','steps','solution_source_pages','solution_pedagogy','solution_graph_data','source_verification','review_status','display','source_text_policy','content_separation','source_reference','verification','renderer','base64'}


def compact_content(content):
    def clean(value):
        if isinstance(value,list):return [clean(v) for v in value]
        if not isinstance(value,dict):return value
        out={}
        for key,v in value.items():
            if key in DROP:continue
            if key=='svg':
                try:
                    root=ET.fromstring(str(v))
                    labels=[''.join(n.itertext()).strip() for n in root.iter() if n.tag.split('}')[-1] in ('text','title','desc')]
                    out['svg_labels']=[x for x in labels if x]
                    if root.get('aria-label'):out['svg_description']=root.get('aria-label')
                except ET.ParseError:out['svg_description']='رسم مرجعي؛ استعمل وصفه والمعطيات النصية دون تخمين تفاصيل مفقودة.'
            else:out[key]=clean(v)
        return out
    useful={key:value for key,value in content.items() if key in ('title','chapter_code','chapter_title','statement','statement_sections','questions','given_data','data','constants','tables','documents','visuals','figures','statement_graph_data','statement_graphs')}
    out=clean(useful)
    # Files frequently store identical full statements in statement_sections.
    out['statement_sections']=[s for s in out.get('statement_sections',[]) if not isinstance(s,dict) or s.get('text')!=out.get('statement') or any(k in s for k in ('table','graph','visuals','documents'))]
    if out.get('figures')==out.get('statement_graphs'):out.pop('figures',None)
    return out
