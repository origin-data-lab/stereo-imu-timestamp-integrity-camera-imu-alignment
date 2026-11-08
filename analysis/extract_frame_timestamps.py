# NOTE: device-specific readers in this file are withheld (see CODE_AVAILABILITY.md).
import sys,subprocess,struct,re,numpy as np
vid,out=sys.argv[1],sys.argv[2]
p=subprocess.run(['ffmpeg','-v','error','-i',vid,'-map','0:v','-c','copy','-bsf:v','h264_mp4toannexb','-f','h264','-'],capture_output=True)
b=p.stdout
rows=[]
pass  # device-specific code withheld
a=np.array(rows,dtype=np.int64); np.save(out,a)
print(vid.split('/')[-1],len(a),'exp_us med',np.median(a[:,2]),'min',a[:,2].min(),'max',a[:,2].max(),'dt med',np.median(np.diff(a[:,1])),'max',np.diff(a[:,1]).max(),'flags',np.unique(a[:,4]))
