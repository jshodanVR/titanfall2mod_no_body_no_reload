from pathlib import Path
import collections,json,struct,hashlib,shutil
import numpy as np
ROOT=Path(__file__).parent
SOURCE=ROOT/'hands_models/generated'
DEST=ROOT/'hands_capped/generated'
DEST.mkdir(parents=True,exist_ok=True)
reports=[]
def triangulate(ordered,positions):
    xyz=np.array([positions[i]for i in ordered]);center=xyz.mean(0)
    _,_,axes=np.linalg.svd(xyz-center);xy=(xyz-center)@axes[:2].T
    area=sum(xy[i,0]*xy[(i+1)%len(xy),1]-xy[i,1]*xy[(i+1)%len(xy),0]for i in range(len(xy)))
    sign=1 if area>0 else -1
    def cross(a,b,c):
        u,v=b-a,c-a
        return u[0]*v[1]-u[1]*v[0]
    todo=list(range(len(ordered)));result=[]
    while len(todo)>3:
        for t,b in enumerate(todo):
            a,c=todo[t-1],todo[(t+1)%len(todo)]
            if cross(xy[a],xy[b],xy[c])*sign<=1e-8:continue
            if any(all(v*sign>=-1e-8 for v in (cross(xy[a],xy[b],xy[p]),cross(xy[b],xy[c],xy[p]),cross(xy[c],xy[a],xy[p])))for p in todo if p not in (a,b,c)):continue
            result.append((ordered[a],ordered[b],ordered[c]));todo.pop(t);break
        else:raise AssertionError('Boundary polygon cannot be triangulated safely.')
    result.append(tuple(ordered[i]for i in todo));assert len(result)==len(ordered)-2
    return result
for topology in (ROOT/'hands_models').glob('topology-*.json'):
    name=topology.name[len('topology-'):-len('.json')]
    info=json.loads(topology.read_text());positions=info['positions']
    source=SOURCE/'mod/models/weapons/arms'/name
    data=source.read_bytes();out=bytearray(data);caps=[];visible=[]
    for g in info['groups']:
        mapping=g['mapping'];edges=collections.defaultdict(list);kept=[];free=[]
        key=lambda i:tuple(round(v,4)for v in positions[mapping[i]])
        for t in g['triangles']:
            if not t['kept']:free.append(t['offset']);continue
            tri=t['tri'];kept.append(tri)
            for a,b in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((key(a),key(b))))].append((a,b))
        boundary=[v[0]for v in edges.values()if len(v)==1]
        # The gauntlet material contains the cuff; preserve glass and small existing details.
        gauntlet=g['mesh'] in ([0,1]if name=='pov_mlt_hero_jack.mdl'else[1])
        additions=[]
        if gauntlet and boundary:
            assert g['strip_count']==1,'Cap must reuse the same hardware bone palette.'
            outgoing={key(a):(a,b)for a,b in boundary};assert len(outgoing)==len(boundary)
            remaining=set(outgoing)
            while remaining:
                seed=next(iter(remaining));p=seed;ring=[]
                while p in remaining:
                    remaining.remove(p);a,b=outgoing[p];ring.append(a);p=key(b)
                assert p==seed,'Boundary is not a closed manifold loop.'
                if len(ring)<10:continue
                # Reverse the sidewall boundary so cap and sidewall face the correct way.
                local=list(reversed(ring))
                triangles=triangulate(local,[positions[i]for i in mapping])
                additions.extend(triangles)
                caps.append(dict(mesh=g['mesh'],border_vertices=len(ring),triangles=len(triangles)))
        assert len(additions)<=len(free)
        for offset,triangle in zip(free,additions):
            assert max(triangle)<len(mapping)
            struct.pack_into('<3H',out,offset,*triangle)
        # Verify each previously open cuff edge now has exactly one cap neighbour.
        final_edges=collections.Counter()
        for tri in kept+additions:
            for a,b in zip(tri,tri[1:]+tri[:1]):final_edges[tuple(sorted((key(a),key(b))))]+=1
            visible.append(tuple(mapping[i]for i in tri))
        for tri in additions:
            for a,b in zip(tri,tri[1:]+tri[:1]):assert final_edges[tuple(sorted((key(a),key(b))))]==2
    assert len(caps)==(4 if name=='pov_mlt_hero_jack.mdl'else 2),caps
    vvd=struct.unpack_from('<i',data,0x1b0)[0]
    assert out[vvd:]==data[vvd:], 'Positions, normals, UVs and skinning weights must remain unchanged.'
    assert len(out)==len(data)
    target=DEST/'mod/models/weapons/arms'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
    reports.append(dict(model=name,before_sha256=hashlib.sha256(data).hexdigest(),after_sha256=hashlib.sha256(out).hexdigest(),caps=caps))
    if name.endswith('rifleman.mdl'):
        (ROOT/'hands_capped/preview.json').write_text(json.dumps([positions,visible]))
meta=json.loads((SOURCE/'mod.json').read_text());meta['Version']='0.2.0';meta['Description']='Hands-only pilot geometry with closed wrist cuffs.'
(DEST/'mod.json').write_text(json.dumps(meta,indent=2))
(ROOT/'hands_capped/manifest.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))


