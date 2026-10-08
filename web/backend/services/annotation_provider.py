"""Bounded vision proposals; source identity survives pixel refinement."""
import asyncio
import base64
import io
import logging
import os
import time
from typing import Any, Dict, Optional

from PIL import Image
from web.backend.services.annotation_contract import AnnotationContractError, parse_annotation, render_annotation
from web.backend.services.annotation_prompt import annotation_prompt
from web.backend.utils.llm_config import get_llm_config

logger=logging.getLogger(__name__)


def _bounded_env(name: str, default: int, low: int, high: int) -> int:
    try:
        return min(high,max(low,int(os.getenv(name,str(default)))))
    except (ValueError,TypeError):
        return default


async def propose_annotation(image_bytes: bytes, body_site: str) -> Dict[str,Any]:
    from openai import AsyncOpenAI
    config=get_llm_config('vasi');model=config.get('vision_model')
    if not model or not config.get('api_key') or not config.get('base_url'):
        raise AnnotationContractError('当前配置没有可用的视觉模型，请先配置支持图片输入的模型')
    photo=Image.open(io.BytesIO(image_bytes)).convert('RGB');photo.thumbnail((1536,1536))
    stream=io.BytesIO();photo.save(stream,format='JPEG',quality=95)
    encoded=base64.b64encode(stream.getvalue()).decode('ascii')
    # One request normally; at most one format/truncation retry under one deadline.
    attempts=1+_bounded_env('VASI_ANNOTATION_RETRIES',0,0,1)
    deadline=time.monotonic()+_bounded_env('VASI_ANNOTATION_TOTAL_TIMEOUT',180,30,240)
    layers: Optional[Dict[str,Any]]=None
    document: Dict[str,Any]={}
    last_error: Optional[AnnotationContractError]=None
    for attempt in range(attempts):
        retryable=True
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        try:
            async with AsyncOpenAI(api_key=config['api_key'],base_url=config['base_url'],max_retries=0,timeout=remaining) as client:
                response=await asyncio.wait_for(client.chat.completions.create(
                    model=model,temperature=0,max_tokens=_bounded_env('VASI_OUTLINE_VLM_MAX_TOKENS',32000,2048,32768),
                    messages=[{'role':'user','content':[
                        {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+encoded}},
                        {'type':'text','text':annotation_prompt(body_site)},
                    ]}],
                ),timeout=remaining)
            choice=response.choices[0]
            if choice.finish_reason=='length':
                raise AnnotationContractError('定位信息未完整返回，请稍后重试')
            document=parse_annotation(choice.message.content or '')
            retryable=document.get('status')!='not_assessable'
            layers=await asyncio.to_thread(render_annotation,document,photo.width,photo.height)
            break
        except AnnotationContractError as exc:
            last_error=exc
            if not retryable or attempt+1>=attempts:break
            logger.info('Annotation format retry %d/%d',attempt+1,attempts)
        except Exception as exc:
            logger.warning('Annotation provider unavailable (%s)',type(exc).__name__)
            last_error=AnnotationContractError('视觉定位暂未完成，请重拍或手动核对范围')
            break
    if layers is None:
        raise last_error or AnnotationContractError('视觉定位超时，请稍后重试')
    layers['annotation'].update(provider=config.get('provider') or 'configured',model=model)
    return {'vasi_score':0.,'area_percentage':0.,'classification':'未确定','stage':'未知',
            'confidence':None,'contours':[],'source':'vision-outline-v1','details':layers,
            'raw_response':{'source':'vision-outline-v1','protocol':'skin-outline-v1','geometry':document},
            'visual_features':None}
