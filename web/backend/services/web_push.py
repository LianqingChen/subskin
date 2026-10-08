"""Web Push 发送服务（RFC 8291 + RFC 8188 aes128gcm，VAPID 授权）。

浏览器/网页无法写入手机系统闹钟（iOS/Android 安全限制），Web Push 定时推送
是网页端最接近「闹钟」的机制：服务端在提醒时间向用户浏览器推送通知，
PWA 已安装时安卓可后台收到；iOS Safari 16.4+ 安装到主屏并授权后同样支持。

实现依赖 cryptography（ECDH P-256 / HKDF / AES-128-GCM）与 httpx，
不引入 pywebpush 额外依赖。
"""

import base64
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TTL = 3600


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class PushEndpointGone(Exception):
    """订阅端点已失效（404/410），应标记订阅失效。"""

    def __init__(self, endpoint: str):
        super().__init__(endpoint)
        self.endpoint = endpoint


def _make_vapid_headers(endpoint: str, local_pub_b64: str) -> Optional[Dict[str, str]]:
    """构造 VAPID 授权头（aud 从端点域名推导）。"""
    private_key_b64 = os.getenv("VAPID_PRIVATE_KEY", "")
    subject = os.getenv("VAPID_SUBJECT", "mailto:admin@subskin.cn")
    if not private_key_b64:
        return None
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        # aud = 推送服务源（scheme://host）
        origin = endpoint.split("/")[2] if "://" in endpoint else endpoint
        audience = f"https://{origin}"

        priv_raw = _b64url_decode(private_key_b64)
        private_key = ec.derive_private_key(
            int.from_bytes(priv_raw, "big"), ec.SECP256R1()
        )

        def _seg(obj: Any) -> str:
            return base64.urlsafe_b64encode(
                json.dumps(obj, separators=(",", ":")).encode()
            ).rstrip(b"=").decode()

        header = {"typ": "JWT", "alg": "ES256"}
        payload = {"aud": audience, "exp": int(time.time()) + 12 * 3600, "sub": subject}
        signing_input = f"{_seg(header)}.{_seg(payload)}".encode()
        signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        jwt = f"{signing_input.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
        t, k = jwt.rsplit(".", 1)
        return {
            "Authorization": f"vapid t={t}, k={local_pub_b64}",
            "Crypto-Key": f"dh={local_pub_b64}",
        }
    except Exception:
        logger.warning("web_push: VAPID 头构造失败", exc_info=True)
        return None


def send_web_push(
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    payload: Dict[str, Any],
) -> bool:
    """向单个订阅发送 Web Push 通知。404/410 时抛 PushEndpointGone。"""
    try:
        import httpx
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        # 1) ECDH 共享密钥
        local_private = ec.generate_private_key(ec.SECP256R1())
        remote_pub_raw = _b64url_decode(p256dh_key)
        remote_pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), remote_pub_raw
        )
        shared = local_private.exchange(ec.ECDH(), remote_pub)
        local_pub = local_private.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )
        local_pub_b64 = base64.urlsafe_b64encode(local_pub).rstrip(b"=").decode()

        auth = _b64url_decode(auth_key)

        # 2) HKDF：PRK_key = Extract(salt=auth, IKM=ecdh)；IKM = Expand(PRK, key_info)
        key_info = b"WebPush: info\x00" + local_pub + remote_pub_raw
        ikm = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=auth, info=key_info
        ).derive(shared)

        # 3) aes128gcm（RFC 8188）加密：明文末尾 2 字节分隔填充（RFC 8291）
        plaintext = json.dumps(payload, ensure_ascii=False).encode() + b"\x02\x00"
        salt = os.urandom(16)
        aesgcm = AESGCM(ikm)
        ciphertext = aesgcm.encrypt(salt[:12], plaintext, b"")
        body = salt + len(plaintext).to_bytes(4, "big") + b"\x00" + ciphertext

        vapid_headers = _make_vapid_headers(endpoint, local_pub_b64)
        headers = {
            "Content-Encoding": "aes128gcm",
            "TTL": str(_TTL),
            "Urgency": "high",
            "Content-Type": "application/octet-stream",
        }
        if vapid_headers:
            headers.update(vapid_headers)

        resp = httpx.post(endpoint, content=body, headers=headers, timeout=10)
        if resp.status_code in (200, 201, 202):
            return True
        if resp.status_code in (404, 410):
            raise PushEndpointGone(endpoint)
        logger.warning(
            "web_push: 推送失败 status=%s body=%s", resp.status_code, resp.text[:200]
        )
        return False
    except PushEndpointGone:
        raise
    except Exception:
        logger.warning("web_push: 发送异常", exc_info=True)
        return False
