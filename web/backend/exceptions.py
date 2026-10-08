"""SubSkin 领域异常 — 服务层抛出，API层转换为HTTP响应。"""

from typing import List, Optional


class SubSkinException(Exception):
    """SubSkin 业务异常基类。"""


class CredentialConflictError(SubSkinException):
    """凭证冲突（已绑定同类型凭证 / 凭证已绑定其他账号）。"""

    def __init__(self, message: str = "凭证冲突"):
        super().__init__(message)


class CredentialNotFoundError(SubSkinException):
    """凭证不存在。"""

    def __init__(self, message: str = "凭证不存在"):
        super().__init__(message)


class HospitalNotFoundError(SubSkinException):
    """医院目录条目不存在或不可见。"""

    def __init__(self, message: str = "医院不存在或已下架"):
        super().__init__(message)


class HospitalReviewNotFoundError(SubSkinException):
    """评价不存在、已删除或无权操作。"""

    def __init__(self, message: str = "评价不存在或无权操作"):
        super().__init__(message)


class HospitalReviewRejectedError(SubSkinException):
    """评价内容未通过校验（长度、字段缺失、违规等）。"""

    def __init__(self, message: str = "评价内容不符合要求"):
        super().__init__(message)


class RGBSegmentationError(SubSkinException):
    """Safe domain error with an allowlisted machine-readable reason."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class StoryGenerationError(SubSkinException):
    """Safe, actionable creative generation error; unrelated to measurement."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


class ArtAdmissionRejected(StoryGenerationError):
    """Provider explicitly rejected admission; a later user retry is safe."""


class PlanningDocumentError(SubSkinException):
    """Safe error for a missing, disallowed or oversized archive document."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.status_code = status_code


class TerminalSessionError(SubSkinException):
    """终端会话不存在 / 名称非法 / 无法创建或关闭。"""

    def __init__(self, message: str = "终端会话不可用", status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class TerminalCommandRejected(TerminalSessionError):
    """命令被管理后台安全策略拒绝。"""

    def __init__(self, message: str = "命令被安全策略拒绝", reasons: Optional[List[str]] = None):
        super().__init__(message, status_code=403)
        self.reasons: List[str] = list(reasons or [])


class TerminalAgentError(SubSkinException):
    """AI 能力不可用（未配置 LLM）或未产出结果。"""

    def __init__(self, message: str = "AI 能力暂不可用", status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code
