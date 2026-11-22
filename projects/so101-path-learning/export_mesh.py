"""Export compiled MuJoCo visual geometry in its model-local reference frames."""
import json
import numpy as np
from arm import Bench, ROOT

def main():
    bench=Bench();m=bench.m
    out=ROOT/"web"/"model";out.mkdir(parents=True,exist_ok=True)
    mesh_data=bytearray();meshes=[]
    def append(array,dtype):
        value=np.asarray(array,dtype=dtype)
        offset=len(mesh_data);mesh_data.extend(value.tobytes())
        return [offset,value.size]
    for i in range(m.nmesh):
        v=m.mesh_vertadr[i];f=m.mesh_faceadr[i]
        original=m.mesh_vert[v:v+m.mesh_vertnum[i]]
        # Submillimetre vertex clustering for interactive display only.
        _,ids=np.unique(np.rint(original/.00060).astype(np.int32),axis=0,return_inverse=True)
        counts=np.bincount(ids)
        vertices=np.stack([np.bincount(ids,weights=original[:,axis])/counts for axis in range(3)],axis=1)
        faces=ids[m.mesh_face[f:f+m.mesh_facenum[i]]]
        faces=faces[(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,0]!=faces[:,2])]
        meshes.append(dict(vertices=append(vertices,"<f4"),faces=append(faces,"<u4")))
    geoms=[]
    for g in bench.visual:
        mat=m.material(m.geom_matid[g]).name
        geoms.append(dict(body=int(m.geom_bodyid[g]),mesh=int(m.geom_dataid[g]),motor=mat.startswith("sts3215"),
                          position=m.geom_pos[g].tolist(),rotation=m.geom_quat[g].tolist()))
    (out/"geometry.bin").write_bytes(mesh_data)
    (out/"model.json").write_text(json.dumps(dict(meshes=meshes,geoms=geoms,bytes=len(mesh_data),
                                                 bodies=[m.body(i).name for i in range(m.nbody)])))
    print(len(geoms),"visual mesh instances",len(mesh_data),"bytes")
if __name__=="__main__":main()

