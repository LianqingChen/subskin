# 风险应对方案 - AI模型与对象存储

> **版本**: 1.0  
> **日期**: 2026-04-07  
> **状态**: 可执行方案  

---

## 概述

本文档针对照片上传+AI知识库功能开发中的两个关键风险，提供具体可落地的应对方案。

---

## 风险一：AI模型开发风险

### 风险描述
- **影响等级**: 高
- **发生概率**: 中（40%）
- **具体表现**: 
  - 模型训练时间超出预期
  - 模型准确率未达到80%基准
  - 推理延迟超过10秒目标
  - 模型部署环境配置复杂

### 应对方案：三阶段渐进式交付

#### 阶段1：Mock服务先行（Day 1完成）🎯

**目标**: 快速验证业务逻辑和用户体验，为模型开发争取时间

**实施方案**:
```
文件结构:
web/backend/services/
├── ai_analysis/
│   ├── base.py              # AI服务抽象基类
│   ├── mock_service.py      # Mock实现（优先）
│   ├── real_service.py      # 真实模型实现
│   └── factory.py          # 服务工厂（环境切换）
```

**Mock服务特性**:
1. **智能返回**（基于照片元数据模拟分析）
   ```python
   def analyze_photo(photo_data):
       # 根据身体部位和文件大小生成"合理"的分析结果
       if body_part == "face":
           return mock_face_analysis()
       elif body_part == "hand":
           return mock_hand_analysis()
       # ...
   ```

2. **可配置响应延迟**
   ```python
   MOCK_DELAY = 3.0  # 秒，模拟真实延迟
   ```

3. **随机置信度**（测试前端UI多样性）
   ```python
   confidence = random.uniform(0.65, 0.95)
   ```

4. **Mock标记**（前端显示"演示模式"）
   ```json
   {
     "ai_info": {
       "is_mock": true,
       "message": "当前使用演示模式，AI分析结果为模拟数据"
     }
   }
   ```

**切换机制**:
```python
# 环境变量控制
USE_MOCK_AI = os.getenv("USE_MOCK_AI", "true") == "true"

ai_service = AIAnalysisFactory.create(USE_MOCK_AI)
```

**验收标准**:
- [x] Mock服务返回完整分析结构
- [x] 前端能正常展示Mock结果
- [x] 用户流程可完整走通

---

#### 阶段2：轻量级模型集成（Day 2上午）🤖

**目标**: 集成预训练模型，提供基础诊断能力

**实施方案**:

**使用开源预训练模型**:
1. **白斑检测模型**: 使用医学图像分割模型（如UNet、SAM）
   - 来源: Hugging Face `medical-segmentation/vitiligo-detection`
   - 优势: 无需从零训练，直接Fine-tune

2. **严重程度分类**: 使用ResNet/ViT分类模型
   - 来源: `microsoft/resnet-50`（ImageNet预训练）
   - 优势: 快速微调，准确率可接受

3. **模型部署方案**:
   ```python
   # 使用ONNX Runtime加速推理
   import onnxruntime as ort
   
   session = ort.InferenceSession("model.onnx")
   ```

**轻量级模型性能目标**:
| 指标 | 目标值 | 备注 |
|------|--------|------|
| 推理延迟 | < 3秒 | CPU推理 |
| 准确率 | > 70% | 接受阶段1水平 |
| 模型大小 | < 100MB | 易于部署 |

**集成步骤**:
1. 下载预训练模型权重
2. 实现模型加载和推理封装
3. 添加模型版本管理
4. 编写单元测试
5. 切换环境变量 `USE_MOCK_AI=false`

**降级策略**:
```python
try:
    result = real_service.analyze(photo_data)
except Exception as e:
    logger.error(f"Real AI service failed: {e}")
    # 自动降级到Mock
    result = mock_service.analyze(photo_data)
    result["ai_info"]["degraded"] = True
```

**验收标准**:
- [ ] 模型推理成功
- [ ] 响应时间 < 5秒
- [ ] 准确率 > 70%
- [ ] 异常时自动降级到Mock

---

#### 阶段3：专业模型训练（Phase 2，延后）🎓

**目标**: 训练专业级模型，达到生产要求

**前提条件**:
- 收集至少500张标注的白癜风图像
- 配备GPU训练环境（或使用云服务）

**训练方案**:
1. **数据准备**
   ```bash
   # 标注工具: LabelMe / CVAT
   # 数据增强: Albumentations
   ```

