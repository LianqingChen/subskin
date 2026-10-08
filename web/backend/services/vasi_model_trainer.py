"""
U-Net 白斑分割模型训练管道

从管理员打标数据（VasiTrainingSample，gold standard 蒙层）训练轻量 U-Net，
并与当前线上识别链路（已上线 U-Net 或 CV 颜色分割回退）在随机测试集上
对比 Dice / IoU / 面积误差，产出 VasiModelVersion（默认不上线，管理员手动激活）。

设计约束（共享后端，CPU 训练）:
  - 输入统一 256×256，base 通道 16 的 4 层 U-Net（CPU 数分钟内完成）
  - epochs ≤ 15、batch=4、早停 patience=3、总时长上限 10 分钟
  - 全局锁防止并发训练；训练期间以 torch.set_num_threads(2) 限制 CPU 占用
"""
import base64
import io
import json
import logging
import os
import random
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from web.backend.database.database import SessionLocal
from web.backend.models.vasi import VasiModelVersion, VasiTrainingRun, VasiTrainingSample

logger = logging.getLogger(__name__)

MODELS_DIR = "/root/subskin/data/uploads/vasi/models"
MIN_SAMPLES = 8
INPUT_SIZE = 256
BASE_CHANNELS = 16
MAX_EPOCHS = 15
BATCH_SIZE = 4
EARLY_STOP_PATIENCE = 3
TIME_BUDGET_SECONDS = 600

_training_lock = threading.Lock()


# ── 数据准备 ──────────────────────────────────────────────────────


def _decode_mask_to_binary(mask_data_url: str, target_hw: Tuple[int, int]) -> Optional[np.ndarray]:
    """把 PNG data URL 蒙层解码为原图分辨率下的二值 mask（bool）。"""
    try:
        if mask_data_url.startswith("data:"):
            _, b64 = mask_data_url.split(",", 1)
        else:
            b64 = mask_data_url
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw))
        arr = np.array(img)

        if arr.ndim == 3 and arr.shape[2] == 4:
            binary = arr[:, :, 3] > 32
        elif arr.ndim == 3:
            binary = arr.max(axis=2) > 32
        elif arr.ndim == 2:
            binary = arr > 127
        else:
            return None

        h, w = target_hw
        if binary.shape != (h, w):
            pil_mask = Image.fromarray((binary * 255).astype(np.uint8))
            pil_mask = pil_mask.resize((w, h), Image.NEAREST)
            binary = np.asarray(pil_mask) > 127
        return binary
    except Exception as e:
        logger.warning("Failed to decode mask data URL: %s", e)
        return None


def collect_samples(db) -> List[Dict[str, Any]]:
    """收集有效训练样本：is_active + 管理员蒙层 + 可加载原图。

    Returns:
        [{"sample_id", "image_label_id", "image": PIL.Image, "mask": np.ndarray}]
    """
    from web.backend.api.image_label import _load_image_from_label
    from web.backend.models.image_label import ImageLabel
    from web.backend.services.data_consent import label_training_decision

    samples = db.query(VasiTrainingSample).filter(
        VasiTrainingSample.is_active == True,  # noqa: E712
        VasiTrainingSample.admin_mask_b64.isnot(None),
        VasiTrainingSample.image_label_id.isnot(None),
    ).all()

    collected: List[Dict[str, Any]] = []
    for sample in samples:
        label = db.query(ImageLabel).filter(ImageLabel.id == sample.image_label_id).first()
        if label is None:
            continue
        # 2026-08-30 隐私合规：用户已删除的测评，其病情图片不得继续参与训练
        if getattr(label, "is_user_deleted", False):
            continue
        # 分用途授权：已入库的样本也要逐条校验，撤回或从未授权的不得进入训练
        if not label_training_decision(db, label).allowed:
            continue
        try:
            image = _load_image_from_label(label)
        except Exception as e:
            logger.warning("Failed to load image for label %s: %s", label.id, e)
            continue
        if image is None:
            continue
        image = image.convert("RGB")
        mask = _decode_mask_to_binary(sample.admin_mask_b64, (image.height, image.width))
        if mask is None or not mask.any() or mask.all():
            continue
        collected.append({
            "sample_id": sample.id,
            "image_label_id": sample.image_label_id,
            "image": image,
            "mask": mask,
        })

    logger.info("Collected %d usable training samples out of %d records", len(collected), len(samples))
    return collected


