# 代码证据索引

所有摘录来自审计时工作区；不是线上运行态证明。

## I01 上传质检静默失败
[web/app/src/composables/useVasiUpload.ts:77](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/composables/useVasiUpload.ts:77)

```
77:   async function checkQuality(file: File) {
78:     const generation = ++qualityGeneration
79:     qualityResult.value = null
80:     qualityChecking.value = true
81:     try {
82:       const result = await vasiApi.checkPhotoQuality(file)
83:       if (generation === qualityGeneration) qualityResult.value = result
84:     } catch {
85:       if (generation === qualityGeneration) qualityResult.value = null
86:     } finally {
87:       if (generation === qualityGeneration) qualityChecking.value = false
88:     }
89:   }
90: 
91:   function removeImage() {
92:     qualityGeneration++
93:     uploadedImage.value = null
94:     imagePreview.value = null
95:     qualityResult.value = null
```

## I01 服务端质检鉴权
[web/backend/api/vasi.py:686](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/api/vasi.py:686)

```
686: async def check_photo_quality(
687:     image: UploadFile = File(...),
688:     current_user: User = Depends(get_current_user),
689: ):
690:     # Require authentication — this endpoint runs the quality checker on a
691:     # user-uploaded photo. Without auth it is an unauthenticated CPU/IO sink
692:     # (anyone can POST arbitrary images). Also enforce a size cap to prevent
693:     # oversized uploads from exhausting memory.
694:     MAX_PHOTO_BYTES = 20 * 1024 * 1024  # 20 MB
695:     image_bytes = await image.read()
696:     if len(image_bytes) > MAX_PHOTO_BYTES:
697:         raise HTTPException(
698:             status_code=413,
```

## I01 开始按钮依赖质检
[web/app/src/components/tracker/AssessmentCapture.vue:22](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/components/tracker/AssessmentCapture.vue:22)

```
22: const ready = computed(() => !!props.preview && !!props.bodySite && !!props.context.view && !!props.context.capture_date && !props.checking && !!props.quality && props.quality.overall !== 'poor' && !props.busy)
23: const qualityMessage = computed(() => props.checking ? '检查照片中…' : !props.quality ? '质检未完成，请重新选择照片' : props.quality.overall === 'good' ? '照片清晰' : props.quality.suggestions[0] || '请调整光照后重拍')
24: const nextStep = computed(() => {
25:   if (!props.preview) return '先添加一张照片'
26:   if (!props.bodySite) return '请选择身体部位'
27:   if (!props.context.view) return '请选择拍摄视角'
28:   if (!props.context.capture_date) return '请填写照片的实际拍摄日期'
29:   if (props.checking) return '正在检查照片清晰度，请稍候'
30:   if (!props.quality) return '照片检查未完成，请重新选择照片后重试'
31:   if (props.quality.overall === 'poor') return props.quality.suggestions[0] || '照片暂不适合分析，请调整光照后重拍'
32:   return '信息已齐全，可以开始分析'
33: })
```

## I02 质量分级
[web/backend/services/vasi_quality.py:243](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi_quality.py:243)

```
243:         critical_failures = sum([
244:             blur_score < BLUR_THRESHOLD_ACCEPTABLE * 0.5,
245:             brightness_mean < BRIGHTNESS_DARK_THRESHOLD * 0.6,
246:             brightness_mean > BRIGHTNESS_OVEREXPOSED_THRESHOLD + 20,
247:             not size_ok and (w < MIN_WIDTH * 0.7 or h < MIN_HEIGHT * 0.7),
248:         ])
249:         soft_failures = sum([not blur_ok, not skin_ok, not lighting_ok, not size_ok])
250: 
251:         if critical_failures >= 1:
252:             overall = "poor"
253:         elif soft_failures >= 2:
254:             overall = "acceptable"
255:         elif soft_failures == 1:
256:             overall = "acceptable"
257:         else:
258:             overall = "good"
259: 
260:         return QualityReport(
261:             overall=overall,
262:             blur_score=round(blur_score, 1),
263:             blur_ok=blur_ok,
264:             skin_ratio=round(skin_ratio, 3),
265:             skin_ok=skin_ok,
266:             brightness_mean=round(brightness_mean, 1),
267:             lighting_ok=lighting_ok,
268:             resolution=resolution,
269:             size_ok=size_ok,
```

## I03 默认Prompt的医学判断
[web/backend/services/llm_prompt_service.py:71](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/llm_prompt_service.py:71)

