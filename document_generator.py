from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import random
import io
import requests


# =====================================================
# FONT & UTIL
# =====================================================

def get_fonts():
    try:
        return {
            "title": ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42
            ),
            "heading": ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30
            ),
            "normal": ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22
            ),
            "small": ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18
            ),
        }
    except Exception:
        default = ImageFont.load_default()
        return {
            "title": default,
            "heading": default,
            "normal": default,
            "small": default,
        }


def fetch_photo(url, size=(220, 280)):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img = img.resize(size, Image.LANCZOS)
        return img
    except Exception:
        return None


def image_to_bytes(image):
    """Convert PIL Image ke BytesIO (siap dikirim ke Telegram)."""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="JPEG", quality=95)
    img_byte_arr.seek(0)
    return img_byte_arr


# =====================================================
# 1. FACULTY ID CARD (DEPAN)
# =====================================================

def generate_faculty_id(
    teacher_name: str,
    teacher_email: str,
    school_name: str,
    photo_url: str = "https://github.com/oranglemah/ngebot/raw/main/foto.jpg",
):
    """
    Generate ID card depan mirip Faculty_ID_Front.jpg:
    - Header ungu dengan nama sekolah + 'FACULTY IDENTIFICATION CARD'
    - Logo bulat kiri atas (placeholder)
    - Area foto 3x4
    - Nama, Employee ID, Department di kanan
    - Issue date & valid until di bawah
    """
    W, H = 1200, 768
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Header ungu
    header_h = 220
    header_color = "#7c3aed"
    draw.rectangle([(0, 0), (W, header_h)], fill=header_color)

    # Logo bulat
    logo_r = 140
    draw.ellipse([(40, 40), (40 + logo_r, 40 + logo_r)], fill="white")
    draw.text(
        (40 + logo_r / 2, 40 + logo_r / 2),
        "LOGO",
        fill=header_color,
        font=fonts["small"],
        anchor="mm",
    )

    # Nama sekolah + judul kartu
    draw.text(
        (logo_r + 90, 70),
        school_name,
        fill="white",
        font=fonts["title"],
    )
    draw.text(
        (logo_r + 90, 140),
        "FACULTY IDENTIFICATION CARD",
        fill="white",
        font=fonts["heading"],
    )

    # Area foto 3x4
    photo_x, photo_y = 60, header_h + 40
    photo_w, photo_h = 260, 340
    draw.rectangle(
        [(photo_x, photo_y), (photo_x + photo_w, photo_y + photo_h)],
        fill="#e5e7eb",
    )
    photo = fetch_photo(photo_url, size=(photo_w, photo_h))
    if photo:
        img.paste(photo, (photo_x, photo_y))
    else:
        draw.text(
            (photo_x + photo_w / 2, photo_y + photo_h / 2),
            "PHOTO\n3x4",
            fill="#9ca3af",
            font=fonts["normal"],
            anchor="mm",
            align="center",
        )

    # Info kanan
    info_x = photo_x + photo_w + 80
    info_y = header_h + 60

    emp_id = f"DU-{random.randint(4000,9999)}-{random.randint(100,999)}"
    departments = ["English", "Mathematics", "Science", "History", "Arts"]
    dept = random.choice(departments)

    draw.text((info_x, info_y), "NAME", fill="#6b7280", font=fonts["small"])
    draw.text((info_x, info_y + 32), teacher_name, fill="black", font=fonts["heading"])

    draw.text((info_x, info_y + 90), "EMPLOYEE ID", fill="#6b7280", font=fonts["small"])
    draw.text((info_x, info_y + 122), emp_id, fill="black", font=fonts["normal"])

    draw.text((info_x, info_y + 180), "DEPARTMENT", fill="#6b7280", font=fonts["small"])
    draw.text((info_x, info_y + 212), dept, fill="black", font=fonts["normal"])

    # Label STAFF kecil
    draw.text(
        (info_x, info_y + 260),
        "STAFF",
        fill="#111827",
        font=fonts["normal"],
    )

    # Issue & valid date
    issue_date = datetime.now() - timedelta(days=random.randint(200, 800))
    valid_until = issue_date + timedelta(days=4 * 365)

    bottom_y = H - 120
    draw.text(
        (80, bottom_y),
        "ISSUE DATE",
        fill="#6b7280",
        font=fonts["small"],
    )
    draw.text(
        (80, bottom_y + 32),
        issue_date.strftime("%m/%d/%Y"),
        fill="black",
        font=fonts["normal"],
    )

    draw.text(
        (W - 260, bottom_y),
        "VALID UNTIL",
        fill="#6b7280",
        font=fonts["small"],
    )
    draw.text(
        (W - 260, bottom_y + 32),
        valid_until.strftime("%m/%d/%Y"),
        fill="black",
        font=fonts["normal"],
    )

    return img, emp_id, dept


