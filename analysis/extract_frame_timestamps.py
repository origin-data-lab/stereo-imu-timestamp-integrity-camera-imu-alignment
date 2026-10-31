import sys,subprocess,struct,re,numpy as np
vid,out=sys.argv[1],sys.argv[2]
p=subprocess.run(['ffmpeg','-v','error','-i',vid,'-map','0:v','-c','copy','-bsf:v','h264_mp4toannexb','-f','h264','-'],capture_output=True)
b=p.stdout
rows=[]
for m in re.finditer(re.escape(b'\x00\x00\x01\x06\xf0\x28'),b):
    raw=b[m.start()+6:m.start()+6+60]
    raw=raw.replace(b'\x00\x00\x03',b'\x00\x00')[:40]
    magic,ver,size=raw[:4],*struct.unpack('<HH',raw[4:8])
    pts,exs=struct.unpack('<QQ',raw[8:24]); ext,strobe,flags=struct.unpack('<III',raw[24:36])
    rows.append((pts,exs,ext,strobe,flags))
a=np.array(rows,dtype=np.int64); np.save(out,a)
print(vid.split('/')[-1],len(a),'exp_us med',np.median(a[:,2]),'min',a[:,2].min(),'max',a[:,2].max(),'dt med',np.median(np.diff(a[:,1])),'max',np.diff(a[:,1]).max(),'flags',np.unique(a[:,4]))
