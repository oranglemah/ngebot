from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime, timedelta
import random
import io
import requests
import textwrap

# =====================================================
# UTILITAS GAMBAR & FONT
# =====================================================

def image_to_bytes(image, format="PNG"):
    """
    Mengubah PIL Image menjadi BytesIO agar bisa dikirim ke Telegram
    atau diupload ke API tanpa harus save ke harddisk.
    """
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format=format)
    img_byte_arr.seek(0)
    return img_byte_arr

def get_font(size, bold=False):
    """Mencari font yang tersedia di sistem (Windows/Linux)."""
    font_names = []
    if bold:
        font_names = ["arialbd.ttf", "DejaVuSans-Bold.ttf", "luis_bold.ttf", "Verdana_Bold.ttf"]
    else:
        font_names = ["arial.ttf", "DejaVuSans.ttf", "luis.ttf", "Verdana.ttf"]

    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()

def get_fonts_collection():
    return {
        "title": get_font(50, bold=True),
        "heading": get_font(36, bold=True),
        "subheading": get_font(28, bold=True),
        "normal": get_font(24, bold=False),
        "small": get_font(20, bold=False),
        "tiny": get_font(16, bold=False)
    }

def fetch_photo(url, target_size=(260, 340)):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img = ImageOps.fit(img, target_size, method=Image.LANCZOS, centering=(0.5, 0.5))
        return img
    except Exception:
        return None

# =====================================================
# 1. FACULTY ID CARD
# =====================================================

def generate_faculty_id(teacher_name, teacher_email, school_name, photo_url="https://github.com/oranglemah/ngebot/raw/main/foto.jpg"):
    """
    Output: Tuple (ImageObject, faculty_id_string, department_string)
    """
    W, H = 1200, 768
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts_collection()

    primary_color = "#4c1d95" # Deep Purple
    accent_color = "#fbbf24"  # Amber

    # Header
    header_h = 240
    draw.rectangle([(0, 0), (W, header_h)], fill=primary_color)
    draw.rectangle([(0, header_h), (W, header_h + 15)], fill=accent_color)

    # Logo Placeholder
    logo_r = 160
    logo_x, logo_y = 60, 40
    draw.ellipse([(logo_x, logo_y), (logo_x + logo_r, logo_y + logo_r)], fill="white")
    draw.text((logo_x + logo_r/2, logo_y + logo_r/2), "LOGO", fill=primary_color, font=fonts["heading"], anchor="mm")

    # Text Header
    text_x = logo_x + logo_r + 40
    draw.text((text_x, 80), school_name.upper(), fill="white", font=fonts["title"])
    draw.text((text_x, 150), "FACULTY IDENTIFICATION", fill="#e5e7eb", font=fonts["heading"])

    # Foto
    photo_w, photo_h = 280, 360
    photo_x = 80
    photo_y = header_h + 60
    draw.rectangle([(photo_x - 5, photo_y - 5), (photo_x + photo_w + 5, photo_y + photo_h + 5)], fill="#d1d5db")
    
    photo = fetch_photo(photo_url, target_size=(photo_w, photo_h))
    if photo:
        img.paste(photo, (photo_x, photo_y))
    else:
        draw.rectangle([(photo_x, photo_y), (photo_x + photo_w, photo_y + photo_h)], fill="#e5e7eb")
        draw.text((photo_x + photo_w/2, photo_y + photo_h/2), "NO PHOTO", fill="gray", font=fonts["normal"], anchor="mm")

    # Info
    info_x = photo_x + photo_w + 100
    current_y = header_h + 80
    
    emp_id = f"EDU-{random.randint(10000, 99999)}"
    departments = ["Science & Tech", "Mathematics", "Linguistics", "Social Studies", "Arts"]
    dept = random.choice(departments)

    def draw_field(label, value, y_pos, is_highlight=False):
        draw.text((info_x, y_pos), label, fill="#6b7280", font=fonts["small"])
        font_val = fonts["title"] if is_highlight else fonts["heading"]
        draw.text((info_x, y_pos + 30), value, fill="black", font=font_val)
        return y_pos + 90

    current_y = draw_field("NAME", teacher_name, current_y, is_highlight=True)
    current_y = draw_field("EMPLOYEE ID", emp_id, current_y)
    current_y = draw_field("DEPARTMENT", dept, current_y)

    # Badge Staff
    draw.rectangle([(info_x, current_y + 10), (info_x + 200, current_y + 70)], fill=primary_color)
    draw.text((info_x + 100, current_y + 40), "STAFF", fill="white", font=fonts["heading"], anchor="mm")

    # Footer Date
    bottom_y = H - 100
    issue_date = datetime.now() - timedelta(days=random.randint(100, 900))
    valid_until = issue_date + timedelta(days=5 * 365)

    draw.text((80, bottom_y), "ISSUED:", fill="#6b7280", font=fonts["small"])
    draw.text((190, bottom_y), issue_date.strftime("%d %b %Y").upper(), fill="black", font=fonts["normal"])
    draw.text((W - 400, bottom_y), "EXPIRES:", fill="#6b7280", font=fonts["small"])
    draw.text((W - 280, bottom_y), valid_until.strftime("%d %b %Y").upper(), fill="#dc2626", font=fonts["heading"])

    return img, emp_id, dept

