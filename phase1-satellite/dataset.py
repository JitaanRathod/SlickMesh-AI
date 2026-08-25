"""
Dataset Loader & Synthetic Generator for Sentinel-1 SAR Oil Spill Patches.
Ref: phase1-satellite-detection.md §3
"""

import os
import glob
import torch
import numpy as np
from PIL import Image
from typing import Tuple, List, Optional
from torch.utils.data import Dataset


def generate_synthetic_sar_patch(
    image_size: int = 256,
    has_spill: bool = True,
    seed: Optional[int] = None
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Generates a realistic synthetic SAR VV image patch (256x256) and binary ground truth slick mask.
    Simulates SAR ocean speckle noise with a dark low-backscatter oil slick damping anomaly.
    """
    if seed is not None:
        np.random.seed(seed)

    # 1. Base ocean speckle background (Rayleigh / Gamma distribution simulation for SAR)
    ocean_mean = 0.55
    speckle_noise = np.random.gamma(shape=4.0, scale=ocean_mean / 4.0, size=(image_size, image_size))
    sar_image = np.clip(speckle_noise, 0.0, 1.0)
    slick_mask = np.zeros((image_size, image_size), dtype=np.float32)

    if has_spill:
        # 2. Generate random irregular dark slick patch using ellipse / Gaussian blobs
        center_x = np.random.randint(64, image_size - 64)
        center_y = np.random.randint(64, image_size - 64)
        axis_x = np.random.randint(20, 50)
        axis_y = np.random.randint(15, 40)
        angle = np.radians(np.random.randint(0, 180))

        grid_y, grid_x = np.ogrid[:image_size, :image_size]
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        x_rot = cos_a * (grid_x - center_x) + sin_a * (grid_y - center_y)
        y_rot = -sin_a * (grid_x - center_x) + cos_a * (grid_y - center_y)

        ellipse_dist = (x_rot / axis_x) ** 2 + (y_rot / axis_y) ** 2
        slick_region = ellipse_dist <= 1.0
        
        # Add boundary noise / irregularity
        boundary_noise = np.random.normal(0.0, 0.2, size=(image_size, image_size))
        slick_region = (ellipse_dist + boundary_noise) <= 1.0

        slick_mask[slick_region] = 1.0

        # Damping effect: Reduce backscatter (brightness drop) over slick area
        damping_factor = np.random.uniform(0.2, 0.4)
        sar_image[slick_region] = sar_image[slick_region] * damping_factor

    # Convert to Tensors (1 x H x W)
    image_tensor = torch.from_numpy(sar_image).float().unsqueeze(0)
    mask_tensor = torch.from_numpy(slick_mask).float().unsqueeze(0)

    return image_tensor, mask_tensor


class SARDataset(Dataset):
    """
    Dataset class for loading Sentinel-1 SAR oil spill patches.
    Supports loading from image directory or generating synthetic SAR samples.
    """
    def __init__(
        self,
        data_dir: Optional[str] = None,
        transform=None,
        synthetic: bool = False,
        num_synthetic_samples: int = 200,
        image_size: int = 256
    ):
        self.data_dir = data_dir
        self.transform = transform
        self.synthetic = synthetic
        self.num_synthetic_samples = num_synthetic_samples
        self.image_size = image_size

        self.image_paths: List[str] = []
        self.mask_paths: List[str] = []

        if not synthetic and data_dir and os.path.exists(data_dir):
            images_folder = os.path.join(data_dir, "images")
            masks_folder = os.path.join(data_dir, "masks")
            if os.path.exists(images_folder) and os.path.exists(masks_folder):
                self.image_paths = sorted(glob.glob(os.path.join(images_folder, "*.png")))
                self.mask_paths = sorted(glob.glob(os.path.join(masks_folder, "*.png")))

        # If no image files found or synthetic mode requested, fallback to synthetic mode
        if not self.image_paths:
            self.synthetic = True

    def __len__(self) -> int:
        if self.synthetic:
            return self.num_synthetic_samples
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.synthetic:
            # 80% chance of slick present, 20% ocean only
            has_spill = (idx % 5) != 0
            image_t, mask_t = generate_synthetic_sar_patch(
                image_size=self.image_size,
                has_spill=has_spill,
                seed=idx
            )
            return image_t, mask_t

        # Load real image patch
        img_path = self.image_paths[idx]
        mask_path = self.mask_paths[idx]

        img = Image.open(img_path).convert("L")
        mask = Image.open(mask_path).convert("L")

        img_np = np.array(img, dtype=np.float32) / 255.0
        mask_np = (np.array(mask, dtype=np.float32) > 127).astype(np.float32)

        image_t = torch.from_numpy(img_np).unsqueeze(0)
        mask_t = torch.from_numpy(mask_np).unsqueeze(0)

        return image_t, mask_t
