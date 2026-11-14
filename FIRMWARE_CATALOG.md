# Reliance Jio Ecosystem Official OTA / Firmware Catalog

All packages below are directly hosted on Reliance Jio's public Akamai NetStorage distribution servers (`fota.slv.kai.jiophone.net` and `fota.slv.fxd.jiophone.net`) without authentication.

> [!TIP]
> **Have a newly discovered firmware or Akamai OTA link?**  
> Help expand this open-source archive!  
> * 📝 **Quick Submission (No GitHub account needed):** [Submit via Google Form](https://forms.gle/thYgeHvudJRGabWn7)  
> * 🐙 **GitHub Submission:** Open an issue via [GitHub New Firmware Issue](https://github.com/krishnasen2401/jiostb/issues/new) or run `SHARE_NEW_FIRMWARE.bat`.

---

## 1. Jio Set-Top Boxes (STBs)

| Model / Variant | Hardware / Codename | Version | Android OS | Package Size | Direct Download URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **JHS D200 v2 / JHS C200 (Franklin)** | Bluebank Franklin (`BHTS` / `DIN995` / `V06`) | `11.3.46` | **Android 11** | **792,359,990 bytes** (~792.3 MB) | [Download](http://fota.slv.kai.jiophone.net/BHTS/DIN995/B002D_346/qdOdPlaXso.zip) |
| **JHS D200 v1** | Droidlogic Franklin | `5.7.1` | **Android 9 (Pie)** | **533,312,179 bytes** (~533.3 MB) | [Download](http://fota.slv.fxd.jiophone.net/STB/Droidlogic/JHSD200/STB-JHSD200-5.7.1.zip) |
| **JHS C200 (SDMC Legacy)** | SDMC (`DV8545-Cn2`) | `5.7.1` | **Android 9 (Pie)** | **532,008,639 bytes** (~532.0 MB) | [Download](http://fota.slv.fxd.jiophone.net/STB/SDMC/STB-JHSC200-5.7.1.zip) |

---

### Internal Partition Layouts (Verified via Central Directory Inspection)

#### JHS D200 v2 (Android 11 - 11.3.46)
- **`boot.img`** (16.7 MB uncompressed) — Linux kernel & ramdisk
- **`recovery.img`** (25.1 MB uncompressed) — Stock recovery
- **`bootloader.img`** (1.67 MB uncompressed) — U-Boot bootloader
- **`vbmeta.img`** (8.1 KB uncompressed) — AVB 2.0 signatures
- **`dt.img` / `dtbo.img`** (8.6 MB uncompressed) — Device tree blobs & overlays
- **`logo.img`** (1.16 MB uncompressed) — Boot splash screen
- **`system.new.dat.br`** (580.3 MB compressed) — Android 11 system partition
- **`vendor.new.dat.br`** (81.2 MB compressed) — Amlogic hardware HALs & drivers
- **`product.new.dat.br`** (98.5 MB compressed) — Carrier apps & services
- **`odm.new.dat.br` & `odm_ext.new.dat.br`** (547 KB compressed) — ODM partition
- **`super_empty_all.img`** (12.7 KB uncompressed) — Dynamic partitions super table

#### JHS D200 v1 (Android 9 - 5.7.1)
- **`boot.img`** (9.4 MB uncompressed) — Android 9 kernel
- **`recovery.img`** (14.9 MB uncompressed) — Android 9 recovery
- **`bootloader.img`** (2.0 MB uncompressed) — U-Boot bootloader
- **`system.new.dat.br`** (393.0 MB compressed) — Android 9 system partition
- **`vendor.new.dat.br`** (75.1 MB compressed) — Android 9 vendor partition
- **`product.new.dat.br`** (37.5 MB compressed) — Android 9 product partition

#### JHS C200 (Android 9 - 5.7.1)
- **`boot.img`** (9.3 MB uncompressed) — SDMC DV8545 kernel
- **`recovery.img`** (14.8 MB uncompressed) — SDMC DV8545 recovery
- **`bootloader.img`** (2.0 MB uncompressed) — SDMC U-Boot bootloader
- **`system.new.dat.br`** (394.7 MB compressed) — SDMC system partition
- **`vendor.new.dat.br`** (72.3 MB compressed) — SDMC vendor partition

---

## 2. JioFiber Routers / ONTs (Home Gateways)

| Router Model | Manufacturer | Firmware Version | File Format | Package Size | Direct Download URL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **JCOW411** | Arcadyan | `R2.3` | `.img` | **69,468,436 bytes** (~69.4 MB) | [Download](http://fota.slv.fxd.jiophone.net/ONT/Arcadyan/JCOW411/ARCNTF1_JCOW411_R2.3.img) |
| **JCOW404** | Sercomm | `R2.3` | `.img` | **69,075,220 bytes** (~69.0 MB) | [Download](http://fota.slv.fxd.jiophone.net/ONT/Sercomm/JCOW404/SRCMTF1_JCOW404_R2.3.img) |
| **JCOW401** | Arcadyan | `R1.34` | `.img` | **63,176,980 bytes** (~63.1 MB) | [Download](http://fota.slv.fxd.jiophone.net/ONT/Arcadyan/JCOW401/ARCTF1_JCOW401_R1.34.img) |
| **JCO110** | Arcadyan | `R1.130` | `.img` | **55,443,732 bytes** (~55.4 MB) | [Download](http://fota.slv.fxd.jiophone.net/ONT/Arcadyan/JCO110/ARCTF1_JCO110_R1.130.img) |
