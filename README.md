# 🎓 K12 Teacher Verification Bot

Bot Telegram untuk verifikasi guru K12 menggunakan SheerID API dengan document generation otomatis.

## 📋 Fitur

- ✅ Verifikasi otomatis ke SheerID
- 📄 Generate dokumen realistis (Faculty ID, Pay Stub, Employment Letter)
- 🏫 Search sekolah K12 dan HIGH_SCHOOL
- 🤖 Interactive Telegram bot interface
- 📊 Multi-step verification process

## 🗂️ Struktur File

```
.
├── k12_teacher_bot.py       
├── document_generator.py    
├── requirements.txt         
└── README.md               
```

## 📦 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable

**Linux/Mac:**
```bash
export BOT_TOKEN="your_telegram_bot_token_here"
```

**Windows (CMD):**
```cmd
set BOT_TOKEN=your_telegram_bot_token_here
```

**Windows (PowerShell):**
```powershell
$env:BOT_TOKEN="your_telegram_bot_token_here"
```

### 3. Jalankan Bot

```bash
python k12_teacher_bot.py
```

## 🚀 Cara Menggunakan

### Step 1: Start Bot
```
/start
```

### Step 2: Kirim SheerID URL
```
https://services.sheerid.com/verify/68d47554.../verificationId=...
```

### Step 3: Masukkan Data
1. **Full Name**: John Smith
2. **Email**: jsmith@schools.nyc.gov
3. **School Name**: The Clinton School

### Step 4: Pilih Sekolah
- Bot akan menampilkan list sekolah yang cocok
- Klik button untuk memilih sekolah

### Step 5: Verifikasi Otomatis
- Bot akan generate 3 dokumen:
  - 📇 Faculty ID Card
  - 💰 Payroll Statement
  - 📄 Employment Letter
- Submit otomatis ke SheerID
- Terima konfirmasi sukses

## 🔧 Technical Details

### API Endpoints

**SheerID Organization Search:**
```
GET https://orgsearch.sheerid.net/rest/organization/search
Parameters:
  - country: US
  - type: K12 | HIGH_SCHOOL
  - name: <school_name>
```

**SheerID Verification Steps:**
1. `POST /rest/v2/verification/{id}/step/collectTeacherPersonalInfo`
2. `DELETE /rest/v2/verification/{id}/step/sso`
3. `POST /rest/v2/verification/{id}/step/docUpload`
4. `PUT` to S3 upload URLs
5. `POST /rest/v2/verification/{id}/step/completeDocUpload`

### Document Generation

**Faculty ID Card** (850x540px)
- Logo placeholder
- Faculty photo placeholder
- Name, email, department
- Faculty ID number (FAC-XXXXX)
- Expiry date
- Barcode

**Payroll Statement** (850x1100px)
- School header
- Pay period and date
- Employee information
- Earnings breakdown
- Deductions (Federal, State, 403b)
- Net pay calculation

**Employment Letter** (850x1100px)
- Official letterhead
- Verification text
- Employment details
- HR signature
- Official seal

## 📝 Code Structure

### k12_teacher_bot.py

```python
# Configuration
BOT_TOKEN, SHEERID_BASE_URL, ORGSEARCH_URL

# Conversation States
SHEERID_URL, NAME, EMAIL, SCHOOL

# Main Handlers
- start()              # /start command
- get_sheerid_url()    # Receive verification URL
- get_name()           # Receive full name
- get_email()          # Receive email
- get_school()         # Receive school name & search

# School Functions
- search_schools()     # Query SheerID API
- display_schools()    # Show results with buttons
- button_callback()    # Handle school selection

# Submission
- submit_sheerid()     # Multi-step API submission

# Utilities
- cancel()            # Cancel operation
- main()              # Bot entry point
```

### document_generator.py

```python
# Font Management
- get_fonts()

# Document Generators
- generate_faculty_id()        # Returns (Image, faculty_id)
- generate_pay_stub()          # Returns Image
- generate_employment_letter() # Returns Image

# Utilities
- image_to_bytes()    # Convert PIL Image to BytesIO
```

## 🐛 Troubleshooting

### Bot tidak start
```bash
# Check BOT_TOKEN
echo $BOT_TOKEN

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### School search tidak ada hasil
- Pastikan nama sekolah benar (case-insensitive)
- Coba nama lebih spesifik atau lebih umum
- Check console untuk error API

### Verification failed
- Check verification URL valid
- Pastikan data sesuai (nama, email)
- Check console logs untuk detail error

## 📊 Success Indicators

✅ Console output saat berhasil:
```
📡 Searching K12 schools...
✅ K12: Found 5 schools
✅ HIGH_SCHOOL: Found 3 schools
📊 Total unique schools: 8

📄 Generating documents for John Smith...
✅ Documents generated successfully
Faculty ID: FAC-12345

🚀 Starting SheerID submission...
✅ Step 2 success: Personal info submitted
✅ Step 3 success: SSO skipped
✅ Step 4 success: Received 2 upload URLs
✅ Upload completed: 200
🎉 Verification submitted successfully!
```

## ⚠️ Important Notes

1. **Bot Token**: Jangan share BOT_TOKEN di public repository
2. **SheerID URLs**: Each verification URL is single-use
3. **School Types**: Hanya support K12 dan HIGH_SCHOOL
4. **Document Quality**: Documents adalah mock-ups untuk testing
5. **Rate Limiting**: SheerID mungkin ada rate limits

## 🔐 Security

- Bot token disimpan di environment variable
- User data temporary (tidak persistent)
- Verification URLs di-validate format
- Email format di-validate

## 📞 Support

Untuk issues atau questions:
1. Check console logs untuk error details
2. Validate semua input data
3. Verify internet connection untuk API calls

## 📄 License

Educational/Testing purposes only.

---

**Version:** 1.0.0  
**Last Updated:** December 2025  
**Python:** 3.8+
