from pathlib import Path
import struct,json,hashlib
ROOT=Path(__file__).parent
DEST=ROOT/'hands_models/generated'
MODELS=DEST/'mod/models/weapons/arms'
MODELS.mkdir(parents=True,exist_ok=True)
def ints(d,o,n):return struct.unpack_from('<'+'i'*n,d,o)
all_reports=[];preview=[]
for name in ['pov_mlt_hero_jack.mdl','pov_mlt_hero_jack_rifleman.mdl']:
    data=(ROOT/name).read_bytes();out=bytearray(data)
    assert data[:4]==b'IDST' and ints(data,4,1)==(53,)
    nb,bo=ints(data,0xa0,2);names=[];parents=[]
    for i in range(nb):
        p=bo+i*244;s,pa=ints(data,p,2)
        names.append(data[p+s:].split(b'\0')[0].decode());parents.append(pa)
    wrists={names.index('def_l_wrist'),names.index('def_r_wrist')}
    def is_hand(i):
        while i>=0:
            if i in wrists:return True
            i=parents[i]
        return False
    hand_bones={i for i in range(nb) if is_hand(i)}
    vtx,vvd=ints(data,0x1ac,2)
    assert ints(data,vtx,1)==(7,) and data[vvd:vvd+4]==b'IDSV'
    assert ints(data,8,1)==ints(data,vtx+16,1)==ints(data,vvd+8,1)
    lods=ints(data,vvd+12,1)[0];assert lods==1
    assert ints(data,vvd+48,1)==(0,), 'LOD fixups require a separate parser.'
    vertices=ints(data,vvd+16,1)[0];vertex_base=vvd+ints(data,vvd+56,1)[0]
    hand_weight=[];positions=[]
    for i in range(vertices):
        p=vertex_base+i*48;weights=struct.unpack_from('<3f',data,p);bones=struct.unpack_from('<3B',data,p+12);count=data[p+15]
        assert 1<=count<=3 and all(0<=b<nb for b in bones[:count])
        hand_weight.append(sum(w for w,b in zip(weights[:count],bones[:count]) if b in hand_bones))
        positions.append(struct.unpack_from('<3f',data,p+16))
    mdl_bp_count,mdl_bp=ints(data,0xec,2);vtx_bp_count,vtx_bp=ints(data,vtx+28,2)
    assert mdl_bp_count==vtx_bp_count
    kept=removed=0;kept_triangles=[];group_records=[]
    for bi in range(mdl_bp_count):
        bp=mdl_bp+bi*16;models=ints(data,bp+4,1)[0];mo=bp+ints(data,bp+12,1)[0]
        vb=vtx+vtx_bp+bi*8;vmc,vmo=ints(data,vb,2);assert models==vmc
        for mi in range(models):
            m=mo+mi*148;meshes,mesh_offset,vc,vo=ints(data,m+72,4)
            vm=vb+vmo+mi*8;nl,lo=ints(data,vm,2);assert nl==1
            for li in range(nl):
                vl=vm+lo+li*12;nm,meo=ints(data,vl,2);assert meshes==nm
                for mei in range(meshes):
                    mesh=m+mesh_offset+mei*116;mat,model_rel,nv,vert_off=ints(data,mesh,4)
                    vme=vl+meo+mei*9;ng,go=ints(data,vme,2)
                    for gi in range(ng):
                        g=vme+go+gi*33;gn,gv,ni,io,ns,so=ints(data,g,6)
                        mapping=[struct.unpack_from('<H',data,g+gv+i*9+4)[0]+vert_off+vo//48 for i in range(gn)]
                        assert all(0<=i<vertices for i in mapping)
                        group_record={'mesh':mei,'group':gi,'strip_count':ns,'vtx_vertices_offset':g+gv,'mapping':mapping,'triangles':[]}
                        for si in range(ns):
                            strip=g+so+si*35;nind,istart,nvert,vstart=ints(data,strip,4)
                            assert data[strip+18]&1 and nind%3==0
                            assert 0<=istart and istart+nind<=ni
                            for ti in range(0,nind,3):
                                p=g+io+(istart+ti)*2;tri=struct.unpack_from('<3H',data,p)
                                assert all(i<gn for i in tri)
                                ids=tuple(mapping[i] for i in tri)
                                group_record['triangles'].append({'offset':p,'tri':tri,'kept':all(hand_weight[i]>=0.01 for i in ids)})
                                if all(hand_weight[i]>=0.01 for i in ids):
                                    kept+=1;kept_triangles.append(ids)
                                else:
                                    struct.pack_into('<3H',out,p,tri[0],tri[0],tri[0]);removed+=1
                        group_records.append(group_record)
    assert kept>300 and removed>kept
    assert len(out)==len(data)
    assert out[bo:bo+nb*244]==data[bo:bo+nb*244]
    assert out[vvd:]==data[vvd:], 'Vertex positions, weights and animation skeleton must remain intact.'
    (MODELS/name).write_bytes(out)
    (ROOT/'hands_models'/('topology-'+name+'.json')).write_text(json.dumps({'positions':positions,'groups':group_records}))
    report=dict(model=name,bones=nb,hand_bones=len(hand_bones),vertices=vertices,kept_hand_triangles=kept,removed_triangles=removed,original_sha256=hashlib.sha256(data).hexdigest(),patched_sha256=hashlib.sha256(out).hexdigest())
    all_reports.append(report)
    if name.endswith('rifleman.mdl'):preview=[positions,kept_triangles]
(DEST/'mod.json').write_text(json.dumps({'Name':'generated','Description':'Hands-only pilot geometry; preserves original bones, animation and held objects.','Version':'0.1.0','LoadPriority':100,'RequiredOnClient':False},indent=2))
(ROOT/'hands_models/manifest.json').write_text(json.dumps(all_reports,indent=2))
(ROOT/'hands_models/preview.json').write_text(json.dumps(preview))
print(json.dumps(all_reports,indent=2))