```
71: - 中央复色/边缘内收提示病情好转，颜色描述需体现这一变化，不可与脱色等级矛盾。
72: 
73: 【你需要输出的核心字段】
74: 1. skin_region: 皮肤区域
75:    - bbox: [x1, y1, x2, y2] 照片中皮肤区域的归一化包围盒 (0-1)
76:    - fitzpatrick: 估计分型 "I"-"VI"
77: 2. suspected_lesions: 疑似白斑列表，每项包含:
78:    - center: [x, y] 白斑几何中心 (0-1归一化坐标)
79:    - bbox: [x1, y1, x2, y2] 紧贴白斑边界的归一化包围盒 (0-1)
80:    - edge_points: [[x,y], ...] 4-8个沿白斑轮廓的归一化边界关键点 (0-1)，均匀覆盖凸点+凹点
81:    - estimated_size_percent: 占照片面积百分比 (数字)
82:    - size_category: tiny/small/medium/large
83:    - depigmentation_level: 1(轻度) / 2(中度) / 3(重度)
84:    - contrast_to_skin: 与周围正常皮肤的对比度 0-1 (按上述量化标准)
85:    - boundary_type: clear(清晰) / diffuse(模糊弥散) / mixed(混合)
86:    - boundary_confidence: 边界判定置信度 0-1
87:    - color_consistency: uniform/mottled/central_repigmentation/edge_repigmentation/mixed
88:    - confidence: 该处为白斑的置信度 0-1
89: 3. visual_features: 视觉特征概述
90:    - visibility: {"level": visible/faint/subtle, "description": "..."}
91:    - color: {"level": pale_white/milky_white/porcelain_white/pure_white, "description": "..."}
92:    - border: {"level": clear/partial/unclear, "description": "..."}
93:    - shape: {"pattern": round/oval/irregular/linear, "description": "..."}
94:    - surface: {"texture": smooth/scaly/atrophic, "description": "..."}
95:    - distribution: {"pattern": localized/segmental/bilateral/generalized/scattered, "description": "..."}
96:    - similarity_note: 一句总结 (20字以内)
97:    - recommendation: 建议 (如"建议皮肤科就诊")
98: 4. classification: 分型 (节段型/非节段型/混合型/未确定)
99: 5. stage: 阶段 (进展期/稳定期/好转期)
100: 6. overall_depigmentation: 整体脱色程度 1-3
101: 7. confidence: 本次整体分析置信度 0-1
```

## I04 缺失与空混淆
[web/backend/services/vasi_consensus.py:262](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi_consensus.py:262)

```
262:     if patient_mask_orig is None and (sam_mask is None or not sam_mask.any()):
263:         consensus["verdict"] = "both_empty"
264:         out["consensus"] = consensus
265:         out["auto_finalize"] = True  # 双方都认为无白斑
266:         out["note"] = "both empty consensus"
267:         return out
268: 
269:     iou = mask_iou(sam_mask, patient_mask_orig) \
270:         if (sam_mask is not None and patient_mask_orig is not None) else None
271:     consensus["iou"] = round(iou, 3) if iou is not None else None
272: 
273:     if iou is not None and iou >= _IOU_AGREE:
274:         consensus["verdict"] = "agreed"
275:         out["auto_finalize"] = True
276:         out["note"] = f"consensus IoU={iou:.2f}"
277:     else:
278:         # 分歧/单方检出 → 色值验证（画布上）
```

## I04 首训晋级
[web/backend/services/vasi_autoloop.py:295](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi_autoloop.py:295)

```
295:         if active_clf is None:
296:             should_deploy = True
297:             result["reason"] = "first model"
298:         elif new_dice is not None and active_dice is not None:
299:             if new_dice >= active_dice - 0.02:
300:                 should_deploy = True
301:                 result["reason"] = f"improved dice {active_dice:.3f}→{new_dice:.3f}"
302:             else:
303:                 result["reason"] = f"degraded ({active_dice:.3f}→{new_dice:.3f}), keep active"
304:         elif new_dice is not None:
305:             should_deploy = True
306:             result["reason"] = "no baseline dice, deploy"
307: 
308:         if should_deploy:
```

## I04 LLM伪标签
[web/backend/services/vasi_autoloop.py:485](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi_autoloop.py:485)