def count_usable_samples(db) -> int:
    """快速统计潜在可用样本数（不加载图片，用于门槛校验）。

    与 collect_samples 同口径：已删除或未获“改进识别”授权的样本不计入，
    否则门槛校验会通过、实际训练却取不到足够样本。
    """
    from web.backend.models.image_label import ImageLabel
    from web.backend.services.data_consent import label_training_decision

    rows = db.query(VasiTrainingSample.image_label_id).filter(
        VasiTrainingSample.is_active == True,  # noqa: E712
        VasiTrainingSample.admin_mask_b64.isnot(None),
        VasiTrainingSample.image_label_id.isnot(None),
        VasiTrainingSample.admin_mask_b64 != "",
    ).all()
    count = 0
    for (label_id,) in rows:
        label = db.query(ImageLabel).filter(ImageLabel.id == label_id).first()
        if label is not None and label_training_decision(db, label).allowed:
            count += 1
    return count


# ── U-Net 模型 ────────────────────────────────────────────────────


def _build_unet():
    """轻量 U-Net：4 层 encoder/decoder，256×256 输入，base=16 通道。"""
    import torch
    import torch.nn as nn

    def conv_block(cin: int, cout: int) -> nn.Module:
        return nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1),
            nn.BatchNorm2d(cout),
            nn.ReLU(inplace=True),
        )

    class UNet(nn.Module):
        def __init__(self, base: int = BASE_CHANNELS):
            super().__init__()
            b = base
            self.enc1 = conv_block(3, b)
            self.enc2 = conv_block(b, b * 2)
            self.enc3 = conv_block(b * 2, b * 4)
            self.enc4 = conv_block(b * 4, b * 8)
            self.pool = nn.MaxPool2d(2)
            self.up3 = nn.ConvTranspose2d(b * 8, b * 4, 2, stride=2)
            self.dec3 = conv_block(b * 8, b * 4)
            self.up2 = nn.ConvTranspose2d(b * 4, b * 2, 2, stride=2)
            self.dec2 = conv_block(b * 4, b * 2)
            self.up1 = nn.ConvTranspose2d(b * 2, b, 2, stride=2)
            self.dec1 = conv_block(b * 2, b)
            self.out = nn.Conv2d(b, 1, 1)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(self.pool(e1))
            e3 = self.enc3(self.pool(e2))
            e4 = self.enc4(self.pool(e3))
            d3 = self.dec3(torch.cat([self.up3(e4), e3], dim=1))
            d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
            d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
            return self.out(d1)

    return UNet()


def load_unet(version_tag: str):
    """从模型目录加载已保存的 U-Net 权重；文件缺失返回 None。"""
    import torch

    path = os.path.join(MODELS_DIR, f"{version_tag}.pt")
    if not os.path.exists(path):
        logger.warning("U-Net weights not found: %s", path)
        return None
    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=True)
        model = _build_unet()
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        return model
    except Exception as e:
        logger.error("Failed to load U-Net %s: %s", version_tag, e)
        return None


def predict_mask(model, img_np: np.ndarray, threshold: float = 0.5) -> Optional[np.ndarray]:
    """用 U-Net 对原图分辨率 RGB ndarray 推理，返回原图分辨率二值 mask。"""
    import torch

    try:
        h, w = img_np.shape[:2]
        pil = Image.fromarray(img_np.astype(np.uint8)).resize(
            (INPUT_SIZE, INPUT_SIZE), Image.BILINEAR
        )
        x = np.asarray(pil, dtype=np.float32) / 255.0
        x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0)

        model.eval()
        with torch.no_grad():
            logits = model(x)
            prob = torch.sigmoid(logits)[0, 0].numpy()

        mask_small = prob > threshold
        if mask_small.shape == (h, w):
            return mask_small
        mask_pil = Image.fromarray((mask_small * 255).astype(np.uint8)).resize((w, h), Image.NEAREST)
        return np.asarray(mask_pil) > 127
    except Exception as e:
        logger.error("U-Net prediction failed: %s", e)
        return None


# ── 评估 ──────────────────────────────────────────────────────────


