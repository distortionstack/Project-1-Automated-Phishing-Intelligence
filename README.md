# Automated Phishing Intelligence — Refactored Prototype

โปรเจกต์นี้เป็นระบบต้นแบบสำหรับตรวจสอบและวิเคราะห์เว็บไซต์ฟิชชิ่งแบบอัตโนมัติ โดยหลังการ refactor รอบนี้โค้ดถูกแยกเป็นโมดูลชัดเจนขึ้น, ลด side effect ตอน import, เพิ่ม data contract ระหว่างแต่ละ stage และทำให้ระบบทดสอบกับตรวจสอบผลลัพธ์ได้ง่ายกว่าเดิม

## โครงสร้างใหม่

```text
src/phishing_intel/
├── config.py
├── contracts.py
├── ingestion.py
├── browser.py
├── model.py
├── reporting.py
├── pipeline.py
└── features/
    ├── url_features.py
    ├── html_features.py
    └── visual_features.py

main.py
phishing_intel.py
tests/
```

## แนวคิดการออกแบบ

ระบบถูกแยกเป็น 5 ส่วนหลักเหมือนเดิม แต่เปลี่ยนจาก script เดียวเป็น orchestration + pure components

1. `ingestion.py`
   ดึง URL phishing/benign จาก source ภายนอก หรือ fallback เป็น demo dataset เมื่ออยู่ในโหมด offline
2. `browser.py`
   รับผิดชอบ capture หน้าเว็บ, HTML และ screenshot โดยแยก fallback path ออกมาอย่างชัดเจน
3. `features/`
   แยก URL, HTML และ visual features ออกจากกันเพื่อให้ทดสอบได้เป็น unit
4. `model.py`
   แยก `train`, `predict`, `explain` และประเมินด้วย train/test split + stratified CV
5. `reporting.py`
   สร้างรายงานจาก prediction และ metadata โดยไม่ผูกกับ internals ของ model

## สิ่งที่ตรวจสอบได้ดีขึ้น

- เก็บ `fallback_used`, `capture_mode`, `error_reason` ลงใน snapshot และ report
- มี `metrics.json` สำหรับเก็บ F1, precision, recall, confusion matrix และ global feature importance
- มี validation ของ feature matrix และ labels ก่อน train
- synthetic fallback screenshot ถูกทำให้ deterministic มากขึ้น
- เพิ่มชุดทดสอบ offline ใน `tests/`

## การติดตั้ง

1. สร้าง virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

2. ติดตั้ง dependencies

```bash
pip install -r requirements.txt
```

3. ถ้าต้องการใช้ browser capture จริง ติดตั้ง Playwright browser เพิ่ม

```bash
playwright install chromium
```

## วิธีรัน

รันผ่าน entry point ใหม่:

```bash
python main.py
```

ตัวเลือกที่ใช้บ่อย:

```bash
python main.py --offline-only --no-browser
python main.py --n-urls 10 --log-level DEBUG
```

ยังสามารถเรียกแบบเดิมได้เพื่อ compatibility:

```bash
python phishing_intel.py
```

## Output

เมื่อรันเสร็จ ระบบจะสร้าง artifact ใน `output/`

- `output/features.csv` ตาราง feature matrix
- `output/phishing_report.csv` ตาราง prediction พร้อมเหตุผลและ metadata ของ fallback
- `output/metrics.json` metric สำหรับตรวจสอบคุณภาพโมเดล
- `output/screenshots/` screenshot จริงหรือ synthetic fallback

## การทดสอบ

รันชุดทดสอบแบบ offline:

```bash
python -m unittest discover -s tests -v
```

ชุดทดสอบที่มีตอนนี้:

- `test_url_features.py`
- `test_html_features.py`
- `test_browser_fallback.py`
- `test_pipeline_smoke.py`

## หมายเหตุ

- ตัวอย่างหน้า phishing ใน `example/` ถูกใช้เป็น fixture สำหรับโหมด demo/offline
- ถ้า environment ไม่มี dependency บางตัว เช่น Playwright, SHAP หรือ ImageHash ระบบจะใช้ fallback path เท่าที่ทำได้ และจะสะท้อนสถานะนั้นออกมาในรายงานแทนการเงียบหาย
