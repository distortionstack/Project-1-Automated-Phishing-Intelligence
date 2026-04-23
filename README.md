# Automated Phishing Intelligence — Prototype

โปรเจกต์นี้เป็นระบบต้นแบบสำหรับตรวจสอบและวิเคราะห์เว็บไซต์ฟิชชิ่ง (Phishing) โดยอัตโนมัติ ซึ่งรวมเอาการดึงข้อมูลหน้าเว็บ การสกัดฟีเจอร์ (Feature Extraction) ทั้งทางภาพและโครงสร้าง HTML การใช้ Machine Learning และการอธิบายผลลัพธ์ด้วย SHAP (Explainable AI) เข้าด้วยกัน

## ⚙️ การทำงานของระบบ (Pipeline)
ระบบทำงานผ่าน 5 ขั้นตอนหลัก ดังนี้:

1. **Data Ingestion (การดึงข้อมูล):** 
   - ดึงรายชื่อ URL ที่เป็นฟิชชิ่งจาก PhishTank และ URL ที่เป็นเว็บปกติจาก Tranco List
   - หากไม่มีการเชื่อมต่ออินเทอร์เน็ต ระบบจะใช้ชุดข้อมูล Demo ที่เตรียมไว้ล่วงหน้าแทน
2. **Browser Instrumentation (การท่องเว็บและบันทึกภาพ):** 
   - ใช้ **Playwright** เปิดเบราว์เซอร์ Chromium แบบ Headless เพื่อเข้าสู่ URL
   - บันทึกระยะเวลาในการโหลดหน้าเว็บ, Status Code, ดึงซอร์สโค้ด HTML, และ **ถ่าย Screenshot** หน้าเว็บ (หากเข้าเว็บไม่ได้ ระบบจะจำลองรูปภาพ Screenshot และ HTML ขึ้นมาสำหรับการสาธิต)
3. **Feature Extraction (การสกัดคุณลักษณะ):**
   - **URL Features:** ความยาว URL, โครงสร้างโดเมน, ระดับเอนโทรปี (Entropy), การมีอยู่ของ TLD ที่น่าสงสัย และคำสำคัญของแบรนด์ (เช่น paypal, facebook)
   - **Visual Features:** ตรวจสอบโทนสี (Color Analysis), ค้นหาสีที่เป็นเอกลักษณ์ของแบรนด์ และเปรียบเทียบโครงสร้างภาพ (Perceptual Hash - ImageHash) กับหน้าเว็บของแบรนด์ดัง
   - **HTML Features:** จำนวนแท็ก `<form>`, `<iframe>`, `<script>`, โค้ด JavaScript ที่น่าสงสัย, พาสเวิร์ดฟิลด์ และลิงก์ภายนอก
4. **ML Modeling (การวิเคราะห์ด้วย Machine Learning):**
   - นำฟีเจอร์ที่สกัดได้ไปสอนและทดสอบกับโมเดล **Random Forest** และ **XGBoost** (ใช้เทคนิค Ensemble และประเมินผลแบบ Cross-Validation)
5. **SHAP Reporting (การอธิบายผลด้วย AI):**
   - ใช้ **SHAP (SHapley Additive exPlanations)** เพื่อบอกเหตุผลระดับลึกว่า ทำไมระบบถึงมองว่าหน้าเว็บนี้เป็นฟิชชิ่ง (เช่น พบช่องกรอกพาสเวิร์ดมากผิดปกติ, URL มีความน่าสงสัยสูง เป็นต้น)
   - สรุปผลลัพธ์และเซฟเป็นไฟล์รีพอร์ต

---

## 🛠 สิ่งที่ต้องติดตั้ง (Prerequisites & Installation)

ระบบนี้เขียนด้วย Python และใช้ไลบรารีที่ระบุไว้ใน `requirements.txt`

1. แนะนำให้สร้าง Virtual Environment ก่อน (เป็นตัวเลือกเสริม):
   ```bash
   python -m venv venv
   source venv/bin/activate  # สำหรับ Linux/Mac
   # หรือ venv\Scripts\activate สำหรับ Windows
   ```

2. ติดตั้งไลบรารีที่จำเป็น:
   ```bash
   pip install -r requirements.txt
   ```

3. ติดตั้งเบราว์เซอร์สำหรับ Playwright:
   ```bash
   playwright install chromium
   ```

---

## 🚀 วิธีการรัน (How to Run)

คุณสามารถสั่งรันสคริปต์หลักได้โดยตรง:

```bash
python phishing_intel.py
```

เมื่อทำงานเสร็จสิ้น ระบบจะสร้างโฟลเดอร์ `output/` และบันทึกผลลัพธ์ต่างๆ เอาไว้ ได้แก่:
- `output/screenshots/` : โฟลเดอร์เก็บรูปภาพ Screenshot หน้าเว็บทั้งหมดที่ระบบเข้าไปวิเคราะห์
- `output/features.csv` : ตารางข้อมูล Features ทั้งหมดที่ระบบสกัดออกมาจากแต่ละ URL
- `output/phishing_report.csv` : ตารางรายงานผลลัพธ์การทำนาย พร้อมคำอธิบายเหตุผลจากโมเดล SHAP (Top reasons) ว่าเหตุใดจึงถูกมองว่าเป็นฟิชชิ่ง หรือเว็บปกติ
