# Automated Phishing Intelligence

โปรเจกต์นี้เป็นต้นแบบระบบตรวจจับและวิเคราะห์เว็บไซต์ฟิชชิ่งแบบอัตโนมัติ โดยแยกส่วน core logic ให้อยู่ใน `src/phishing_intel/` และมีเว็บ dashboard ใน `app/` เพื่อให้ใช้งานง่ายขึ้น

## โครงสร้างโปรเจกต์

```
.
├── README.md
├── main.py
├── phishing_intel.py
├── requirements.txt
├── requirement.txt
├── src/
│   ├── __init__.py
│   └── phishing_intel/
│       ├── __init__.py
│       ├── browser.py
│       ├── config.py
│       ├── contracts.py
│       ├── ingestion.py
│       ├── model.py
│       ├── pipeline.py
│       ├── reporting.py
│       ├── utils.py
│       └── features/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── schemas.py
│   ├── routes/
│   │   ├── api.py
│   │   └── pages.py
│   ├── services/
│   │   └── analysis_service.py
│   ├── static/
│   └── templates/
├── tests/
├── example/
└── output/
```

## คำอธิบายส่วนหลัก

- `main.py` : entry point ของ CLI สำหรับรัน pipeline วิเคราะห์ URL และสร้างไฟล์ผลลัพธ์
- `phishing_intel.py` : compatibility entry point แบบเก่า ใช้เรียก `run_pipeline()` แบบตรง ๆ
- `requirements.txt` : รายการ dependency ของโปรเจกต์
- `src/phishing_intel/` : core package ของระบบ
  - `browser.py` : capture HTML, screenshot และ fallback capture
  - `ingestion.py` : จัดการข้อมูล URL และ demo dataset
  - `pipeline.py` : orchestration ของ ingestion, feature extraction, model, reporting
  - `model.py` : สร้าง model, predict และประเมินผล
  - `reporting.py` : สร้างรายงาน prediction และ metadata
  - `utils.py` : ฟังก์ชันช่วยเหลือต่าง ๆ
- `app/` : web dashboard บน FastAPI
  - `main.py` : FastAPI application entry point
  - `routes/` : API และหน้าเว็บ
  - `services/analysis_service.py` : ตัวช่วยเชื่อม core logic กับเว็บ
  - `templates/`, `static/` : frontend assets
- `tests/` : ชุด unit tests
- `example/` : ตัวอย่างหน้า phishing สำหรับ demo หรือ offline testing
- `output/` : โฟลเดอร์เก็บผลลัพธ์และ artifacts ที่สร้างขึ้น

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

3. ถ้าต้องการให้ browser capture ทำงานจริง ๆ ให้ติดตั้ง Playwright browser

```bash
playwright install chromium
```

## การรัน

### รัน pipeline แบบ CLI

```bash
python main.py
```

ตัวเลือกที่ใช้บ่อย

```bash
python main.py --offline-only --no-browser
python main.py --n-urls 10 --log-level DEBUG
```

### รันเว็บ dashboard

```bash
uvicorn app.main:app --reload
```

แล้วเปิดในเบราว์เซอร์

```text
http://127.0.0.1:8000
```

## ผลลัพธ์ที่สร้าง

เมื่อรัน pipeline จะได้ไฟล์หลักใน `output/`

- `features.csv` : feature matrix ของ URL ที่ประมวลผล
- `phishing_report.csv` : ผล prediction พร้อมเมตาดาต้า
- `metrics.json` : metric ของโมเดล
- `screenshots/` : screenshot จริงหรือ fallback
- `jobs/<job_id>/` : artifact ของงานแต่ละ job เมื่อใช้เว็บ dashboard

## การทดสอบ

```bash
python -m unittest discover -s tests -v
```

## หมายเหตุ

- `app/main.py` เป็น FastAPI application
- `src/phishing_intel` เป็น core logic ของระบบ
- `example/` มีตัวอย่างหน้า phishing ที่ใช้เป็น fixture
- หาก dependency ยังไม่ครบ เช่น `fastapi`, `uvicorn` หรือ `playwright` ระบบจะใช้ fallback path เท่าที่ทำได้
