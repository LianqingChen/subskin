"""pixel-refine-v2: image-supported masks or explicit unresolved regions.

A candidate polygon is a proposal, never a successful fallback measurement.
The time budget is an admission deadline; native SAM calls cannot be interrupted.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from web.backend.services import vasi_promptable
from web.backend.services.annotation_contract import encode_layer, raster_polygons
from web.backend.services.assessment_measurement import decode_mask
from web.backend.services.vasi_edge_segmentation import refine_mask_by_edges, refine_skin_region, segment_lesions_edge_aware
from web.backend.services.vasi_skin_mask import build_skin_mask
from web.backend.services.vasi_pixel_evidence import interior_prompts, local_roi, colour_stats, colour_plausible, boundary_support

logger = logging.getLogger(__name__)
REFINE_VERSION = 'pixel-refine-v2'
COLOR_SKIN, COLOR_LESION = (96,165,250), (0,170,100)
COLOR_UNCERTAIN, COLOR_EXCLUDED = (240,143,0), (100,116,139)
DEFAULT_TIME_BUDGET_S, DEFAULT_MAX_LESION_REGIONS = 25., 4
SAM_SCORE_MIN, IOU_MIN, AREA_RATIO_MIN, AREA_RATIO_MAX = .80, .20, .20, 3.
SKIN_CV_OVERLAP_MIN, MIN_COMPONENT_AREA = .35, 64
WORK_MAX_SIDE = 1280


def _env_float(name: str, default: float) -> float:
    try:
        value=float(os.getenv(name,str(default)))
        return value if math.isfinite(value) else default
    except (TypeError,ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name,default))


def is_enabled() -> bool:
    return os.getenv('VASI_PIXEL_REFINE','1').lower() not in ('0','false')


def _decode_rgb(image_bytes: bytes) -> Optional[np.ndarray]:
    try:
        photo=Image.open(io.BytesIO(image_bytes)).convert('RGB')
        photo.thumbnail((WORK_MAX_SIDE,WORK_MAX_SIDE))
        return np.asarray(photo)
    except (ValueError,OSError):
        return None


def _components(mask: np.ndarray, min_area: int = MIN_COMPONENT_AREA) -> List[np.ndarray]:
    if mask is None or not mask.any():
        return []
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),connectivity=8)
    indices=sorted((i for i in range(1,count) if stats[i,cv2.CC_STAT_AREA]>=min_area),
                   key=lambda i:-int(stats[i,cv2.CC_STAT_AREA]))
    return [labels==i for i in indices]


def _sam_points(mask: np.ndarray, width: int, height: int, negative_pool=None) -> List[Tuple[float,float,int]]:
    return interior_prompts(mask,width,height,negative_pool)


def _colour_stats(rgb: np.ndarray, mask: np.ndarray, skin: np.ndarray) -> Dict[str,float]:
    return colour_stats(rgb,mask,skin)


def _colour_plausible(stats: Dict[str,float]) -> bool:
    return colour_plausible(stats)


def _iou(a: np.ndarray,b: np.ndarray) -> float:
    union=int((a|b).sum())
    return float((a&b).sum())/union if union else 0.


def _resize_to(mask: np.ndarray,shape: Tuple[int,int]) -> np.ndarray:
    return cv2.resize(mask.astype(np.uint8),(shape[1],shape[0]),interpolation=cv2.INTER_NEAREST).astype(bool) if mask.shape!=shape else mask.astype(bool)


class _Budget:
    def __init__(self,seconds: float) -> None:
        self.deadline=time.monotonic()+max(0.,seconds)
    def exhausted(self) -> bool:
        return time.monotonic()>=self.deadline


def _accept(rgb, mask, component, roi, reference, reasons, engine, score=None, prompts=None) -> Tuple[Optional[np.ndarray],Dict[str,Any]]:
    evidence: Dict[str,Any]={}
    if mask is None or not mask.any():
        reasons.append('lesion:'+engine+'-empty')
        return None,evidence
    mask=_resize_to(mask,component.shape)
    ratio=float(mask.sum())/max(1,int(component.sum()));iou=_iou(mask,component)
    evidence.update(iou_vs_candidate=round(iou,3),area_ratio=round(ratio,3),score=score)
    reason=None
    if score is not None and (not math.isfinite(score) or score<SAM_SCORE_MIN):
        reason='sam-low-score'
    elif not AREA_RATIO_MIN<=ratio<=AREA_RATIO_MAX:
        reason=engine+'-area-ratio'
    elif iou<IOU_MIN:
        reason=engine+'-low-iou'
    elif int((mask&~roi).sum())>max(4,int(mask.sum()*.02)):
        reason=engine+'-outside-roi'
    if reason:
        reasons.append('lesion:'+reason)
        return None,evidence
    mask &= roi
    if prompts:
        height,width=mask.shape
        for x,y,label in prompts:
            px=min(width-1,max(0,int(round(x*width))));py=min(height-1,max(0,int(round(y*height))))
            if bool(mask[py,px]) != bool(label):
                reasons.append('lesion:prompt-disagreement')
                return None,evidence
    stats=_colour_stats(rgb,mask,reference);evidence['colour']=stats
    if not _colour_plausible(stats):
        reasons.append('lesion:colour-implausible' if stats.get('available') else 'lesion:colour-unavailable')
        return None,evidence
    boundary=boundary_support(rgb,mask,roi);evidence['boundary']=boundary
    if not boundary.get('available') or boundary['support']<.55:
        reasons.append('lesion:boundary-unsupported')
        return None,evidence
    return mask,evidence


def _layers(skin, lesion, uncertain, excluded, proposal, provenance, protocol='skin-outline-v1') -> Dict[str,Any]:
    h,w=skin.shape
    lesion &= skin & ~uncertain
    count,_=cv2.connectedComponents(lesion.astype(np.uint8),connectivity=8)
    pixels=int(skin.sum())
    return {'skin_layer_data_url':encode_layer(skin,COLOR_SKIN),
            'lesion_layer_data_url':encode_layer(lesion,COLOR_LESION),
            'annotation':{'protocol':protocol,'review_state':'pending','width':w,'height':h,
                'uncertain_layer_data_url':encode_layer(uncertain&skin,COLOR_UNCERTAIN),
                'excluded_layer_data_url':encode_layer(excluded,COLOR_EXCLUDED),
                'proposal_layer_data_url':encode_layer(proposal,COLOR_UNCERTAIN),
                'uncertain_pixels':int((uncertain&skin).sum()),'skin_pixels':pixels,
                'candidate_pixels':int(lesion.sum()),'region_count':max(0,count-1),
                'uncertain_percentage':round(float((uncertain&skin).sum())/pixels*100,2) if pixels else 0.,
                'uncertainty_kind':'unresolved_review_regions_not_statistical_ci','refine':provenance},
            'provenance':provenance}


def refine_annotation_layers(image_bytes: bytes, geometry: Dict[str,Any], *,
                             time_budget_s: Optional[float]=None,
                             max_lesion_regions: Optional[int]=None) -> Optional[Dict[str,Any]]:
    if not is_enabled():
        return None
    rgb=_decode_rgb(image_bytes)
    if rgb is None:
        return None
    h,w=rgb.shape[:2];start=time.monotonic()
    budget_s=min(60.,max(0.,time_budget_s if time_budget_s is not None else _env_float('VASI_PIXEL_REFINE_BUDGET_S',25.)))
    limit=min(64,max(0,max_lesion_regions if max_lesion_regions is not None else _env_int('VASI_PIXEL_REFINE_MAX_REGIONS',4)))
    budget=_Budget(budget_s)
    raster=lambda key:raster_polygons(geometry.get(key,[]),w,h)
    skin_candidate=raster('skin_regions');excluded=raster('excluded_regions')
    proposal=raster('lesion_regions');uncertain_input=raster('uncertain_regions')
    if not skin_candidate.any():
        return None
    skin=skin_candidate.copy();skin_engine='candidate';reasons=[]
    try:
        cv_skin=build_skin_mask(rgb)
        if cv_skin is not None and cv_skin.any() and _iou(cv_skin,skin_candidate)>=SKIN_CV_OVERLAP_MIN:
            refined=refine_skin_region(rgb,cv_skin,proposal)
            if refined is not None and refined.any():
                bounded=refined.astype(bool)&skin_candidate  # No neck/background expansion.
                if bounded.any():
                    skin=bounded;skin_engine='cv'
        if skin_engine=='candidate':
            reasons.append('skin:unverified-candidate')
    except Exception as exc:
        logger.info('Skin refinement unavailable (%s)',type(exc).__name__)
        reasons.append('skin:cv-error')
    skin_boundary=boundary_support(rgb,skin,np.ones((h,w),bool))
    skin_supported=skin_engine=='cv' and bool(skin_boundary.get('available')) and skin_boundary.get('support',0.)>=.55
    skin &= ~excluded  # Never reintroduce excluded tissue when empty.
    all_components=_components(proposal,min_area=1)
    reference=skin & ~proposal & ~uncertain_input
    unresolved=np.zeros((h,w),bool);lesion=np.zeros((h,w),bool)
    regions=[];sam_ready=None
    buffer=io.BytesIO();Image.fromarray(rgb).save(buffer,format='PNG');working_bytes=buffer.getvalue()
    key='pixel-v2-'+hashlib.sha256(working_bytes).hexdigest()[:24]
    for index,component in enumerate(all_components):
        local_reasons=[];chosen=None;evidence={};engine='unresolved'
        roi,box=local_roi(component,skin)
        prompts=_sam_points(component & skin & ~uncertain_input,w,h,reference)
        if index>=limit:
            local_reasons.append('lesion:region-limit')
        elif int(component.sum())<MIN_COMPONENT_AREA:
            local_reasons.append('lesion:too-small-for-automatic-refinement')
        elif budget.exhausted():
            local_reasons.append('lesion:budget-exhausted')
        elif not roi.any():
            local_reasons.append('lesion:no-valid-roi')
        else:
            try:
                if sam_ready is None:
                    sam_ready=bool(vasi_promptable.prepare_image(key,working_bytes))
                if sam_ready and not budget.exhausted():
                    prediction=vasi_promptable.predict_by_points(key,prompts,multimask=True,box=box)
                    if prediction and prediction.get('mask_b64_png'):
                        raw=decode_mask(prediction['mask_b64_png'])
                        chosen,evidence=_accept(rgb,raw,component,roi,reference,local_reasons,'sam',float(prediction.get('score') or 0.),prompts)
                        if chosen is not None:
                            engine='sam'
                else:
                    local_reasons.append('lesion:sam-unavailable')
            except Exception as exc:
                logger.info('SAM refinement unavailable (%s)',type(exc).__name__)
                local_reasons.append('lesion:sam-error')
            # All rejection paths clear chosen. CV has the same evidence gate.
            if chosen is None and not budget.exhausted():
                try:
                    cv_result=segment_lesions_edge_aware(rgb,region=roi)
                    cv_mask=(cv_result or {}).get('lesion_mask')
                    if cv_mask is not None:
                        parts=[m for m in _components(_resize_to(cv_mask,(h,w))) if _iou(m,component)>.05]
                        merged=np.zeros((h,w),bool)
                        for part in parts:merged |= part
                        chosen,evidence=_accept(rgb,merged,component,roi,reference,local_reasons,'edge-cv',prompts=prompts)
                        if chosen is not None:engine='edge-cv'
                except Exception as exc:
                    logger.info('CV refinement unavailable (%s)',type(exc).__name__)
                    local_reasons.append('lesion:cv-error')
            if chosen is not None and not budget.exhausted():
                try:
                    snapped=refine_mask_by_edges(rgb,chosen,region=roi)
                    checked,checked_evidence=_accept(rgb,snapped,component,roi,reference,[],'edge-snap',prompts=prompts)
                    if checked is not None:
                        chosen,evidence=checked,checked_evidence
                except Exception as exc:
                    logger.info('Edge snap unavailable (%s)',type(exc).__name__)
            if budget.exhausted():
                chosen=None;engine='unresolved';local_reasons.append('lesion:budget-exhausted')
        if chosen is None:
            unresolved |= component
            local_reasons.append('lesion:needs-user-review')
        else:
            lesion |= chosen
        reasons.extend(local_reasons)
        regions.append({'index':index,'status':'accepted' if chosen is not None else 'unresolved',
                        'engine':engine,'candidate_pixels':int(component.sum()),'roi_box':box,
                        'reasons':list(dict.fromkeys(local_reasons)),'evidence':evidence})
    uncertain=(uncertain_input|unresolved)&skin
    blockers=[]
    if not skin_supported:blockers.append('skin-unverified')
    if any(r['status']=='unresolved' for r in regions):blockers.append('regions-unresolved')
    if not regions:blockers.append('no-verified-regions')
    if excluded.any():blockers.append('exclusions-unreviewed')
    if uncertain.any():blockers.append('uncertainty-unreviewed')
    accepted=sum(r['status']=='accepted' for r in regions)
    provenance={'version':REFINE_VERSION,'status':'refined' if not blockers else 'partial' if accepted else 'candidate-only',
                'measurement_eligible':not blockers,'measurement_blockers':blockers,
                'engine':{'skin':skin_engine,'lesion':[r['engine'] for r in regions]},
                'regions':regions,'skin_boundary':skin_boundary,'scope_locked':True,
                'fallback_reasons':list(dict.fromkeys(reasons)),
                'timings':{'total_s':round(time.monotonic()-start,2)},'budget_s':budget_s,
                'max_lesion_regions':limit,'lesion_regions_total':len(regions),
                'unresolved_region_count':len(regions)-accepted}
    logger.info('Pixel refinement %s: %d accepted, %d unresolved',REFINE_VERSION,accepted,len(regions)-accepted)
    return _layers(skin,lesion,uncertain,excluded,proposal,provenance)


def cv_only_layers(image_bytes: bytes) -> Optional[Dict[str,Any]]:
    """Keep ungrounded CV proposals orange and unmeasurable, never final lesions."""
    if not is_enabled():return None
    rgb=_decode_rgb(image_bytes)
    if rgb is None:return None
    try:
        skin=build_skin_mask(rgb)
        if skin is None or not skin.any():return None
        candidate=(segment_lesions_edge_aware(rgb,region=skin) or {}).get('lesion_mask')
        candidate=_resize_to(candidate,rgb.shape[:2]) if candidate is not None else np.zeros(rgb.shape[:2],bool)
    except Exception as exc:
        logger.info('CV reference unavailable (%s)',type(exc).__name__)
        return None
    empty=np.zeros(rgb.shape[:2],bool)
    regions=_components(candidate,min_area=1)
    provenance={'version':REFINE_VERSION,'status':'cv-fallback','measurement_eligible':False,
                'measurement_blockers':['model-unavailable','skin-unverified','regions-unresolved'],
                'engine':{'skin':'candidate','lesion':['unresolved']*len(regions)},
                'lesion_regions_total':len(regions),'unresolved_region_count':len(regions),
                'fallback_reasons':['model:unavailable-review-only']}
    return _layers(skin.astype(bool),empty,candidate,empty,candidate,provenance)
