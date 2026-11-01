"""Source-stratified validation gate for ordered synthetic pairs."""

def validation_stats(pairs):
    if len(pairs)!=160:raise ValueError('expected 160 validation samples')
    sources=[]
    for index in range(10):
        recalls=[];negatives=[]
        for pred,target in pairs[index*16:(index+1)*16]:
            valid=target!=255
            if not bool(valid.any()):raise ValueError('empty validation target')
            truth=(target==2)&valid;found=(pred==2)&valid;total=int(truth.sum())
            if total:recalls.append(int((truth&found).sum())/total)
            else:negatives.append(bool(found.any()))
        if len(recalls)!=8 or len(negatives)!=8:raise ValueError('source class composition differs')
        sources.append({'source_index':index,'positive':8,'negative':8,'recall':sum(recalls)/8,'false_positives':sum(negatives)})
    return {'positive':80,'negative':80,'recall':sum(x['recall'] for x in sources)/10,'false_positives':sum(x['false_positives'] for x in sources),'sources':sources}

def passes_validation(stats):
    return stats['recall']>=.30 and stats['false_positives']<=20 and len(stats['sources'])==10 and all(x['recall']>=.10 and x['false_positives']<=4 for x in stats['sources'])
