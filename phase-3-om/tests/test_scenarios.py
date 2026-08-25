"""Tests executing real-world synthetic maritime scenarios."""

import pytest
from engine import AttributionEngine
from scenarios import SCENARIO_CANONICAL, SCENARIO_DENSE_TRAFFIC, SCENARIO_AIS_SPOOFING_GAP


def test_scenario_canonical():
    engine = AttributionEngine()
    result = engine.process(SCENARIO_CANONICAL, spill_id="SPILL-MOCK-001")
    assert len(result.ranked_vessels) == 2
    assert result.ranked_vessels[0].name == "MV Ocean Star"
    assert result.ranked_vessels[0].confidence > 80
    assert result.ranked_vessels[1].confidence < 50


def test_scenario_dense_traffic():
    engine = AttributionEngine()
    result = engine.process(SCENARIO_DENSE_TRAFFIC, spill_id="SPILL-BOMBAY-HIGH")
    assert len(result.ranked_vessels) == 5
    
    # Highest ranked should be Al-Bahar Crude (closest, tanker, loitering speed)
    top = result.ranked_vessels[0]
    assert top.name == "Al-Bahar Crude"
    assert top.confidence >= 85
    
    # Second should be Bharat Pioneer (product tanker inside corridor)
    second = result.ranked_vessels[1]
    assert second.name in ("Bharat Pioneer", "Sindhu Shrestha")
    
    # Fishing trawler and container far away must be ranked lowest
    confidences = [v.confidence for v in result.ranked_vessels]
    assert confidences == sorted(confidences, reverse=True)


def test_scenario_ais_spoofing_gap():
    engine = AttributionEngine()
    result = engine.process(SCENARIO_AIS_SPOOFING_GAP, spill_id="SPILL-DARK-SHIP")
    assert len(result.ranked_vessels) == 2
    
    shadow_trader = result.ranked_vessels[0]
    assert shadow_trader.name == "Shadow Trader"
    assert "gaps" in shadow_trader.reason.lower() or "discontinuous" in shadow_trader.reason.lower()
