from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.request import HTTPXRequest
import httpx
import re
import os
import random
from datetime import datetime, timedelta
from document_generator import (
    generate_faculty_id,
    generate_pay_stub,
    generate_employment_letter,
    image_to_bytes
)

# =====================================================
# KONFIGURASI
# =====================================================
# Bot utama
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Bot logger
LOG_BOT_TOKEN = os.environ.get("LOG_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
BOT_NAME = os.environ.get("BOT_NAME", "K12_BOT")

SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

LOG_API_URL = (
    f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
    if LOG_BOT_TOKEN
    else None
)

# States untuk ConversationHandler
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)

# Timeout per step (detik)
STEP_TIMEOUT = 300  # 5 menit

# Storage untuk data user (per user_id)
user_data = {}

# =====================================================
# HELPER: LOGGING VIA BOT LOGGER
# =====================================================

async def send_log(text: str):
    """Kirim log ke admin lewat BOT logger (LOG_BOT_TOKEN)."""
    if not LOG_BOT_TOKEN or ADMIN_CHAT_ID == 0 or not LOG_API_URL:
        print("⚠️ LOG_BOT_TOKEN atau ADMIN_CHAT_ID belum diset, skip log")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "chat_id": ADMIN_CHAT_ID,
                "text": text,
               # "parse_mode": "Markdown",
            }
            resp = await client.post(LOG_API_URL, json=payload)
            if resp.status_code != 200:
                print(f"❌ Log send failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Exception sending log: {e}")


async def log_user_start(update: Update):
    """Log saat user kirim /start ke bot utama."""
    user = update.effective_user
    chat = update.effective_chat
    text = (
        f"📥 NEW USER STARTED BOT ({BOT_NAME})\n\n"
        f"ID: {user.id}\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username or '-'}\n"
        f"Chat ID: {chat.id}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await send_log(text)


async def log_verification_result(
    user_id: int,
    full_name: str,
    school_name: str,
    email: str,
    faculty_id: str,
    success: bool,
    error_msg: str = "",
):
    """Log hasil verifikasi (sukses / gagal)."""
    status_emoji = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"
    text = (
        f"{status_emoji} VERIFICATION {status_text} ({BOT_NAME})\n\n"
        f"ID: {user_id}\n"
        f"Name: {full_name}\n"
        f"School: {school_name}\n"
        f"Email: {email}\n"
        f"Faculty ID: {faculty_id}\n"
    )
    if not success:
        text += f"\nError: {error_msg}"
    await send_log(text)

# =====================================================
# HELPER: TIMEOUT PER STEP (JOBQUEUE)
# =====================================================

async def step_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    """Dipanggil kalau user tidak respon di step tertentu dalam 5 menit."""
    job = context.job
    chat_id = job.chat_id
    user_id = job.user_id
    step_name = job.data.get("step", "UNKNOWN")

    if user_id in user_data:
        del user_data[user_id]

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏰ *Timeout di step {step_name}*\n\n"
                "Kamu tidak merespon dalam 5 menit.\n"
                "Silakan kirim /start untuk mengulang dari awal."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"❌ Failed to send timeout message: {e}")

    print(f"⏰ Timeout {step_name} untuk user {user_id}")


def set_step_timeout(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, step: str
):
    """Set timeout 5 menit untuk step tertentu."""
    
    if context.job_queue is None:
        print("⚠️ JobQueue is None, skip set_step_timeout")
        return

    job_name = f"timeout_{step}_{user_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_once(
        step_timeout_job,
        when=STEP_TIMEOUT,
        chat_id=chat_id,
        user_id=user_id,
        name=job_name,
        data={"step": step},
    )