```
485:                 if verdict.get("is_vitiligo"):
486:                     _judge_positive_to_sample(db, a, payload, verdict)
487:                 else:
488:                     # 更新共识 JSON：裁决为假阳性
489:                     try:
490:                         cons = json.loads(a.consensus_json or "{}")
491:                         cons["judge_verdict"] = {"is_vitiligo": False,
```

## I05 图片级split
[web/backend/services/vasi_model_trainer.py:349](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi_model_trainer.py:349)

```
349:     rng = random.Random(42)
350:     n = len(data)
351:     best_loss = float("inf")
352:     patience = 0
353:     epochs_run = 0
354: 
355:     for epoch in range(MAX_EPOCHS):
356:         if time_budget_deadline is not None and time.time() > time_budget_deadline:
357:             logger.info("Training time budget reached, stopping at epoch %d", epoch)
358:             break
359: 
```

## I08 取消只清前端状态
[web/app/src/composables/useVasiAssess.ts:128](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/composables/useVasiAssess.ts:128)

```
128:   function cancelPending() { generation++; isUploading.value = false; uploadStage.value = ''; cleanupState() }
```

## I09 结果优先模型描述
[web/app/src/components/tracker/AssessmentObservationResult.vue:30](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/components/tracker/AssessmentObservationResult.vue:30)

```
30:         <div><dt class="text-xs text-gray-500"><i class="ri-palette-line mr-1" aria-hidden="true"></i>颜色</dt><dd class="mt-1.5 line-clamp-2 text-sm">{{ visualFeatures?.color?.description || (measure?.color ? '已记录与周围皮肤的色差' : '暂未量化') }}</dd></div>
31:         <div><dt class="text-xs text-gray-500"><i class="ri-shape-line mr-1" aria-hidden="true"></i>边缘</dt><dd class="mt-1.5 line-clamp-2 text-sm">{{ measure?.touches_frame ? '边缘未拍全，建议重拍' : visualFeatures?.border?.description || (lesionLayer ? '见照片标注范围' : '需要核对范围') }}</dd></div>
32:       </dl>
```

## I11 颜色周长
[web/backend/services/assessment_measurement.py:90](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/assessment_measurement.py:90)

```
90:     if image_bytes and lesion.any():
91:         import cv2
92:         rgb = np.asarray(Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(
93:             (skin.shape[1], skin.shape[0]), Image.Resampling.LANCZOS))
94:         lab = cv2.cvtColor(rgb.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
95:         ring = cv2.dilate(lesion.astype(np.uint8), np.ones((21, 21), np.uint8)).astype(bool) & skin & ~lesion
96:         if int(ring.sum()) >= 50:
97:             delta = np.median(lab[lesion], axis=0) - np.median(lab[ring], axis=0)
98:             result["color"] = {"relative_lightness": round(float(delta[0]), 1),
99:                                "delta_e76": round(float(np.linalg.norm(delta)), 1),
100:                                "scope": "within_photo", "calibrated": False}
101:         contours, _ = cv2.findContours(lesion.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
102:         perimeter = sum(cv2.arcLength(c, True) for c in contours)
103:         result["border"] = {"perimeter_pixels": round(perimeter, 1),
104:                             "status": "partial" if touches_edge else "outlined"}
```

## 已修复：没有随机假数据
[web/backend/services/vasi.py:1122](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/vasi.py:1122)

```
1122:     def _mock_result(self) -> Dict[str, Any]:
1123:         """Fail closed when all AI services are unavailable.
1124: 
1125:         Previously this returned random VASI scores (10–60) and area percentages
1126:         (5–30), which were persisted as real clinical assessments. That risks
1127:         users trusting fabricated scores. We now raise so the caller surfaces a
1128:         clear error and no assessment row is created.
1129:         """
1130:         raise VASIAssessmentError(
1131:             "AI 评估服务暂时不可用，无法生成评估结果。请稍后重试或使用「手动勾勒」模式自行标注白斑区域。"
1132:         )
1133: 
```

## 已修复：仅依据像素比较
[web/backend/services/spot_compare.py:976](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/backend/services/spot_compare.py:976)

