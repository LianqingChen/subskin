"""Select feasible large-small intervention centers inside a synthetic skin core."""
import cv2
import numpy as np


def shape_fields(core,rng):
    core=core.astype(bool);u=core.astype('uint8')
    big_safe=cv2.erode(u,np.ones((91,91),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
    small_safe=cv2.erode(u,np.ones((41,41),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0).astype(bool)
    large=np.argwhere(big_safe);small=np.argwhere(small_safe)
    if not len(large) or not len(small):raise ValueError('empty safe area')
    hull=cv2.convexHull(small[:,::-1].astype('float32')).reshape(-1,2)[:,::-1]
    eligible=[]
    for offset in range(0,len(large),1024):
        chunk=large[offset:offset+1024];maximum=np.max(np.square(chunk[:,None,:]-hull[None,:,:]).sum(axis=2),axis=1);eligible.extend(chunk[maximum>=3600].tolist())
    if not eligible:raise ValueError('no feasible separated pair')
    eligible=np.asarray(eligible);first=eligible[rng.integers(len(eligible))];others=small[np.square(small-first).sum(axis=1)>=3600]
    if not len(others):raise ValueError('feasibility invariant failed')
    second=others[rng.integers(len(others))];br=int(rng.integers(28,41));sr=int(rng.integers(12,17));fields=[]
    for point,radius,sigma in ((first,br,1.2),(second,sr,.8)):
        mask=np.zeros(core.shape,np.uint8);cv2.circle(mask,(int(point[1]),int(point[0])),radius,1,-1);fields.append(cv2.GaussianBlur(mask.astype('float32'),(0,0),sigma))
    if np.any((np.maximum(*fields)>.2)&~core):raise ValueError('intervention outside core')
    if not all(np.any(x>=.8) for x in fields):raise ValueError('empty core')
    return fields,{'big_yx':first.tolist(),'small_yx':second.tolist(),'big_radius':br,'small_radius':sr,'big_eligible_count':len(eligible),'small_candidate_count':len(others)}
