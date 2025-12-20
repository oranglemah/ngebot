from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import random
import io
import requests


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
    """Ambil foto dari URL dan resize"""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img = img.resize(size, Image.LANCZOS)
        return img
    except Exception:
        return None


def generate_faculty_id(
    teacher_name,
    teacher_email,
    school_name,
    photo_url="https://github.com/oranglemah/ngebot/raw/main/foto.jpg",
):
    """Generate Faculty ID Card realistis dengan foto dari URL"""
    width, height = 850, 540
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Border
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline="#1e3a8a", width=4)

    # Header
    draw.rectangle([(0, 0), (width, 130)], fill="#1e40af")
    # Logo placeholder
    draw.ellipse([(30, 30), (110, 110)], fill="white")
    draw.text((70, 70), "LOGO", fill="#1e40af", font=fonts["small"], anchor="mm")

    draw.text(
        (width // 2, 40),
        school_name.upper(),
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )
    draw.text(
        (width // 2, 90),
        "FACULTY IDENTIFICATION CARD",
        fill="white",
        font=fonts["heading"],
        anchor="mm",
    )

    # Photo section
    photo_x, photo_y = 40, 150
    photo_w, photo_h = 230, 300
    draw.rectangle(
        [(photo_x, photo_y), (photo_x + photo_w, photo_y + photo_h)],
        fill="#e5e7eb",
        outline="#374151",
        width=3,
    )

    photo = fetch_photo(photo_url, size=(photo_w - 10, photo_h - 10))
    if photo:
        img.paste(photo, (photo_x + 5, photo_y + 5))
    else:
        draw.text(
            (photo_x + photo_w // 2, photo_y + photo_h // 2),
            "FACULTY\nPHOTO",
            fill="#6b7280",
            font=fonts["heading"],
            anchor="mm",
            align="center",
        )

    # Info section (lebih besar & rapi)
    info_x = 320
    y_start = 150

    draw.text((info_x, y_start), "NAME", fill="#374151", font=fonts["small"])
    draw.text((info_x, y_start + 30), teacher_name, fill="black", font=fonts["heading"])

    draw.text((info_x, y_start + 85), "EMAIL", fill="#374151", font=fonts["small"])
    draw.text(
        (info_x, y_start + 115), teacher_email, fill="black", font=fonts["normal"]
    )

    faculty_id = f"FAC-{random.randint(10000, 99999)}"
    draw.text((info_x, y_start + 165), "FACULTY ID", fill="#374151", font=fonts["small"])
    draw.text(
        (info_x, y_start + 195), faculty_id, fill="black", font=fonts["heading"]
    )

    departments = [
        "Mathematics",
        "English",
        "Science",
        "History",
        "Physical Education",
    ]
    dept = random.choice(departments)
    draw.text((info_x, y_start + 245), "DEPARTMENT", fill="#374151", font=fonts["small"])
    draw.text((info_x, y_start + 275), dept, fill="black", font=fonts["normal"])

    expiry = (datetime.now() + timedelta(days=365)).strftime("%m/%Y")
    draw.text(
        (info_x, y_start + 320),
        f"EXPIRES {expiry}",
        fill="#dc2626",
        font=fonts["heading"],
    )

    # Barcode
    bar_top, bar_bottom = 480, 520
    draw.rectangle([(40, bar_top), (810, bar_bottom)], fill="black")
    for i in range(0, 770, 14):
        if random.choice([True, False]):
            draw.rectangle([(40 + i, bar_top), (40 + i + 7, bar_bottom)], fill="white")
    draw.text(
        (425, 530),
        faculty_id,
        fill="#374151",
        font=fonts["normal"],
        anchor="mm",
    )

    return img, faculty_id


def generate_pay_stub(teacher_name, teacher_email, school_name, faculty_id):
    """Slip gaji lebih lengkap dan tulisan besar"""
    width, height = 850, 1200
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Header
    draw.rectangle([(0, 0), (width, 140)], fill="#1e40af")
    draw.text(
        (width // 2, 45),
        school_name.upper(),
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )
    draw.text(
        (width // 2, 100),
        "PAYROLL STATEMENT",
        fill="white",
        font=fonts["heading"],
        anchor="mm",
    )

    # Date & period
    pay_date = datetime.now().strftime("%B %d, %Y")
    pay_period_start = (datetime.now() - timedelta(days=15)).strftime("%m/%d/%Y")
    pay_period_end = datetime.now().strftime("%m/%d/%Y")

    y = 155
    draw.text((50, y), f"Pay Date: {pay_date}", fill="black", font=fonts["normal"])
    draw.text(
        (50, y + 35),
        f"Pay Period: {pay_period_start} - {pay_period_end}",
        fill="black",
        font=fonts["normal"],
    )

    
    y = 220
    draw.rectangle([(40, y), (810, y + 200)], outline="#374151", width=2)
    draw.text((60, y + 15), "EMPLOYEE INFORMATION", fill="#1e40af", font=fonts["heading"])

    draw.text((60, y + 55), f"Name: {teacher_name}", fill="black", font=fonts["normal"])
    draw.text(
        (60, y + 85), f"Email: {teacher_email}", fill="black", font=fonts["normal"]
    )
    draw.text(
        (60, y + 115), f"Employee ID: {faculty_id}", fill="black", font=fonts["normal"]
    )
    draw.text((60, y + 145), "Position: Teacher", fill="black", font=fonts["normal"])
    draw.text(
        (60, y + 175),
        "Department: Faculty of Education",
        fill="black",
        font=fonts["normal"],
    )

    # Earnings
    y = 450
    draw.rectangle([(40, y), (810, y + 300)], outline="#374151", width=2)
    draw.text((60, y + 15), "EARNINGS", fill="#1e40af", font=fonts["heading"])

    base_salary = random.randint(3800, 5800)
    benefits = random.randint(300, 600)
    overtime = random.randint(0, 400)
    bonus = random.randint(0, 300)
    total_gross = base_salary + benefits + overtime + bonus

    earnings = [
        ("Base Salary", f"${base_salary:,.2f}"),
        ("Benefits", f"${benefits:,.2f}"),
        ("Overtime", f"${overtime:,.2f}"),
        ("Bonus", f"${bonus:,.2f}"),
        ("", ""),
        ("GROSS PAY", f"${total_gross:,.2f}"),
    ]

    line_y = y + 55
    for desc, amount in earnings:
        if desc:
            draw.text((60, line_y), desc, fill="black", font=fonts["normal"])
            draw.text(
                (780, line_y),
                amount,
                fill="black",
                font=fonts["normal"],
                anchor="rm",
            )
        if desc == "GROSS PAY":
            draw.line([(60, line_y - 10), (780, line_y - 10)], fill="#374151", width=2)
        line_y += 35

    # Deductions
    y = 780
    draw.rectangle([(40, y), (810, y + 260)], outline="#374151", width=2)
    draw.text((60, y + 15), "DEDUCTIONS", fill="#1e40af", font=fonts["heading"])

    fed_tax = total_gross * 0.14
    state_tax = total_gross * 0.05
    retirement = total_gross * 0.06
    health_ins = total_gross * 0.03
    total_deduct = fed_tax + state_tax + retirement + health_ins

    deductions = [
        ("Federal Tax", f"${fed_tax:,.2f}"),
        ("State Tax", f"${state_tax:,.2f}"),
        ("Retirement (403b)", f"${retirement:,.2f}"),
        ("Health Insurance", f"${health_ins:,.2f}"),
        ("", ""),
        ("TOTAL DEDUCTIONS", f"${total_deduct:,.2f}"),
    ]

    line_y = y + 55
    for desc, amount in deductions:
        if desc:
            draw.text((60, line_y), desc, fill="black", font=fonts["normal"])
            draw.text(
                (780, line_y),
                amount,
                fill="black",
                font=fonts["normal"],
                anchor="rm",
            )
        if desc == "TOTAL DEDUCTIONS":
            draw.line([(60, line_y - 10), (780, line_y - 10)], fill="#374151", width=2)
        line_y += 35

    # Net pay
    net_pay = total_gross - total_deduct
    y = 1070
    draw.rectangle([(40, y), (810, y + 110)], fill="#16a34a")
    draw.text(
        (width // 2, y + 30),
        "NET PAY",
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )
    draw.text(
        (width // 2, y + 75),
        f"${net_pay:,.2f}",
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )

    return img


def generate_employment_letter(teacher_name, teacher_email, school_name):
    """Surat keterangan kerja dengan format lebih resmi & font besar"""
    width, height = 850, 1200
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts()

    # Letterhead
    draw.rectangle([(0, 0), (width, 150)], fill="#1e40af")
    draw.text(
        (width // 2, 50),
        school_name.upper(),
        fill="white",
        font=fonts["title"],
        anchor="mm",
    )
    draw.text(
        (width // 2, 105),
        "Office of Human Resources",
        fill="white",
        font=fonts["heading"],
        anchor="mm",
    )

    # Date
    today = datetime.now().strftime("%B %d, %Y")
    draw.text((560, 180), today, fill="black", font=fonts["normal"])

    # Title
    y = 240
    draw.text((100, y), "TO WHOM IT MAY CONCERN", fill="black", font=fonts["heading"])

    hire_year = random.randint(2018, 2023)

    # Isi surat 
    letter_text = [
        f"This letter is to certify that {teacher_name} is currently employed",
        f"as a full-time faculty member at {school_name}.",
        "",
        f"Employment Start Date: August {hire_year}",
        "Position: Teacher",
        "Status: Active - Full Time",
        f"Official Email: {teacher_email}",
        "",
        f"During the course of employment, {teacher_name} has fulfilled all assigned",
        "teaching duties and institutional responsibilities in a professional manner.",
        "",
        "This letter is issued at the request of the above-named employee for",
        "the purpose of employment verification and may be presented to any",
        "institution or agency that requires proof of current employment.",
        "",
        "Should you require any additional information, please contact the",
        "Human Resources Department during regular business hours.",
    ]

    line_y = y + 60
    for line in letter_text:
        draw.text((100, line_y), line, fill="black", font=fonts["normal"])
        line_y += 32

    # Signature
    y = 900
    draw.text((100, y), "Sincerely,", fill="black", font=fonts["normal"])

    draw.line([(100, y + 80), (420, y + 80)], fill="#374151", width=2)
    draw.text((100, y + 90), "Dr. Sarah Johnson", fill="black", font=fonts["normal"])
    draw.text(
        (100, y + 120),
        "Director of Human Resources",
        fill="#6b7280",
        font=fonts["small"],
    )
    draw.text((100, y + 145), school_name, fill="#6b7280", font=fonts["small"])

    # Official stamp
    draw.ellipse([(540, 830), (780, 1070)], outline="#dc2626", width=4)
    draw.text(
        (660, 950),
        "OFFICIAL\nSEAL",
        fill="#dc2626",
        font=fonts["heading"],
        anchor="mm",
        align="center",
    )

    return img


def image_to_bytes(image):
    """Convert PIL Image ke bytes"""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="JPEG", quality=95)
    img_byte_arr.seek(0)
    return img_byte_arr
