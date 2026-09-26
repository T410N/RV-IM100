import re,glob,os,hashlib,json,sys
R='/home/khwl/Desktop/RV-IM100/RV-IM100_RTL/project_files'
out=[]
for d in sorted(glob.glob(R+'/RV*s/SoCs/*_Dhry')+glob.glob(R+'/RV*s/SoCs/*_Coremark')):
    xpr=glob.glob(d+'/*.xpr')[0]; px=open(xpr).read()
    files=re.findall(r'<File Path="([^"]+)"',px)
    base=os.path.splitext(xpr)[0]
    files=[f.replace('$PPRDIR',d).replace('$PSRCDIR',base+'.srcs') for f in files]
    im=[f for f in files if f.endswith('Instruction_Memory.v')]
    src=open(im[0]).read()
    src=re.sub(r'//.*','',src)
    mems=re.findall(r'readmemh\(\s*"([^"]+)"',src)
    memname=os.path.basename(mems[0])
    cands=[f for f in files if os.path.basename(f)==memname]
    h=[hashlib.md5(open(c,'rb').read()).hexdigest() if os.path.exists(c) else 'MISSING' for c in cands]
    # PLL frequency from xci
    xci=[f for f in files if f.endswith('clk_wiz_0.xci')]
    freq=None
    if xci:
        t=open(xci[0]).read()
        m=re.search(r'"CLKOUT1_REQUESTED_OUT_FREQ":\s*\[\s*\{\s*"value":\s*"([0-9.]+)"',t) or re.search(r'CLKOUT1_REQUESTED_OUT_FREQ[^0-9]*([0-9.]+)',t)
        freq=m.group(1) if m else None
    out.append(dict(project=os.path.relpath(d,R),im=os.path.relpath(im[0],d),mem=memname,n_cand=len(cands),md5=h,paths=[os.path.relpath(c,d) for c in cands],pll=freq))
json.dump(out,open(sys.argv[1],'w'),indent=1)
for o in out: print(o['project'].split('/')[-1],o['mem'],o['pll'],o['md5'],o['n_cand'])
