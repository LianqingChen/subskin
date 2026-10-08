"""Image/geometry checks for candidate refinement; not calibrated medical confidence."""
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


def interior_prompts(mask: np.ndarray, width: int, height: int,
                     negative_pool: Optional[np.ndarray] = None) -> List[Tuple[float, float, int]]:
    """Use interior distance maxima; background points never belong to the mask."""
    if mask.shape != (height, width) or not mask.any():
        return []
    distance = cv2.distanceTransform(np.pad(mask.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    y, x = np.unravel_index(int(distance.argmax()), distance.shape)
    points = [(float(x)/width, float(y)/height, 1)]
    yy, xx = np.where(mask)
    radius = max(4, int(max(xx.max()-xx.min()+1, yy.max()-yy.min()+1)*.12))
    radius = min(radius, max(width, height))
    ring = cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))).astype(bool)
    ring &= ~cv2.dilate(mask.astype(np.uint8), np.ones((3,3),np.uint8)).astype(bool)
    if negative_pool is not None:
        if negative_pool.shape != mask.shape:
            return points
        ring &= negative_pool
    ry, rx = np.where(ring)
    if not len(rx):
        return points
    seen = set()
    targets = [(xx.min()-radius,y),(xx.max()+radius,y),(x,yy.min()-radius),(x,yy.max()+radius)]
    for tx,ty in targets:
        i = int(np.argmin((rx-tx)**2+(ry-ty)**2))
        point = (int(rx[i]),int(ry[i]))
        if point not in seen:
            points.append((point[0]/width,point[1]/height,0))
            seen.add(point)
    return points


def local_roi(mask: np.ndarray, allowed: np.ndarray) -> Tuple[np.ndarray, List[float]]:
    yy, xx = np.where(mask)
    if not len(xx):
        return np.zeros_like(mask), [0.,0.,0.,0.]
    h,w = mask.shape
    pad = max(4,int(max(xx.max()-xx.min()+1,yy.max()-yy.min()+1)*.25))
    x0,x1=max(0,int(xx.min())-pad),min(w,int(xx.max())+pad+1)
    y0,y1=max(0,int(yy.min())-pad),min(h,int(yy.max())+pad+1)
    roi=np.zeros_like(mask);roi[y0:y1,x0:x1]=True
    return roi & allowed, [x0/w,y0/h,x1/w,y1/h]


def colour_stats(rgb: np.ndarray, mask: np.ndarray, reference_skin: np.ndarray) -> Dict[str, float]:
    kernel=np.ones((5,5),np.uint8)
    inner=cv2.erode(mask.astype(np.uint8),kernel).astype(bool)
    ring=cv2.dilate(mask.astype(np.uint8),kernel,iterations=3).astype(bool) & reference_skin & ~mask
    if inner.sum()<16 or ring.sum()<16:
        return {'available':0.}
    lab=cv2.cvtColor(rgb.astype(np.float32)/255.,cv2.COLOR_RGB2LAB)
    inside=np.median(lab[inner],axis=0);outside=np.median(lab[ring],axis=0)
    return {'available':1.,'lesion_L':round(float(inside[0]),2),'skin_L':round(float(outside[0]),2),
            'lesion_C':round(float(np.hypot(inside[1],inside[2])),2),
            'skin_C':round(float(np.hypot(outside[1],outside[2])),2),
            'clipped_fraction':round(float((rgb[inner].min(axis=1)>=248).mean()),4)}


def colour_plausible(stats: Dict[str,float]) -> bool:
    if not stats.get('available'):
        return False
    return not (stats['lesion_L']<stats['skin_L']-8. or
                stats['lesion_C']>stats['skin_C']+max(4.,stats['skin_C']*.30) or
                stats.get('clipped_fraction',0.)>.10)


def boundary_support(rgb: np.ndarray, mask: np.ndarray, valid: np.ndarray) -> Dict[str,float]:
    """Sample Lab differences across contour normals. A heuristic, not accuracy."""
    h,w=mask.shape
    edge=mask & ~cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    ys,xs=np.where(edge)
    if len(xs)<8:
        return {'available':0.,'support':0.}
    # Bound cost without replacing the actual returned mask by a polygon.
    take=np.linspace(0,len(xs)-1,min(1024,len(xs)),dtype=int);ys,xs=ys[take],xs[take]
    smooth=cv2.GaussianBlur(mask.astype(np.float32),(0,0),1.)
    gx=cv2.Sobel(smooth,cv2.CV_32F,1,0);gy=cv2.Sobel(smooth,cv2.CV_32F,0,1)
    norm=np.hypot(gx[ys,xs],gy[ys,xs]);ok=norm>1e-5
    dx=gx[ys,xs]/np.maximum(norm,1e-5);dy=gy[ys,xs]/np.maximum(norm,1e-5)
    xi=np.rint(xs+3*dx).astype(int);yi=np.rint(ys+3*dy).astype(int)
    xo=np.rint(xs-3*dx).astype(int);yo=np.rint(ys-3*dy).astype(int)
    ok &= (xi>=0)&(xi<w)&(xo>=0)&(xo<w)&(yi>=0)&(yi<h)&(yo>=0)&(yo<h)
    xi,yi,xo,yo=xi[ok],yi[ok],xo[ok],yo[ok]
    if len(xi)<8:
        return {'available':0.,'support':0.}
    usable=valid[yi,xi]&valid[yo,xo]&mask[yi,xi]&~mask[yo,xo]
    if usable.sum()<8:
        return {'available':0.,'support':0.}
    lab=cv2.cvtColor(rgb.astype(np.float32)/255.,cv2.COLOR_RGB2LAB)
    delta=np.linalg.norm(lab[yi[usable],xi[usable]]-lab[yo[usable],xo[usable]],axis=1)
    return {'available':1.,'support':round(float((delta>=3.).mean()),3),
            'median_delta_e76':round(float(np.median(delta)),2),'samples':int(usable.sum())}
