from pathlib import Path
import struct,json,collections,hashlib
import numpy as np
ROOT=Path(__file__).parent
SOURCE=ROOT/'hands_capped/generated'
DEST=ROOT/'hands_refined/generated';DEST.mkdir(parents=True,exist_ok=True)
reports=[]
for topo in (ROOT/'hands_models').glob('topology-*.json'):
    name=topo.name[len('topology-'):-len('.json')];info=json.loads(topo.read_text());pos=np.array(info['positions']);newpos=pos.copy()
    data=(SOURCE/'mod/models/weapons/arms'/name).read_bytes();out=bytearray(data)
    nb,bo=struct.unpack_from('<ii',data,160);bones={}
    for i in range(nb):
        p=bo+i*244;s=struct.unpack_from('<i',data,p)[0];n=data[p+s:].split(b'\0')[0].decode();a=np.eye(4);a[:3]=np.array(struct.unpack_from('<12f',data,p+120)).reshape(3,4)
        bones[n]=(i,np.linalg.inv(a)[:3,3])
    vvd=struct.unpack_from('<i',data,0x1b0)[0];vb=vvd+struct.unpack_from('<i',data,vvd+56)[0]
    changed={};rings=[]
    for g in info['groups']:
        if g['mesh']not in ([0,1]if name=='pov_mlt_hero_jack.mdl'else[1]):continue
        mp=g['mapping'];key=lambda i:tuple(np.round(pos[mp[i]],4));edges=collections.defaultdict(list)
        for t in g['triangles']:
            if not t['kept']:continue
            tri=t['tri']
            for a,b in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((key(a),key(b))))].append((a,b))
        outgoing={key(e[0][0]):e[0]for e in edges.values()if len(e)==1};left=set(outgoing)
        while left:
            seed=next(iter(left));k=seed;ring=[]
            while k in left:
                left.remove(k);a,b=outgoing[k];ring.append(mp[a]);k=key(b)
            assert k==seed
            if len(ring)<10:continue
            center=pos[ring].mean(0);side=min(['l','r'],key=lambda s:np.linalg.norm(center-bones['def_'+s+'_wrist'][1]))
            wrist,w=bones['def_'+side+'_wrist'];el=bones['def_'+side+'_elbow'][1];axis=w-el;axis/=np.linalg.norm(axis)
            depth=(pos[ring]-w)@axis;plane=float(np.median(depth))
            # Flatten just the closure rim. Keeping a separate plane per ring avoids coplanar caps.
            for idx in ring:
                newpos[idx]=pos[idx]+(plane-float((pos[idx]-w)@axis))*axis;changed[idx]=wrist
            rings.append({'side':side,'vertices':len(ring),'old_depth_range':float(np.ptp(depth)),'new_depth':plane})
        # Duplicate seam vertices must move and bind together.
        by_key={tuple(np.round(pos[i],4)):i for i in list(changed)}
        for idx in mp:
            other=by_key.get(tuple(np.round(pos[idx],4)))
            if other is not None:newpos[idx]=newpos[other];changed[idx]=changed[other]
        for side in ['l','r']:
            wrist=bones['def_'+side+'_wrist'][0];palette=set()
            for j,idx in enumerate(mp):
                p=vb+idx*48
                e=g['vtx_vertices_offset']+j*9
                weights=struct.unpack_from('<3f',data,p)
                for hw in range(data[e+3]):
                    weight_slot=data[e+hw]
                    if weight_slot<3 and data[p+12+weight_slot]==wrist and weights[weight_slot]>1e-5:
                        palette.add(data[e+6+hw])
            affected=[(j,i)for j,i in enumerate(mp)if changed.get(i)==wrist]
            if not affected:continue
            assert len(palette)==1,('Ambiguous wrist hardware palette.',name,g['mesh'],side,palette)
            palette_index=next(iter(palette))
            for j,idx in affected:
                e=g['vtx_vertices_offset']+j*9
                out[e:e+4]=bytes([0,1,2,1]);out[e+6:e+9]=bytes([palette_index,0,0])
    for idx,wrist in changed.items():
        p=vb+idx*48
        struct.pack_into('<3f4B',out,p,1.,0.,0.,wrist,0,0,1)
        struct.pack_into('<3f',out,p+16,*newpos[idx])
    assert len(rings)==(4 if name=='pov_mlt_hero_jack.mdl'else 2)
    assert len(out)==len(data) and out[bo:bo+nb*244]==data[bo:bo+nb*244]
    for idx in range(len(pos)):
        p=vb+idx*48
        if idx not in changed:assert out[p:p+48]==data[p:p+48]
        else:
            assert out[p+28:p+48]==data[p+28:p+48] # original normals and UVs
            assert out[p+15]==1 and out[p+12]in(20,44)
    assert set(changed.values())=={bones['def_l_wrist'][0],bones['def_r_wrist'][0]}
    # Index buffers, including watertight caps, are unchanged.
    for g in info['groups']:
        for t in g['triangles']:
            o=t['offset'];assert out[o:o+6]==data[o:o+6]
    target=DEST/'mod/models/weapons/arms'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
    reports.append(dict(model=name,before_sha256=hashlib.sha256(data).hexdigest(),after_sha256=hashlib.sha256(out).hexdigest(),rim_vertices_refined=len(changed),rings=rings))
    if name.endswith('rifleman.mdl'):
        _,triangles=json.loads((ROOT/'hands_capped/preview.json').read_text());(ROOT/'hands_refined/preview.json').write_text(json.dumps([newpos.tolist(),triangles]))
meta=json.loads((SOURCE/'mod.json').read_text());meta['Version']='0.3.0';meta['Description']='Hands-only geometry with closed, smoothed and wrist-bound cuffs.'
(DEST/'mod.json').write_text(json.dumps(meta,indent=2));(ROOT/'hands_refined/manifest.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports,indent=2))


