from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.request import HTTPXRequest
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

import httpx
import re
import os
import random
import asyncio
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

# Bot tokens
BOT_TOKEN = os.environ.get("BOT_TOKEN")
LOG_BOT_TOKEN = os.environ.get("LOG_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
BOT_NAME = os.environ.get("BOT_NAME", "K12_BOT")

# SheerID URLs
SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

# Email Worker Configuration
CUSTOM_MAIL_API = "https://bot-emails.pilarjalar.workers.dev"
CUSTOM_DOMAIN = "zzzz.biz.id"

# Timeouts
STEP_TIMEOUT = 300  # 5 menit
EMAIL_CHECK_INTERVAL = 10  # 10 detik
EMAIL_CHECK_TIMEOUT = 300  # 5 menit

# Rate limiting
REQUEST_DELAY = 2
MAX_RETRIES = 3
RETRY_BACKOFF = 5

LOG_API_URL = (
    f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
    if LOG_BOT_TOKEN
    else None
)

# States untuk ConversationHandler
NAME, SCHOOL, SHEERID_URL = range(3)

# Storage
user_data = {}
temp_email_storage = {}

# =====================================================
# CUSTOM TEMPMAIL API FUNCTIONS
# =====================================================

async def create_temp_email() -> dict:
    """Generate email dengan custom domain"""
    try:
        username = f"teacher{random.randint(1000, 9999)}{random.randint(100, 999)}"
        email = f"{username}@{CUSTOM_DOMAIN}"
        print(f"✅ Generated custom email: {email}")
        return {
            "success": True,
            "email": email,
            "token": email
        }
    except Exception as e:
        print(f"❌ Error generating email: {e}")
        return {"success": False, "message": str(e)}

async def check_inbox(email: str) -> list:
    """Check inbox via custom worker"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CUSTOM_MAIL_API}/emails/{email}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("emails", [])
            return []
    except Exception as e:
        print(f"❌ Error checking inbox: {e}")
        return []

async def get_message_content(email: str, message_id: str) -> dict:
    """Get full message content"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CUSTOM_MAIL_API}/inbox/{message_id}")
            if resp.status_code == 200:
                return resp.json()
            return {}
    except Exception as e:
        print(f"❌ Error getting message: {e}")
        return {}

