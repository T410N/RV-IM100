import json,collections,csv,os
rows=[];sites=collections.defaultdict(set)
for l in open('cf_results.jsonl'):
    d=json.loads(l); img=os.path.basename(d['image']).replace('.hex','').replace('_100000000.mem','')
    rows.append(dict(variant=d['variant'],workload=img,retired=d['retired'],violations=d['violations'],halted=d['halted'],
                     sites=';'.join(sorted({f"{f['prev_pc']}->{f['pc']}" for f in d['first']}))))
    for f in d['first']: sites[(d['variant'][:4],img.split('_')[0])].add(f"{f['prev_pc']}->{f['pc']}")
csv.DictWriter(open('t6_p1_workloads.csv','w',newline=''),fieldnames=list(rows[0])).writeheader()
csv.DictWriter(open('t6_p1_workloads.csv','a',newline=''),fieldnames=list(rows[0])).writerows(rows)
V=['RV32I_5SP','RV32IM_5SP','RV32IM_6SP','RV32IM_7SP','RV32IM_7SP_BRAM','RV32IM_7SP_BRAM_Opt','RV32IM_8SP_withoutOpt','RV32IM_8SP','RV64I_5SP','RV64IM_5SP','RV64IM_6SP','RV64IM_7SP','RV64IM_7SP_BRAM','RV64IM_7SP_BRAM_Opt','RV64IM_8SP_withoutOpt','RV64IM_8SP']
W=sorted({r['workload'].split('_')[0] for r in rows})
M={(r['variant'],r['workload'].split('_')[0]):r['violations'] for r in rows}
print('workload'.ljust(15)+''.join(v.replace('RV32','32').replace('RV64','64').replace('_withoutOpt','_wo')[:13].rjust(14) for v in V))
for w in W: print(w[:14].ljust(15)+''.join(str(M.get((v,w),'-')).rjust(14) for v in V))
