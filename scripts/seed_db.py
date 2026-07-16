"""
CLI script to seed the database with mock structural assets and inspections.
Useful for testing API CRUD and future frontends.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings
from backend.app.database.session import AsyncSessionFactory, create_db_and_tables
from backend.app.models.asset import Asset, AssetStatus, AssetType
from backend.app.models.inspection import Inspection, InspectionSource, InspectionStatus
from backend.app.models.detection import Detection, DefectType
from backend.app.models.health_record import HealthRecord, RiskLevel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed() -> None:
    """Seed script logic."""
    import os
    logger.info("Initializing database schema...")
    # Ensure data directory exists
    os.makedirs(PROJECT_ROOT / "data", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "data" / "uploads", exist_ok=True)
    await create_db_and_tables()

    logger.info("Seeding mock assets and inspections...")
    async with AsyncSessionFactory() as session:
        # Check if assets already exist
        from sqlalchemy import select
        existing = await session.execute(select(Asset).limit(1))
        if existing.scalar():
            logger.info("Database already contains data. Skipping seed.")
            return

        # ── 1. Create Assets ──────────────────────────────────────────────────
        bridge_asset = Asset(
            name="Golden Gate Bridge North Pier",
            asset_type=AssetType.BRIDGE,
            status=AssetStatus.ACTIVE,
            location="37.8199 N, 122.4783 W",
            description="Reinforced concrete pier foundation subjected to marine spray and tidal action.",
            construction_year=1937,
            material="reinforced concrete",
            design_life_years=100.0,
            latest_health_score=82.5,
        )

        tunnel_asset = Asset(
            name="Lincoln Tunnel South Tube",
            asset_type=AssetType.TUNNEL,
            status=AssetStatus.ACTIVE,
            location="40.7628 N, 74.0085 W",
            description="Concrete lining section subjected to heavy exhaust emissions and traffic vibrations.",
            construction_year=1937,
            material="steel-reinforced concrete segment panels",
            design_life_years=120.0,
            latest_health_score=68.0,
        )

        building_asset = Asset(
            name="HQ Parking Structure Deck C",
            asset_type=AssetType.BUILDING,
            status=AssetStatus.UNDER_MAINTENANCE,
            location="40.7128 N, 74.0060 W",
            description="Multi-story post-tensioned slab parking garage deck.",
            construction_year=2005,
            material="post-tensioned concrete",
            design_life_years=50.0,
            latest_health_score=45.2,
        )

        session.add_all([bridge_asset, tunnel_asset, building_asset])
        await session.flush()  # assign IDs

        # ── 2. Create Inspections ─────────────────────────────────────────────
        # Bridge Inspection
        bridge_insp = Inspection(
            asset_id=bridge_asset.id,
            status=InspectionStatus.COMPLETED,
            source=InspectionSource.IMAGE,
            input_path="/uploads/bridge_pier_001.png",
            notes="Routine visual inspection of splash zone.",
            defect_count=2,
            health_score=82.5,
            processing_time_ms=350.2,
        )

        # Tunnel Inspection
        tunnel_insp = Inspection(
            asset_id=tunnel_asset.id,
            status=InspectionStatus.COMPLETED,
            source=InspectionSource.IMAGE,
            input_path="/uploads/tunnel_seg_42.png",
            notes="Annual structural integrity inspection.",
            defect_count=4,
            health_score=68.0,
            processing_time_ms=410.8,
        )

        # Building Inspection
        building_insp = Inspection(
            asset_id=building_asset.id,
            status=InspectionStatus.COMPLETED,
            source=InspectionSource.DRONE,
            input_path="/uploads/drone_deck_c.png",
            notes="Drone crack mapping survey.",
            defect_count=7,
            health_score=45.2,
            processing_time_ms=1240.0,
        )

        session.add_all([bridge_insp, tunnel_insp, building_insp])
        await session.flush()

        # ── 3. Create Detections ──────────────────────────────────────────────
        # Bridge defects
        bridge_det_1 = Detection(
            inspection_id=bridge_insp.id,
            defect_type=DefectType.CRACK,
            confidence=0.89,
            bbox_x1=0.25, bbox_y1=0.30, bbox_x2=0.28, bbox_y2=0.65,
            area_px=1420.0, length_px=450.0, width_px=3.2, orientation_deg=85.0
        )
        bridge_det_2 = Detection(
            inspection_id=bridge_insp.id,
            defect_type=DefectType.CORROSION,
            confidence=0.76,
            bbox_x1=0.60, bbox_y1=0.45, bbox_x2=0.72, bbox_y2=0.55,
            area_px=3400.0
        )

        # Tunnel defects
        tunnel_det_1 = Detection(
            inspection_id=tunnel_insp.id,
            defect_type=DefectType.CRACK,
            confidence=0.92,
            bbox_x1=0.10, bbox_y1=0.15, bbox_x2=0.55, bbox_y2=0.20,
            area_px=2200.0, length_px=820.0, width_px=2.7, orientation_deg=5.0
        )
        tunnel_det_2 = Detection(
            inspection_id=tunnel_insp.id,
            defect_type=DefectType.SPALLING,
            confidence=0.81,
            bbox_x1=0.75, bbox_y1=0.60, bbox_x2=0.88, bbox_y2=0.78,
            area_px=8500.0
        )

        # Building defects (High Severity)
        building_det_1 = Detection(
            inspection_id=building_insp.id,
            defect_type=DefectType.CRACK,
            confidence=0.95,
            bbox_x1=0.05, bbox_y1=0.08, bbox_x2=0.90, bbox_y2=0.12,
            area_px=12000.0, length_px=1850.0, width_px=6.5, orientation_deg=-2.0
        )
        building_det_2 = Detection(
            inspection_id=building_insp.id,
            defect_type=DefectType.EXPOSED_REINFORCEMENT,
            confidence=0.91,
            bbox_x1=0.40, bbox_y1=0.50, bbox_x2=0.52, bbox_y2=0.70,
            area_px=6400.0
        )

        session.add_all([bridge_det_1, bridge_det_2, tunnel_det_1, tunnel_det_2, building_det_1, building_det_2])

        # ── 4. Create Health Records ──────────────────────────────────────────
        bridge_hr = HealthRecord(
            inspection_id=bridge_insp.id,
            health_score=82.5,
            risk_level=RiskLevel.LOW,
            severity_details={"crack": 1.2, "corrosion": 2.5},
            failure_modes={"shear": False, "flexural": True},
            inspection_priority="routine",
            notes="Structure in stable condition. Corrosion spot requires minor patch."
        )

        tunnel_hr = HealthRecord(
            inspection_id=tunnel_insp.id,
            health_score=68.0,
            risk_level=RiskLevel.MEDIUM,
            severity_details={"crack": 2.1, "spalling": 4.8},
            failure_modes={"shear": True, "compression": False},
            inspection_priority="routine",
            notes="Transverse crack observed on segment panel 42. Minor spalling near joint."
        )

        building_hr = HealthRecord(
            inspection_id=building_insp.id,
            health_score=45.2,
            risk_level=RiskLevel.HIGH,
            severity_details={"crack": 8.5, "exposed_reinforcement": 9.2},
            failure_modes={"flexural": True, "punching_shear": True},
            inspection_priority="urgent",
            notes="Large structural crack crossing main deck spans. Rebar exposure indicates severe carbonation."
        )

        session.add_all([bridge_hr, tunnel_hr, building_hr])
        await session.commit()
        logger.info("Database successfully seeded with mock data.")


if __name__ == "__main__":
    asyncio.run(seed())