```
976: def _merge_results(
977:     vlm: Optional[Dict[str, Any]],
978:     cv: Optional[Dict[str, Any]],
979:     quality_a: Tuple[float, str],
980:     quality_b: Tuple[float, str],
981: ) -> Dict[str, Any]:
982:     """Only validated pixel measurements may supply numeric changes."""
983:     evidence = (cv or {}).get("evidence") or {}
984:     good_quality = quality_a[1] in ("good", "acceptable") and quality_b[1] in ("good", "acceptable")
985:     comparable = evidence.get("status") == "measured" and good_quality
986:     reasons = list(evidence.get("reasons") or [])
987:     if not good_quality:
988:         reasons.append("照片质量不足，请在清晰、均匀光照下重拍")
989:     if not evidence:
990:         reasons.append("缺少通过对齐验证的像素测量，不能判断变化")
991:     direction = evidence.get("area_direction") if comparable else "unknown"
992:     labels = {"decreasing": "面积减小", "increasing": "面积增大", "uncertain": "未见明确面积变化", "unknown": "无法可靠比较"}
993:     trend = labels.get(direction, "无法可靠比较")
994:     result = {
995:         "measurement_version": "common-roi-v1", "comparison_status": "measured" if comparable else "not_comparable",
996:         "reasons": reasons, "trend": trend, "trend_en": direction or "unknown",
997:         "size_change_percent": evidence.get("size_change_percent") if comparable else None,
998:         "change_interval_percent": evidence.get("change_interval_percent") if comparable else None,
999:         "color_change": evidence.get("color_change") if comparable else None,
1000:         "border_change": evidence.get("border_change") if comparable else None,
1001:         "color_reason": evidence.get("color_reason") if comparable else "拍摄条件不可比",
1002:         "melanin_score_a": None, "melanin_score_b": None, "melanin_change": None, "melanin_signals": {},
1003:         "confidence": None, "low_confidence": not comparable,
1004:         "capture_note": "；".join(reasons) or None,
1005:         "summary": trend + "。" + ("；".join(reasons) if reasons else "仅描述本次照片共同可见区域，不代表病情分期。"),
1006:         "evidence": evidence,
1007:     }
1008:     return result
1009: 
```

## 当前相机主路径
[web/app/src/components/tracker/BodyPartCamera.vue:126](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/components/tracker/BodyPartCamera.vue:126)

```
126:       <p class="shrink-0 px-4 py-3 text-sm text-gray-200">{{ baselineUrl ? '对照上次照片，保持相同角度与距离。' : '均匀光照下拍摄，把白斑边缘和周围正常皮肤拍完整。' }}</p>
127:       <div class="relative min-h-0 flex-1">
128:         <video ref="video" autoplay playsinline muted class="h-full w-full object-contain"></video>
129:         <img v-if="baselineUrl && showBaseline" :src="toProtectedFileUrl(baselineUrl)" alt="上次拍摄的位置参考" class="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-30" />
130:         <p v-if="loading || error" role="status" class="absolute inset-x-4 top-1/2 rounded-xl bg-gray-900/90 p-4 text-center">{{ error || '正在打开相机…' }}</p>
131:       </div>
132:       <div class="shrink-0 space-y-3 px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
133:         <button v-if="baselineUrl" class="min-h-[44px] w-full rounded-xl border border-gray-500 text-sm" :aria-pressed="showBaseline" @click="showBaseline = !showBaseline">{{ showBaseline ? '隐藏上次照片' : '显示上次照片' }}</button>
134:         <button v-if="error" class="min-h-[44px] w-full rounded-xl border border-gray-500" @click="start">重新打开相机</button>
135:         <div class="flex gap-3">
136:           <button class="min-h-[48px] flex-1 rounded-xl border border-gray-500" :disabled="loading || capturing" @click="facing = facing === 'user' ? 'environment' : 'user'; start()">切换镜头</button>
137:           <button class="min-h-[48px] flex-1 rounded-xl bg-primary-500 font-semibold disabled:opacity-40" :disabled="loading || capturing || !!error" @click="capture">{{ capturing ? '正在生成照片…' : '拍照' }}</button>
```

## 隐私说明承诺
[web/app/src/views/PrivacyPolicyPage.vue:239](/run/user/1000/gvfs/sftp:host=124.174.0.212,user=root/root/subskin/web/app/src/views/PrivacyPolicyPage.vue:239)

```
239:             <li>人工智能服务提供商（用于智能问答、体检报告解读、日记智能整理、白斑照片分析等功能。
240:               <strong>仅当您在「个人中心 → 隐私设置」中开启相应授权后</strong>，您的健康记录
241:               或报告才会用于个性化 AI 功能；关闭授权后数据不再外送。发送内容仅限于完成
242:               该功能所必需的最小范围）</li>
243:             <li>地图与定位服务商（用于同城内容展示。反向地理编码仅使用约 1 公里精度的
244:               模糊坐标，不发送精确位置）</li>
```
