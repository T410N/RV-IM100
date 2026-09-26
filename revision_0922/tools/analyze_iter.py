import json,csv,collections
R={}
for l in open('iter_results.jsonl'):
    d=json.loads(l); R[(d['variant'],d['bench'],d['iters'])]=d
# master values: run MHz, CoreMark it/s (board), Dhrystone/s (board)
M={'RV32I_5SP':(45,50,87378,45),'RV32IM_5SP':(43,117,83820,43),'RV32IM_6SP':(50,125,97015,51.515152),'RV32IM_7SP':(57.5,117,80669,53),
   'RV32IM_7SP_BRAM':(72,142,99447,72),'RV32IM_7SP_BRAM_Opt':(92,176,121862,90.909091),'RV32IM_8SP_withoutOpt':(114,166,134433,114),'RV32IM_8SP':(122,200,140229,122)}
import openpyxl
wb=openpyxl.load_workbook('/home/khwl/Desktop/RV-IM100/Research_data_MASTER_0921.xlsx',data_only=True)
def rv64():
    ws=wb['RV64 SoC and FPGA']; out={}
    for r in ws.iter_rows(min_row=3,max_row=10,values_only=True):
        if r[1]: out['RV64'+r[1]]=r
    return out
r64=rv64()
for v,r in r64.items():
    dm=float(str(r[4]).split('@')[1].replace('MHz','')); cm=float(str(r[7]).split('@')[1].replace('MHz',''))
    M[v]=(cm,r[3],r[2],dm)
rows=[]
for v in M:
    cmf,cm_board,dh_board,dhf=M[v]
    a,b=R[(v,'coremark',10)],R[(v,'coremark',20)]
    c,d=R[(v,'dhrystone',1000)],R[(v,'dhrystone',2000)]
    cpi_cm=(b['region_cycles']-a['region_cycles'])/10; ipi_cm=(b['region_instret']-a['region_instret'])/10
    ovh=a['region_cycles']-10*cpi_cm
    cpi_dh=(d['region_cycles']-c['region_cycles'])/1000; ipi_dh=(d['region_instret']-c['region_instret'])/1000
    Fimg=(100e6 if v=='RV32IM_8SP_withoutOpt' else cmf*1e6)
    # replay core_main.c calibration with integer seconds
    ticks=lambda n: n*cpi_cm+ovh
    n=1; secs=0
    while secs<1:
        n*=10; secs=int(ticks(n)//Fimg)
    n*=1+10//max(secs,1)
    fs=int(ticks(n)//Fimg); pred_print=n//fs
    true_cm=cmf*1e6/cpi_cm
    true_dh=dhf*1e6/cpi_dh
    rows.append(dict(variant=v,cm_cyc_per_iter=round(cpi_cm,1),cm_instr_per_iter=round(ipi_cm,1),cm_cpi=round(cpi_cm/ipi_cm,4),
        cm_valid=a['cm_valid'] and b['cm_valid'],run_MHz_cm=cmf,image_MHz=Fimg/1e6,board_iters=n,board_secs_int=fs,predicted_print=pred_print,master_cm=cm_board,
        replay_match=(pred_print==int(round(float(cm_board)))),true_cm_its=round(true_cm,2),cm_error_pct=round((float(cm_board)-true_cm)/true_cm*100,2),
        true_CM_per_MHz=round(true_cm/cmf,4),
        dh_cyc_per_iter=round(cpi_dh,2),dh_instr_per_iter=round(ipi_dh,2),dh_ok=c['dhry_ok'] and d['dhry_ok'],run_MHz_dh=dhf,master_dh=dh_board,pred_dh=round(true_dh,1),dh_error_pct=round((dh_board-true_dh)/true_dh*100,3),
        elf_cm10=a['elf_sha256'][:16],elf_dh1000=c['elf_sha256'][:16]))
w=csv.DictWriter(open('iter_analysis.csv','w',newline=''),fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows: print(r['variant'].ljust(22),r['cm_cyc_per_iter'],r['cm_instr_per_iter'],r['cm_valid'],'| iters',r['board_iters'],'secs',r['board_secs_int'],'pred',r['predicted_print'],'master',r['master_cm'],r['replay_match'],'| true',r['true_cm_its'],'err%',r['cm_error_pct'],'| DH cyc',r['dh_cyc_per_iter'],'ins',r['dh_instr_per_iter'],'pred',r['pred_dh'],'master',r['master_dh'],'err%',r['dh_error_pct'])