def _compute_metrics(pred: np.ndarray, gt: np.ndarray) -> Dict[str, float]:
    pred = pred.astype(bool)
    gt = gt.astype(bool)
    inter = int(np.logical_and(pred, gt).sum())
    union = int(np.logical_or(pred, gt).sum())
    pred_area = int(pred.sum())
    gt_area = int(gt.sum())

    denom = pred_area + gt_area
    dice = 2.0 * inter / denom if denom > 0 else 1.0
    iou = inter / union if union > 0 else 1.0
    if gt_area > 0:
        area_error = abs(pred_area - gt_area) / gt_area * 100.0
    else:
        area_error = 0.0 if pred_area == 0 else 100.0

    return {
        "dice": round(float(dice), 4),
        "iou": round(float(iou), 4),
        "area_error_pct": round(float(min(area_error, 999.0)), 1),
    }


def _predict_baseline_mask(img_np: np.ndarray) -> np.ndarray:
    """当前线上识别链路的预测：已上线 U-Net 优先，否则 CV 颜色分割回退。"""
    from web.backend.services.vasi_segmentation import _fallback_segmentation, segment_with_unet

    unet_mask = segment_with_unet(img_np)
    if unet_mask is not None and unet_mask.any():
        return unet_mask

    result = _fallback_segmentation(img_np, 0.005, 5)
    lesion_url = result.get("lesion_layer_data_url")
    if not lesion_url:
        return np.zeros(img_np.shape[:2], dtype=bool)
    mask = _decode_mask_to_binary(lesion_url, img_np.shape[:2])
    return mask if mask is not None else np.zeros(img_np.shape[:2], dtype=bool)


def _evaluate(
    collected: List[Dict[str, Any]],
    test_indices: List[int],
    model=None,
    progress_cb=None,
) -> Dict[str, Any]:
    """在测试集上评估（baseline 传 model=None，新模型传训练好的 U-Net）。"""
    per_image = []
    for i, idx in enumerate(test_indices):
        item = collected[idx]
        img_np = np.array(item["image"])
        if model is not None:
            pred = predict_mask(model, img_np)
            if pred is None:
                pred = np.zeros(img_np.shape[:2], dtype=bool)
        else:
            pred = _predict_baseline_mask(img_np)
        metrics = _compute_metrics(pred, item["mask"])
        metrics["image_label_id"] = item["image_label_id"]
        per_image.append(metrics)
        if progress_cb:
            progress_cb(i + 1, len(test_indices))

    return {
        "dice": round(float(np.mean([m["dice"] for m in per_image])), 4),
        "iou": round(float(np.mean([m["iou"] for m in per_image])), 4),
        "area_error_pct": round(float(np.mean([m["area_error_pct"] for m in per_image])), 1),
        "n": len(per_image),
        "per_image": per_image,
    }


# ── 训练 ──────────────────────────────────────────────────────────


