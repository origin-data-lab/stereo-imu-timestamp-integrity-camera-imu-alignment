# NOTE: device-specific readers in this file are withheld (see CODE_AVAILABILITY.md).
import numpy as np, sys
dt = None  # device-specific layout withheld
def load(p):
    raise NotImplementedError('Origin Data Lab device-specific reader withheld; results are in assets/tables. Contact founder@origindatalab.io')
if __name__=='__main__':
    for p in sys.argv[1:]:
        r,h=load(p); g=r[r['k1']==2]; a=r[r['k1']==4]
        d=np.diff(g['ts'].astype(np.int64)); sq=np.diff(r['seq'].astype(np.int64))
        G=np.c_[g['x'],g['y'],g['z']]
        print(p.split('/')[-1],'n',len(g),len(a),'dur %.2fs'%((g['ts'][-1]-g['ts'][0])/1e6),'rate %.2f'%(1e6/np.median(d)),'maxgap us',d.max(),'seq jumps',(sq!=1).sum(),'gyro p95 deg/s %.0f'%np.degrees(np.percentile(np.linalg.norm(G,axis=1),95)),'t0',g['ts'][0])
