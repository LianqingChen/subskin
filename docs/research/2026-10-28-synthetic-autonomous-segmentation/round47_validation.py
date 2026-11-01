"""Dual standard/small synthetic validation gate with source-level checks."""
from round42_validation import validation_stats as base_stats, passes_validation as base_pass

def validation_stats(pairs):
    if len(pairs)!=320:raise ValueError('expected 320 validation samples')
    ordinary=base_stats(pairs[:160]);small=base_stats(pairs[160:]);source_rows=[];all_dice=[]
    for idx in range(10):
        dices=[];detected=0
        for pred,target in pairs[160+idx*16:160+(idx+1)*16]:
            valid=target!=255;truth=(target==2)&valid;candidate=(pred==2)&valid;n=int(truth.sum())
            if not n:continue
            if n>64:raise ValueError('small group has a large core')
            m=int(candidate.sum());tp=int((truth&candidate).sum());dices.append(2*tp/(n+m));detected+=int(tp>0)
        if len(dices)!=8:raise ValueError('small source composition differs')
        all_dice.extend(dices);source_rows.append({'source_index':idx,'small_mean_dice':sum(dices)/8,'detected_positive_images':detected})
    return {'ordinary':ordinary,'small':small,'small_mean_dice':sum(all_dice)/len(all_dice),'small_sources':source_rows}

def passes_validation(s):
    return base_pass(s['ordinary']) and base_pass(s['small']) and s['small_mean_dice']>=.20 and len(s['small_sources'])==10 and all(v['detected_positive_images']>=4 for v in s['small_sources'])
