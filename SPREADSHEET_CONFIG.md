# SPREADSHEET CONFIGURATION (REVISED v2)

## OVERVIEW
Data dibagi menjadi Tab Water Quality, Farm Control, dan **Multiple Biological Tabs** sesuai permintaan user untuk pemisahan data granular.

## 1. TAB: WATER QUALITY (Sensor & Manual Air)
*Sama seperti sebelumnya*
| Col | Header Name |
|---|---|
| A | Timestamp |
| B | Type (IoT/Manual) |
| C | Device |
| D | DO |
| E | DO ADC |
| ... | ... |
| L | Media Link |

## 2. TAB: FARM CONTROL (Infrastruktur)
*Sama seperti sebelumnya*
| Col | Header Name |
|---|---|
| A | Timestamp |
| ... | ... |

## 3. BIOLOGICAL DATA (SPLIT TABS)

### Tab 3a: `Bio - Dead Fish` (Mortalitas)
| Col | Header Name | Description |
|---|---|---|
| A | Timestamp | Waktu lapor |
| B | Source | Manual WA |
| C | Count (Ekor) | Jumlah mati |
| D | Photo Link | Bukti foto |
| E | Note | Catatan detil |

### Tab 3b: `Bio - Feed Weight` (Penyusutan Pakan)
| Col | Header Name | Description |
|---|---|---|
| A | Timestamp | Waktu pemberian |
| B | Weight (gram) | Berat pakan |
| C | Photo Link | Foto timbangan |
| D | Note | - |

### Tab 3c: `Bio - Feeding Freq` (Frekuensi)
| Col | Header Name | Description |
|---|---|---|
| A | Date | Tanggal (bukan jam) |
| B | Frequency | Total kali makan/hari |
| C | Note | - |

### Tab 3d: `Bio - Sampling` (Weight & Length)
| Col | Header Name | Description |
|---|---|---|
| A | Timestamp | Waktu sampling |
| B | Avg Weight (g) | Berat rata-rata |
| C | Avg Length (cm)| Panjang rata-rata |
| D | Sample Size | Jumlah sampel (e.g. 30) |
| E | Photo Link | Foto perwakilan |
| F | Detail JSON | (Opsional) Data mentah 30 ikan |

---

## 4. TAB: AI MATRIX (Training Data)
*Tetap satu tab rekapitulasi*