2. **模型架构**
   - Backbone: EfficientNet / ConvNeXt
   - Head: 多任务学习（分类+分割）
   - 训练框架: PyTorch Lightning

3. **训练策略**
   - Batch Size: 16（GPU显存8GB）
   - Learning Rate: 1e-4（带Cosine Annealing）
   - Epochs: 100（Early Stopping）
   - 优化器: AdamW

4. **性能目标**
   - 准确率: > 85%
   - mIoU: > 75%
   - 推理延迟: < 2秒

**交付时间线**:
| 任务 | 工期 | 负责人 |
|------|------|--------|
| 数据收集与标注 | 2周 | 标注团队 |
| 模型训练 | 1周 | AI工程师 |
| 模型验证与部署 | 3天 | AI工程师 |

---

### 风险缓解效果评估

| 阶段 | 时间 | 价值 | 风险降低 |
|------|------|------|----------|
| Mock服务 | 1天 | 功能可用 | 60% |
| 轻量级模型 | 1天 | 基础诊断 | 80% |
| 专业模型 | 3周 | 生产级别 | 95% |

---

## 风险二：对象存储配置风险

### 风险描述
- **影响等级**: 中
- **发生概率**: 低（20%）
- **具体表现**:
  - 云服务商SDK兼容性问题
  - 网络连接超时
  - 存储配额不足
  - 权限配置错误

### 应对方案：存储抽象层 + 多级降级

#### 方案1：存储抽象层设计 🏗️

**目标**: 统一存储接口，支持多种后端

**接口设计**:
```python
from abc import ABC, abstractmethod
from typing import Tuple, Optional

class StorageBackend(ABC):
    """存储后端抽象基类"""
    
    @abstractmethod
    def upload_file(
        self, 
        file_path: str, 
        object_key: str,
        metadata: dict = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        上传文件
        
        Returns:
            (success, url, error_message)
        """
        pass
    
    @abstractmethod
    def get_presigned_url(
        self, 
        object_key: str, 
        expires_in: int = 300
    ) -> Optional[str]:
        """获取预签名URL"""
        pass
    
    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        """删除文件"""
        pass
    
    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """检查文件是否存在"""
        pass
```

**实现列表**:
```
web/backend/services/storage/
├── backend.py              # 抽象基类
├── oss_backend.py          # 阿里云OSS实现
├── s3_backend.py           # AWS S3实现
├── local_backend.py         # 本地文件系统实现（降级）
├── memory_backend.py       # 内存存储（测试用）
└── factory.py              # 后端工厂
```

---

#### 方案2：多级降级策略 ⬇️

**降级链路**:
```
Primary: 阿里云OSS / AWS S3
    ↓ (失败)
Fallback 1: 本地文件系统
    ↓ (失败)
Fallback 2: 内存存储（仅临时）
    ↓ (失败)
Return Error
```

**实现逻辑**:
```python
class StorageService:
    def __init__(self):
        self.backends = []
        
        # 按优先级添加后端
        if os.getenv("USE_OSS") == "true":
            self.backends.append(OSSBackend())
        if os.getenv("USE_S3") == "true":
            self.backends.append(S3Backend())
        
        # 降级备选
        self.backends.append(LocalBackend())
        self.backends.append(MemoryBackend())
    
    def upload_file(self, file_path: str, object_key: str):
        for i, backend in enumerate(self.backends):
            try:
                success, url, error = backend.upload_file(file_path, object_key)
                if success:
                    if i > 0:
                        logger.warning(
                            f"Storage degraded to {backend.__class__.__name__}"
                        )
                    return url
            except Exception as e:
                logger.error(f"{backend.__class__.__name__} failed: {e}")
                continue
        
        raise StorageError("All storage backends failed")
```

**降级通知**:
```python
# 在响应中标记降级状态
{
    "storage_info": {
        "backend": "LocalFileSystem",
        "degraded": true,
        "message": "云存储暂时不可用，使用本地存储"
    }
}
```

---

#### 方案3：本地存储备选方案 💾

**目标**: 开发环境独立运行，不依赖外部服务

**目录结构**:
```
local_storage/
├── photos/
│   ├── original/
│   └── thumbnails/
├── documents/
└── tmp/
```

