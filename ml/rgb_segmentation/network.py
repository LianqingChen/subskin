"""Small five-class RGB U-Net baseline. No automatic weight downloads."""

import torch
from torch import nn
from torch.nn import functional as F


def block(cin: int, cout: int) -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1),
        nn.GroupNorm(4, cout),
        nn.ReLU(),
        nn.Conv2d(cout, cout, 3, padding=1),
        nn.GroupNorm(4, cout),
        nn.ReLU(),
    )


class RGBUNet(nn.Module):
    def __init__(self, base: int = 16):
        super().__init__()
        self.e1 = block(3, base)
        self.e2 = block(base, base * 2)
        self.e3 = block(base * 2, base * 4)
        self.bridge = block(base * 4, base * 8)
        self.d3 = block(base * 12, base * 4)
        self.d2 = block(base * 6, base * 2)
        self.d1 = block(base * 3, base)
        self.out = nn.Conv2d(base, 5, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        a = self.e1(x)
        b = self.e2(F.max_pool2d(a, 2))
        c = self.e3(F.max_pool2d(b, 2))
        z = self.bridge(F.max_pool2d(c, 2))
        z = self.d3(
            torch.cat(
                [
                    F.interpolate(
                        z, size=c.shape[-2:], mode="bilinear", align_corners=False
                    ),
                    c,
                ],
                1,
            )
        )
        z = self.d2(
            torch.cat(
                [
                    F.interpolate(
                        z, size=b.shape[-2:], mode="bilinear", align_corners=False
                    ),
                    b,
                ],
                1,
            )
        )
        z = self.d1(
            torch.cat(
                [
                    F.interpolate(
                        z, size=a.shape[-2:], mode="bilinear", align_corners=False
                    ),
                    a,
                ],
                1,
            )
        )
        return self.out(z)
