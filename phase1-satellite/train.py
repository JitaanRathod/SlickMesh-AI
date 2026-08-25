"""
U-Net Training CLI Script for Sentinel-1 Oil Spill Detection.
Ref: phase1-satellite-detection.md §5
"""

import os
import sys
import argparse
import torch

# Ensure script directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from torch.utils.data import DataLoader, random_split
from model import UNet, BCEDiceLoss, compute_segmentation_metrics
from dataset import SARDataset


def train_model(
    data_dir: str = None,
    epochs: int = 5,
    batch_size: int = 8,
    lr: float = 1e-4,
    synthetic: bool = True,
    output_model: str = "weights/unet_best.pth"
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Phase 1 Train] Using compute device: {device}")

    # Load dataset
    full_dataset = SARDataset(data_dir=data_dir, synthetic=synthetic, num_synthetic_samples=160)
    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # Instantiate Model, Loss, Optimizer
    model = UNet(in_channels=1, out_channels=1).to(device)
    criterion = BCEDiceLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best_val_iou = 0.0
    os.makedirs(os.path.dirname(output_model) or ".", exist_ok=True)

    print(f"[Phase 1 Train] Starting training for {epochs} epochs ({len(train_ds)} train, {len(val_ds)} val samples)...")

    try:
        for epoch in range(1, epochs + 1):
            model.train()
            train_loss = 0.0

            for images, masks in train_loader:
                images, masks = images.to(device), masks.to(device)
                optimizer.zero_grad()

                preds = model(images)
                loss = criterion(preds, masks)
                loss.backward()
                optimizer.step()

                train_loss += loss.item() * images.size(0)

            train_loss /= len(train_ds)

            # Validation loop
            model.eval()
            val_loss = 0.0
            val_iou = 0.0
            val_dice = 0.0

            with torch.no_grad():
                for images, masks in val_loader:
                    images, masks = images.to(device), masks.to(device)
                    preds = model(images)
                    loss = criterion(preds, masks)
                    val_loss += loss.item() * images.size(0)

                    metrics = compute_segmentation_metrics(preds, masks)
                    val_iou += metrics["iou"] * images.size(0)
                    val_dice += metrics["dice"] * images.size(0)

            val_loss /= len(val_ds)
            val_iou /= len(val_ds)
            val_dice /= len(val_ds)

            print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val IoU: {val_iou:.4f} | Val Dice: {val_dice:.4f}", flush=True)

            if val_iou >= best_val_iou:
                best_val_iou = val_iou
                torch.save(model.state_dict(), output_model)

        print(f"[Phase 1 Train] Training complete! Best Val IoU: {best_val_iou:.4f}. Weights saved to: {output_model}", flush=True)
    except Exception as err:
        import traceback
        print(f"[Phase 1 Train] Error during training: {err}", flush=True)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train U-Net model for Satellite SAR Oil Spill Detection.")
    parser.add_argument("--data-dir", type=str, default=None, help="Directory containing dataset images and masks")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--no-synthetic", action="store_false", dest="synthetic", default=True, help="Disable synthetic dataset and use real data-dir")
    parser.add_argument("--output-model", type=str, default="weights/unet_best.pth", help="Target model weights file path")

    args = parser.parse_args()
    train_model(
        data_dir=args.data_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        synthetic=args.synthetic,
        output_model=args.output_model
    )
