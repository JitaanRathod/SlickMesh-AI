"""
Deep-SAR Oil Spill (SOS) Zenodo Benchmark Dataset Parser & Loader.
Ref: phase1-satellite-detection.md §3 (Zenodo records 8346860 / 15298010)
"""

import os
import glob
import torch
import numpy as np
from PIL import Image
from typing import Tuple, List, Optional
from torch.utils.data import Dataset


class SOSDataset(Dataset):
    """
    Dataset loader for Deep-SAR Oil Spill (SOS) benchmark patches (256x256 VV SAR + GT Masks).
    """
    def __init__(self, dataset_dir: str = "phase1-satellite/data/sos_dataset", transform=None):
        self.dataset_dir = dataset_dir
        self.transform = transform

        self.image_paths: List[str] = sorted(glob.glob(os.path.join(dataset_dir, "images", "*.png")))
        self.mask_paths: List[str] = sorted(glob.glob(os.path.join(dataset_dir, "masks", "*.png")))

        if not self.image_paths:
            # Check direct folder
            self.image_paths = sorted(glob.glob(os.path.join(dataset_dir, "*.png")))
            self.mask_paths = self.image_paths

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img_path = self.image_paths[idx]
        mask_path = self.mask_paths[idx] if idx < len(self.mask_paths) else img_path

        img = Image.open(img_path).convert("L").resize((256, 256))
        mask = Image.open(mask_path).convert("L").resize((256, 256))

        img_np = np.array(img, dtype=np.float32) / 255.0
        mask_np = (np.array(mask, dtype=np.float32) > 127).astype(np.float32)

        image_t = torch.from_numpy(img_np).unsqueeze(0)
        mask_t = torch.from_numpy(mask_np).unsqueeze(0)

        return image_t, mask_t