def _to_train_tensor(image: Image.Image, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    pil = image.resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    x = np.asarray(pil, dtype=np.float32) / 255.0
    mask_pil = Image.fromarray((mask * 255).astype(np.uint8)).resize(
        (INPUT_SIZE, INPUT_SIZE), Image.NEAREST
    )
    y = (np.asarray(mask_pil) > 127).astype(np.float32)
    return x, y


def _augment(x: np.ndarray, y: np.ndarray, rng: random.Random) -> Tuple[np.ndarray, np.ndarray]:
    if rng.random() < 0.5:
        x, y = x[:, ::-1], y[:, ::-1]
    k = rng.randint(0, 3)
    if k:
        x, y = np.rot90(x, k), np.rot90(y, k)
    return np.ascontiguousarray(x), np.ascontiguousarray(y)


def _train_unet(
    collected: List[Dict[str, Any]],
    train_indices: List[int],
    epoch_progress_cb=None,
    time_budget_deadline: Optional[float] = None,
):
    """在训练集上训练 U-Net，返回 (model, epochs_run)。"""
    import torch
    import torch.nn as nn

    torch.manual_seed(42)
    model = _build_unet()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    bce = nn.BCEWithLogitsLoss()

    def dice_loss(logits, targets):
        probs = torch.sigmoid(logits)
        inter = (probs * targets).sum(dim=(1, 2, 3))
        union = probs.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
        return (1.0 - (2.0 * inter + 1.0) / (union + 1.0)).mean()

    data = []
    for idx in train_indices:
        x, y = _to_train_tensor(collected[idx]["image"], collected[idx]["mask"])
        data.append((x, y))

    rng = random.Random(42)
    n = len(data)
    best_loss = float("inf")
    patience = 0
    epochs_run = 0

    for epoch in range(MAX_EPOCHS):
        if time_budget_deadline is not None and time.time() > time_budget_deadline:
            logger.info("Training time budget reached, stopping at epoch %d", epoch)
            break

        model.train()
        order = list(range(n))
        rng.shuffle(order)

        epoch_loss = 0.0
        batches = 0
        for i in range(0, n, BATCH_SIZE):
            xb_list, yb_list = [], []
            for idx in order[i:i + BATCH_SIZE]:
                x, y = _augment(data[idx][0], data[idx][1], rng)
                xb_list.append(x.transpose(2, 0, 1))
                yb_list.append(y[None, :, :])

            xb = torch.from_numpy(np.stack(xb_list)).float()
            yb = torch.from_numpy(np.stack(yb_list)).float()

            logits = model(xb)
            loss = bce(logits, yb) + dice_loss(logits, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            batches += 1

        epoch_loss /= max(batches, 1)
        epochs_run = epoch + 1
        logger.info("U-Net epoch %d/%d loss=%.4f", epoch + 1, MAX_EPOCHS, epoch_loss)

        if epoch_progress_cb:
            epoch_progress_cb(epoch + 1, epoch_loss)

        if epoch_loss < best_loss - 1e-4:
            best_loss = epoch_loss
            patience = 0
        else:
            patience += 1
            if patience >= EARLY_STOP_PATIENCE:
                logger.info("Early stopping at epoch %d (loss plateau)", epoch + 1)
                break

    return model, epochs_run


# ── 训练运行编排 ──────────────────────────────────────────────────


def is_training_active() -> bool:
    return _training_lock.locked()


def _update_run(run_id: int, **fields) -> None:
    session = SessionLocal()
    try:
        run = session.query(VasiTrainingRun).filter(VasiTrainingRun.id == run_id).first()
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)
        session.commit()
    except Exception:
        logger.exception("Failed to update training run %s", run_id)
        session.rollback()
    finally:
        session.close()


def start_training_run(started_by: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    """创建训练运行并启动后台线程。返回 (run_id, error)。"""
    if is_training_active():
        return None, "已有训练任务正在运行，请等待完成后再试"

    session = SessionLocal()
    try:
        count = count_usable_samples(session)
        if count < MIN_SAMPLES:
            return None, (
                f"有效训练样本不足（需≥{MIN_SAMPLES}，当前{count}），"
                "请先完成打标并添加至训练样本"
            )

        run = VasiTrainingRun(status="pending", started_by=started_by, stage="collect", progress=0)
        session.add(run)
        session.commit()
        run_id = run.id
    finally:
        session.close()

    thread = threading.Thread(target=run_training, args=(run_id, started_by), daemon=True)
    thread.start()
    logger.info("Training run %d started by user %s", run_id, started_by)
    return run_id, None


def run_training(run_id: int, started_by: Optional[int] = None) -> None:
    """训练主流程（后台线程执行）— 收集→划分→基线→训练→评估→保存版本。"""
    if not _training_lock.acquire(blocking=False):
        _update_run(run_id, status="failed", error="已有训练任务正在运行",
                    finished_at=datetime.utcnow())
        return

    # 限制训练 CPU 线程数，避免与用户请求争抢资源
    # （注意：os.nice 是进程级的，会降低整个后端的调度优先级，方向相反）
    prior_threads = None
    try:
        import torch as _torch
        prior_threads = _torch.get_num_threads()
        _torch.set_num_threads(2)
    except Exception:
        pass

    try:
        started = time.time()
        deadline = started + TIME_BUDGET_SECONDS
        _update_run(run_id, status="running", stage="collect", progress=5)

        session = SessionLocal()
        try:
            collected = collect_samples(session)
        finally:
            session.close()

        n = len(collected)
        if n < MIN_SAMPLES:
            _update_run(
                run_id, status="failed",
                error=f"有效训练样本不足（需≥{MIN_SAMPLES}，当前{n}）",
                finished_at=datetime.utcnow(),
            )
            return

        # ── 测试集划分：随机 20%（样本 <15 时固定 3 张） ──
        rng = random.Random(42)
        indices = list(range(n))
        rng.shuffle(indices)
        if n < 15:
            test_n = 3
        else:
            test_n = max(3, int(round(n * 0.2)))
        test_n = max(1, min(test_n, n - 5))
        test_indices = indices[:test_n]
        train_indices = indices[test_n:]

        _update_run(run_id, stage="split", progress=10,
                    train_size=len(train_indices), test_size=len(test_indices))

        # ── 基线评估（当前线上链路） ──
        _update_run(run_id, stage="baseline", progress=15)
        baseline_metrics = _evaluate(collected, test_indices, model=None, progress_cb=lambda d, t: None)
        _update_run(run_id, progress=25, baseline_metrics_json=json.dumps(baseline_metrics))
        logger.info("Baseline metrics: %s", baseline_metrics)

        # ── U-Net 训练 ──
        _update_run(run_id, stage="train", progress=30)

        def on_epoch(epoch: int, loss: float) -> None:
            progress = 30 + int(50 * epoch / MAX_EPOCHS)
            _update_run(run_id, progress=min(progress, 80))

        model, epochs_run = _train_unet(
            collected, train_indices,
            epoch_progress_cb=on_epoch,
            time_budget_deadline=deadline,
        )

        # ── 新模型评估 ──
        _update_run(run_id, stage="eval", progress=85)
        new_metrics = _evaluate(collected, test_indices, model=model, progress_cb=lambda d, t: None)
        logger.info("New model metrics: %s", new_metrics)

        # ── 保存模型与版本记录 ──
        import torch

        version_tag = f"unet-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        os.makedirs(MODELS_DIR, exist_ok=True)
        model_path = os.path.join(MODELS_DIR, f"{version_tag}.pt")
        torch.save({
            "state_dict": model.state_dict(),
            "version_tag": version_tag,
            "input_size": INPUT_SIZE,
            "train_size": len(train_indices),
            "test_size": len(test_indices),
            "created_at": datetime.utcnow().isoformat(),
        }, model_path)

        elapsed = int(time.time() - started)
        metrics = {
            "baseline_dice": baseline_metrics["dice"],
            "dice": new_metrics["dice"],
            "baseline_iou": baseline_metrics["iou"],
            "iou": new_metrics["iou"],
            "baseline_area_error_pct": baseline_metrics["area_error_pct"],
            "area_error_pct": new_metrics["area_error_pct"],
            "train_size": len(train_indices),
            "test_size": len(test_indices),
            "epochs": epochs_run,
            "elapsed_seconds": elapsed,
            "model_path": model_path,
        }

        session = SessionLocal()
        try:
            version = VasiModelVersion(
                version_tag=version_tag,
                description=f"U-Net 白斑分割模型 — 训练样本 {len(train_indices)} 张（测试集 {len(test_indices)} 张）",
                evolution_layer="model_weights",
                changes_json=json.dumps({
                    "architecture": "unet-light-256",
                    "base_channels": BASE_CHANNELS,
                    "input_size": INPUT_SIZE,
                    "epochs": epochs_run,
                    "augmentation": ["hflip", "rot90"],
                }),
                metrics_json=json.dumps(metrics),
                sample_count=len(test_indices),
                is_active=False,
            )
            session.add(version)

            run = session.query(VasiTrainingRun).filter(VasiTrainingRun.id == run_id).first()
            if run is not None:
                run.status = "completed"
                run.stage = "done"
                run.progress = 100
                run.version_tag = version_tag
                run.new_metrics_json = json.dumps(new_metrics)
                run.finished_at = datetime.utcnow()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        logger.info("Training run %d completed: version=%s metrics=%s elapsed=%ds",
                    run_id, version_tag, metrics, elapsed)

    except Exception as e:
        logger.exception("Training run %d failed", run_id)
        _update_run(run_id, status="failed", error=str(e)[:500], finished_at=datetime.utcnow())
    finally:
        if prior_threads is not None:
            try:
                import torch as _torch
                _torch.set_num_threads(prior_threads)
            except Exception:
                pass
        _training_lock.release()
