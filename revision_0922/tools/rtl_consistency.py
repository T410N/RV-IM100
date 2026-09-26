import re,glob,os,hashlib,collections,sys
R='/home/khwl/Desktop/RV-IM100/RV-IM100_RTL/project_files'
sys.path.insert(0,'/home/khwl/Desktop/RV-IM100/riscof-env/scripts')
EX={'Instruction_Memory.v','UART_TX.v'}
def xpr_sources(d):
    xpr=glob.glob(d+'/*.xpr')[0]; base=os.path.splitext(xpr)[0]
    px=open(xpr).read()
    # only files in sources_1 fileset
    fs=re.search(r'<FileSet Name="sources_1".*?</FileSet>',px,re.S).group(0)
    files=[f.replace('$PPRDIR',d).replace('$PSRCDIR',base+'.srcs') for f in re.findall(r'<File Path="([^"]+)"',fs)]
    return [f for f in files if f.endswith(('.v','.vh','.sv')) and '/ip/' not in f]
def h(f): return hashlib.md5(open(f,'rb').read()).hexdigest()[:10]
legacy=dict(l for l in [
 ("RV32I_5SP","RV32s/SoCs/RV32I_5SP"),("RV32IM_5SP","RV32s/SoCs/RV32IM_5SP"),("RV32IM_6SP","RV32s/SoCs/RV32IM_6SP"),("RV32IM_7SP","RV32s/SoCs/RV32IM_7SP"),("RV32IM_7SP_BRAM","RV32s/SoCs/RV32IM_7SP_BRAM"),("RV32IM_7SP_BRAM_Opt","RV32s/SoCs/RV32IM_7SP_BRAM_Opt"),("RV32IM_8SP","RV32s/SoCs/RV32IM_8SP"),("RV32IM_8SP_withoutOpt","RV32s/SoCs/RV32IM_8SP_withoutOpt"),
 ("RV64I_5SP","RV64s/SoCs/RV64I5SP_SoC"),("RV64IM_5SP","RV64s/SoCs/RV64IM_5SP"),("RV64IM_6SP","RV64s/SoCs/RV64IM_6SP"),("RV64IM_7SP","RV64s/SoCs/RV64IM_7SP"),("RV64IM_7SP_BRAM","RV64s/SoCs/RV64IM_7SP_BRAM"),("RV64IM_7SP_BRAM_Opt","RV64s/SoCs/RV64IM_7SP_BRAM_Opt/RV64IM72F_7SP_BRAM_Final_1431"),("RV64IM_8SP","RV64s/SoCs/RV64IM_8SP"),("RV64IM_8SP_withoutOpt","RV64s/SoCs/RV64IM_8SP_withoutOpt")])
SIMB='/home/khwl/Desktop/RV-IM100/riscof-env/build'
bad=0
for v,lp in legacy.items():
    arch=v[:4]
    projs={'legacy':R+'/'+lp}
    for p in sorted(glob.glob(f'{R}/{arch}s/SoCs/{v}_*')):
        suf=p.split(v+'_',1)[1]
        if suf in('Dhry','Coremark') or suf.startswith('Embench_'): projs[suf]=p
    table=collections.defaultdict(dict)
    for k,p in projs.items():
        try: fl=xpr_sources(p)
        except Exception as e: print(v,k,'ERR',e); continue
        for f in fl:
            b=os.path.basename(f)
            if b in EX: continue
            table[b][k]=h(f) if os.path.exists(f) else 'MISSING'
    diffs=[(b,d) for b,d in table.items() if len(set(d.values()))>1 or len(d)!=len(projs)]
    print(f'{v}: {len(projs)} projects, {len(table)} files, {len(diffs)} files differ/missing')
    for b,d in diffs[:8]:
        g=collections.defaultdict(list)
        for k,x in d.items(): g[x].append(k)
        miss=[k for k in projs if k not in d]
        print('   ',b,dict(g),'absent in:',miss if miss else '')
        bad+=1
print('TOTAL differing file entries',bad)
