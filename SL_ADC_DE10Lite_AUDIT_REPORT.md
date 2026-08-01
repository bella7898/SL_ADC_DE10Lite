# SL_ADC_DE10Lite design audit

Audit date: 2026-08-01  
Audited revision: Git `b0c6d87`, including the uncommitted on-disk PCB state present at audit time  
KiCad checker: 10.0.3  
Scope: read-only schematic, PCB, ADS8528 datasheet, DE10-Lite JP1 pinout, and mechanical comparison to the supplied STEP model

## Executive verdict

The mechanical mating geometry passes with one negligible outline deviation: the DE10 header, the 2x14 analog header, and all four standoff holes are at exactly the same XY coordinates, pitches, and drill diameters as the supplied STEP source geometry. The overall outline extent is unchanged. Three lower-left outline primitives moved by at most 0.0102 mm, which is mechanically immaterial for ordinary PCB fabrication. The current via pattern is different, so the complete board solid is not byte-for-byte/geometrically identical if 0.3 mm via holes are included.

The PCB is fully routed and the current KiCad DRC finds no copper errors, no unrouted items, and no schematic/PCB parity mismatch. The ADS8528 custom symbol's pin numbers agree with the datasheet.

I do **not** recommend releasing the design for assembly yet. There is one stop-ship schematic issue and several interface/layout risks:

1. **Stop-ship - REFN (ADS8528 pin 55) is not connected to AGND.** It is connected only to C16. The datasheet requires REFN to be connected to the reference decoupling capacitor and AGND. This leaves the reference return floating.
2. **Assembly-documentation issue - C16, C18, and C19 have incorrect manufacturer part numbers.** All three specify `CL21B106KOQNNNE`, a 10 uF part. C16 is called out as 0.47 uF and C18/C19 as 0.1 uF. This is not an electrical design defect if the board will be hand-populated with the intended values, but the generated BOM is unsafe for automated purchasing or assembly until corrected.
3. **High - seven numbered GPIO net labels do not match the actual DE10-Lite JP1 GPIO positions.** This is not a copper short, but it is a serious FPGA constraint/firmware integration trap. In particular, the net labelled `GPIO(22)-HW/SW` is physically GPIO_31; physical GPIO_22 is intentionally unconnected.
4. **Accepted design assumption - HVDD is deliberately tied to AVDD on a shared +5 V rail.** This is within both pins' recommended operating ranges and is valid for the intended +/-5 V input case. With the internal 2.5 V reference, firmware must select the +/-2 VREF range for every active channel pair, and the external front end must keep inputs within the actual HVSS/HVDD rails. The shared rail still needs to be clean and well decoupled because its noise reaches both supply domains.
5. **High for ADC performance - reference and supply bypass loops are much longer than the datasheet layout example.** The four REFxP paths to their 10 uF capacitors are about 9.7-11.1 mm; REFIO and REFN paths to C16 are about 12.9 and 10.2 mm. The datasheet places these parts immediately beside the package.

## Audit snapshot and sources

| Item | SHA-256 |
|---|---|
| `SL_ADC_DE10Lite.kicad_sch` | `3CBD19D540D7ED2B6ACBE2EE071264726EED962D781FC2C48B18861EFC06B268` |
| `SL_ADC_DE10Lite.kicad_pcb` | `22EE8DF472AD46F81CA0F35F166CC8AA6FEBEFCA80BB616F91D0D1B58381D9D9` |
| Supplied `step` | `7BCE2049FB16147B238A39BAC3AC97396411EB024417A922F1BBB5F072D09A09` |
| Supplied ADS8528 PDF | `9B56606B9D76635B2961EB60B3B0A74F1BB415AADBD6210067660E7DB8B7E767` |

Primary technical references:

- Texas Instruments, ADS8528/ADS8548/ADS8568 datasheet SBAS543C, especially pp. 5-13, 16-17, 27-40, and 46-47.
- [Texas Instruments ADS8568EVM-PDK User Guide SBAU193E](https://www.ti.com/lit/ug/sbau193e/sbau193e.pdf), especially Figure 2-1 and the ADC schematic.
- [TI E2E clarification of the ADS8528 REFN pin](https://e2e.ti.com/support/data-converters-group/data-converters/f/data-converters-forum/921340/ads8528-refn-pin-s-purpose).
- Texas Instruments ADS8555/ADS8556 and ADS9810/ADS9811 family datasheets for comparison of the REFIO-to-reference-ground architecture.
- [Terasic DE10-Lite User Manual](https://fpgacademy.org/Downloads/DE10_Lite_User_Manual.pdf), section 3.5 and Figure 3-18/Table 3-7 for JP1.
- [Terasic DE10-Lite product resources](https://www.terasic.com.tw/cgi-bin/page/archive.pl?Language=English&No=1021&PartNo=4).
- Samsung Electro-Mechanics component data for [CL21B106KOQNNN](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL21B106KOQNNN) and [CL21B105KBFNNN](https://weblib.samsungsem.com/mlcc/mlcc-ec-data-sheet.do?partNumber=CL21B105KBFNNN).

## Mechanical audit

### What the supplied STEP contains

The supplied STEP is one PCB solid with through-holes; it does not contain connector bodies, standoffs, or component models. The audit therefore validates the board outline, XY locations, pitch, drill diameters, and board-body Z span. It cannot validate connector mating height, pin length, keying, or standoff hardware length from this STEP alone.

The STEP is exactly reproducible from `SL_ADC_DE10Lite-backups/SL_ADC_DE10Lite-2026-07-08_225252.zip` using the KiCad auxiliary origin `(60.5, 50.5)`, board-only export, and via holes cut into the body. All 5,625 STEP entity definitions are identical to that export except the top-level product filename.

### Outline comparison

| Check | Supplied STEP source | Current PCB | Result |
|---|---:|---:|---|
| Nominal X extent | 60.000 to 158.000 mm | 60.000 to 158.000 mm | Exact |
| Nominal Y extent | 50.000 to 117.025 mm | 50.000 to 117.025 mm | Exact |
| Overall nominal span | 98.000 x 67.025 mm | 98.000 x 67.025 mm | Exact |
| Edge primitives | 35 | 35 | 32 exact; 3 changed |
| Maximum changed-point displacement | - | 0.0102 mm | Negligible mechanically |

The only outline change is at the lower-left transition around `(69.0, 113.5)` to `(72.0, 103.5)`. Two line endpoints and the connecting arc moved by roughly 7-10 um. This is far below ordinary routed-board outline tolerance and does not affect any hole or header.

### Headers and standoff holes

All values below are exact matches to the STEP source PCB.

| Feature | Key pad/hole centers in current KiCad coordinates (mm) | Pitch/drill | Result |
|---|---|---|---|
| J1, DE10 2x20 socket | P1 `(132.760, 52.460)`, P2 `(132.760, 55.000)`, P39 `(84.500, 52.460)`, P40 `(84.500, 55.000)` | 2.54 mm; 1.00 mm drill | Exact |
| J2, analog 2x14 header | P1 `(92.800, 104.000)`, P2 `(92.800, 101.460)`, P27 `(125.820, 104.000)`, P28 `(125.820, 101.460)` | 2.54 mm; 1.00 mm drill | Exact |
| H1 | `(63.500, 53.500)` | 4.00 mm drill | Exact |
| H2 | `(154.500, 53.500)` | 4.00 mm drill | Exact |
| H3 | `(73.500, 112.000)` | 4.00 mm drill | Exact |
| H4 | `(142.000, 112.000)` | 4.00 mm drill | Exact |

The mounting-hole footprint is named `MountingHole_2.5mm`, but the actual PCB and STEP drill is 4.00 mm. KiCad also reports all four mounting footprints as modified relative to the library. Fabrication will use 4.00 mm; the name is misleading for mechanical/BOM review.

### Other mechanical differences and caveats

- The supplied STEP source has 40 x 0.30 mm via holes. The current PCB has 29 x 0.30 mm vias; only ten centers remain unchanged. These are not connector or standoff holes, but they mean the complete drilled board solid is not identical.
- The KiCad project declares a 1.60 mm finished stack. The board-only STEP solid spans 1.51 mm because the export represents the board body without all outer copper/mask thickness. Use the 1.60 mm fabrication thickness, not the STEP body's 1.51 mm Z span, for final connector-tail and standoff-height checks.
- J1 is a bottom-side pin socket and J2 a top-side pin header in the PCB. That orientation is consistent with a DE10 board below and an analog board above, but the supplied STEP has no connector bodies with which to verify mating height or polarity.

## DE10-Lite JP1 routing audit

The physical power pins are correct: J1.11 is +5 V, J1.12/J1.30 are ground, and J1.29 is +3.3 V. The PCB uses +3.3 V for DVDD, ties both grounds to the common ground system, and leaves the DE10 +5 V net unused. No ADC data/control signal is accidentally connected to a DE10 power pin.

The following table compares every J1 pin to the Terasic JP1 definition. `Label mismatch` means the functional signal is on a valid FPGA GPIO, but the GPIO number embedded in the KiCad net name is wrong.

| J1 | Official DE10 signal / FPGA ball | PCB net | Assessment |
|---:|---|---|---|
| 1 | GPIO_0 / V10 | `GPIO(19)-PAR/SER` | **Label mismatch: physical GPIO_0, not GPIO_19** |
| 2 | GPIO_1 / W10 | `GPIO(24)-STBY` | **Label mismatch: physical GPIO_1, not GPIO_24** |
| 3 | GPIO_2 / V9 | `GPIO(25)-RESET` | **Label mismatch: physical GPIO_2, not GPIO_25** |
| 4 | GPIO_3 / W9 | `GPIO(23)-REFEN/WR` | **Label mismatch: physical GPIO_3, not GPIO_23** |
| 5 | GPIO_4 / V8 | `RD` | Valid GPIO |
| 6 | GPIO_5 / W8 | `CS/FS` (net text contains `F5`) | Valid GPIO; naming typo |
| 7 | GPIO_6 / V7 | `DB15` | Valid GPIO |
| 8 | GPIO_7 / W7 | `DB14` | Valid GPIO |
| 9 | GPIO_8 / W6 | `DB13` | Valid GPIO |
| 10 | GPIO_9 / V5 | `DB12` | Valid GPIO |
| 11 | +5 V | `DE10_5V` | Correct pin; intentionally unused downstream |
| 12 | GND | `AGND` | Correct |
| 13 | GPIO_10 / W5 | `DB11` | Valid GPIO |
| 14 | GPIO_11 / AA15 | `DB10` | Valid GPIO |
| 15 | GPIO_12 / AA14 | `DB9` | Valid GPIO |
| 16 | GPIO_13 / W13 | `DB8` | Valid GPIO |
| 17 | GPIO_14 / W12 | `DB7` | Valid GPIO |
| 18 | GPIO_15 / AB13 | `DB6` | Valid GPIO |
| 19 | GPIO_16 / AB12 | `DB5` | Valid GPIO |
| 20 | GPIO_17 / Y11 | `DB4` | Valid GPIO |
| 21 | GPIO_18 / AB11 | `DB3` | Valid GPIO |
| 22 | GPIO_19 / W11 | `DB2` | Valid GPIO |
| 23 | GPIO_20 / AB10 | `DB1` | Valid GPIO |
| 24 | GPIO_21 / AA10 | `DB0` | Valid GPIO |
| 25 | GPIO_22 / AA9 | NC | Intentional NC; notably not the HW/SW signal |
| 26 | GPIO_23 / Y8 | `GPIO(20)-BUSY/INT` | **Label mismatch: physical GPIO_23** |
| 27 | GPIO_24 / AA8 | `GPIO(21)-RANGE/XCLK` | **Label mismatch: physical GPIO_24** |
| 28 | GPIO_25 / Y7 | `ASLEEP` | Valid GPIO |
| 29 | +3.3 V | `DVDD` | Correct |
| 30 | GND | `AGND` | Correct |
| 31 | GPIO_26 / AA7 | `GPIO(26)-CONVSTA` | Correct label |
| 32 | GPIO_27 / Y6 | `GPIO(27)-CONVSTB` | Correct label |
| 33 | GPIO_28 / AA6 | `GPIO(28)-CONVSTC` | Correct label |
| 34 | GPIO_29 / Y5 | `GPIO(29)-CONVSTD` | Correct label |
| 35 | GPIO_30 / AA5 | `I2C5` | Valid GPIO |
| 36 | GPIO_31 / Y4 | `GPIO(22)-HW/SW` | **Label mismatch: physical GPIO_31, not GPIO_22** |
| 37 | GPIO_32 / AB3 | `I2C3` | Valid GPIO |
| 38 | GPIO_33 / Y3 | `I2C2` | Valid GPIO |
| 39 | GPIO_34 / AB2 | `I2C1` | Valid GPIO |
| 40 | GPIO_35 / AA2 | `I2C4` | Valid GPIO |

The HDL/QSF must follow the physical GPIO column above. If the existing FPGA project was written from the numbered KiCad net labels, PAR/SER, STBY, RESET, REFEN/WR, BUSY, RANGE/XCLK, and HW/SW will be assigned to the wrong FPGA balls.

## ADS8528 schematic audit

### Pin-number validation

The custom ADS8528 symbol's 64 pin numbers and functions match the TI PM-package top-view table. In particular:

- AVDD: pins 4, 14, 45, 52, 57, 61.
- AGND: pins 5, 15, 44, 51, 58, 62.
- DVDD/DGND: pins 25/24.
- HVDD/HVSS: pins 48/1.
- CH_A0 through CH_D1: pins 42, 47, 49, 54, 64, 59, 7, 2.
- REFAP/AN, REFBP/BN, REFCP/CN, REFDP/DN: 43/46, 50/53, 63/60, 6/3.
- REFIO/REFN: pins 56/55.
- DB[15:0] and all control pins agree with datasheet pp. 5-8.

The PCB footprint is the correct generic 64-pin, 10 x 10 mm, 0.5 mm-pitch TQFP geometry for the ADS8528SPM package. However, the schematic and PCB value fields are blank/`~`, the manufacturer part number is absent, and the current library configuration cannot resolve `KiCad components:ADS8528SPM`. This is a documentation/procurement risk even though the audited pin numbering is correct.

### Power and ground

What is correct:

- All six AGND pins and DGND are on one common AGND system. This follows TI's recommendation for a common local reference/low-impedance bridge under the converter.
- Both inner copper layers are AGND pours, giving the digital and analog routes continuous return planes.
- DVDD is supplied from the DE10's 3.3 V pin and has a 1 uF bypass capacitor, which is within the ADS8528's 2.7-5.5 V DVDD range.
- Six 1 uF capacitors are present for the six AVDD pins, matching TI's allowed alternative of one 1 uF ceramic per AVDD pin.
- HVDD and HVSS each have schematic 0.1 uF plus 10 uF bypasses to AGND.

Risks/conditions:

- HVDD and AVDD are the same PCB net. J2.25/J2.27 labelled AVDD supply both. A clean +5 V shared rail is within the recommended operating range of both pins and avoids any HVDD-before-AVDD sequencing concern; this tie is not itself a defect. The tradeoff is that supply noise is shared and the positive input range is limited by the +5 V HVDD rail.
- With VREF = 2.5 V, hardware RANGE high selects +/-2 VREF (about +/-5 V). In software mode, CONFIG bits C24, C23, C21, and C19 independently select that range for channel pairs A-D. The reset/default value is 0 (the +/-4 VREF or +/-10 V setting), so firmware must write every active pair to 1 before accepting analog inputs. The external board must guarantee that applied inputs never exceed the actual HVSS/HVDD rails.
- HVSS is expected from J2.21/J2.23. The acceptable datasheet range is -16.5 to -5.0 V. The external board's actual rail value, regulator noise, sequencing, and available current were not present in this repository and remain system-level verification items.
- Every routed track, including AVDD, DVDD, HVSS, and ground stubs, is 0.20 mm wide. DC current is modest, but the narrow/long bypass connections add inductance.

### Reference network

| Function | Current design | Datasheet requirement | Result |
|---|---|---|---|
| REFAP-REFAN | C8, 10 uF; REFAN tied AGND | 4.7-10 uF between pair, negative side to AGND | Correct electrically |
| REFBP-REFBN | C9, 10 uF; REFBN tied AGND | Same | Correct electrically |
| REFCP-REFCN | C23, 10 uF; REFCN tied AGND | Same | Correct electrically |
| REFDP-REFDN | C24, 10 uF; REFDN tied AGND | Same | Correct electrically |
| REFIO-REFN | C16, nominal 0.47 uF | 100 nF minimum, 470 nF recommended; REFN connected to AGND | **REFN is not grounded** |
| C16 purchasing value | MPN is a 10 uF part | Maximum listed REFIO load is 470 nF | **BOM out of specification** |

This is the most important schematic defect. Netlist `/REFN` contains only IC1.55 and C16.2. It must not be left floating.

TI's Figure 49 layout recommendation is genuinely ambiguous: it depicts the 0.47 uF part between REFIO and REFN without a clearly drawn REFN ground via. The other evidence is consistent and more explicit:

- The ADS8528 pin table defines REFN as the negative reference input/output and says to connect it to the decoupling capacitor **and AGND**.
- TI's ADS8568EVM-PDK schematic ties pin 55 directly to GND and places its 0.47 uF C49 from REFIO pin 56 to that grounded node. The EVM guide also says the ground ends of decoupling capacitors connect to the ground plane using vias.
- TI support describes REFN as the ground reference for REFIO and states that it must be tied to the analog ground plane.
- In the closely related six-channel ADS8555/ADS8556 architecture, REFIO is decoupled to adjacent pin 52, and pin 52 is explicitly an AGND pin. Newer TI simultaneous-sampling converters use the name REFM for the equivalent reference-ground node and require it to connect to ground.

Electrical interpretation: REFIO is the programmable internal-reference output or external-reference input, while REFN establishes its DC zero/reference potential. C16 supplies AC decoupling between those nodes but cannot establish a DC potential by itself. Leaving REFN floating makes the reference common-mode/return dependent on leakage and parasitic paths, so gain, span, offset, or startup behavior is not guaranteed.

A direct, short connection from REFN/C16.2 to AGND is preferred. A populated 0 ohm resistor is also electrically reasonable if an assembly option is desired; place it with a short return to the AGND plane and populate it by default. On the current PCB, the REFN trace runs only from IC1.55 to C16.2, and the nearest existing AGND via to C16.2 is approximately 5.1 mm away, so a local AGND via/connection would be better than extending the reference return to a remote ground point.

### Capacitor value/MPN cross-check

| References | Schematic value | MPN field | MPN actual value | Assessment |
|---|---:|---|---:|---|
| C1-C5, C10, C11 | 1 uF | `CL21B105KBFNNNE` | 1 uF, 50 V, X7R, 0805 | Correct |
| C8, C9, C20, C21, C23, C24 | 10 uF | `CL21B106KOQNNNE` | 10 uF, 16 V, X7R, 0805 | Correct for the current +/-5 V plan |
| C16 | 0.47 uF | `CL21B106KOQNNNE` | 10 uF | **Wrong** |
| C18, C19 | 0.1 uF | `CL21B106KOQNNNE` | 10 uF | **Wrong** |

The incorrect fields are an assembly-documentation risk rather than a circuit fault under the stated plan to select and install the intended capacitor values manually. The fitted C16 must still be 100-470 nF, preferably 470 nF, and C18/C19 must still provide the intended 100 nF high-frequency bypasses.

If HVDD/HVSS are ever raised near +/-15 V, the 16 V-rated 10 uF parts have very little voltage margin and should be re-evaluated for rating and DC-bias derating.

### Misleading schematic annotations

Several blue explanatory pin annotations are wrong even though most net connections are correct:

- C2's AGND annotation says pin 46; pin 46 is REFAN. The nearby AGND is pin 44.
- C3's AGND annotation says pin 53; pin 53 is REFBN. The nearby AGND is pin 51.
- C8's REFAN annotation says pin 47; REFAN is pin 46 and pin 47 is CH_A1.
- C16's REFN annotation says pin 58; REFN is pin 55 and pin 58 is AGND.

These notes should not be used as a wiring reference. The C16 error appears consistent with the pin-58/pin-55 confusion.

### Mode/control pins and startup state

PAR/SER, HW/SW, STBY, RESET, REFEN/WR, RANGE/XCLK, ASLEEP, CS/FS, RD, and the four CONVST inputs are all driven directly from FPGA GPIO with no external pull-up/down resistors.

This can work after FPGA configuration, but there is no hardware-defined safe state while FPGA pins are high-impedance or during reconfiguration. The ADS8528 inputs have no documented internal bias in the supplied datasheet. Particular consequences include:

- PAR/SER can float between incompatible parallel and serial pin functions.
- STBY can float into power-down; RESET can receive an unintended pulse.
- REFEN/WR can leave the internal reference disabled or act as a write strobe depending on mode.
- RANGE can select the +/-10 V transfer range while the analog rails remain +/-5 V.
- HW/SW can change whether external pins or the CONFIG register control operation.
- RANGE/XCLK and DB pins can become ADS8528 outputs in some modes; FPGA firmware must never drive them simultaneously in those modes.

Define the required power-up mode and add/locate safe-state biasing somewhere in the stack, or document and verify the MAX 10 pre-configuration behavior and configuration timing as an explicit design assumption.

## PCB routing and placement audit

### Positive observations

- KiCad DRC reports zero unconnected PCB items and zero schematic parity discrepancies.
- All ADC pins route to the intended schematic nets; there is no pad-number swap between schematic and footprint.
- Analog inputs stay on F.Cu from J2 to the ADC; the parallel bus/control routes approach from J1, limiting analog/digital route intermixing.
- Both inner layers provide AGND reference, and 19 current AGND vias stitch local returns to the planes.
- Parallel data-route lengths are 13.9-21.8 mm. The roughly 7.9 mm length spread is electrically insignificant relative to the ADS8528's 15 ns data-valid timing at its sub-MHz parallel conversion rate.

### Decoupling/reference placement

Measured shortest routed lengths from ADC pad to the named bypass/reference capacitor pad are:

| ADC connection | Capacitor | Copper path |
|---|---|---:|
| HVSS pin 1 | C19 | 5.614 mm |
| AVDD pin 4 | C1 | 6.466 mm |
| AVDD pin 14 | nearest 1 uF C2 | 4.441 mm |
| AVDD pin 52 | nearest 1 uF C4 | 3.941 mm |
| AVDD pin 57 | nearest 1 uF C11 | 4.148 mm |
| AVDD pin 61 | nearest 1 uF C10 | 4.332 mm |
| DVDD pin 25 | C5 | 4.726 mm |
| REFAP pin 43 | C8 | 9.716 mm |
| REFBP pin 50 | C9 | 11.099 mm |
| REFCP pin 63 | C23 | 10.314 mm |
| REFDP pin 6 | C24 | 10.271 mm |
| REFIO pin 56 | C16 | 12.947 mm |
| REFN pin 55 | C16 | 10.153 mm |
| AVDD pin 45 | nearest local AVDD bypass branch C18 | 9.869 mm |
| HVDD pin 48 (on AVDD net) | C20 | 5.708 mm |

TI's layout example puts the reference and 100 nF supply capacitors immediately adjacent to the corresponding package pins, with short/wide connections and nearby plane vias. The current reference loop is an order of magnitude longer than a tight package-adjacent placement. The nearest ground via at a capacitor ground pad is typically 1.5-2.5 mm away and reaches 4.15 mm for one AVDD capacitor.

This does not create a DRC error, but it can increase reference settling error, supply bounce, crosstalk, and distortion. It is a performance risk for a simultaneous-sampling ADC, especially at high throughput or near 12-bit accuracy limits.

### Analog input routes and external-board dependency

The eight input routes are approximately:

| Channel | Route length |
|---|---:|
| CH_A0 | 45.752 mm |
| CH_A1 | 28.935 mm |
| CH_B0 | 27.355 mm |
| CH_B1 | 25.033 mm |
| CH_C0 | 22.812 mm |
| CH_C1 | 28.293 mm |
| CH_D0 | 45.442 mm |
| CH_D1 | 34.161 mm |

There is no local input series resistor, RC anti-alias filter, clamp, or amplifier on this PCB. That may be intentional because the stacked analog board provides the front end. The external board must therefore provide all of the following:

- Input amplitude limited to the actual HVSS/HVDD rails under power-up, power-down, and fault conditions.
- A driver stable with the ADS8528's 10-20 pF switched-capacitor input and the connector/trace capacitance.
- Any desired anti-alias filtering and source impedance required for acquisition settling.
- A quiet, low-impedance common ground path and appropriate protection.

The pair-length asymmetry is not a digital timing problem, but it produces unequal parasitics (especially A0/A1 and D0/D1) that may matter for channel matching in a precision measurement application.

### I2C pass-through

I2C1-I2C5 are direct GPIO-to-J2 routes of about 51-55.5 mm. No local pull-ups, series damping, level translation, or protection are present. Confirm that pull-ups exist exactly once on the assembled stack, that they pull to 3.3 V, and that the FPGA pins are configured open-drain. Five separately named I2C nets are not enough to infer whether these are five independent signals, one bus, or a custom interface.

## Automated checker results

### ERC: 10 reported items

- Four `power_pin_not_driven` errors: HVSS, REFDN, AVDD, and DVDD. These supplies/grounds enter through passive connectors, so KiCad cannot see a power-output source. They are primarily schematic-annotation issues, but external rail values still require system verification.
- J1.25 and J2.12 are reported unconnected. PCB silkscreen marks them `ZZZ` and `X`, suggesting they are intentional; explicit no-connect markers are missing in the schematic.
- The ADS8528 custom symbol library cannot be resolved in the current library configuration.
- `DE10_5V` appears only once because it is intentionally unused.
- AVDD/HVDD and AGND/REFAN each have two net names on a single electrical net. The latter is the intended reference-negative ground connection; the former is the deliberate rail tie discussed above.

The ERC does **not** catch the floating REFN because the capacitor gives pin 55 a second connection.

### DRC: 13 warnings, no copper errors

- Zero unconnected items.
- Zero schematic parity issues.
- Ten library-footprint mismatch warnings: six decorative graphics and four locally modified mounting holes.
- Three silkscreen-clearance warnings, including text near J2. These are readability/fabrication-cleanup issues, not connectivity failures.

### Manufacturing metadata

- Four copper layers, nominal 1.60 mm FR4, 35 um copper.
- Both inner layers are AGND zones.
- Copper finish is set to `None`; the fabrication finish is not documented in the PCB stackup.
- No impedance constraints are declared. That is acceptable for the present low-rate parallel interface but should be an explicit fabrication decision.

## Recommended disposition before fabrication

### Must resolve

1. Connect REFN pin 55 to AGND with the intended short reference-return topology and keep C16 at the ADC pins.
2. Reconcile the seven incorrect GPIO numbers with the actual QSF/HDL assignments. Treat the DE10 physical mapping table in this report as authoritative for the audited PCB.

### Resolve or formally accept

3. Correct the C16/C18/C19 MPN fields before any generated-BOM workflow, or document the controlled hand-population plan. Verify the fitted C16 is 470 nF (or another datasheet-compliant 100-470 nF value) and C18/C19 are 100 nF.
4. Document and verify the intended +5 V shared AVDD/HVDD architecture, the negative HVSS rail, and the firmware initialization that sets CONFIG `RANGE_A`, `RANGE_B`, `RANGE_C`, and `RANGE_D` to 1 for every active pair before normal sampling. If +/-10 V inputs are ever required, the power architecture/header must change.
5. Move or re-route the REFx and supply bypass capacitors to meet TI's close-placement example, or characterize the present layout for reference stability, settling, SNR, and THD at the required sample rate.
6. Define deterministic startup states for mode/control pins and validate FPGA/ADC bus direction through configuration and reset.
7. Confirm the external analog front end, I2C pull-ups, rail sequencing, and ground strategy on the complete stack.
8. Replace the blank IC value with the exact orderable ADS8528 package/grade and restore a resolvable symbol library/datasheet link.
9. Rename or document the 4.00 mm mounting holes and record the required board finish/fabrication tolerances.

## Final assessment

- **Mechanical mating geometry:** pass, subject to connector-height verification outside the supplied board-only STEP.
- **Header power-pin placement:** pass.
- **DE10 digital GPIO numbering/documentation:** fail until net labels/QSF are reconciled.
- **ADS8528 pin-number mapping:** pass.
- **Reference circuit:** fail due to floating REFN; the C16 MPN mismatch is an assembly-control issue if the correct value is installed manually.
- **Power architecture:** pass for the documented +/-5 V input system with a clean shared +5 V AVDD/HVDD rail; firmware range initialization and input limiting remain interface requirements.
- **PCB connectivity/DRC:** pass for copper connectivity; warnings remain.
- **ADC layout quality:** high performance risk because reference/supply bypass paths are long.
- **Release recommendation:** hold fabrication/assembly until the must-resolve items are closed.