async def delete_email_inbox(email: str) -> bool:
    """Delete email inbox after verification done"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"{CUSTOM_MAIL_API}/emails/{email}")
            return resp.status_code == 200
    except Exception as e:
        print(f"❌ Error deleting inbox: {e}")
        return False

# =====================================================
# EMAIL LINK EXTRACTION
# =====================================================

def extract_verification_link(text: str) -> str:
    """Extract complete SheerID verification link from email"""
    patterns = [
        r'(https://services\.sheerid\.com/verify/[^\s\)]+\?[^\s\)]*emailToken=[^\s\)]+)',
        r'(https://services\.sheerid\.com/verify/[^\s\)]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            link = match.group(1)
            link = re.sub(r'[<>"\'\)]$', '', link)
            print(f"🔗 Extracted complete link: {link}")
            return link
    return None

def extract_email_token_only(text: str) -> str:
    """Extract emailToken parameter dari text email"""
    match = re.search(r'emailToken=([A-Za-z0-9]+)', text, re.IGNORECASE)
    if match:
        token = match.group(1)
        print(f"🎫 Extracted emailToken: {token}")
        return token
    match = re.search(r'[?&]token=([A-Za-z0-9]+)', text, re.IGNORECASE)
    if match:
        token = match.group(1)
        print(f"🎫 Extracted token (alternative): {token}")
        return token
    return None

def build_complete_verification_link(original_url: str, verification_id: str, email_token: str) -> str:
    """Build complete verification link dari original URL + emailToken"""
    base_url = original_url.split('?')[0]
    complete_link = f"{base_url}?verificationId={verification_id}&emailToken={email_token}"
    print(f"🔧 Built complete link: {complete_link}")
    return complete_link

# =====================================================
# BROWSER AUTOMATION - REAL CLICK!
# =====================================================

async def click_verification_link_with_browser(verification_url: str) -> dict:
    """
    🎯 BROWSER AUTOMATION: Buka browser Chromium dan klik link seperti manusia!
    """
    browser = None
    try:
        print(f"🌐 Starting browser automation for: {verification_url}")

        async with async_playwright() as p:
            # Launch Chromium browser
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-gpu',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-background-networking',
                ]
            )

            # Create browser context dengan user agent real
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York'
            )

            # Create new page
            page = await context.new_page()

            print(f"🖱️ Browser opened - navigating to verification link...")

            # Navigate ke URL - INI YANG BENAR-BENAR KLIK!
            response = await page.goto(
                verification_url,
                wait_until='networkidle',
                timeout=30000
            )

            print(f"📊 Page loaded - Status: {response.status}")
            print(f"📍 Final URL: {page.url}")

            # Wait untuk JavaScript execution
            await asyncio.sleep(3)

            # Get visible text di page
            try:
                visible_text = await page.inner_text('body')
                visible_text_lower = visible_text.lower()
                print(f"📄 Visible text preview: {visible_text[:300]}")
            except:
                page_content = await page.content()
                visible_text_lower = page_content.lower()
                visible_text = visible_text_lower

            final_url = page.url.lower()

            # DETEKSI STATUS dari page content
            not_approved_indicators = [
                'not approved',
                'we are unable',
                'could not verify',
                'unable to verify',
                'verification failed',
                'try again',
                'error',
                'source error',
                'cannot verify',
                'no match found',
                'could not be verified'
            ]

            success_indicators = [
                'verified successfully',
                'status verified',
                'continue to openai',
                'successfully verified',
                'verification successful',
                'you are verified',
                'approved',
                'congratulations',
                'eligibility confirmed'
            ]

            pending_indicators = [
                'pending review',
                'under review',
                'being reviewed',
                'manual review'
            ]

            document_indicators = [
                'upload document',
                'document required',
                'please upload',
                'provide documentation',
                'add document'
            ]

            # Check URL patterns
            is_error_url = any(x in final_url for x in ['error', 'failed', 'notapproved', 'unable'])
            is_success_url = any(x in final_url for x in ['success', 'verified', 'complete', 'approved'])

            # Check visible text
            has_error = any(indicator in visible_text_lower for indicator in not_approved_indicators)
            has_success = any(indicator in visible_text_lower for indicator in success_indicators)
            has_pending = any(indicator in visible_text_lower for indicator in pending_indicators)
            has_document = any(indicator in visible_text_lower for indicator in document_indicators)

            # Determine final status
            if has_error or is_error_url:
                verification_status = "not_approved"
                is_verified = False
                status_msg = "NOT APPROVED - Data tidak cocok atau ditolak"
            elif has_success or is_success_url:
                verification_status = "approved"
                is_verified = True
                status_msg = "APPROVED - Verifikasi berhasil!"
            elif has_document:
                verification_status = "document_required"
                is_verified = False
                status_msg = "DOCUMENT REQUIRED - Butuh upload dokumen"
            elif has_pending:
                verification_status = "pending_review"
                is_verified = False
                status_msg = "PENDING REVIEW - Sedang direview manual"
            else:
                verification_status = "unknown"
                is_verified = False
                status_msg = "UNKNOWN - Status tidak dapat dideteksi"

            print(f"🎯 Detection Result: {verification_status}")
            print(f"📝 Status Message: {status_msg}")

            await browser.close()

            return {
                "success": True,
                "clicked": True,
                "status_code": response.status,
                "final_url": page.url,
                "verified": is_verified,
                "verification_status": verification_status,
                "status_message": status_msg,
                "response_snippet": visible_text[:800]
            }

    except PlaywrightTimeout:
        if browser:
            await browser.close()
        return {
            "success": False,
            "clicked": False,
            "message": "Browser timeout - page tidak load dalam 30 detik",
            "verification_status": "timeout"
        }
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except:
                pass
        print(f"❌ Browser automation error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "clicked": False,
            "message": f"Browser error: {str(e)}",
            "verification_status": "error"
        }

# =====================================================
# EMAIL MONITORING JOB
# =====================================================

async def monitor_email_job(context: ContextTypes.DEFAULT_TYPE):
    """Monitor inbox dan auto-click verification link dengan REAL BROWSER"""
    job = context.job
    user_id = job.user_id
    chat_id = job.chat_id

    if user_id not in temp_email_storage:
        print(f"⚠️ No email storage for user {user_id}")
        return

    email_data = temp_email_storage[user_id]
    check_count = email_data.get("check_count", 0)
    email_data["check_count"] = check_count + 1

    if check_count >= 30:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⏰ *Email monitoring timeout*\n\n"
                "Tidak ada email verifikasi masuk dalam 5 menit.\n"
                f"📧 Email: `{email_data.get('email')}`\n\n"
                "❌ *Verification FAILED*\n\n"
                "Kemungkinan:\n"
                "• Data tidak valid\n"
                "• SheerID butuh document upload\n"
                "• Email belum dikirim\n\n"
                "Coba lagi dengan /start"
            ),
            parse_mode="Markdown"
        )
        await delete_email_inbox(email_data.get("email"))
        job.schedule_removal()
        temp_email_storage.pop(user_id, None)
        return

    try:
        email = email_data.get("email")
        messages = await check_inbox(email)

        if not messages:
            print(f"📭 No messages yet for {email} (check #{check_count})")
            return

        print(f"📬 Found {len(messages)} messages for {email}")

        for msg in messages:
            msg_from = msg.get("from", "")
            subject = msg.get("subject", "")
            msg_id = msg.get("id")

            print(f"📨 From: {msg_from}, Subject: {subject}")

            if "sheerid" in msg_from.lower() or "verif" in subject.lower():
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "📧 *Email verifikasi diterima!*\n\n"
                        f"From: `{msg_from}`\n"
                        f"Subject: `{subject}`\n\n"
                        "🔄 Mengekstrak verification link..."
                    ),
                    parse_mode="Markdown"
                )

                full_msg = await get_message_content(email, msg_id)
                body_text = full_msg.get("text", "")
                print(f"📄 Email body (first 300 chars): {body_text[:300]}")

                verification_link = extract_verification_link(body_text)

                if not verification_link or "emailToken=" not in verification_link:
                    print("⚠️ Link tidak lengkap, ekstrak emailToken...")
                    email_token = extract_email_token_only(body_text)

                    if email_token:
                        verification_id = email_data.get("verification_id")
                        original_url = email_data.get("original_url")
                        verification_link = build_complete_verification_link(
                            original_url,
                            verification_id,
                            email_token
                        )

                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                "🔧 *Link tidak lengkap di email!*\n\n"
                                f"✅ emailToken ditemukan: `{email_token}`\n"
                                "🔗 Building complete verification link...\n\n"
                                f"`{verification_link[:80]}...`"
                            ),
                            parse_mode="Markdown"
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                "❌ *Gagal ekstrak emailToken*\n\n"
                                "Email dari SheerID tidak mengandung token.\n"
                                f"Body preview:\n`{body_text[:200]}`\n\n"
                                "Coba manual atau /start untuk restart."
                            ),
                            parse_mode="Markdown"
                        )
                        await delete_email_inbox(email)
                        job.schedule_removal()
                        temp_email_storage.pop(user_id, None)
                        return

                if verification_link:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "🔗 *Verification link ready!*\n\n"
                            "🌐 Membuka browser...\n"
                            "🖱️ Bot sedang klik link!\n"
                            "⏳ Tunggu sebentar (30 detik max)..."
                        ),
                        parse_mode="Markdown"
                    )

                    # CLICK DENGAN BROWSER ASLI!
                    click_result = await click_verification_link_with_browser(verification_link)

                    if click_result.get("success") and click_result.get("clicked"):
                        await asyncio.sleep(2)

                        verification_id = email_data.get("verification_id")
                        status_check = await check_sheerid_status(verification_id)
                        sheerid_status = status_check.get("status", "unknown")

                        verification_status = click_result.get("verification_status", "unknown")
                        status_message = click_result.get("status_message", "")

                        # NOTIFIKASI BERDASARKAN STATUS
                        if verification_status == "approved":
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    "✅ *VERIFICATION APPROVED!*\n\n"
                                    "🎉 *Status: SUCCESSFULLY VERIFIED*\n\n"
                                    f"📧 Email: `{email}`\n"
                                    f"🎯 SheerID Status: `{sheerid_status}`\n"
                                    f"📊 HTTP Status: `{click_result.get('status_code')}`\n"
                                    f"✨ Message: {status_message}\n\n"
                                    "🔗 Final URL:\n"
                                    f"`{click_result.get('final_url', 'N/A')[:100]}...`\n\n"
                                    "✨ *Verifikasi teacher berhasil!*\n"
                                    "Sekarang kamu bisa gunakan educator discount."
                                ),
                                parse_mode="Markdown"
                            )

                            await send_log(
                                f"✅ VERIFICATION APPROVED ({BOT_NAME})\n\n"
                                f"User ID: {user_id}\n"
                                f"Email: {email}\n"
                                f"Status: {verification_status}\n"
                                f"SheerID: {sheerid_status}\n"
                                f"Link: {verification_link}"
                            )

                        elif verification_status == "not_approved":
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    "❌ *VERIFICATION NOT APPROVED*\n\n"
                                    "⚠️ *Status: NOT APPROVED / REJECTED*\n\n"
                                    f"📧 Email: `{email}`\n"
                                    f"🎯 SheerID Status: `{sheerid_status}`\n"
                                    f"📊 HTTP Status: `{click_result.get('status_code')}`\n"
                                    f"💬 Message: {status_message}\n\n"
                                    "📋 *Alasan kemungkinan:*\n"
                                    "• Data tidak cocok dengan database SheerID\n"
                                    "• Informasi teacher tidak valid\n"
                                    "• School tidak match\n\n"
                                    "💡 *Saran:*\n"
                                    "• Cek kembali data yang diinput\n"
                                    "• Gunakan data teacher yang valid\n"
                                    "• Coba dengan data berbeda\n\n"
                                    "Ketik /start untuk mencoba lagi."
                                ),
                                parse_mode="Markdown"
                            )

                            await send_log(
                                f"❌ VERIFICATION NOT APPROVED ({BOT_NAME})\n\n"
                                f"User ID: {user_id}\n"
                                f"Email: {email}\n"
                                f"Status: NOT APPROVED\n"
                                f"SheerID: {sheerid_status}"
                            )

                        elif verification_status == "document_required":
                            # AUTO UPLOAD DOKUMEN!
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    "📄 *DOCUMENT UPLOAD REQUIRED!*\n\n"
                                    "🤖 Bot akan upload dokumen secara otomatis...\n"
                                    "⏳ Generating documents..."
                                ),
                                parse_mode="Markdown"
                            )

                            # Get user data untuk generate dokumen
                            full_name = email_data.get("full_name")
                            school_name = email_data.get("school_name")
                            school = email_data.get("school")

                            try:
                                # Generate 3 documents
                                print(f"\n📄 Generating documents for {full_name}...")

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

                                # Convert to bytes
                                pdf_paystub = image_to_bytes(pay_stub).getvalue()
                                png_id = image_to_bytes(id_card).getvalue()
                                pdf_letter = image_to_bytes(letter).getvalue()

                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text="✅ Documents generated! Uploading to SheerID...",
                                    parse_mode="Markdown"
                                )

                                # Upload documents
                                upload_result = await upload_documents_to_sheerid(
                                    verification_id,
                                    pdf_paystub,
                                    png_id,
                                    pdf_letter
                                )

                                if upload_result.get("success"):
                                    # Send documents to user
                                    await context.bot.send_photo(
                                        chat_id=chat_id,
                                        photo=image_to_bytes(id_card),
                                        caption=f"📇 *Faculty ID Card*\n`{faculty_id}`",
                                        parse_mode="Markdown"
                                    )

                                    await context.bot.send_photo(
                                        chat_id=chat_id,
                                        photo=image_to_bytes(pay_stub),
                                        caption="💰 *Payroll Statement*",
                                        parse_mode="Markdown"
                                    )

                                    await context.bot.send_photo(
                                        chat_id=chat_id,
                                        photo=image_to_bytes(letter),
                                        caption="📄 *Employment Verification Letter*",
                                        parse_mode="Markdown"
                                    )

                                    await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=(
                                            "✅ *DOCUMENTS UPLOADED!*\n\n"
                                            "📄 3 dokumen berhasil di-upload ke SheerID\n\n"
                                            "⏳ Status: *PENDING REVIEW*\n"
                                            "SheerID akan review dokumen dalam beberapa saat.\n\n"
                                            "Cek email untuk update status."
                                        ),
                                        parse_mode="Markdown"
                                    )

                                    await send_log(
                                        f"📄 DOCUMENTS UPLOADED ({BOT_NAME})\n\n"
                                        f"User ID: {user_id}\n"
                                        f"Email: {email}\n"
                                        f"School: {school_name}\n"
                                        f"Faculty ID: {faculty_id}"
                                    )
                                else:
                                    await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=(
                                            f"❌ Upload failed: {upload_result.get('message')}\n\n"
                                            "Coba upload manual di browser."
                                        ),
                                        parse_mode="Markdown"
                                    )

                            except Exception as e:
                                print(f"❌ Error generating/uploading documents: {e}")
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"❌ Error: {str(e)}",
                                    parse_mode="Markdown"
                                )

                        elif verification_status == "pending_review":
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    "🔄 *VERIFICATION PENDING REVIEW*\n\n"
                                    "⏳ *Status: UNDER MANUAL REVIEW*\n\n"
                                    f"📧 Email: `{email}`\n"
                                    f"🎯 SheerID Status: `{sheerid_status}`\n\n"
                                    "📋 SheerID sedang melakukan review manual.\n"
                                    "Cek email untuk update status."
                                ),
                                parse_mode="Markdown"
                            )

                        else:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=(
                                    "⚠️ *VERIFICATION STATUS UNCLEAR*\n\n"
                                    "🔄 *Status: UNKNOWN / AMBIGUOUS*\n\n"
                                    f"📧 Email: `{email}`\n"
                                    f"🎯 SheerID Status: `{sheerid_status}`\n"
                                    f"📊 HTTP Status: `{click_result.get('status_code')}`\n\n"
                                    "💡 Akses link ini di browser untuk cek status:\n"
                                    f"`{click_result.get('final_url', 'N/A')}`\n\n"
                                    "Response preview:\n"
                                    f"`{click_result.get('response_snippet', '')[:200]}...`"
                                ),
                                parse_mode="Markdown"
                            )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                "❌ *BROWSER AUTO-CLICK FAILED*\n\n"
                                f"Error: {click_result.get('message', 'Unknown')}\n\n"
                                f"🔗 Link: `{verification_link[:100]}...`\n\n"
                                "Coba klik manual atau /start restart."
                            ),
                            parse_mode="Markdown"
                        )

                    await delete_email_inbox(email)
                    job.schedule_removal()
                    temp_email_storage.pop(user_id, None)
                    return

    except Exception as e:
        print(f"❌ Error in monitor_email_job: {e}")
        import traceback
        traceback.print_exc()

def start_email_monitoring(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    """Start background job to monitor email"""
    if context.job_queue is None:
        print("⚠️ JobQueue is None")
        return

    job_name = f"email_monitor_{user_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_repeating(
        monitor_email_job,
        interval=EMAIL_CHECK_INTERVAL,
        first=EMAIL_CHECK_INTERVAL,
        chat_id=chat_id,
        user_id=user_id,
        name=job_name
    )

    print(f"🔄 Started email monitoring for user {user_id}")

# =====================================================
# HELPER: LOGGING VIA BOT LOGGER
# =====================================================

async def send_log(text: str):
    """Kirim log ke admin lewat BOT logger (LOG_BOT_TOKEN)."""
    if not LOG_BOT_TOKEN or ADMIN_CHAT_ID == 0 or not LOG_API_URL:
        print("⚠️ LOG_BOT_TOKEN atau ADMIN_CHAT_ID belum diset, skip log")
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"chat_id": ADMIN_CHAT_ID, "text": text}
                resp = await client.post(LOG_API_URL, json=payload)
                if resp.status_code == 200:
                    return
        except Exception as e:
            print(f"❌ Log error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

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

    for step in ["URL", "NAME", "SCHOOL"]:
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
    user_data[user_id] = {
        "verification_id": verification_id,
        "original_url": url
    }

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
    set_step_timeout(context, chat_id, user_id, "SCHOOL")

    await update.message.reply_text(
        f"✅ *Name:* {full_name}\n\n"
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
    async with httpx.AsyncClient(timeout=10.0) as client:
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
        keyboard.append([
            InlineKeyboardButton(
                button_text, callback_data=f"sel_{user_id}_{idx}"
            )
        ])

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
    """Cek status verifikasi dari SheerID."""
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
        f"⚙️ *Generating temporary email...*",
        parse_mode="Markdown",
    )

    verification_id = user_data[user_id]["verification_id"]
    first_name = user_data[user_id]["first_name"]
    last_name = user_data[user_id]["last_name"]
    full_name = user_data[user_id]["full_name"]
    original_url = user_data[user_id]["original_url"]

    try:
        # Generate temporary email
        email_result = await create_temp_email()

        if not email_result.get("success"):
            await query.message.reply_text(
                f"❌ *Failed to generate email*\n\n"
                f"Error: {email_result.get('message')}",
                parse_mode="Markdown"
            )
            return

        temp_email = email_result.get("email")

        await query.message.reply_text(
            f"✅ *Temporary email generated!*\n\n"
            f"📧 Email: `{temp_email}`\n\n"
            f"⚙️ *Submitting to SheerID...*",
            parse_mode="Markdown"
        )

        # Submit to SheerID
        result = await submit_sheerid(
            verification_id,
            first_name,
            last_name,
            temp_email,
            school
        )

        if not result["success"]:
            await query.message.reply_text(
                "❌ *SUBMISSION FAILED*\n\n"
                f"Error: {result.get('message')}\n\n"
                "Please try again or contact support.",
                parse_mode="Markdown",
            )
            return

        # Store email data untuk monitoring
        temp_email_storage[user_id] = {
            "email": temp_email,
            "verification_id": verification_id,
            "original_url": original_url,
            "full_name": full_name,
            "school_name": school_name,
            "school": school,
            "check_count": 0
        }

        # Start email monitoring
        start_email_monitoring(context, query.message.chat_id, user_id)

        await query.message.reply_text(
            "✅ *Data submitted to SheerID!*\n\n"
            f"📧 Monitoring email: `{temp_email}`\n"
            "🔄 Waiting for verification email...\n\n"
            "⏰ Bot akan otomatis:
"
            "1️⃣ Detect email dari SheerID
"
            "2️⃣ Klik verification link
"
            "3️⃣ Upload dokumen jika diperlukan

"
            "*Tunggu maksimal 5 menit...*",
            parse_mode="Markdown"
        )

        if user_id in user_data:
            del user_data[user_id]

    except Exception as e:
        print(f"❌ Error in button_callback: {e}")
        import traceback
        traceback.print_exc()
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
) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
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
                msg = f"Step 2 failed: {step2_resp.status_code} - {step2_resp.text[:200]}"
                print("❌", msg)
                return {"success": False, "message": msg}

            print(f"✅ Step 2 (collectTeacherPersonalInfo): {step2_resp.status_code}")

            # Skip SSO
            sso_resp = await client.delete(
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/sso"
            )
            print(f"✅ Step 3 skip SSO: {sso_resp.status_code}")

            return {"success": True, "message": "Data submitted, waiting for email"}

        except httpx.TimeoutException:
            msg = "Request timeout to SheerID - please try again"
            print("❌", msg)
            return {"success": False, "message": msg}
        except Exception as e:
            msg = f"Submission error: {str(e)}"
            print("❌", msg)
            return {"success": False, "message": msg}

# =====================================================
# DOCUMENT UPLOAD TO SHEERID
# =====================================================

async def upload_documents_to_sheerid(
    verification_id: str,
    pdf_paystub: bytes,
    png_id: bytes,
    pdf_letter: bytes
) -> dict:
    """Upload 3 documents to SheerID"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n📤 Uploading documents to SheerID... ID: {verification_id}")

            # Step 1: Request upload URLs
            step4_url = (
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/docUpload"
            )

            step4_body = {
                "files": [
                    {
                        "fileName": "paystub.pdf",
                        "mimeType": "application/pdf",
                        "fileSize": len(pdf_paystub),
                    },
                    {
                        "fileName": "faculty_id.png",
                        "mimeType": "image/png",
                        "fileSize": len(png_id),
                    },
                    {
                        "fileName": "employment_letter.pdf",
                        "mimeType": "application/pdf",
                        "fileSize": len(pdf_letter),
                    }
                ]
            }

            step4_resp = await client.post(step4_url, json=step4_body)

            if step4_resp.status_code != 200:
                msg = f"Step 4 failed: {step4_resp.status_code}"
                print("❌", msg)
                return {"success": False, "message": msg}

            docs = step4_resp.json().get("documents", [])

            if len(docs) < 3:
                msg = f"Not enough upload URLs received (got {len(docs)}, need 3)"
                print("❌", msg)
                return {"success": False, "message": msg}

            # Step 2: Upload files
            paystub_url = docs[0]["uploadUrl"]
            id_url = docs[1]["uploadUrl"]
            letter_url = docs[2]["uploadUrl"]

            # Upload paystub PDF
            up_paystub = await client.put(
                paystub_url, 
                content=pdf_paystub, 
                headers={"Content-Type": "application/pdf"}
            )
            print(f"  ✓ Paystub upload: {up_paystub.status_code}")

            # Upload faculty ID PNG
            up_id = await client.put(
                id_url, 
                content=png_id, 
                headers={"Content-Type": "image/png"}
            )
            print(f"  ✓ Faculty ID upload: {up_id.status_code}")

            # Upload employment letter PDF
            up_letter = await client.put(
                letter_url, 
                content=pdf_letter, 
                headers={"Content-Type": "application/pdf"}
            )
            print(f"  ✓ Employment Letter upload: {up_letter.status_code}")

            # Step 3: Complete upload
            complete_resp = await client.post(
                f"{SHEERID_BASE_URL}/rest/v2/verification/"
                f"{verification_id}/step/completeDocUpload"
            )
            print(f"✅ Complete upload: {complete_resp.status_code}")

            return {
                "success": True, 
                "message": "3 documents uploaded successfully"
            }

        except httpx.TimeoutException:
            msg = "Upload timeout - please try again"
            print("❌", msg)
            return {"success": False, "message": msg}
        except Exception as e:
            msg = f"Upload error: {str(e)}"
            print("❌", msg)
            import traceback
            traceback.print_exc()
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
    print(f"🎓 {BOT_NAME} - Email Worker Edition")
    print("=" * 70)
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"👮 Admin Chat ID: {ADMIN_CHAT_ID}")
    print(f"📨 LOG_BOT_TOKEN set: {bool(LOG_BOT_TOKEN)}")
    print(f"📧 Email Worker: {CUSTOM_MAIL_API}")
    print(f"🌐 Domain: {CUSTOM_DOMAIN}")
    print(f"⏰ Step timeout: {STEP_TIMEOUT} detik")
    print("=" * 70 + "\n")

    # Request Telegram dengan timeout lebih besar
    request = HTTPXRequest(
        read_timeout=30,
        write_timeout=30,
        connect_timeout=10,
        pool_timeout=10,
    )

    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        conversation_timeout=None,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Bot is starting with Email Worker automation...")
    print("✨ Features:")
    print("  • Auto-generate temporary email")
    print("  • Email monitoring & detection")
    print("  • Browser automation for link clicking")
    print("  • Auto document upload (3 files)")
    print("  • Status detection (approved/rejected/pending)")
    print()

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
