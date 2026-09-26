"""Lowest sp reached vs the linker's _bss_end / RAM base, per Embench benchmark.
usage: stack_audit.py <variant> <isa> <bench>   -> one TSV line"""
import sys,os,subprocess
v,isa,b=sys.argv[1:4]
ENV='/home/khwl/Desktop/RV-IM100/riscof-env'
S=os.path.dirname(os.path.abspath(sys.argv[0]))
elf=f'{ENV}/build/embench/{isa}/{b}.elf'; hexf=f'{ENV}/build/embench/{isa}/{b}.hex'
if not os.path.exists(hexf): print(f'{v}\t{isa}\t{b}\tNO_IMAGE'); sys.exit()
nm=subprocess.run(['/opt/riscv/bin/riscv64-unknown-elf-nm',elf],capture_output=True,text=True).stdout
sym={p[2]:int(p[0],16) for p in (l.split() for l in nm.splitlines()) if len(p)==3}
tr=f'{S}/fifo_sa_{v}_{b}'
if os.path.exists(tr): os.remove(tr)
os.mkfifo(tr)
p=subprocess.Popen([f'{ENV}/build/socs_{v}/Vsim_top',f'+HEX={hexf}','+HALT_ADDR=10012000',f'+TRACE={tr}','+MAX_CYCLES=60000000'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
minsp=None
for line in open(tr):
    if line[0]=='S': continue
    parts=line.split()
    if len(parts)>=4 and parts[3].startswith('x2='):
        sp=int(parts[3][3:],16)
        if minsp is None or sp<minsp: minsp=sp
out=p.stdout.read(); p.wait(); os.remove(tr)
be,se=sym['_bss_end'],sym['_stack_end']
depth=se-minsp
verdict='OK' if minsp>=be else ('INTO_BSS' if minsp>=0x10000000 else 'BELOW_RAM')
print(f'{v}\t{isa}\t{b}\t{"HALT" in out}\t0x{be:x}\t0x{se:x}\t0x{minsp:x}\t{depth}\t{be-minsp if minsp<be else 0}\t{verdict}')
