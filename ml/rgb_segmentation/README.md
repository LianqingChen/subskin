# RGB 白斑候选分割：私有训练与评测

这是普通手机RGB照片的五类语义分割工具链。不是现成、已验证的白癜风模型，也不提供医学确诊。

## 数据准备

工具不会查询SubSkin用户数据库或自动收集修正。操作者必须先取得适用于模型训练的真实授权、审核像素标注，并给受试者分配不含姓名/手机号/邮箱的伪匿名ID。清单中的授权/审核标记是流程记录，不替代真实授权凭据或临床审核。

在私有目录保存manifest.json、已经转正为RGB的图片和同尺寸灰度PNG标签。标签：0背景/衣物，1正常皮肤，2疑似脱色皮肤，3遮挡/非皮肤器官，4反光等不可判读区域；255为无法确定的像素。照片EXIF方向须已应用并清除或设为1，避免标签错位。

清单结构（占位值需替换；至少包含train、validation、test三个split）：

```json
{
  "labels": ["background", "normal_skin", "depigmented_skin", "occlusion", "unreadable"],
  "coordinate_frame": "normalized_rgb",
  "synthetic": false,
  "authorization": {"training": true, "reference": "授权记录ID", "expires_at": null},
  "dataset_review_id": "数据集审核记录ID",
  "items": [{
    "id": "image_001", "subject_id": "subject_0123456789abcdef", "split": "train",
    "image": "images/001.png", "mask": "masks/001.png",
    "image_sha256": "替换为图片SHA256", "mask_sha256": "替换为标签SHA256",
    "review_reference": "该图审核记录ID",
    "groups": {"body_site": "face", "skin_tone": "unknown", "lighting": "indoor", "quality": "clear", "device": "unknown"}
  }]
}
```

同一受试者和重复图片不能跨split；不确定分组填unknown。清单路径限制在数据集目录内，拒绝文件路径逃逸。原图和标签哈希都必须匹配。

## 执行

在项目根目录，使用支持PyTorch、OpenCV、Pillow、NumPy的离线环境：

```bash
python -m ml.rgb_segmentation validate /private/dataset/manifest.json
python -m ml.rgb_segmentation train /private/dataset/manifest.json --output /private/runs/run-001 --epochs 20 --side 512
python -m ml.rgb_segmentation evaluate /private/dataset/manifest.json --weights /private/runs/run-001/model.pt --output /private/reports/run-001-test.json
```

训练输出TorchScript与training-report.json，始终enabled=false。当前实现为轻量U-Net随机初始化基线，无预训练权重下载；RGB预训练编码器可作为后续实验，不能将随机初始化基线称为已训练好的专用模型。训练使用validation选最佳checkpoint，不使用test选模型。

不带--weights时评估原始CV候选作为对照，报告会明确该对照不是旧VLM+SAM完整链路。Synthetic数据必须显式--allow-synthetic，产物不允许注册成真实模型。

报告包括Dice、IoU、Precision、Recall、Boundary F1、面积相对误差/占比百分点误差、漏检/误检、同图Mask导致的颜色差异及按部位/肤色/光照/质量/设备/面积分组。边界统一到长边1024、容差2px，未知标签附近的边界不计入；阴性图不填Dice=1拉高正例均值。报告同时包含失败和患者bootstrap区间。当前自动测量覆盖率为0，不能以人工核对率或成功请求数充当模型准确率。

## 模型注册

经过授权训练、独立评测与审核后，由维护者把可信权重复制到models/rgb/，将审核后的training-report相应字段填入configs/rgb_segmentation_registry.json，并核对SHA256、五类字典和dataset_review_id。

注册是人工维护操作，不会因训练完成自动发生。来源为synthetic、缺少审核记录、路径逃逸或校验和不符时拒绝加载。当前发布版本即使注册了真实模型，也只给候选，仍需用户核对；开放自动测量必须另行完成独立验收和策略变更。

权重和报告放在私有、Git忽略的目录，不提交患者图片、标签或身份信息。
