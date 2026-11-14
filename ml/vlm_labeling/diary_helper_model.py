"""Inference-only architecture and tiling for the public-trained auxiliary checkpoint."""

import math

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import resnet18


class Block(nn.Sequential):
    def __init__(self, a, b):
        super().__init__(
            nn.Conv2d(a, b, 3, padding=1, bias=False),
            nn.GroupNorm(8, b),
            nn.ReLU(),
            nn.Conv2d(b, b, 3, padding=1, bias=False),
            nn.GroupNorm(8, b),
            nn.ReLU(),
        )


class Seg(nn.Module):
    def __init__(self):
        super().__init__()
        e = resnet18(weights=None)
        e.fc = nn.Identity()
        self.encoder = e
        self.d4 = Block(512 + 256, 128)
        self.d3 = Block(128 + 128, 64)
        self.d2 = Block(64 + 64, 32)
        self.d1 = Block(32 + 64, 16)
        self.d0 = Block(16 + 3, 16)
        self.head = nn.Conv2d(16, 1, 1)
        self.register_buffer(
            "mean", torch.tensor([0.485, 0.456, 0.406])[None, :, None, None]
        )
        self.register_buffer(
            "std", torch.tensor([0.229, 0.224, 0.225])[None, :, None, None]
        )


class Dual(Seg):
    def __init__(self):
        super().__init__()
        self.head = nn.Conv2d(16, 2, 1)

    def forward(self, x):
        e = self.encoder
        z = (x - self.mean) / self.std
        s1 = e.relu(e.bn1(e.conv1(z)))
        s2 = e.layer1(e.maxpool(s1))
        s3 = e.layer2(s2)
        s4 = e.layer3(s3)
        s5 = e.layer4(s4)

        def up(a, c):
            return torch.cat(
                [
                    F.interpolate(
                        a, size=c.shape[-2:], mode="bilinear", align_corners=False
                    ),
                    c,
                ],
                1,
            )

        v = self.d4(up(s5, s4))
        v = self.d3(up(v, s3))
        v = self.d2(up(v, s2))
        v = self.d1(up(v, s1))
        return self.head(self.d0(up(v, x)))


def probabilities(logit):
    p = logit.sigmoid()
    return torch.stack([p[:, 0] * p[:, 1], p[:, 1]], 1)


@torch.inference_mode()
def tiled(model, x, window=256, stride=128):
    (h, w) = x.shape[:2]
    hp = max(window, int(math.ceil(max(0, h - window) / stride)) * stride + window)
    wp = max(window, int(math.ceil(max(0, w - window) / stride)) * stride + window)
    xp = cv2.copyMakeBorder(x, 0, hp - h, 0, wp - w, cv2.BORDER_REFLECT_101)
    out = np.zeros((2, hp, wp), np.float32)
    den = np.zeros((hp, wp), np.float32)
    ww = np.maximum(np.outer(np.hanning(window), np.hanning(window)), 0.01).astype(
        np.float32
    )
    locations = [
        (y, z)
        for y in range(0, hp - window + 1, stride)
        for z in range(0, wp - window + 1, stride)
    ]
    for start in range(0, len(locations), 4):
        loc = locations[start : start + 4]
        a = (
            np.stack(
                [
                    xp[y : y + window, z : z + window].transpose(2, 0, 1)
                    for (y, z) in loc
                ]
            ).astype(np.float32)
            / 255.0
        )
        probs = probabilities(model(torch.from_numpy(a))).numpy()
        assert np.isfinite(probs).all()
        for (y, z), p in zip(loc, probs):
            out[:, y : y + window, z : z + window] += p * ww[None]
            den[y : y + window, z : z + window] += ww
    assert (den > 0).all()
    return (out / den[None])[:, :h, :w]


def infer(model, x, cfg):
    model.eval()
    (h, w) = x.shape[:2]
    pred = []
    for scale in cfg["scales"]:
        im = (
            x
            if scale == 1
            else cv2.resize(
                x,
                (max(1, round(w * scale)), max(1, round(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        )
        p = tiled(model, im, cfg["window"], cfg["stride"])
        if p.shape[1:] != (h, w):
            p = np.stack(
                [cv2.resize(q, (w, h), interpolation=cv2.INTER_LINEAR) for q in p]
            )
        pred.append(p)
    p = np.stack(pred).mean(0)
    assert np.isfinite(p).all() and (p[0] <= p[1] + 1e-06).all()
    return p
