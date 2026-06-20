# 调研发现 — 体检报告解读功能

## 竞品分析

### 蚂蚁集团阿福 (AI Health Friend)
- **核心亮点**: 多模态输入（照片/PDF）+ 过程透明化 + 分流式行动推荐
- **过程可视化**: 上传→扫描→脱敏→分析→整理结论 实时进度
- **隐私优先**: "无痕拍"模式自动脱敏个人信息
- **家族账户**: 支持添加多位家庭成员，分别管理体检报告
- **行动路由**: 解读后 继续AI问诊 / 真人医生解读 双路径
- **健康微目标**: 将解读转化为可执行的行为目标

### 爱康国宾 (iKang)
- **核心亮点**: 异常结果分级展示 + 历年对比 + 一键预约挂号
- **三级展示结构**: 总检建议 → 异常结果汇总 → AI解读报告
- **人体视图**: 异常指标直接在人体示意图上标注
- **复查计划**: 按疾病复查频率自动生成提醒
- **服务连贯性**: 解读→快速问诊→预约挂号→就医绿通 一链到底

### Apple Health (Lab Results)
- **核心亮点**: "在你的范围内"替代原始数字 + 个人基线对比
- **三层披露**: 每日摘要 → 个人基线卡 → 每周回顾
- **混合展示**: 数字 + 自然语言 + 图形 三位一体
- **颜色克制**: 红色仅用于真正危急的指标，避免制造焦虑

### 开源项目关键发现

| 项目 | 语言 | 适用性 |
|------|------|--------|
| **parselabs** | Python | 实验室结果提取 + AI验证 + 单位转换，MIT协议 |
| **MOSAICX** | Python | 医疗影像报告处理 + 去标识化，Apache 2.0 |
| **RxLM-Med** | Python | System 2推理 + RAG + 交通灯安全协议 |
| **pdfplumber** | Python | 无边框表格提取准确率92%，最适合中文体检报告 |
| **OpenDataLoader PDF** | Python | 综合准确率97.9%但资源消耗大 |
| **fhir.resources** | Python | FHIR标准建模，Pydantic V2驱动 |
| **medspacy** | Python | 临床NLP，Section检测 + 上下文分析 |

## 当前代码问题诊断

### 文件查看链路
- `ReportDetailPage.vue:180` → `getFileViewUrl(file.id, token)` → `/api/files/view/{id}?access_token=...`
- `files.py:116` → `view_file_as_html()` → auth → ownership check → viewer_template
- 🔴 问题: 用户token与报告owner不匹配时返回404
- 🔴 问题: viewer_template.html可能不被微信WebView支持
- 🔴 问题: PDF预转换失败的fallback仅提供下载链接

### AI解读截断点
| 位置 | 截断量 | 影响 |
|------|--------|------|
| `report_interpreter.py:210` | `raw_text[:2000]` | 🔴 主因: 报告全文截断 |
| `report_interpreter.py:243` | `full_text[:12000]` | 🟡 次因: full_text路径也有限制 |
| `rag.py:827` | `doc_text[:3000]` | 🟡 RAG路径截断 |
| `medical_report.py:594` | `f.read()[:5000]` | 🟡 文本文件截断 |

### 数据溯源缺失
- `AbnormalItem` 无 `source_indicators` / `source_text_excerpt` 字段
- `SectionIndicator` 无 page/line 定位信息
- LLM prompt 未要求标明每个结论的数据来源

### 用户档案关联
- `MedicalReport` 仅有 `user_id` → User 关联
- `PatientProfile` 已存在（name/gender/birth_date）但未被 `MedicalReport` 链接
- `user_context` 由前端手动传参，未从 PatientProfile 自动获取

## 技术方案建议

### PDF解析推荐栈
1. **首选**: `pdfplumber` — 92% 无边框表格准确率，纯Python
2. **高级**: `OpenDataLoader PDF` — 97.9% 准确率但更重
3. **OCR fallback**: 通义千问Vision → Text LLM（已在用）

### LLM Prompt改造关键点
1. 强制覆盖所有Section: "必须列出报告中出现的每一个检查项目"
2. 正常+异常指标都展示: "正常指标以列表展示，异常指标详细解读"
3. 结论溯源: "每个结论标明依据的具体指标名称和原始数值"
4. 置信度标注: "对不确定的推断，注明置信度并建议核实"

### 架构设计原则
- 渐进式展示 (Progressive Disclosure): 摘要 → 分项详细 → 原始数据
- 行动导向 (Actionable): 每个解读结论都指向下一步
- 隐私优先 (Privacy-first): 上传自动脱敏，数据本地处理
- 可溯源 (Traceable): 每个结论 → 源指标 → 原文位置
