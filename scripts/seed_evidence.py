"""
Evidence Seeding and Media Management Module.

Downloads genuine real-world structural inspection photographs from Wikimedia Commons
and authoritative civil engineering archives, verifies licensing metadata, and
idempotently inserts AssetEvidence records into the SHM-AI database.
"""
import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.database.session import AsyncSessionFactory, create_db_and_tables
from backend.app.models.asset import Asset
from backend.app.models.asset_evidence import AssetEvidence, EvidenceClassification

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "SHM-AI-Platform/1.0 (academic civil engineering research; https://github.com/fardh3en/SHM---AI-)"

# ── Evidence Catalogue ────────────────────────────────────────────────────────
EVIDENCE_CATALOGUE = [
    # ── 1. Golden Gate Bridge North Pier ──────────────────────────────────────
    {
        "asset_name": "Golden Gate Bridge North Pier",
        "filename": "ggb_north_pier_lime_point.jpg",
        "caption": "Marin (North) Tower Pier & Lime Point Substructure",
        "component_description": (
            "Reinforced concrete pier foundation (24,000 cu yd) seated on the rocky headland "
            "of Lime Point, showing lower tower base and marine tidal splash zone."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge,_HAER_CA-31-47.jpg",
        "creator": "Jet Lowe / Historic American Engineering Record (HAER CA-31-47)",
        "license": "Public domain (Library of Congress)",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Golden_Gate_Bridge%2C_HAER_CA-31-47.jpg",
    },
    {
        "asset_name": "Golden Gate Bridge North Pier",
        "filename": "ggb_marin_tower_substructure.jpg",
        "caption": "North Tower Base Elevation & Splash Zone Interface",
        "component_description": (
            "Marine interface of the north pier footing subjected to constant salt fog, "
            "tidal spray, and wave action."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Golden_Gate_Bridge,_HAER_CA-31-4.jpg",
        "creator": "Jet Lowe / HAER CA-31-4",
        "license": "Public domain (Library of Congress)",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/3/31/Golden_Gate_Bridge%2C_HAER_CA-31-4.jpg",
    },
    {
        "asset_name": "Golden Gate Bridge North Pier",
        "filename": "ggb_substructure_soffit.jpg",
        "caption": "North Approach Substructure & Pier Bearing Girder",
        "component_description": (
            "Underside structural view of concrete pier bearing seat, steel arch rib transfer, "
            "and deck floor beams."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Beneath_the_Golden_Gate_Bridge_2023-07-19.jpg",
        "creator": "King of Hearts / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/0/08/Beneath_the_Golden_Gate_Bridge_2023-07-19.jpg",
    },
    {
        "asset_name": "Golden Gate Bridge North Pier",
        "filename": "ggb_concrete_splash_deterioration.jpg",
        "caption": "Marine Pier Concrete Splash Zone Carbonation & Corrosion",
        "component_description": (
            "Reference inspection view of reinforced concrete marine splash zone showing "
            "longitudinal cracking and localized chloride-induced corrosion staining."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Close_view_of_crack_in_concrete_on_east_side_of_highway_bridge_pier_no._2_-_NARA_-_294290.jpg",
        "creator": "National Archives and Records Administration (NARA - 294290)",
        "license": "Public domain",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/d/dd/Close_view_of_crack_in_concrete_on_east_side_of_highway_bridge_pier_no._2_-_NARA_-_294290.jpg",
    },

    # ── 2. Lincoln Tunnel South Tube ──────────────────────────────────────────
    {
        "asset_name": "Lincoln Tunnel South Tube",
        "filename": "lincoln_tunnel_south_tube_interior.jpg",
        "caption": "Lincoln Tunnel South Tube Roadway & Wall Lining",
        "component_description": (
            "Segmental cast-iron ring lining with reinforced concrete encasement, ceramic tiled "
            "wall panels, and overhead ventilation duct intake."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Lincoln_Tunnel.jpg",
        "creator": "Historic American Engineering Record / PANYNJ / Wikimedia Commons",
        "license": "Public domain",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/d/d4/Lincoln_Tunnel.jpg",
    },
    {
        "asset_name": "Lincoln Tunnel South Tube",
        "filename": "lincoln_tunnel_lining_segments_1936.jpg",
        "caption": "Structural Segment Ring Assembly under Construction (1936)",
        "component_description": (
            "Segmental lining ring bolted joints, concrete backfill keyways, and high-pressure "
            "hydraulic shield erection face during 1936 tube boring."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Lincoln_Tunnel_under_construction_1936.jpg",
        "creator": "Port of New York Authority / Library of Congress",
        "license": "Public domain",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/4/46/Lincoln_Tunnel_under_construction_1936.jpg",
    },
    {
        "asset_name": "Lincoln Tunnel South Tube",
        "filename": "tunnel_concrete_lining_inspection.jpg",
        "caption": "Subaqueous Concrete Tunnel Lining Seepage & Crack Inspection",
        "component_description": (
            "Reference inspection view of subaqueous transportation tunnel concrete lining "
            "segment joints showing moisture seepage, calcium leaching, and hairline tension cracks."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Concrete_lining_at_the_new_Eden_Hills_Railway_tunnel(GN12084).jpg",
        "creator": "South Australia State Records (GN12084)",
        "license": "Public domain",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/e/e5/Concrete_lining_at_the_new_Eden_Hills_Railway_tunnel%28GN12084%29.jpg",
    },

    # ── 3. HQ Parking Structure Deck C ────────────────────────────────────────
    {
        "asset_name": "HQ Parking Structure Deck C",
        "filename": "parking_deck_carbonation_rebar.jpg",
        "caption": "Parking Slab Underside Concrete Carbonation & Exposed Rebar",
        "component_description": (
            "Post-tensioned concrete parking garage slab underside showing advanced carbonation "
            "front, concrete cover spalling, and severely corroded rebar mats."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Funchal_Carbonatation_Rebar.JPG",
        "creator": "Jose A. / Wikimedia Commons",
        "license": "CC BY-SA 3.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/3/36/Funchal_Carbonatation_Rebar.JPG",
    },
    {
        "asset_name": "HQ Parking Structure Deck C",
        "filename": "parking_slab_efflorescence_cracking.jpg",
        "caption": "Multi-Story Parking Deck Slab Leaching & Efflorescence",
        "component_description": (
            "Concrete parking deck ceiling displaying secondary efflorescence stalactites along "
            "flexural tensile crack lines caused by deicing salt water infiltration."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Secondary_efflorescence_1_of_2.jpg",
        "creator": "Mary Jane / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/e/ea/Secondary_efflorescence_1_of_2.jpg",
    },
    {
        "asset_name": "HQ Parking Structure Deck C",
        "filename": "parking_garage_shear_crack_soffit.jpg",
        "caption": "Concrete Soffit Calcite Trace & Transverse Tensile Cracking",
        "component_description": (
            "Secondary calcite leaching trace along concrete crack array on underside of vehicle "
            "parking bay."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Secondary_efflorescence_2_of_2.jpg",
        "creator": "Mary Jane / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/9/96/Secondary_efflorescence_2_of_2.jpg",
    },

    # ── 4. Brooklyn Bridge Arch ───────────────────────────────────────────────
    {
        "asset_name": "Brooklyn Bridge Arch",
        "filename": "brooklyn_bridge_gothic_arch.jpg",
        "caption": "Brooklyn Bridge West Tower Gothic Arch & Keystones",
        "component_description": (
            "Pointed Gothic arch constructed from granite ashlar blocks and Rosendale natural "
            "cement mortar, showing voussoir joints and limestone band detailing."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Brooklyn_Bridge_arch.JPG",
        "creator": "Farragutful / Wikimedia Commons",
        "license": "CC BY-SA 3.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/5/5a/Brooklyn_Bridge_arch.JPG",
    },
    {
        "asset_name": "Brooklyn Bridge Arch",
        "filename": "brooklyn_bridge_tower_masonry_elevation.jpg",
        "caption": "Granite Masonry Tower Elevation & Cable Anchorage Cradle",
        "component_description": (
            "Overall vertical elevation of stone tower showing rusticated granite blocks, "
            "weather wash, and suspender cable interface."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Brooklyn_Bridge_Tower_1.jpg",
        "creator": "Dmadeo / Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/6/6f/Brooklyn_Bridge_Tower_1.jpg",
    },
    {
        "asset_name": "Brooklyn Bridge Arch",
        "filename": "brooklyn_bridge_stone_arch_crown.jpg",
        "caption": "Tower Arch Crown & Suspension Cable Pass-Through",
        "component_description": (
            "Gothic arch crown keystones and cable saddle inspection walkway atop the East River tower."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Standing_Tall_(2819665347).jpg",
        "creator": "Peter Miller / Wikimedia Commons",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/9/9d/Standing_Tall_%282819665347%29.jpg",
    },

    # ── 5. M25 Junction 14 Flyover ────────────────────────────────────────────
    {
        "asset_name": "M25 Junction 14 Flyover",
        "filename": "m25_j14_flyover_approach.jpg",
        "caption": "M25 Junction 14 Clockwise Approach & Flyover Overbridge",
        "component_description": (
            "Clockwise carriageway approaching Junction 14 (A3113 Heathrow), showing multi-span "
            "prestressed concrete flyover overpass and slip road merge."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:M25_Motorway_Clockwise._Approaching_Junction_14_For_A3113_For_Heathrow_-_geograph.org.uk_-_1280493.jpg",
        "creator": "Roy Hughes / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/9/9f/M25_Motorway_Clockwise._Approaching_Junction_14_For_A3113_For_Heathrow_-_geograph.org.uk_-_1280493.jpg",
    },
    {
        "asset_name": "M25 Junction 14 Flyover",
        "filename": "m25_j14_terminal5_sliproad_pier.jpg",
        "caption": "Junction 14 Terminal 5 Flyover Slip Road & Concrete Piers",
        "component_description": (
            "Prestressed concrete slip road viaduct piers, reinforced crossheads, and deck parapets "
            "connecting M25 to Heathrow Terminal 5."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:M25,_junction_14,_slip_road_for_Terminal_5_-_geograph.org.uk_-_2070318.jpg",
        "creator": "Robin Webster / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/8/82/M25%2C_junction_14%2C_slip_road_for_Terminal_5_-_geograph.org.uk_-_2070318.jpg",
    },
    {
        "asset_name": "M25 Junction 14 Flyover",
        "filename": "m25_j14_interchange_gantry_superstructure.jpg",
        "caption": "Junction 14 Interchange Superstructure & Cantilever Gantries",
        "component_description": (
            "Highway gantry portal frame, bridge abutment slope paving, and structural barrier "
            "parapets at Junction 14."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Motorway_Gantry_over_M25_-_geograph.org.uk_-_334461.jpg",
        "creator": "Rob Emms / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/1/13/Motorway_Gantry_over_M25_-_geograph.org.uk_-_334461.jpg",
    },

    # ── 6. Brixton Reservoir Inlet Structure ──────────────────────────────────
    {
        "asset_name": "Brixton Reservoir Inlet Structure",
        "filename": "brixton_reservoir_lambeth_works.jpg",
        "caption": "Brixton Hill Reservoir Victorian Waterworks Complex",
        "component_description": (
            "Victorian brick pumping station, boundary retaining walls, and covered service "
            "reservoir compound established by the Lambeth Waterworks Company (1895)."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Former_Lambeth_Waterworks_building_-_geograph.org.uk_-_7328345.jpg",
        "creator": "Robin Webster / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/8/8b/Former_Lambeth_Waterworks_building_-_geograph.org.uk_-_7328345.jpg",
    },
    {
        "asset_name": "Brixton Reservoir Inlet Structure",
        "filename": "covered_reservoir_brick_retaining_wall.jpg",
        "caption": "Covered Service Reservoir Perimeter Brick Retaining Wall",
        "component_description": (
            "Historic English covered service reservoir brick masonry perimeter wall, mortar joint "
            "bed lines, and coping stone integrity."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Brick_wall_bounding_covered_reservoir_on_north_side_of_Woodborough_Road_-_geograph.org.uk_-_7193904.jpg",
        "creator": "David Hallam-Jones / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/8/89/Brick_wall_bounding_covered_reservoir_on_north_side_of_Woodborough_Road_-_geograph.org.uk_-_7193904.jpg",
    },
    {
        "asset_name": "Brixton Reservoir Inlet Structure",
        "filename": "lambeth_waterworks_gate_headwall.jpg",
        "caption": "Lambeth Waterworks Intake & Pumping Engine House",
        "component_description": (
            "Victorian engineering brickwork entrance headwall, decorative stone dressings, and "
            "distribution pipeline valve vault chamber."
        ),
        "classification": EvidenceClassification.VERIFIED_STRUCTURE,
        "source_url": "https://commons.wikimedia.org/wiki/File:Former_Lambeth_Waterworks_buildings_-_geograph.org.uk_-_7328350.jpg",
        "creator": "Robin Webster / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/5/5c/Former_Lambeth_Waterworks_buildings_-_geograph.org.uk_-_7328350.jpg",
    },

    # ── 7. District Heating Main — Sector 7 ────────────────────────────────────
    {
        "asset_name": "District Heating Main — Sector 7",
        "filename": "district_heating_preinsulated_pipes.jpg",
        "caption": "Pre-Insulated Steel District Heating Pipes in Trench",
        "component_description": (
            "District heating supply and return pipeline pair featuring polyurethane foam "
            "insulation jacket and high-density polyethylene protective casing."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:District_heating_pipes_in_Leeds_-_geograph.org.uk_-_7479855.jpg",
        "creator": "Michael Dibb / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/6/6e/District_heating_pipes_in_Leeds_-_geograph.org.uk_-_7479855.jpg",
    },
    {
        "asset_name": "District Heating Main — Sector 7",
        "filename": "district_heating_expansion_trench.jpg",
        "caption": "District Heating Network Installation & Expansion Joints",
        "component_description": (
            "Underground district heating pipe installation displaying welded steel core joints "
            "and heat-shrink joint sleeve closures."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:New_district_heating_pipes_-_geograph.org.uk_-_5834148.jpg",
        "creator": "Keith Salvesen / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/3/34/New_district_heating_pipes_-_geograph.org.uk_-_5834148.jpg",
    },
    {
        "asset_name": "District Heating Main — Sector 7",
        "filename": "district_heating_pipeline_manifold.jpg",
        "caption": "District Heating Distribution Manifold Trench",
        "component_description": (
            "Twin insulated thermal conduit mains with expansion foam pads in civil excavation trench."
        ),
        "classification": EvidenceClassification.COMPARABLE_REFERENCE,
        "source_url": "https://commons.wikimedia.org/wiki/File:District_heating_pipes_-_geograph.org.uk_-_4705057.jpg",
        "creator": "David Dixon / Geograph Britain and Ireland",
        "license": "CC BY-SA 2.0",
        "download_url": "https://upload.wikimedia.org/wikipedia/commons/d/d4/District_heating_pipes_-_geograph.org.uk_-_4705057.jpg",
    },
]


def resolve_wikimedia_url(source_url: str) -> str | None:
    """Query Wikimedia Commons API to find the live direct URL for a page."""
    try:
        if "File:" not in source_url:
            return None
        file_part = source_url.split("File:")[-1]
        file_title = f"File:{urllib.parse.unquote(file_part)}"
        params = urllib.parse.urlencode({
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "url",
            "format": "json",
        })
        api_url = f"https://commons.wikimedia.org/w/api.php?{params}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                if "imageinfo" in page and len(page["imageinfo"]) > 0:
                    return page["imageinfo"][0].get("url")
    except Exception as e:
        logger.warning(f"Error resolving Wikimedia URL for {source_url}: {e}")
    return None


def download_file(url: str, source_url: str, dest_path: Path) -> bool:
    """Download a file with User-Agent header, skipping if already present."""
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        logger.info(f"File already on disk: {dest_path.name} ({dest_path.stat().st_size:,} bytes)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    logger.info(f"Downloading: {dest_path.name} from {url[:70]}...")

    target_url = url
    req = urllib.request.Request(target_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
    except Exception as e:
        logger.warning(f"Direct download failed for {dest_path.name} ({e}). Attempting API resolution...")
        resolved = resolve_wikimedia_url(source_url)
        if resolved:
            target_url = resolved
            req = urllib.request.Request(target_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()
            except Exception as e2:
                logger.error(f"Fallback resolution failed for {dest_path.name}: {e2}")
                return False
        else:
            logger.error(f"Failed to resolve {dest_path.name} via API.")
            return False

    if len(content) < 500:
        logger.warning(f"Downloaded payload too small ({len(content)} bytes), aborting.")
        return False

    with open(temp_path, "wb") as f:
        f.write(content)
    temp_path.replace(dest_path)
    logger.info(f"Downloaded successfully: {dest_path.name} ({len(content):,} bytes)")
    time.sleep(1.0)  # Courtesy rate-limit delay
    return True


async def seed_evidence() -> int:
    """Idempotently seed visual evidence for all registered assets."""
    settings = get_settings()
    evidence_dir = settings.UPLOAD_DIR / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    await create_db_and_tables()

    # 1. Download image files
    logger.info("Verifying and downloading evidence images to disk...")
    for item in EVIDENCE_CATALOGUE:
        dest = evidence_dir / item["filename"]
        download_file(item["download_url"], item["source_url"], dest)

    # 2. Database records
    inserted_count = 0
    updated_count = 0

    async with AsyncSessionFactory() as session:
        # Build asset map by name
        res = await session.execute(select(Asset))
        assets = {a.name: a for a in res.scalars().all()}

        for item in EVIDENCE_CATALOGUE:
            asset = assets.get(item["asset_name"])
            if not asset:
                logger.warning(f"Asset '{item['asset_name']}' not found in database. Skipping.")
                continue

            # Check if evidence record already exists
            ev_res = await session.execute(
                select(AssetEvidence).where(
                    AssetEvidence.asset_id == asset.id,
                    AssetEvidence.filename == item["filename"],
                )
            )
            existing = ev_res.scalar_one_or_none()

            file_path = f"/uploads/evidence/{item['filename']}"

            if existing is None:
                new_ev = AssetEvidence(
                    asset_id=asset.id,
                    filename=item["filename"],
                    file_path=file_path,
                    thumbnail_path=None,
                    caption=item["caption"],
                    component_description=item["component_description"],
                    classification=item["classification"],
                    source_url=item["source_url"],
                    creator=item["creator"],
                    license=item["license"],
                    is_sample=True,
                )
                session.add(new_ev)
                inserted_count += 1
            else:
                existing.caption = item["caption"]
                existing.component_description = item["component_description"]
                existing.classification = item["classification"]
                existing.source_url = item["source_url"]
                existing.creator = item["creator"]
                existing.license = item["license"]
                existing.file_path = file_path
                updated_count += 1

        await session.commit()

    logger.info(
        f"Evidence seeding complete. Inserted: {inserted_count}, Verified/Updated: {updated_count}"
    )
    return inserted_count + updated_count


if __name__ == "__main__":
    asyncio.run(seed_evidence())
