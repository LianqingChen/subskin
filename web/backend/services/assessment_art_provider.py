"""Bailian asynchronous image generation. Only prompts and abstract contour guides leave this service."""
import base64
import io
import re
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import requests
from PIL import Image
from web.backend.exceptions import StoryGenerationError, ArtAdmissionRejected
from web.backend.utils.llm_config import get_llm_config

MODEL = 'qwen-image-3.0-pro'


def connection() -> Dict[str, str]:
    config = get_llm_config('vasi')
    parts = urlsplit(config.get('base_url', ''))
    if not config.get('api_key') or parts.scheme != 'https' or not (parts.hostname or '').endswith('.aliyuncs.com'):
        raise StoryGenerationError('百炼生图配置暂不可用', 503)
    return {'root': 'https://' + parts.netloc, 'key': config['api_key']}


def submit(prompt: str, guide: Optional[str] = None) -> str:
    config = connection()
    content = ([{'image': guide}] if guide else []) + [{'text': prompt}]
    response = requests.post(config['root'] + '/api/v1/services/aigc/image-generation/generation',
        headers={'Authorization': 'Bearer ' + config['key'], 'X-DashScope-Async': 'enable'},
        json={'model': MODEL, 'input': {'messages': [{'role': 'user', 'content': content}]},
              'parameters': {'size': '1024*1024', 'n': 1, 'watermark': False, 'prompt_extend': True}}, timeout=(5, 25))
    if not response.ok:
        raise ArtAdmissionRejected('艺术画面暂未生成，请稍后重试', 503)
    task = (response.json().get('output') or {}).get('task_id', '')
    if not isinstance(task, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', task):
        raise StoryGenerationError('艺术任务状态暂未确认', 503)
    return task


def poll(task: str) -> Dict[str, Any]:
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', task):
        raise StoryGenerationError('艺术任务暂不可用', 503)
    config = connection()
    response = requests.get(config['root'] + '/api/v1/tasks/' + task, headers={'Authorization': 'Bearer ' + config['key']}, timeout=(5, 20))
    if not response.ok:
        raise StoryGenerationError('艺术画面仍在准备，请稍后重试', 503)
    output = response.json().get('output') or {}
    state = output.get('task_status')
    if state in ('PENDING', 'RUNNING'): return {'status': 'pending'}
    if state in ('FAILED', 'CANCELED', 'UNKNOWN'): return {'status': 'failed', 'retryable': True}
    if state == 'SUCCEEDED':
        for choice in output.get('choices', []):
            for item in choice.get('message', {}).get('content', []):
                if isinstance(item.get('image'), str):
                    return {'status': 'ready', 'image_data_url': download_image(item['image'])}
    raise StoryGenerationError('艺术画面结果暂不可用', 503)


def download_image(url: str) -> str:
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
            or not re.fullmatch(r'dashscope[-a-z0-9]*\.oss[-a-z0-9.]*\.aliyuncs\.com', parts.hostname or '')):
        raise StoryGenerationError('艺术图片来源校验失败', 503)
    # Never forward credentials to the signed image host or follow redirects.
    with requests.get(url, timeout=(5, 25), stream=True, allow_redirects=False) as response:
        if response.status_code != 200: raise StoryGenerationError('艺术图片暂不可用', 503)
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 8 * 1024 * 1024: raise StoryGenerationError('艺术图片过大', 503)
            chunks.append(chunk)
    try:
        image = Image.open(io.BytesIO(b''.join(chunks)))
        if image.width * image.height > 2048 * 2048: raise ValueError('dimensions')
        image = image.convert('RGB'); image.thumbnail((1024, 1024))
        output = io.BytesIO(); image.save(output, format='JPEG', quality=88)
        if len(output.getvalue()) > 1024 * 1024: raise ValueError('encoded size')
    except (ValueError, OSError, Image.DecompressionBombError):
        raise StoryGenerationError('艺术图片格式暂不可用', 503)
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode()
