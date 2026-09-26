import json,csv,collections,os
st={}
for r in csv.DictReader(open('/home/khwl/Desktop/RV-IM100/riscof-env/logs/aapg_results.csv')):
    st[(r['variant'].replace('socs_',''),r['program'])]=r['status']
res={}
for l in open('cf_aapg.jsonl'):
    d=json.loads(l); prog=os.path.basename(os.path.dirname(os.path.normpath(d['image']))); res[(d['variant'],prog)]=d
tab=collections.Counter(); miss=[]; rows=[]
for k,d in sorted(res.items()):
    s=st.get(k,'?'); fired=d['violations']>0
    tab[(s,fired)]+=1
    if s=='TIMEOUT' and not fired: miss.append(k)
    rows.append(dict(variant=k[0],program=k[1],aapg_status=s,violations=d['violations'],halted_3M=d['halted'],first_violation_cycle=d['first'][0]['cycle'] if d['first'] else ''))
csv.DictWriter(open('t6_aapg_monitor.csv','w',newline=''),fieldnames=list(rows[0])).writeheader()
w=csv.DictWriter(open('t6_aapg_monitor.csv','a',newline=''),fieldnames=list(rows[0])); w.writerows(rows)
print(len(res),'runs'); print('status x monitor-fired:')
for k,v in sorted(tab.items()): print('  ',k,v)
print('TIMEOUT runs where monitor did NOT fire:',miss)