**实现代码**:
```python
class LocalBackend(StorageBackend):
    def __init__(self, base_path: str = "./local_storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def upload_file(self, file_path: str, object_key: str):
        dest_path = self.base_path / object_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(file_path, dest_path)
        
        # 返回相对路径URL
        url = f"/local_storage/{object_key}"
        return True, url, None
    
    def get_presigned_url(self, object_key: str, expires_in: int = 300):
        # 本地存储无需预签名URL
        return f"/local_storage/{object_key}"
```

**FastAPI静态文件服务**:
```python
from fastapi.staticfiles import StaticFiles

app.mount("/local_storage", StaticFiles(directory="local_storage"), name="local_storage")
```

---

#### 方案4：配置管理与健康检查 🔍

**环境变量配置**:
```bash
# .env
STORAGE_TYPE=oss  # oss/s3/local
USE_OSS=true
USE_S3=false
USE_LOCAL=true  # 作为降级备选

# 阿里云OSS配置
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx
OSS_BUCKET=subskin-photos
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com

# AWS S3配置
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_BUCKET=subskin-photos
AWS_REGION=us-east-1
```

**健康检查端点**:
```python
@app.get("/api/storage/health")
async def storage_health():
    backends_status = []
    
    for backend in storage_service.backends:
        try:
            # 简单的连通性测试
            is_healthy = backend.health_check()
            backends_status.append({
                "name": backend.__class__.__name__,
                "status": "healthy" if is_healthy else "unhealthy"
            })
        except Exception as e:
            backends_status.append({
                "name": backend.__class__.__name__,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "primary_backend": storage_service.backends[0].__class__.__name__,
        "backends": backends_status
    }
```

**健康检查响应示例**:
```json
{
  "primary_backend": "OSSBackend",
  "backends": [
    {
      "name": "OSSBackend",
      "status": "unhealthy",
      "error": "Connection timeout"
    },
    {
      "name": "S3Backend",
      "status": "healthy"
    },
    {
      "name": "LocalBackend",
      "status": "healthy"
    }
  ]
}
```

---

### 存储方案对比

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| 阿里云OSS | 高可用、CDN加速、生命周期管理 | 依赖外部服务 | 生产环境 |
| AWS S3 | 全球可用、SDK成熟 | 国际网络延迟 | 国际用户 |
| 本地文件系统 | 零依赖、快速开发 | 无CDN、需备份 | 开发/测试 |
| 内存存储 | 极快速度 | 不持久化 | 单元测试 |

---

### 配置迁移指南

**开发环境 → 生产环境**:
```bash
# 开发环境
export USE_MOCK_AI=true
export STORAGE_TYPE=local

# 测试环境
export USE_MOCK_AI=false
export STORAGE_TYPE=oss
export USE_LOCAL=true  # 降级备选

# 生产环境
export USE_MOCK_AI=false
export STORAGE_TYPE=oss
export USE_LOCAL=false
```

---

## 应对方案总结

### AI模型风险缓解

| 阶段 | 实施时间 | 交付物 | 风险降低度 |
|------|----------|--------|------------|
| Mock服务 | Day 1 | 可演示的完整功能 | 60% |
| 轻量级模型 | Day 2 | 基础诊断能力 | 80% |
| 专业模型 | Phase 2 | 生产级AI服务 | 95% |

### 对象存储风险缓解

| 方案 | 实施时间 | 风险降低度 | 备注 |
|------|----------|------------|------|
| 存储抽象层 | Day 1 | 40% | 统一接口 |
| 多级降级 | Day 1 | 70% | 自动切换 |
| 本地存储备选 | Day 1 | 50% | 独立运行 |
| 健康检查 | Day 1 | 30% | 实时监控 |

---

## 执行检查清单

### Day 1 检查清单
- [ ] 创建AI服务抽象基类和工厂
- [ ] 实现Mock AI服务
- [ ] 创建存储抽象层和工厂
- [ ] 实现本地文件系统存储
- [ ] 实现多级降级逻辑
- [ ] 添加环境变量配置
- [ ] 实现健康检查端点
- [ ] 编写单元测试

### Day 2 检查清单
- [ ] 集成轻量级预训练模型
- [ ] 实现自动降级逻辑
- [ ] 测试降级场景
- [ ] 更新API文档
- [ ] 部署到测试环境
- [ ] 进行压力测试

---

**文档状态**: 已完成，可立即执行

**下一步**: 根据此方案开始编码实施
