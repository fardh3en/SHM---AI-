"""
Development seed script — inserts realistic demo assets and inspections.

This data is clearly labelled as DEVELOPMENT / DEMO data.
It does NOT represent results from a real analysis pipeline.
It does NOT delete or overwrite existing records.
It is NOT exposed through a public API endpoint.

Idempotency: each asset is identified by its name.  If a named asset already
exists the record (and its dependent inspections) is skipped, so the script
is safe to run multiple times.

Usage:
    python scripts/seed_db.py            # from project root
"""
import asyncio
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap sys.path so that backend package is importable when this script
# is run from the project root (or from scripts/).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings  # noqa: F401 — triggers env load
from backend.app.database.session import AsyncSessionFactory, create_db_and_tables
from backend.app.models.asset import Asset, AssetStatus, AssetType
from backend.app.models.inspection import Inspection, InspectionSource, InspectionStatus
from backend.app.models.detection import Detection, DefectType
from backend.app.models.health_record import HealthRecord, RiskLevel

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------

ASSET_DEFS = [
    # ── existing three assets (originally in seed v1) ─────────────────────
    dict(
        name="Golden Gate Bridge North Pier",
        asset_type=AssetType.BRIDGE,
        status=AssetStatus.ACTIVE,
        location="37.8199 N, 122.4783 W",
        description="[DEMO] Reinforced concrete pier foundation subjected to marine spray and tidal action.",
        construction_year=1937,
        material="reinforced concrete",
        design_life_years=100.0,
        latest_health_score=82.5,
    ),
    dict(
        name="Lincoln Tunnel South Tube",
        asset_type=AssetType.TUNNEL,
        status=AssetStatus.ACTIVE,
        location="40.7628 N, 74.0085 W",
        description="[DEMO] Concrete lining section subjected to heavy exhaust emissions and traffic vibrations.",
        construction_year=1937,
        material="steel-reinforced concrete segment panels",
        design_life_years=120.0,
        latest_health_score=68.0,
    ),
    dict(
        name="HQ Parking Structure Deck C",
        asset_type=AssetType.BUILDING,
        status=AssetStatus.UNDER_MAINTENANCE,
        location="40.7128 N, 74.0060 W",
        description="[DEMO] Multi-story post-tensioned slab parking garage deck.",
        construction_year=2005,
        material="post-tensioned concrete",
        design_life_years=50.0,
        latest_health_score=45.2,
    ),
    # ── three new assets ───────────────────────────────────────────────────
    dict(
        name="M25 Junction 14 Flyover",
        asset_type=AssetType.ROAD,
        status=AssetStatus.ACTIVE,
        location="51.4731 N, 0.5527 W",
        description="[DEMO] Prestressed concrete flyover bridge carrying motorway traffic over the slip road interchange.",
        construction_year=1986,
        material="prestressed concrete",
        design_life_years=60.0,
        latest_health_score=74.0,
    ),
    dict(
        name="Brixton Reservoir Inlet Structure",
        asset_type=AssetType.DAM,
        status=AssetStatus.ACTIVE,
        location="51.4389 N, 0.1145 W",
        description="[DEMO] Masonry inlet works forming part of a Victorian-era service reservoir.",
        construction_year=1895,
        material="brick masonry",
        design_life_years=150.0,
        latest_health_score=61.0,
    ),
    dict(
        name="District Heating Main — Sector 7",
        asset_type=AssetType.PIPELINE,
        status=AssetStatus.INACTIVE,
        location="53.4808 N, 2.2426 W",
        description="[DEMO] Insulated steel district-heating pipe subjected to thermal cycling and soil loading.",
        construction_year=2002,
        material="carbon steel with polyurethane insulation",
        design_life_years=40.0,
        latest_health_score=None,  # never inspected yet
    ),
]


# Inspection definitions reference asset names so we can look up live UUIDs.
# Inspections that have not been processed have no input_path, no health_score,
# and defect_count=0 — they are clearly "pending" or "manual" entries.