def clear_all_timeouts(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Hapus semua timeout milik user ini."""
   
    if context.job_queue is None:
        print("⚠️ JobQueue is None, skip clear_all_timeouts")
        return

    for step in ["URL", "NAME", "EMAIL", "SCHOOL"]:
        job_name = f"timeout_{step}_{user_id}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()

# =====================================================
# CONVERSATION HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    await log_user_start(update)

    if user_id in user_data:
        del user_data[user_id]
    clear_all_timeouts(context, user_id)

    set_step_timeout(context, chat_id, user_id, "URL")

    await update.message.reply_text(
        "🎓 *K12 Teacher Verification Bot*\n\n"
        "Send your SheerID verification URL:\n\n"
        "`https://services.sheerid.com/verify/.../verificationId=...`\n\n"
        "Example:\n"
        "`https://services.sheerid.com/verify/68d47554...`\n\n"
        "*⏰ Kamu punya 5 menit untuk kirim link*",
        parse_mode="Markdown",
    )
    return SHEERID_URL


async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima URL SheerID"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    match = re.search(r"verificationId=([a-f0-9]{24})", url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ *Invalid URL!*\n\n"
            "Please send a valid SheerID verification URL.\n"
            "Format: `verificationId=...`\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "URL")
        return SHEERID_URL

    verification_id = match.group(1)
    user_data[user_id] = {"verification_id": verification_id}

    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "NAME")

    await update.message.reply_text(
        f"✅ *Verification ID:* `{verification_id}`\n\n"
        "What's your *full name*?\n"
        "Example: Elizabeth Bradly\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode="Markdown",
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nama lengkap"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    full_name = update.message.text.strip()

    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Please provide *first name AND last name*\n"
            "Example: John Smith\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "NAME")
        return NAME

    user_data.setdefault(user_id, {})
    user_data[user_id]["first_name"] = parts[0]
    user_data[user_id]["last_name"] = " ".join(parts[1:])
    user_data[user_id]["full_name"] = full_name

    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "EMAIL")

    await update.message.reply_text(
        f"✅ *Name:* {full_name}\n\n"
        "What's your *school email address*?\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode="Markdown",
    )
    return EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima email sekolah"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    email = update.message.text.strip()

    if "@" not in email or "." not in email:
        await update.message.reply_text(
            "❌ Invalid email format!\n"
            "Please provide a valid school email address.\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode="Markdown",
        )
        set_step_timeout(context, chat_id, user_id, "EMAIL")
        return EMAIL

    user_data.setdefault(user_id, {})
    user_data[user_id]["email"] = email

    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, "SCHOOL")

    await update.message.reply_text(
        f"✅ *Email:* `{email}`\n\n"
        "What's your *school name*?\n"
        "Example: The Clinton School\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode="Markdown",
    )
    return SCHOOL


async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terima nama sekolah & search"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    school_name = update.message.text.strip()
    user_data.setdefault(user_id, {})
    user_data[user_id]["school_name"] = school_name

    set_step_timeout(context, chat_id, user_id, "SCHOOL")

    try:
        msg = await update.message.reply_text(
            f"⚙️ Searching for schools matching: *{school_name}*\n"
            "Please wait...",
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"❌ Error sending search message: {e}")
        return ConversationHandler.END

    schools = await search_schools(school_name)

    if not schools:
        try:
            await msg.edit_text(
                "❌ *No schools found or SheerID timeout!*\n\n"
                "Try a different school name later.\n\n"
                "*⏰ Kamu bisa /start lagi*",
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"❌ Error editing message: {e}")
        return ConversationHandler.END

    try:
        await msg.delete()
    except Exception as e:
        print(f"⚠️ Failed to delete temp message: {e}")

    await display_schools(update, schools, user_id)

    clear_all_timeouts(context, user_id)
    return ConversationHandler.END

# =====================================================
# SCHOOL SEARCH
# =====================================================

async def search_schools(query: str) -> list:
    """Search schools via SheerID OrgSearch (K12 + HIGH_SCHOOL)."""
    async with httpx.AsyncClient(timeout=10.0) as client:  # timeout dipersempit
        all_schools = []

        for school_type in ["K12", "HIGH_SCHOOL"]:
            try:
                params = {"country": "US", "type": school_type, "name": query}
                print(f"\n📡 Searching {school_type} schools... Query: {query}")
                resp = await client.get(ORGSEARCH_URL, params=params)

                if resp.status_code != 200:
                    print(f"❌ API error for {school_type}: {resp.status_code}")
                    continue

                data = resp.json()
                if isinstance(data, list):
                    all_schools.extend(data)
            except httpx.TimeoutException:
                print(f"❌ SheerID orgsearch timeout for {school_type}")
                continue
            except Exception as e:
                print(f"❌ Error searching {school_type}: {e}")
                continue

        seen = set()
        unique = []
        for s in all_schools:
            sid = s.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                unique.append(s)

        print(f"📊 Total unique schools: {len(unique)}")
        return unique[:20]


async def display_schools(update: Update, schools: list, user_id: int):
    """Tampilkan hasil search + inline buttons."""
    text = "🏫 *SCHOOL SEARCH RESULTS*\n\n"
    text += f"Query: `{user_data[user_id]['school_name']}`\n"
    text += f"Found: *{len(schools)}* schools\n\n"

    keyboard = []

    for idx, school in enumerate(schools):
        user_data[user_id][f"school_{idx}"] = school
        name = school.get("name", "Unknown")
        city = school.get("city", "")
        state = school.get("state", "")
        s_type = school.get("type", "SCHOOL")
        location = f"{city}, {state}" if city and state else state or "US"

        text += f"{idx+1}. *{name}*\n"
        text += f"   📍 {location}\n"
        text += f"   └─ Type: `{s_type}`\n\n"

        button_text = f"{idx+1}. {name[:40]}{'...' if len(name) > 40 else ''}"
        keyboard.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=f"sel_{user_id}_{idx}"
                )
            ]
        )

    text += "\n👆 *Click button to select school*"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

# =====================================================
# SHEERID STATUS CHECK
# =====================================================

async def check_sheerid_status(verification_id: str) -> dict:
    """Cek status verifikasi dari SheerID (success / pending / error / docUpload / dll)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}"
            resp = await client.get(url)
            if resp.status_code != 200:
                msg = f"Status check failed: {resp.status_code}"
                print("❌", msg)
                return {"success": False, "status": "unknown", "message": msg}

            data = resp.json()
            step = data.get("currentStep", "unknown")
            print(f"🔎 SheerID currentStep: {step}")
            return {"success": True, "status": step, "data": data}
        except httpx.TimeoutException:
            msg = "Status check timeout"
            print("❌", msg)
            return {"success": False, "status": "unknown", "message": msg}
        except Exception as e:
            msg = f"Status check error: {str(e)}"
            print("❌", msg)
            return {"success": False, "status": "unknown", "message": msg}