# =====================================================
# 2. PAY STUB
# =====================================================

def generate_pay_stub(teacher_name, teacher_email, school_name, emp_id, department):
    """
    Output: ImageObject
    """
    W, H = 850, 1150
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts_collection()
    
    margin = 50
    center = W / 2

    # Header
    draw.text((center, 50), school_name, fill="black", font=fonts["heading"], anchor="mm")
    draw.text((center, 90), "PAYROLL SERVICES | 123 Education Lane", fill="#4b5563", font=fonts["small"], anchor="mm")
    draw.line([(margin, 120), (W-margin, 120)], fill="black", width=2)
    draw.text((center, 150), "EARNINGS STATEMENT", fill="black", font=fonts["heading"], anchor="mm")

    # Kotak Info
    box_top = 200
    draw.rectangle([(margin, box_top), (W-margin, box_top + 180)], outline="black", width=1)
    
    col1_x = margin + 20
    draw.text((col1_x, box_top + 20), f"Employee: {teacher_name}", fill="black", font=fonts["normal"])
    draw.text((col1_x, box_top + 60), f"ID: {emp_id}", fill="black", font=fonts["normal"])
    draw.text((col1_x, box_top + 100), f"Dept: {department}", fill="black", font=fonts["normal"])
    
    pay_end = datetime.now()
    pay_start = pay_end - timedelta(days=30)
    col2_x = W / 2 + 20
    draw.text((col2_x, box_top + 20), f"Pay Date: {pay_end.strftime('%m/%d/%Y')}", fill="black", font=fonts["normal"])
    draw.text((col2_x, box_top + 60), f"Period: {pay_start.strftime('%m/%d')}-{pay_end.strftime('%m/%d')}", fill="black", font=fonts["normal"])
    draw.text((col2_x, box_top + 100), f"Email: {teacher_email}", fill="black", font=fonts["small"])

    # Tabel
    table_y = 420
    draw.rectangle([(margin, table_y), (W-margin, table_y + 40)], fill="#e5e7eb")
    draw.text((margin + 20, table_y+10), "DESCRIPTION", fill="black", font=fonts["subheading"])
    draw.text((W - margin - 20, table_y+10), "AMOUNT ($)", fill="black", font=fonts["subheading"], anchor="ra")

    y = table_y + 60
    base_salary = random.randint(3500, 4800)
    items = [("Regular Earnings", base_salary), ("Stipend", random.choice([0, 150, 300]))]
    
    gross_pay = 0
    for label, amount in items:
        if amount > 0:
            draw.text((margin + 20, y), label, fill="black", font=fonts["normal"])
            draw.text((W - margin - 20, y), f"{amount:,.2f}", fill="black", font=fonts["normal"], anchor="ra")
            gross_pay += amount
            y += 40
    
    y += 10
    draw.line([(margin, y), (W-margin, y)], fill="black", width=1)
    y += 20
    draw.text((margin + 20, y), "GROSS PAY", fill="black", font=fonts["subheading"])
    draw.text((W - margin - 20, y), f"{gross_pay:,.2f}", fill="black", font=fonts["subheading"], anchor="ra")

    y += 60
    draw.rectangle([(margin, y), (W-margin, y + 40)], fill="#e5e7eb")
    draw.text((margin + 20, y+10), "TAXES & DEDUCTIONS", fill="black", font=fonts["subheading"])
    
    y += 60
    deductions = [("Federal Tax", gross_pay * 0.12), ("Social Security", gross_pay * 0.062), ("Medicare", gross_pay * 0.0145)]
    total_ded = 0
    for label, amount in deductions:
        draw.text((margin + 20, y), label, fill="black", font=fonts["normal"])
        draw.text((W - margin - 20, y), f"({amount:,.2f})", fill="#dc2626", font=fonts["normal"], anchor="ra")
        total_ded += amount
        y += 40
        
    net_pay = gross_pay - total_ded
    y += 40
    draw.rectangle([(margin, y), (W-margin, y + 80)], fill="#1f2937")
    draw.text((margin + 30, y + 25), "NET PAY CHECK", fill="white", font=fonts["heading"])
    draw.text((W - margin - 30, y + 20), f"${net_pay:,.2f}", fill="white", font=fonts["title"], anchor="ra")

    return img