INSPECTION_DEFS = [
    # ── Bridge: 2 inspections ─────────────────────────────────────────────
    dict(
        asset_name="Golden Gate Bridge North Pier",
        status=InspectionStatus.COMPLETED,
        source=InspectionSource.IMAGE,
        input_path="/uploads/evidence/ggb_marin_tower_substructure.jpg",
        notes="[DEMO] Routine visual inspection of splash zone.",
        defect_count=2,
        health_score=82.5,
        processing_time_ms=350.2,
        detections=[
            dict(defect_type=DefectType.CRACK, confidence=0.89,
                 bbox_x1=0.25, bbox_y1=0.30, bbox_x2=0.28, bbox_y2=0.65,
                 area_px=1420.0, length_px=450.0, width_px=3.2, orientation_deg=85.0),
            dict(defect_type=DefectType.CORROSION, confidence=0.76,
                 bbox_x1=0.60, bbox_y1=0.45, bbox_x2=0.72, bbox_y2=0.55,
                 area_px=3400.0),
        ],
        health_record=dict(
            health_score=82.5, risk_level=RiskLevel.LOW,
            severity_details={"crack": 1.2, "corrosion": 2.5},
            failure_modes={"shear": False, "flexural": True},
            inspection_priority="routine",
            notes="[DEMO] Structure in stable condition. Corrosion spot requires minor patch.",
        ),
    ),
    dict(
        asset_name="Golden Gate Bridge North Pier",
        status=InspectionStatus.PENDING,
        source=InspectionSource.DRONE,
        input_path=None,
        notes="[DEMO] Scheduled Q4 drone survey — awaiting flight clearance.",
        defect_count=0,
        health_score=None,
        processing_time_ms=None,
    ),
    # ── Tunnel: 2 inspections ─────────────────────────────────────────────
    dict(
        asset_name="Lincoln Tunnel South Tube",
        status=InspectionStatus.COMPLETED,
        source=InspectionSource.IMAGE,
        input_path="/uploads/evidence/lincoln_tunnel_south_tube_interior.jpg",
        notes="[DEMO] Annual structural integrity inspection.",
        defect_count=4,
        health_score=68.0,
        processing_time_ms=410.8,
        detections=[
            dict(defect_type=DefectType.CRACK, confidence=0.92,
                 bbox_x1=0.10, bbox_y1=0.15, bbox_x2=0.55, bbox_y2=0.20,
                 area_px=2200.0, length_px=820.0, width_px=2.7, orientation_deg=5.0),
            dict(defect_type=DefectType.SPALLING, confidence=0.81,
                 bbox_x1=0.75, bbox_y1=0.60, bbox_x2=0.88, bbox_y2=0.78,
                 area_px=8500.0),
        ],
        health_record=dict(
            health_score=68.0, risk_level=RiskLevel.MEDIUM,
            severity_details={"crack": 2.1, "spalling": 4.8},
            failure_modes={"shear": True, "compression": False},
            inspection_priority="routine",
            notes="[DEMO] Transverse crack on segment panel 42. Minor spalling near joint.",
        ),
    ),
    dict(
        asset_name="Lincoln Tunnel South Tube",
        status=InspectionStatus.FAILED,
        source=InspectionSource.CAMERA_FEED,
        input_path="/uploads/evidence/tunnel_concrete_lining_inspection.jpg",
        notes="[DEMO] Automated camera feed review — pipeline failed during processing.",
        defect_count=0,
        health_score=None,
        processing_time_ms=None,
        error_message="Vision pipeline: model weights not found at configured path.",
    ),
    # ── Building: 2 inspections ───────────────────────────────────────────
    dict(
        asset_name="HQ Parking Structure Deck C",
        status=InspectionStatus.COMPLETED,
        source=InspectionSource.DRONE,
        input_path="/uploads/evidence/parking_deck_carbonation_rebar.jpg",
        notes="[DEMO] Drone crack mapping survey.",
        defect_count=7,
        health_score=45.2,
        processing_time_ms=1240.0,
        detections=[
            dict(defect_type=DefectType.CRACK, confidence=0.95,
                 bbox_x1=0.05, bbox_y1=0.08, bbox_x2=0.90, bbox_y2=0.12,
                 area_px=12000.0, length_px=1850.0, width_px=6.5, orientation_deg=-2.0),
            dict(defect_type=DefectType.EXPOSED_REINFORCEMENT, confidence=0.91,
                 bbox_x1=0.40, bbox_y1=0.50, bbox_x2=0.52, bbox_y2=0.70,
                 area_px=6400.0),
        ],
        health_record=dict(
            health_score=45.2, risk_level=RiskLevel.HIGH,
            severity_details={"crack": 8.5, "exposed_reinforcement": 9.2},
            failure_modes={"flexural": True, "punching_shear": True},
            inspection_priority="urgent",
            notes="[DEMO] Large structural crack crossing main deck spans. Rebar exposure indicates severe carbonation.",
        ),
    ),
    dict(
        asset_name="HQ Parking Structure Deck C",
        status=InspectionStatus.PROCESSING,
        source=InspectionSource.IMAGE,
        input_path="/uploads/evidence/parking_slab_efflorescence_cracking.jpg",
        notes="[DEMO] Follow-up image batch — vision pipeline currently running.",
        defect_count=0,
        health_score=None,
        processing_time_ms=None,
    ),
    # ── Road flyover: 1 inspection ────────────────────────────────────────
    dict(
        asset_name="M25 Junction 14 Flyover",
        status=InspectionStatus.COMPLETED,
        source=InspectionSource.IMAGE,
        input_path="/uploads/evidence/m25_j14_flyover_approach.jpg",
        notes="[DEMO] Soffit inspection via cherry-picker. Hairline cracks observed at midspan.",
        defect_count=3,
        health_score=74.0,
        processing_time_ms=680.5,
        detections=[
            dict(defect_type=DefectType.CRACK, confidence=0.87,
                 bbox_x1=0.30, bbox_y1=0.45, bbox_x2=0.35, bbox_y2=0.70,
                 area_px=950.0, length_px=320.0, width_px=1.8, orientation_deg=90.0),
        ],
        health_record=dict(
            health_score=74.0, risk_level=RiskLevel.LOW,
            severity_details={"crack": 1.8},
            failure_modes={"flexural": False, "shear": False},
            inspection_priority="routine",
            notes="[DEMO] Hairline flexural crack at midspan soffit. Monitor at next scheduled inspection.",
        ),
    ),
    # ── Reservoir: 1 inspection (manual) ──────────────────────────────────
    dict(
        asset_name="Brixton Reservoir Inlet Structure",
        status=InspectionStatus.COMPLETED,
        source=InspectionSource.MANUAL,
        input_path=None,
        notes="[DEMO] Manual visual assessment — access restricted, no imaging equipment used.",
        defect_count=2,
        health_score=61.0,
        processing_time_ms=None,
        health_record=dict(
            health_score=61.0, risk_level=RiskLevel.MEDIUM,
            severity_details={"crack": 3.5, "spalling": 2.0},
            failure_modes={"compression": True, "shear": False},
            inspection_priority="routine",
            notes="[DEMO] Mortar joint deterioration on north face. Efflorescence visible at seepage points.",
        ),
    ),
    # ── Pipeline: 1 inspection (pending) ──────────────────────────────────
    dict(
        asset_name="District Heating Main — Sector 7",
        status=InspectionStatus.PENDING,
        source=InspectionSource.MANUAL,
        input_path=None,
        notes="[DEMO] Baseline visual walkover — corridor inspection scheduled for next maintenance window.",
        defect_count=0,
        health_score=None,
        processing_time_ms=None,
    ),
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def seed() -> None:
    """Insert demo records, skipping any asset that already exists by name."""
    import os
    from sqlalchemy import select

    logger.info("Ensuring database schema and data directories exist…")
    os.makedirs(PROJECT_ROOT / "data", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "data" / "uploads", exist_ok=True)
    await create_db_and_tables()

    async with AsyncSessionFactory() as session:
        inserted_assets = 0
        inserted_inspections = 0

        for asset_def in ASSET_DEFS:
            name = asset_def["name"]

            # Idempotency check — skip if this asset is already present
            existing = await session.execute(
                select(Asset).where(Asset.name == name).limit(1)
            )
            if existing.scalar():
                logger.info("  SKIP asset (already exists): %s", name)
                continue

            asset = Asset(**asset_def)
            session.add(asset)
            await session.flush()  # assign UUID before referencing in inspections
            logger.info("  + asset: %s (%s)", name, asset.id)
            inserted_assets += 1

            # Insert associated inspections — copy each def so pops don't mutate globals
            for raw_def in INSPECTION_DEFS:
                if raw_def["asset_name"] != name:
                    continue

                insp_def = dict(raw_def)  # shallow copy; nested lists/dicts re-used safely
                detections = insp_def.pop("detections", [])
                health_record_def = insp_def.pop("health_record", None)
                insp_def.pop("asset_name")

                insp = Inspection(asset_id=asset.id, **insp_def)
                session.add(insp)
                await session.flush()
                logger.info("    + inspection: %s (%s)", insp.status, insp.id)
                inserted_inspections += 1

                for det_def in detections:
                    session.add(Detection(inspection_id=insp.id, **det_def))

                if health_record_def:
                    session.add(HealthRecord(inspection_id=insp.id, **health_record_def))

        await session.commit()

    if inserted_assets == 0:
        logger.info("Nothing new to insert — all seed assets already present.")
    else:
        logger.info(
            "Seed complete: %d asset(s), %d inspection(s) inserted.",
            inserted_assets,
            inserted_inspections,
        )

    # ── Seed visual evidence & genuine inspection photographs ─────────────────
    from scripts.seed_evidence import seed_evidence
    logger.info("Seeding structural evidence photographs and licensing metadata...")
    await seed_evidence()


if __name__ == "__main__":
    asyncio.run(seed())
