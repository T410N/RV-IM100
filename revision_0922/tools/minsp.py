import sys,os,subprocess,re
v,isa,b,maxc=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
ENV='/home/khwl/Desktop/RV-IM100/riscof-env'
S=os.path.dirname(os.path.abspath(__file__))
tr=f'{S}/fifo_{v}_{b}'
if os.path.exists(tr): os.remove(tr)
os.mkfifo(tr)
p=subprocess.Popen([f'{ENV}/build/socs_{v}/Vsim_top',f'+HEX={ENV}/build/embench/{isa}/{b}.hex','+HALT_ADDR=10012000',f'+TRACE={tr}',f'+MAX_CYCLES={maxc}'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
minsp=None;minsp_cyc=None;n=0;below=0;first_below=None;lastpcs=[]
stores_below=0;first_store_below=None
for line in open(tr):
    if line[0]=='S':
        a=int(line.split()[1],16)
        continue
    n+=1
    parts=line.split()
    if len(parts)>=4 and parts[3].startswith('x2='):
        sp=int(parts[3][3:],16)
        if minsp is None or sp<minsp: minsp,minsp_cyc,minsp_pc=sp,int(parts[0]),parts[1]
    lastpcs.append(parts[1]); lastpcs=lastpcs[-4:]
p.wait(); os.remove(tr)
print(f'{v} {b}: retired={n} min_sp=0x{minsp:x} at cycle {minsp_cyc} pc {minsp_pc}; last pcs {lastpcs}; halted={"HALT" in p.stdout.read()}')
