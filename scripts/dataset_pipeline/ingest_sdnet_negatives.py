"""
Ingests verified uncracked concrete structural images from SDNET2018 as hard negative samples.

STRICT CONCRETE-ONLY RULES:
1. Concrete Structures Priority: Only uncracked concrete walls (UW) and bridge decks/slabs (UD)
   are ingested by default. Pavements (UP) and road surfaces are excluded.
2. SDNET2018 is an image classification dataset (256x256 sub-images).
3. Cracked subfolders (CD, CW, CP) DO NOT locate individual cracks and must NEVER
   be given invented/fabricated full-frame bounding boxes.
4. Uncracked subfolders (UD, UW) represent verified, authentic undamaged concrete
   (decks, walls, slabs) and are ingested as true hard negative samples with 0-byte labels.
"""
import shutil
from pathlib import Path
from typing import Any

# Retain structural concrete walls and bridge decks; exclude road/pavement
STRUCTURAL_CONCRETE_NEGATIVE_SUBSETS = {
    "UW": "Uncracked Concrete Wall (Structural)",
    "UD": "Uncracked Concrete Bridge Deck (Structural Slab)",
}

EXCLUDED_ROAD_SUBSETS = {
    "UP": "Uncracked Pavement (Excluded - Road/Pavement)",
    "CP": "Cracked Pavement (Excluded - Road/Pavement)",
}

RESERVED_UNLOCALIZED_SUBSETS = {
    "CW": "Cracked Concrete Wall (unlocalized - no bounding boxes)",
    "CD": "Cracked Concrete Bridge Deck (unlocalized - no bounding boxes)",
}


def ingest_sdnet_negatives(
    sdnet_root: Path,
    dst_images_dir: Path,
    dst_labels_dir: Path,
    max_samples_per_subset: int = 500,
    include_pavements: bool = False,
) -> dict[str, Any]:
    """
    Sample verified uncracked structural concrete images from SDNET2018 and write 0-byte label files.
    """
    dst_images_dir.mkdir(parents=True, exist_ok=True)
    dst_labels_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "ingested_negatives": 0,
        "by_subset": {},
        "excluded_road_subsets": {},
        "reserved_unlocalized_skipped": 0,
    }

    subsets_to_process = dict(STRUCTURAL_CONCRETE_NEGATIVE_SUBSETS)
    if include_pavements:
        subsets_to_process["UP"] = EXCLUDED_ROAD_SUBSETS["UP"]

    for subset_key, desc in subsets_to_process.items():
        subset_dir = sdnet_root / subset_key
        # Check alternative folder structures e.g. W/UW, D/UD
        if not subset_dir.is_dir():
            candidates = list(sdnet_root.glob(f"**/{subset_key}"))
            subset_dir = candidates[0] if candidates else None

        if subset_dir is None or not subset_dir.is_dir():
            continue

        images = sorted([p for p in subset_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
        sampled = images[:max_samples_per_subset]
        count = 0

        for img in sampled:
            target_img_name = f"sdnet_{subset_key.lower()}_{img.name}"
            target_img_path = dst_images_dir / target_img_name
            target_lbl_path = dst_labels_dir / f"{target_img_path.stem}.txt"

            shutil.copy2(img, target_img_path)
            target_lbl_path.write_text("", encoding="utf-8")  # 0-byte negative label
            count += 1

        summary["by_subset"][subset_key] = {"count": count, "description": desc}
        summary["ingested_negatives"] += count

    # Audit excluded road pavement
    if not include_pavements:
        for road_key, desc in EXCLUDED_ROAD_SUBSETS.items():
            candidates = list(sdnet_root.glob(f"**/{road_key}"))
            if candidates and candidates[0].is_dir():
                count = len(list(candidates[0].glob("*.jpg")))
                summary["excluded_road_subsets"][road_key] = {"count": count, "reason": "Road/pavement surface excluded"}

    # Log reminder about unlocalized cracked folders
    for reserved_key, desc in RESERVED_UNLOCALIZED_SUBSETS.items():
        candidates = list(sdnet_root.glob(f"**/{reserved_key}"))
        if candidates and candidates[0].is_dir():
            unloc_count = len(list(candidates[0].glob("*.jpg")))
            summary["reserved_unlocalized_skipped"] += unloc_count

    return summary
