"""Keep geometric arithmetic separate from whether a proposal is fit to measure."""
from typing import Any, Dict, Optional

REASONS = {
    'skin-unverified': '皮肤范围尚未得到足够图像证据，请先核对所选部位和背景',
    'regions-unresolved': '部分区域未完成可靠分割，请核对橙色区域后再测量',
    'exclusions-unreviewed': '眼睛、毛发或其他排除范围仍需核对，暂不提供完整面积',
    'uncertainty-unreviewed': '边界存在待核对部分，暂不提供完整面积',
    'no-verified-regions': '本次未获得可测的浅色区域，不能据此排除皮肤问题',
    'model-unavailable': '视觉模型未给出可用定位，当前仅保留待核对参考',
}


def guard_annotation_measurement(measurement: Dict[str,Any], annotation: Optional[Dict[str,Any]]) -> Dict[str,Any]:
    if not annotation or annotation.get('review_state')=='user_reviewed':
        return dict(measurement)
    if annotation.get('protocol') == 'skin-seg-v2':
        result = dict(measurement, status='unavailable', availability='review_required')
        result['reasons'] = measurement.get('reasons') or ['请先核对皮肤与浅色范围后再测量']
        for key in ('area_percentage', 'area_cm2', 'color', 'border', 'extent', 'lesion_pixels', 'skin_pixels', 'region_count', 'regions'):
            result[key] = None
        return result
    refinement=annotation.get('refine') or {}
    eligible=refinement.get('version')=='pixel-refine-v2' and refinement.get('measurement_eligible') is True
    if eligible:
        return dict(measurement, availability='pixel_reference_not_clinical_validation')
    reasons=[REASONS.get(code,'标注尚未完成图像证据核对') for code in refinement.get('measurement_blockers',[])]
    if not reasons:
        reasons=['当前仅有粗定位或未经验证的精修结果，请先核对范围后再测量']
    old=measurement.get('reasons') or []
    result=dict(measurement, status='unavailable', availability='review_required',
                reasons=list(dict.fromkeys(reasons+old)))
    for key in ('area_percentage','area_cm2','color','border','extent','lesion_pixels','skin_pixels'):
        result[key]=None
    return result
