"""SubSkin 领域异常 — 服务层抛出，API层转换为HTTP响应。"""


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