# =====================================================
# 3. EMPLOYMENT LETTER
# =====================================================

def generate_employment_letter(teacher_name, teacher_email, school_name, emp_id, department):
    """
    Output: ImageObject
    """
    W, H = 850, 1100
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fonts = get_fonts_collection()
    
    margin = 80
    
    # Letterhead
    draw.text((W/2, 60), school_name, fill="#1f2937", font=fonts["title"], anchor="mm")
    draw.text((W/2, 110), "OFFICE OF HUMAN RESOURCES", fill="#4b5563", font=fonts["subheading"], anchor="mm")
    draw.line([(margin, 140), (W-margin, 140)], fill="black", width=2)
    
    y = 180
    draw.text((margin, y), datetime.now().strftime("%B %d, %Y"), fill="black", font=fonts["normal"])
    draw.text((margin, y + 40), "To Whom It May Concern,", fill="black", font=fonts["normal"])
    
    y = 300
    draw.text((W/2, y), "CERTIFICATE OF EMPLOYMENT", fill="black", font=fonts["heading"], anchor="mm")
    
    start_date_str = (datetime.now() - timedelta(days=random.randint(700, 2000))).strftime("%B %d, %Y")
    body_text = (
        f"This letter is to certify that {teacher_name} is currently employed with {school_name} "
        f"as a full-time employee in the {department} Department.\n\n"
        f"The employee has been with our institution since {start_date_str} and holds the employee ID number {emp_id}. "
        f"{teacher_name} is an employee in good standing.\n\n"
        "This certification is being issued upon the request of the employee for whatever legal purpose it may serve."
    )
    
    y = 360
    paragraphs = body_text.split('\n\n')
    for para in paragraphs:
        lines = textwrap.wrap(para, width=60)
        for line in lines:
            draw.text((margin, y), line, fill="black", font=fonts["normal"])
            y += 35
        y += 20

    # Details Box
    y += 20
    draw.rectangle([(margin, y), (W-margin, y+200)], outline="black")
    details = [("Name", teacher_name), ("Position", "Senior Lecturer"), ("Department", department), ("Status", "Full-Time")]
    
    row_y = y + 20
    for label, value in details:
        draw.text((margin + 20, row_y), f"{label}:", fill="#4b5563", font=fonts["normal"])
        draw.text((margin + 250, row_y), value, fill="black", font=fonts["subheading"])
        row_y += 45

    # Signature
    sig_y = H - 200
    draw.text((margin, sig_y), "Sincerely,", fill="black", font=fonts["normal"])
    draw.line([(margin, sig_y + 80), (margin + 250, sig_y + 80)], fill="black", width=2)
    draw.text((margin, sig_y + 90), "Eleanor Rigby", fill="black", font=fonts["heading"])
    draw.text((margin, sig_y + 125), "Director of HR", fill="#4b5563", font=fonts["normal"])

    return img
