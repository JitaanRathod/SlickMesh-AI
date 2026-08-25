"""
Unit Tests for Phase 1 Satellite Detection Module.
Run via: python -m unittest discover -s phase1-satellite/tests -p "test_*.py"
"""

import sys
import os
import unittest
import numpy as np
import torch

# Add phase1-satellite folder to sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contracts import SatelliteDetectionOutput, Centroid, QualityFlagEnum, get_mock_contract_a
from wind_flag import evaluate_wind_quality_flag
from geometry import extract_slick_geometry
from model import UNet, BCEDiceLoss, compute_segmentation_metrics
from detect import run_detection


class TestContracts(unittest.TestCase):
    def test_mock_contract_a_validity(self):
        mock_output = get_mock_contract_a()
        self.assertEqual(mock_output.spill_id, "SPILL-001")
        self.assertEqual(mock_output.quality_flag, QualityFlagEnum.FAVORABLE)
        self.assertAlmostEqual(mock_output.centroid.lat, 20.48)
        self.assertAlmostEqual(mock_output.centroid.lon, 67.52)
        self.assertTrue(len(mock_output.polygon) >= 3)
        # Check GeoJSON [lon, lat] coordinate pairs
        for pt in mock_output.polygon:
            self.assertEqual(len(pt), 2)
            self.assertTrue(60.0 <= pt[0] <= 80.0)  # lon range
            self.assertTrue(10.0 <= pt[1] <= 30.0)  # lat range

    def test_json_serialization(self):
        mock_output = get_mock_contract_a()
        json_str = mock_output.model_dump_json()
        parsed = SatelliteDetectionOutput.model_validate_json(json_str)
        self.assertEqual(parsed.spill_id, mock_output.spill_id)


class TestWindFlag(unittest.TestCase):
    def test_wind_regimes(self):
        self.assertEqual(evaluate_wind_quality_flag(1.5), QualityFlagEnum.UNRELIABLE)
        self.assertEqual(evaluate_wind_quality_flag(5.4), QualityFlagEnum.FAVORABLE)
        self.assertEqual(evaluate_wind_quality_flag(12.0), QualityFlagEnum.HIGH_WIND_RISK)
        self.assertEqual(evaluate_wind_quality_flag(18.0), QualityFlagEnum.UNRELIABLE)
        self.assertEqual(evaluate_wind_quality_flag(None), QualityFlagEnum.FAVORABLE)


class TestUNetModel(unittest.TestCase):
    def test_forward_pass_shape(self):
        model = UNet(in_channels=1, out_channels=1)
        dummy_input = torch.randn(2, 1, 256, 256)
        output = model(dummy_input)
        self.assertEqual(output.shape, (2, 1, 256, 256))
        self.assertTrue((output >= 0.0).all() and (output <= 1.0).all())

    def test_bce_dice_loss(self):
        criterion = BCEDiceLoss()
        pred = torch.tensor([[[[0.9, 0.1], [0.8, 0.2]]]], dtype=torch.float32)
        target = torch.tensor([[[[1.0, 0.0], [1.0, 0.0]]]], dtype=torch.float32)
        loss = criterion(pred, target)
        self.assertTrue(isinstance(loss.item(), float))
        self.assertGreater(loss.item(), 0.0)

    def test_metrics_computation(self):
        pred = torch.tensor([[[[0.9, 0.1], [0.8, 0.2]]]], dtype=torch.float32)
        target = torch.tensor([[[[1.0, 0.0], [1.0, 0.0]]]], dtype=torch.float32)
        metrics = compute_segmentation_metrics(pred, target)
        self.assertIn("iou", metrics)
        self.assertIn("dice", metrics)
        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)


class TestGeometry(unittest.TestCase):
    def test_geometry_extraction(self):
        mask = np.zeros((256, 256), dtype=np.uint8)
        mask[100:150, 100:150] = 1  # 50x50 slick square
        
        stats = extract_slick_geometry(mask, ref_lat=20.48, ref_lon=67.52, pixel_size_km=0.05)
        self.assertTrue(stats["spill_detected"])
        self.assertGreater(stats["area_km2"], 0.0)
        self.assertIsInstance(stats["centroid"], Centroid)
        self.assertTrue(len(stats["polygon"]) > 0)


class TestDetectPipeline(unittest.TestCase):
    def test_mock_detection_execution(self):
        test_out_path = "test_spill_output.json"
        if os.path.exists(test_out_path):
            os.remove(test_out_path)

        res = run_detection(mock=True, output_path=test_out_path)
        self.assertEqual(res.spill_id, "SPILL-001")
        self.assertTrue(os.path.exists(test_out_path))

        # Cleanup
        if os.path.exists(test_out_path):
            os.remove(test_out_path)


if __name__ == "__main__":
    unittest.main()
