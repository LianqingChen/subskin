"""Research-only U-Net with a zero-initialized local luminance contrast channel."""
import torch
from torch import nn
from torch.nn import functional as F
from ml.rgb_segmentation.network import RGBUNet


def local_contrast(x: torch.Tensor) -> torch.Tensor:
    lum=x[:,0:1]*.299+x[:,1:2]*.587+x[:,2:3]*.114
    mean=F.avg_pool2d(F.pad(lum,(15,15,15,15),mode='reflect'),31,stride=1)
    return ((lum-mean)*2).clamp(-.5,.5)+.5


class LocalContrastUNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.net=RGBUNet()
        old=self.net.e1[0]
        state=torch.get_rng_state()
        new=nn.Conv2d(4,old.out_channels,kernel_size=3,padding=1,bias=True)
        torch.set_rng_state(state)
        with torch.no_grad():
            new.weight[:,:3].copy_(old.weight)
            new.weight[:,3].zero_()
            new.bias.copy_(old.bias)
        self.net.e1[0]=new

    def forward(self,x: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat((x,local_contrast(x)),dim=1))
