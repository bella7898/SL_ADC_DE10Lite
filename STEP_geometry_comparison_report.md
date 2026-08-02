# STEP geometry comparison

Compared files:

- **A:** `650PM.step` (KiCad export timestamp 2026-08-01 18:50:02)
- **B:** `C:\Users\Smitt\Downloads\step` (KiCad export timestamp 2026-07-08 22:53:44)

All dimensions and coordinates below are in millimetres, in the coordinate system stored in the STEP files.

## Summary

The parts have the same overall envelope and thickness. All 68 holes of 1.00 mm diameter and all four holes of 4.00 mm diameter have exactly the same size and axis location in the STEP data.

There are two geometric differences:

1. B has 40 holes of 0.30 mm diameter, versus 29 in A. Five of these small holes are common to both files. A therefore has 24 small-hole locations absent from B, and B has 35 small-hole locations absent from A.
2. One curved outline transition near `(X≈11, Y≈-55)` differs by about 0.01 mm. The remaining outline geometry is identical.

## Overall dimensions

| Measurement | A | B | Difference |
|---|---:|---:|---:|
| X extent | -0.500000 to 97.500000 | -0.500000 to 97.500000 | 0 |
| Y extent | -66.525126 to 0.500000 | -66.525126 to 0.500000 | 0 |
| Z extent / thickness | 0 to 1.510000 | 0 to 1.510000 | 0 |
| Bounding-box size | 98.000000 × 67.025126 × 1.510000 | 98.000000 × 67.025126 × 1.510000 | 0 × 0 × 0 |

## Hole comparison

| Diameter | A count | B count | Common at identical locations | Result |
|---:|---:|---:|---:|---|
| 4.00 | 4 | 4 | 4 | Identical |
| 1.00 | 68 | 68 | 68 | Identical |
| 0.30 | 29 | 40 | 5 | Different pattern; B has 11 more holes net |
| **Total** | **101** | **112** | **77** | **B has 11 more holes net** |

For the 72 common 1.00 mm and 4.00 mm holes, the maximum center displacement and diameter difference represented in the files are both exactly 0.

The five common 0.30 mm hole centers are:

`(42.000, -31.575)`, `(49.500, -25.500)`, `(50.500, -25.500)`, `(51.500, -25.500)`, `(52.500, -25.500)`

### 0.30 mm centers present only in A (24)

```text
(34.860, -28.270)   (38.820, -28.030)   (42.680, -28.040)
(45.970, -31.880)   (46.350, -38.440)   (48.700, -33.020)
(49.530, -23.450)   (50.210, -33.740)   (50.530, -23.450)
(50.630, -38.4375)  (51.500, -21.280)   (51.530, -23.450)
(51.570, -15.110)   (51.960, -32.980)   (52.530, -23.450)
(53.480, -32.970)   (53.490, -25.510)   (53.520, -23.460)
(54.590, -38.480)   (60.520, -19.290)   (60.940, -25.790)
(62.16125, -30.065) (63.01125, -33.345) (65.180, -27.2625)
```

### 0.30 mm centers present only in B (35)

```text
(34.920, -26.530)   (36.000, -48.000)   (42.000, -29.500)
(47.500, -25.500)   (47.500, -24.000)   (48.500, -24.000)
(48.517961, -25.508552)                 (49.000, -31.500)
(49.000, -26.500)   (49.070, -35.270)   (49.500, -24.000)
(50.500, -24.000)   (51.500, -26.500)   (51.500, -24.000)
(51.500, -20.500)   (51.500, -15.500)   (52.000, -31.500)
(52.500, -24.000)   (53.000, -23.000)   (53.000, -22.000)
(53.000, -21.000)   (53.000, -20.000)   (53.520, -35.590)
(54.000, -31.500)   (54.000, -26.500)   (54.500, -48.000)
(54.500, -23.000)   (54.500, -22.000)   (54.500, -21.000)
(54.500, -20.000)   (57.000, -48.000)   (60.000, -20.500)
(62.500, -32.000)   (62.500, -29.925)   (66.770, -26.060)
```

Because the counts and patterns differ, there is no unique one-to-one correspondence for the changed 0.30 mm holes. As a scale indication only, the nearest center in the opposite file is 0.367 mm away at minimum. The median nearest-center distance is approximately 1.5 mm. These are pattern changes, not STEP export rounding noise.

At 1.51 mm thickness, each 0.30 mm through-hole removes approximately 0.1067 mm³. B therefore removes approximately 1.174 mm³ more material from its 11-hole net increase, excluding the very small outline change.

## Outline comparison

The bounding envelope is unchanged. Fifteen of the 16 cylindrical outline wall segments match exactly. One local curved transition differs:

| Feature | A | B | Absolute change |
|---|---:|---:|---:|
| Arc center X | 11.980646 | 11.988623 | +0.007977 |
| Arc center Y | -56.416492 | -56.421459 | -0.004967 |
| Arc-center displacement | — | — | 0.009397 |
| Arc radius | 3.459118 | 3.458688 | -0.000430 |
| First adjoining endpoint | (11.300, -53.025) | (11.310, -53.030) | 0.011180 displacement |
| Second adjoining endpoint | (8.522543, -56.500278) | (8.530968, -56.505976) | 0.010169 displacement |

The maximum observed boundary-vertex shift in this changed region is 0.01118 mm (11.18 µm). All other outline vertices and cylindrical outline segments match.

## Method and interpretation

The comparison resolves the STEP B-rep entities directly: manifold solid vertices, circular edges, cylindrical surfaces, their axes, radii, and axis origins. Hole diameter is twice the cylindrical-surface radius. Identical means the corresponding values in the two STEP files are numerically identical, rather than merely equal after a loose visual tolerance.

The STEP files contain bare solids rather than design intent, so they do not identify which reference designator or PCB feature created each 0.30 mm hole. The coordinates above are the reliable basis for locating those changes in KiCad.