# =====================================================
# 2. PAY STUB / SALARY STATEMENT
# =====================================================

def generate_pay_stub(
    teacher_name: str,
    teacher_email: str,
    school_name: str,
    emp_id: str,
    department: str,
):
    """
    Slip gaji mirip Salary_Statement.jpg + detail realistis:
    - Employer info
    - Pay date & pay period
    - Regular salary, YTD, deductions, net pay
    """
    W, H = 850, 1150
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Header
    header_y = 40
    draw.text(
        (W / 2, header_y),
        school_name,
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )
    draw.text(
        (W / 2, header_y + 35),
        "Payroll Department | 335 Manor Avenue DowningtownPA19335",
        fill="black",
        font=fonts["small"],
        anchor="mm",
    )
    draw.text(
        (W / 2, header_y + 80),
        "SALARY STATEMENT",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )

    # Pay period & pay date
    end = datetime.now() - timedelta(days=random.randint(1, 10))
    start = end - timedelta(days=14)
    pay_date = end + timedelta(days=1)

    draw.text(
        (W / 2, header_y + 118),
        f"Pay Period: {start.strftime('%m/%d/%Y')} - {end.strftime('%m/%d/%Y')}",
        fill="black",
        font=fonts["normal"],
        anchor="mm",
    )
    draw.text(
        (W / 2, header_y + 148),
        f"Pay Date: {pay_date.strftime('%m/%d/%Y')}",
        fill="black",
        font=fonts["normal"],
        anchor="mm",
    )

    # Employee information box
    box_y = 210
    draw.rectangle([(40, box_y), (W - 40, box_y + 190)], outline="black", width=2)

    draw.text(
        (W / 2, box_y + 15),
        "Employee Information",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )

    draw.text(
        (60, box_y + 60),
        f"Name: {teacher_name}",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, box_y + 90),
        f"Employee ID: {emp_id}",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, box_y + 120),
        f"Department: {department}",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, box_y + 150),
        "Position: Administrative Assistant Level I",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, box_y + 180),
        f"Email: {teacher_email}",
        fill="black",
        font=fonts["normal"],
    )

    # Earnings
    earn_y = box_y + 215
    draw.rectangle([(40, earn_y), (W - 40, earn_y + 210)], outline="black", width=2)
    draw.text(
        (W / 2, earn_y + 10),
        "EARNINGS",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )

    regular_salary = random.randint(2100, 2600) + random.random()
    y_line = earn_y + 60
    draw.text(
        (60, y_line),
        "Regular Salary:",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (W - 60, y_line),
        f"${regular_salary:,.2f}",
        fill="black",
        font=fonts["normal"],
        anchor="rm",
    )

    draw.text(
        (60, y_line + 40),
        "TOTAL GROSS PAY:",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (W - 60, y_line + 40),
        f"${regular_salary:,.2f}",
        fill="black",
        font=fonts["normal"],
        anchor="rm",
    )

    # YTD sederhana (sekadar kelipatan random dari gross)
    ytd_multiplier = random.randint(5, 9)
    ytd_gross = regular_salary * ytd_multiplier

    draw.text(
        (60, y_line + 80),
        f"YTD Gross: ${ytd_gross:,.2f}",
        fill="#4b5563",
        font=fonts["small"],
    )

    # Deductions
    ded_y = earn_y + 230
    draw.rectangle([(40, ded_y), (W - 40, ded_y + 230)], outline="black", width=2)
    draw.text(
        (W / 2, ded_y + 10),
        "DEDUCTIONS",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )

    perc = {
        "Federal Tax": random.uniform(0.18, 0.24),
        "State Tax": random.uniform(0.04, 0.07),
        "Social Security": random.uniform(0.05, 0.07),
        "Medicare": random.uniform(0.01, 0.02),
        "Retirement": random.uniform(0.03, 0.06),
    }

    y_line = ded_y + 60
    total_ded = 0
    for label, p in perc.items():
        amount = regular_salary * p
        total_ded += amount
        draw.text((60, y_line), f"{label}:", fill="black", font=fonts["normal"])
        draw.text(
            (W - 60, y_line),
            f"${amount:,.2f}",
            fill="black",
            font=fonts["normal"],
            anchor="rm",
        )
        y_line += 30

    draw.text(
        (60, y_line + 10),
        "TOTAL DEDUCTIONS:",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (W - 60, y_line + 10),
        f"${total_ded:,.2f}",
        fill="black",
        font=fonts["normal"],
        anchor="rm",
    )

    # YTD ded & net (kecil)
    ytd_ded = total_ded * ytd_multiplier
    ytd_net = ytd_gross - ytd_ded
    draw.text(
        (60, y_line + 50),
        f"YTD Deductions: ${ytd_ded:,.2f}   |   YTD Net: ${ytd_net:,.2f}",
        fill="#4b5563",
        font=fonts["small"],
    )

    # Net pay
    net = regular_salary - total_ded
    net_y = ded_y + 260
    draw.rectangle([(40, net_y), (W - 40, net_y + 120)], fill="#111827")
    draw.text(
        (W / 2, net_y + 35),
        "NET PAY",
        fill="white",
        font=fonts["heading"],
        anchor="mm",
    )
    draw.text(
        (W / 2, net_y + 80),
        f"${net:,.2f}",
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )

    # Footer kecil
    footer_y = net_y + 140
    draw.text(
        (W / 2, footer_y),
        "This statement is for informational purposes only.",
        fill="#6b7280",
        font=fonts["small"],
        anchor="mm",
    )

    return img


