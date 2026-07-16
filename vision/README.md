# Vision Engine — Phase 2

**Status**: 🔜 Not yet implemented. Awaiting Phase 1 approval.

## Planned Modules

```
vision/
├── pipeline/
│   ├── base.py                  ← Abstract InferencePipeline interface
│   ├── detection_pipeline.py    ← YOLO11 object detection
│   └── segmentation_pipeline.py ← YOLO11-seg + mask processing
├── preprocessing/
│   ├── image_loader.py          ← Multi-source loader (file/URL/stream/drone)
│   ├── video_loader.py          ← Frame extraction and streaming
│   └── slicing.py               ← Overlap-aware image slicer (rewritten from WhatTheCrack)
├── postprocessing/
│   ├── mask_fusion.py           ← Binary mask OR-fusion across instances
│   ├── skeletonizer.py          ← Crack centerline + length measurement
│   ├── crack_graph.py           ← NetworkX crack topology graph
│   └── measurements.py          ← Width, area, orientation extraction
└── models/
    └── model_registry.py        ← Model loader with DI + device auto-detection
```

## Supported Defect Types
- Cracks (hairline, structural, diagonal)
- Spalling
- Corrosion
- Delamination
- Exposed reinforcement
- Potholes / Surface damage

## Key Algorithms Inherited from Legacy (WhatTheCrack)
- Sliced inference with configurable overlap
- Skeletonization via `skimage.morphology.skeletonize`
- Junction/endpoint detection via convolution kernel `[[1,1,1],[1,10,1],[1,1,1]]`
- Graph-based crack length via NetworkX BFS
