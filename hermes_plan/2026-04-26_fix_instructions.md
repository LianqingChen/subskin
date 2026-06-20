## 你是SubSkin项目后端工程师，请立即修复以下架构审计问题，按P0→P1顺序逐一完成。

### P0 立即修复（5项）

1. **OAuth异常泄露** (`api/oauth.py:68-72, 137-141`)
   - 微信登录和支付宝登录的 `except Exception as e` 中，将 `detail=f"微信登录失败: {str(e)}"` 和 `detail=f"支付宝登录失败: {str(e)}"` 改为通用错误消息 `detail="登录服务暂时不可用，请稍后重试"`
   - 在 logger.error 中保留完整 `str(e)` 用于服务端排查

2. **VASI异常泄露** (`api/vasi.py:82-83, 133-134, 188-189`)
   - 4处 `raise HTTPException(status_code=500, detail=f"...失败: {str(e)}")` 改为通用的 `detail="服务暂时不可用，请稍后重试"`
   - 在每处添加 `logger.error("...失败: %s", str(e))` 记录详细信息

3. **上传异常泄露** (`api/community.py:460, 484`)
   - `detail=f"上传失败: {str(e)}"` 改为通用 `detail="上传失败，请稍后重试"`
   - 添加 logger.error 记录实际异常

4. **开发模式验证码泄露** (`api/user.py:414-417, 428-431`)
   - 在返回开发模式验证码前增加守卫检查：`if os.getenv("ENV") == "development" and sms_provider == "log"` 才返回 code
   - 否则不返回 code 字段

5. **管理员手机号硬编码** (`api/user.py:454`)
   - 将 `{"15810004327", "17319030290", "15978713663", "18790010679"}` 替换为 `set(os.getenv("ADMIN_PHONES", "").split(","))` 
   - 若环境变量为空则用空集合（无人自动成为管理员）

### P1 下迭代修复（4项）

6. **跨API模块导入 - oauth导入user私有函数** (`api/oauth.py:18`)
   - `from web.backend.api.user import _get_user_response` 违规。将 `_get_user_response` 提取到新建的 `web/backend/services/user_serializer.py`
   - oauth.py 和 user.py 都从 serializer 导入

7. **跨API模块导入 - social导入community私有函数** (`api/social.py:287`)
   - `from web.backend.api.community import _post_to_model` 违规。将 `_post_to_model` 提取到 `web/backend/services/community.py` 的 `CommunityService` 中作为公开方法
   - social.py 通过 CommunityService 调用

8. **服务层框架依赖** (`services/credential.py:7-8`)
   - 移除 `from fastapi import HTTPException, status`
   - 创建 `web/backend/exceptions.py` 定义领域异常类 `CredentialException`、`NotFoundException`
   - credential.py 抛出领域异常，由 API 层转换为 HTTP 响应

9. **服务层跨服务私有函数导入** (`services/vasi.py:420`)
   - `from web.backend.services.rag import _get_llm_config` 违规
   - 将 `_get_llm_config` 以及 `services/content_safety.py` 中的重复实现合并提取到 `web/backend/utils/llm_config.py`
   - 定义公开函数 `get_llm_config()`（去掉下划线前缀）
   - vasi.py、rag.py、content_safety.py 都从 utils 导入

### 注意事项
- 所有改造后运行 `sudo systemctl restart subskin-backend` 验证服务正常
- 确保 Python 3.9 兼容（不用 `str|None` 等新语法）