# =====================================================
# 3. EMPLOYMENT VERIFICATION LETTER
# =====================================================

def generate_employment_letter(
    teacher_name: str,
    teacher_email: str,
    school_name: str,
    emp_id: str,
    department: str,
):
    """
    Surat keterangan kerja mirip Employment_Letter.jpg:
    - Letterhead + alamat + kontak
    - Date, Reference No, Employee ID
    - Paragraf status kerja + tanggal mulai
    - Tabel Employment Details
    """
    W, H = 850, 1200
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Header
    top_y = 40
    draw.text(
        (W / 2, top_y),
        school_name.upper(),
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )
    draw.text(
        (W / 2, top_y + 30),
        "Office of Human Resources",
        fill="black",
        font=fonts["normal"],
        anchor="mm",
    )
    draw.text(
        (W / 2, top_y + 55),
        "335 Manor Avenue DowningtownPA19335",
        fill="black",
        font=fonts["small"],
        anchor="mm",
    )
    draw.text(
        (W / 2, top_y + 75),
        "Tel: (555) 123-4500 | Email: hr@downingtownstemacademy.edu",
        fill="black",
        font=fonts["small"],
        anchor="mm",
    )

    # Date + reference + employee id
    today = datetime.now()
    ref_no = f"HR-{today.year}-{random.randint(2000,9999)}"

    # tanggal mulai kerja acak beberapa tahun lalu
    start_year = today.year - random.randint(2, 5)
    start_date = today.replace(year=start_year, month=random.randint(1, 12), day=10)

    base_y = 160
    draw.text(
        (60, base_y),
        f"Date: {today.strftime('%B %d, %Y')}",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, base_y + 30),
        f"Reference No: {ref_no}",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, base_y + 60),
        f"Employee ID: {emp_id}",
        fill="black",
        font=fonts["normal"],
    )

    # To whom it may concern
    draw.text(
        (60, base_y + 110),
        "To Whom It May Concern:",
        fill="black",
        font=fonts["normal"],
    )

    draw.text(
        (W / 2, base_y + 160),
        "EMPLOYMENT VERIFICATION",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )

    # Paragraf
    para_y = base_y + 210
    text_lines = [
        f"This letter is to certify that {teacher_name} has been employed",
        f"as an Administrative Assistant Level I at {school_name} since "
        f"{start_date.strftime('%B %d, %Y')}.",
        "",
        f"{teacher_name} is currently employed on a full-time basis in the",
        f"{department} Department and is in good standing with no",
        "disciplinary actions on record.",
        "",
        f"The official school email address for {teacher_name} is:",
        f"{teacher_email}.",
        "",
        "This verification is issued at the request of the employee and may",
        "be presented to any institution or agency that requires proof of",
        "current employment.",
        "",
        "Should you require any additional information, please contact the",
        "Human Resources Department during regular business hours.",
    ]
    for line in text_lines:
        draw.text((60, para_y), line, fill="black", font=fonts["normal"])
        para_y += 30

    # Tabel Employment Details
    table_y = para_y + 20
    table_h = 240
    draw.text(
        (W / 2, table_y),
        "EMPLOYMENT DETAILS",
        fill="black",
        font=fonts["heading"],
        anchor="mm",
    )
    table_y += 20

    top = table_y + 20
    left = 40
    right = W - 40
    bottom = top + table_h
    draw.rectangle([(left, top), (right, bottom)], outline="black", width=2)

    rows = [
        ("Full Name", teacher_name),
        ("Employee ID", emp_id),
        ("Position", "Administrative Assistant Level I"),
        ("Department", department),
        ("College", "College of Liberal Arts and Social Sciences"),
        ("Employment Status", "Full-time Faculty Member"),
        ("Date of Appointment", start_date.strftime("%m/%d/%Y")),
    ]

    row_h = table_h // len(rows)
    y = top
    for label, value in rows:
        draw.line([(left, y), (right, y)], fill="black", width=1)
        draw.text(
            (left + 10, y + 8),
            f"{label}:",
            fill="black",
            font=fonts["small"],
        )
        draw.text(
            (left + 260, y + 8),
            value,
            fill="black",
            font=fonts["small"],
        )
        y += row_h
    draw.line([(left, bottom), (right, bottom)], fill="black", width=1)

    # Closing + signature
    closing_y = bottom + 40
    draw.text(
        (60, closing_y),
        "Respectfully yours,",
        fill="black",
        font=fonts["normal"],
    )

    sign_y = closing_y + 80
    draw.line([(60, sign_y), (300, sign_y)], fill="black", width=2)
    draw.text(
        (60, sign_y + 10),
        "Eldred Leffler",
        fill="black",
        font=fonts["normal"],
    )
    draw.text(
        (60, sign_y + 40),
        "Director, Human Resources",
        fill="black",
        font=fonts["small"],
    )
    draw.text(
        (60, sign_y + 60),
        school_name,
        fill="black",
        font=fonts["small"],
    )

    return img


# =====================================================
# CONTOH PEMAKAIAN MANUAL
# =====================================================

if __name__ == "__main__":
    school = "Downingtown STEM Academy"
    name = "Kaitlin Brinker"
    email = "kaitlin.brinker@example.edu"

    id_img, emp_id, dept = generate_faculty_id(
        teacher_name=name,
        teacher_email=email,
        school_name=school,
    )
    pay_img = generate_pay_stub(
        teacher_name=name,
        teacher_email=email,
        school_name=school,
        emp_id=emp_id,
        department=dept,
    )
    letter_img = generate_employment_letter(
        teacher_name=name,
        teacher_email=email,
        school_name=school,
        emp_id=emp_id,
        department=dept,
    )

    id_img.save("Faculty_ID_Front_Gen.jpg", "JPEG", quality=95)
    pay_img.save("Salary_Statement_Gen.jpg", "JPEG", quality=95)
    letter_img.save("Employment_Letter_Gen.jpg", "JPEG", quality=95)