# =====================================================
# BUTTON CALLBACK
# =====================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> button_callback called")
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    user_id = int(parts[1])
    school_idx = int(parts[2])

    if user_id not in user_data:
        await query.edit_message_text(
            "❌ *Session expired*\n\n"
            "Please /start again",
            parse_mode="Markdown",
        )
        return

    school = user_data[user_id].get(f"school_{school_idx}")
    if not school:
        await query.edit_message_text(
            "❌ *School data not found*\n\n"
            "Please /start again",
            parse_mode="Markdown",
        )
        return

    school_name = school.get("name")
    school_type = school.get("type", "K12")
    school_id = school.get("id")

    await query.edit_message_text(
        f"✅ *Selected School:*\n"
        f"Name: {school_name}\n"
        f"Type: `{school_type}`\n"
        f"ID: `{school_id}`\n\n"
        f"⚙️ *Generating documents...*",
        parse_mode="Markdown",
    )

    verification_id = user_data[user_id]["verification_id"]
    first_name = user_data[user_id]["first_name"]
    last_name = user_data[user_id]["last_name"]
    full_name = user_data[user_id]["full_name"]
    email = user_data[user_id]["email"]

    try:
        print(f"\n📄 Generating documents for {full_name}...")

        # ---- PEMANGGILAN GENERATOR ----
        id_card, faculty_id, dept = generate_faculty_id(
            teacher_name=full_name,
            teacher_email=email,
            school_name=school_name,
        )
        pay_stub = generate_pay_stub(
            teacher_name=full_name,
            teacher_email=email,
            school_name=school_name,
            emp_id=faculty_id,
            department=dept,
        )
        letter = generate_employment_letter(
            teacher_name=full_name,
            teacher_email=email,
            school_name=school_name,
            emp_id=faculty_id,
            department=dept,
        )
        # -------------------------------

        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()

        await query.edit_message_text(
            f"✅ *Documents generated*\n\n"
            f"⚙️ *Submitting to SheerID...*",
            parse_mode="Markdown",
        )

        result = await submit_sheerid(
            verification_id,
            first_name,
            last_name,
            email,
            school,
            pdf_bytes,
            png_bytes,
        )

        # Cek status setelah upload dokumen (walau mungkin timeout)
        status_info = await check_sheerid_status(verification_id)
        status = status_info.get("status", "unknown")

        await log_verification_result(
            user_id,
            full_name,
            school_name,
            email,
            faculty_id,
            status == "success",
            result.get("message", ""),
        )

        if not result["success"]:
            await query.message.reply_text(
                "❌ *VERIFICATION FAILED*\n\n"
                f"Error: {result.get('message')}\n\n"
                "Please try again or contact support.",
                parse_mode="Markdown",
            )

        else:
            # Kirim dokumen dulu
            await query.message.reply_photo(
                photo=image_to_bytes(id_card),
                caption=f"📇 *Faculty ID Card*\n`{faculty_id}`",
                parse_mode="Markdown",
            )
            await query.message.reply_photo(
                photo=image_to_bytes(pay_stub),
                caption="💰 *Payroll Statement*",
                parse_mode="Markdown",
            )
            await query.message.reply_photo(
                photo=image_to_bytes(letter),
                caption="📄 *Employment Verification Letter*",
                parse_mode="Markdown",
            )

            if status == "success":
                await query.message.reply_text(
                    "✅ *VERIFICATION SUCCESS!*\n\n"
                    "Your educator status has been *approved* by SheerID.\n"
                    "You should now see a page like:\n"
                    "`Status verified – Continue to OpenAI`.",
                    parse_mode="Markdown",
                )
            elif status == "pending":
                await query.message.reply_text(
                    "⏳ *Documents uploaded successfully*\n\n"
                    "Status: `PENDING REVIEW`\n"
                    "You will see `Status verified – Continue to OpenAI` once SheerID approves it.",
                    parse_mode="Markdown",
                )
            else:
                await query.message.reply_text(
                    f"ℹ️ *Documents submitted*\n\n"
                    f"Current SheerID step: `{status}`\n"
                    "If it becomes `success`, you will get a `Status verified` page.",
                    parse_mode="Markdown",
                )

            await query.message.reply_text(
                "Type /start for another verification",
                parse_mode="Markdown",
            )

        if user_id in user_data:
            del user_data[user_id]

    except Exception as e:
        print(f"❌ Error in button_callback: {e}")
        await query.message.reply_text(
            f"❌ *Error occurred:*\n`{str(e)}`",
            parse_mode="Markdown",
        )

