# RGB 任务闭环部署与回退

本批为普通RGB照片的首期工程闭环，不是模型精度已经达标的发布。未取得训练数据授权前，注册表保持disabled，使用CV候选与SAM交互参考，用户核对后才给测量。

## 组成

- 新增rgb_segmentation_jobs表，包含owner、幂等请求、运行状态/租约/截止时间、测评链接和修订号；不修改或删除旧表/旧记录。
- 新增私有二值Mask版本目录data/rgb_segmentation，以及独立subskin-rgb-worker服务。
- 新手帐使用/segmentation-jobs；旧/assess和旧分层协议保留。RGB记录的旧轮廓写入口拒绝无版本保护的更新。
- 新记录原图视图使用现有/api/files/serve/vasi/所有权契约。原始文件留在私有job目录；显示与测量使用已转正的1024上限工作图，记录缩放矩阵。
- 面积、独立区域数量和图像位置来自Mask。区域详情最多返回128条并明确标记截断；数量/面积始终包含全部像素，原始Mask保留全部区域。bbox_pixels格式为x,y,width,height。
- 用户修正不进入旧反馈采集/自循环训练。模型训练只接受单独提供的获授权、已审核清单。

## 资源与生命周期

当前单机单worker，禁止直接多机复制服务而不实现分布式租约。单worker最多1个推理子进程，2 CPU配额、4GB进程组内存上限；每用户最多2个活动任务，全局16个活动任务，每用户24小时260次任务，保守估算存储上限1GB，磁盘不足2GB时拒绝新写入。模型调用90秒全任务截止；主API只读写任务，原生推理在可回收子进程运行。

用户核对每记录最多100次，照片数据跨修订用硬链接复用。不再引用的临时修订清理，失败/取消/无有效记录的任务7天后清理；有效记录保留原始和修订证据。账户删除后最多一个清理周期（约一小时）移除相关新任务工件，晚到任务不能创建新测评。

## 发布顺序（需用户本批明确确认）

1. 将已验证的变更清单同步到/root/subskin，保留逐文件回退副本与源SHA；不覆盖不在清单中的修改。
2. 记录DEPLOY_LOG；构建staging包，不发布正式前端。
3. 共享后端重启会在现有create_all流程创建唯一新增任务表。健康检查和新能力端点成功后，再安装并启动scripts/subskin-rgb-worker.service。
4. 校验/api/vasi/rgb-capabilities worker_ready=true，两站/api/health正常；核对进程资源限制和任务表字段。
5. 发布测试前端并验证version/manifest/SW/入口；正式前端版本与入口SHA保持不变。
6. 用隔离数据库的API测试及scripts/verify_rgb_worker.py验证，不把合成照片保存为真实用户记录。真实用户上传与触控交互需在可用登录通道中验收。

常规命令：

```bash
systemctl restart subskin-backend
install -m 644 scripts/subskin-rgb-worker.service /etc/systemd/system/subskin-rgb-worker.service
systemctl daemon-reload
systemctl enable --now subskin-rgb-worker
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/vasi/rgb-capabilities
```

不要在未获本批共享后端确认前运行这些命令。当前计划与真实部署状态以DEPLOY_LOG为准。

## 回退

先停止新worker并保留任务数据，再恢复本批修改前的后端文件、重启共享后端；恢复测试前端入口和旧哈希资源。新增任务表不删除、不回滚用户数据。worker只读取最小配置data/rgb-worker.env（当前SQLite数据库路径及RGB配置），不加载问答等模块的API密钥；网络访问被禁用，系统目录只读，仅data目录可写。部署时须从共享后端配置核对数据库路径，不能在非SQLite环境直接照搬此单机配置。

新建的RGB记录若旧前端不能编辑，应保留只读记录并提示升级，不进入旧算法重算或训练。

## 已知限制

- 当前没有经过验证的专用RGB权重；不能承诺自动精准识别。初始皮肤候选的解剖部位仍需用户核对。
- 现有MaskEditor为本批前已存在的巨型组件，本批仅接入独立远端选择composable，没有把整套新业务塞入绘图代码；其拆分属于保留技术债，不能声称全部架构规范已满足。
- API与数据校验、真实SAM的合成流程、取消/超时、训练导出评测可自动验证；浏览器连接不可用时不得宣称实机视觉/触控验收完成。
