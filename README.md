# Weed Puller WP-1

Concept design for a small autonomous robot that finds weeds by species, pulls them out at the root with a four-tine plunge head, and backfills each hole with sand, like divot repair on a golf course. It's light enough to lift into the back of an ATV. It works inside a GPS perimeter you set, avoids exclusion zones, and maps the property on its first run.

## Interactive 3D render

Open [`render/index.html`](render/index.html) in a browser. It's a single file, and Three.js loads from a CDN.

- Animated 3D model running the full pull cycle: patrol → detect → align → plunge → close → twist & extract → bin → step → backfill
- Inset showing the robot's down-looking vision camera with live detection boxes (target / scanning / keep)
- View presets (overview, extraction close-up, side elevation, transport), a cutaway shell and labelled components
- Work-area planner: auto-mapped property boundary, operating perimeter, exclusion zones, LiDAR obstacles and coverage lanes. Drag on the map to add a zone, or replay the auto-map run.

## Design summary

| | |
|---|---|
| Envelope | 850 × 610 × 505 mm (mast folded), 565 mm mast up. Fits crosswise on a standard ATV rear rack |
| Mass | 18.5 kg dry, 24.5 kg with a full sand tank. Two side carry handles, four strap points |
| Drive | 4WD skid-steer hub motors, 220 × 90 mm low-pressure tyres (~12 kPa ground pressure), 0.25 m/s working |
| Extraction | 4 × 8 mm stainless pointed tines on a 30 mm pivot circle. They plunge splayed, close under the root ball, twist 30° and lift slowly. Depth 40–130 mm, set per species |
| Backfill | 4 L hopper, auger meters 15–30 ml of dry washed sand per hole. Nozzle sits 180 mm aft of the tine axis and the robot steps forward to line it up |
| Weed bin | 6 L sealed rear bin, so seed heads don't drop back on the lawn |
| Vision | Down-looking global-shutter camera under a shade hood with an LED ring, plus a forward stereo pair for obstacles and people |
| Compute | NVIDIA Jetson Orin Nano, ROS 2 |
| Positioning | Dual-band RTK-GNSS (±2 cm), 2D LiDAR, IMU, wheel odometry |
| Power | 36 V 10 Ah hot-swap Li-ion, about 4 h |

### Weed identification

Two stages, so it still works without mobile coverage:

1. **On-board detection.** A YOLO-class model on the Jetson finds plants and classifies weed vs. keep in real time. Start from open datasets such as DeepWeeds, then fine-tune on photos from your own property.
2. **Species confirmation.** Crops are sent to the **[Plant.id API by Kindwise](https://www.kindwise.com/plant-id)**, which returns species with a confidence score. **[Pl@ntNet](https://my.plantnet.org/)** is the fallback. Requests queue while offline. Check current pricing and licence terms before committing to one.

A keep-list (natives, clover, anything you choose) stops the robot pulling plants you want.

### Location, perimeter and exclusion zones

- **Auto-map.** On the first run the robot follows the fence line with LiDAR and RTK, snaps it to the cadastral parcel boundary and records trees, sheds, tanks and buildings as obstacles. You confirm the boundary in the app before the first job, because a fence line isn't always the legal boundary.
- **Perimeter.** You set the operating area inside the property.
- **Exclusion zones.** Draw any number (veggie garden, septic field, dam, play area). Coverage lanes are replanned around them.
- **Geofence watchdog.** The robot stops if it drifts more than 0.3 m outside an allowed area.

### Soil care

- Tines enter around the crown instead of digging, so about 30 cm³ of soil is displaced per pull and all of it is replaced with sand.
- Slow lift (40 mm/s) so the taproot comes out whole instead of snapping and regrowing.
- Low ground pressure and a working speed of 0.25 m/s, so no ruts or compaction.

## Status

Concept stage. The render is an illustrative model, not engineering CAD. Next steps: mechanical CAD of the extraction head, a bench test of tine geometry in different soil types, and collecting a training set from the target property.
