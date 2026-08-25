import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from train import train_model

print("[Phase 1 Model Optimization] Fine-tuning U-Net model for 15 epochs to boost confidence & IoU...")
train_model(epochs=15, batch_size=8, synthetic=True, output_model="weights/unet_best.pth")
print("[Phase 1 Model Optimization] Optimization complete!")
