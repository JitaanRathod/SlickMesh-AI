"""
PyTorch U-Net Architecture, BCE+Dice Loss, and Evaluation Metrics for Satellite Oil Slick Segmentation.
Ref: phase1-satellite-detection.md §4
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple


class DoubleConv(nn.Module):
    """(Conv2d -> BatchNorm -> ReLU) * 2 block."""
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UNet(nn.Module):
    """
    Standard U-Net Architecture for 256x256x1 SAR image segmentation.
    Encoder (downsampling) -> Bottleneck -> Decoder (upsampling + skip connections) -> Sigmoid Output.
    """
    def __init__(self, in_channels: int = 1, out_channels: int = 1, base_features: int = 32):
        super().__init__()
        # Encoder
        self.enc1 = DoubleConv(in_channels, base_features)
        self.pool1 = nn.MaxPool2d(2, 2)
        
        self.enc2 = DoubleConv(base_features, base_features * 2)
        self.pool2 = nn.MaxPool2d(2, 2)

        self.enc3 = DoubleConv(base_features * 2, base_features * 4)
        self.pool3 = nn.MaxPool2d(2, 2)

        # Bottleneck
        self.bottleneck = DoubleConv(base_features * 4, base_features * 8)

        # Decoder
        self.up3 = nn.ConvTranspose2d(base_features * 8, base_features * 4, kernel_size=2, stride=2)
        self.dec3 = DoubleConv(base_features * 8, base_features * 4)

        self.up2 = nn.ConvTranspose2d(base_features * 4, base_features * 2, kernel_size=2, stride=2)
        self.dec2 = DoubleConv(base_features * 4, base_features * 2)

        self.up1 = nn.ConvTranspose2d(base_features * 2, base_features, kernel_size=2, stride=2)
        self.dec1 = DoubleConv(base_features * 2, base_features)

        # Final Classification Head
        self.final_conv = nn.Conv2d(base_features, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder pass
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))

        # Bottleneck
        b = self.bottleneck(self.pool3(e3))

        # Decoder pass with skip connections
        d3 = self.up3(b)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.dec1(d1)

        # Output probabilities via Sigmoid
        out = torch.sigmoid(self.final_conv(d1))
        return out


class BCEDiceLoss(nn.Module):
    """
    Combined Binary Cross Entropy (BCE) + Dice Loss.
    Loss = 0.5 * BCE + 0.5 * Dice
    """
    def __init__(self, bce_weight: float = 0.5, smooth: float = 1e-6):
        super().__init__()
        self.bce_weight = bce_weight
        self.smooth = smooth
        self.bce = nn.BCELoss()

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce_loss = self.bce(pred, target)
        
        # Flatten tensors for Dice calculation
        pred_flat = pred.view(-1)
        target_flat = target.view(-1)
        
        intersection = (pred_flat * target_flat).sum()
        dice_loss = 1.0 - ((2.0 * intersection + self.smooth) / (pred_flat.sum() + target_flat.sum() + self.smooth))

        return self.bce_weight * bce_loss + (1.0 - self.bce_weight) * dice_loss


def compute_segmentation_metrics(pred: torch.Tensor, target: torch.Tensor, threshold: float = 0.5, smooth: float = 1e-6) -> Dict[str, float]:
    """
    Computes binary segmentation metrics: IoU, Dice/F1, Precision, Recall.
    """
    with torch.no_grad():
        pred_binary = (pred > threshold).float().view(-1)
        target_binary = (target > threshold).float().view(-1)

        tp = (pred_binary * target_binary).sum().item()
        fp = (pred_binary * (1.0 - target_binary)).sum().item()
        fn = ((1.0 - pred_binary) * target_binary).sum().item()

        precision = (tp + smooth) / (tp + fp + smooth)
        recall = (tp + smooth) / (tp + tp + fn + smooth) if (tp + fn) > 0 else (tp + smooth) / (tp + smooth)
        dice = (2.0 * tp + smooth) / (2.0 * tp + fp + fn + smooth)
        iou = (tp + smooth) / (tp + fp + fn + smooth)

    return {
        "iou": round(float(iou), 4),
        "dice": round(float(dice), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4)
    }