# =====================================================
# SHEERID SUBMISSION
# =====================================================

async def submit_sheerid(
    verification_id: str,
    first_name: str,
    last_name: str,
    email: str,
    school: dict,
    pdf_data: bytes,
    png_data: bytes,
) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:  # timeout dipersempit
        try:
            print(f"\n🚀 Starting SheerID submission... ID: {verification_id}")

            age = random.randint(25, 60)
            birth_date = (datetime.now() - timedelta(days=age * 365)).strftime(
                "%Y-%m-%d"
            )
            device_fp = "".join(
                random.choice("0123456789abcdef") for _ in range(32)
            )

            step2_url = (
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/collectTeacherPersonalInfo"
            )
            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "organization": {
                    "id": int(school["id"]),
                    "name": school["name"],
                },
                "deviceFingerprintHash": device_fp,
                "locale": "en-US",
            }

            step2_resp = await client.post(step2_url, json=step2_body)
            if step2_resp.status_code != 200:
                msg = f"Step 2 failed: {step2_resp.status_code}"
                print("❌", msg)
                return {"success": False, "message": msg}

            sso_resp = await client.delete(
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/sso"
            )
            print(f"✅ Step 3 skip SSO: {sso_resp.status_code}")

            step4_url = (
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/docUpload"
            )
            step4_body = {
                "files": [
                    {
                        "fileName": "paystub.pdf",
                        "mimeType": "application/pdf",
                        "fileSize": len(pdf_data),
                    },
                    {
                        "fileName": "faculty_id.png",
                        "mimeType": "image/png",
                        "fileSize": len(png_data),
                    },
                ]
            }
            step4_resp = await client.post(step4_url, json=step4_body)
            if step4_resp.status_code != 200:
                msg = f"Step 4 failed: {step4_resp.status_code}"
                print("❌", msg)
                return {"success": False, "message": msg}

            docs = step4_resp.json().get("documents", [])
            if len(docs) < 2:
                msg = "No upload URLs received from SheerID"
                print("❌", msg)
                return {"success": False, "message": msg}

            pdf_url = docs[0]["uploadUrl"]
            png_url = docs[1]["uploadUrl"]

            up_pdf = await client.put(
                pdf_url, content=pdf_data, headers={"Content-Type": "application/pdf"}
            )
            up_png = await client.put(
                png_url, content=png_data, headers={"Content-Type": "image/png"}
            )
            print(f"  ✓ PDF upload: {up_pdf.status_code}")
            print(f"  ✓ PNG upload: {up_png.status_code}")

            complete_resp = await client.post(
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/completeDocUpload"
            )
            print(f"✅ Complete upload: {complete_resp.status_code}")

            return {"success": True, "message": "Documents uploaded, waiting for review"}

        except httpx.TimeoutException:
            msg = "Request timeout to SheerID - please try again"
            print("❌", msg)
            return {"success": False, "message": msg}
        except Exception as e:
            msg = f"Submission error: {str(e)}"
            print("❌", msg)
            return {"success": False, "message": msg}

# =====================================================
# CANCEL
# =====================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    clear_all_timeouts(context, user_id)

    await update.message.reply_text(
        "❌ *Operation cancelled*\n\n"
        "Type /start to begin again",
        parse_mode="Markdown",
    )
    return ConversationHandler.END

# =====================================================
# MAIN
# =====================================================

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN belum di-set!")
        return

    print("\n" + "=" * 70)
    print(f"🎓 {BOT_NAME}")
    print("=" * 70)
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"👮 Admin Chat ID: {ADMIN_CHAT_ID}")
    print(f"📨 LOG_BOT_TOKEN set: {bool(LOG_BOT_TOKEN)}")
    print(f"⏰ Step timeout: {STEP_TIMEOUT} detik")
    print("=" * 70 + "\n")

    # Request Telegram dengan timeout lebih besar (mengurangi telegram.error.TimedOut).
    request = HTTPXRequest(
        read_timeout=30,
        write_timeout=30,
        connect_timeout=10,
        pool_timeout=10,
    )  # [web:44]

    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=None,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
