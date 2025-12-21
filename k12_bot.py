from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
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
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', '0'))
SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

# States untuk ConversationHandler
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)
STEP_TIMEOUT = 300  # 5 menit per step

# Storage untuk data user
user_data = {}

# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def log_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim log ke admin ketika user pertama kali pakai /start."""
    if ADMIN_CHAT_ID == 0:
        return

    user = update.effective_user
    chat = update.effective_chat

    user_id = user.id
    username = user.username or '-'
    full_name = user.full_name

    text = (
        "📥 *NEW USER STARTED BOT*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"🧾 Name: {full_name}\n"
        f"🏷 Username: @{username}\n"
        f"💬 Chat ID: `{chat.id}`\n"
        f"📅 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode='Markdown'
        )
        print(f"✅ Log dikirim ke admin untuk user {user_id}")
    except Exception as e:
        print(f"❌ Failed to send log to admin: {e}")

async def log_verification_result(admin_chat_id: int, user_id: int, full_name: str, 
                                school_name: str, email: str, faculty_id: str, 
                                success: bool, error_msg: str = ""):
    """Kirim log hasil verifikasi ke admin."""
    if admin_chat_id == 0:
        return

    status_emoji = "✅" if success else "❌"
    status_text = "SUCCESS" if success else "FAILED"

    text = (
        f"{status_emoji} *VERIFICATION {status_text.upper()}*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"👤 Name: {full_name}\n"
        f"🏫 School: {school_name}\n"
        f"📧 Email: `{email}`\n"
        f"🆔 Faculty ID: `{faculty_id}`\n"
    )
    
    if not success:
        text += f"\n❌ Error: {error_msg}"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode='Markdown'
        )
        print(f"✅ Log hasil verifikasi dikirim ke admin")
    except Exception as e:
        print(f"❌ Failed to send verification log: {e}")

async def step_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    """Dipanggil jika user tidak merespon step tertentu dalam 5 menit."""
    job = context.job
    chat_id = job.chat_id
    user_id = job.user_id
    step_name = job.data.get('step', 'UNKNOWN')

    # Bersihkan data user
    if user_id in user_data:
        del user_data[user_id]

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏰ *Timeout di step {step_name}*\n\n"
            "Kamu tidak merespon dalam 5 menit.\n"
            "Silakan ketik /start untuk mengulang proses dari awal."
        ),
        parse_mode='Markdown'
    )
    print(f"⏰ Timeout {step_name} untuk user {user_id}")

def set_step_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, step: str):
    """Set timeout 5 menit untuk step tertentu."""
    job_name = f"timeout_{step}_{user_id}"
    
    # Hapus job lama
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    context.job_queue.run_once(
        step_timeout_job,
        when=STEP_TIMEOUT,
        chat_id=chat_id,
        user_id=user_id,
        name=job_name,
        data={'step': step},
    )

def clear_all_timeouts(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Hapus semua job timeout milik user ini."""
    for step in ['URL', 'NAME', 'EMAIL', 'SCHOOL']:
        job_name = f"timeout_{step}_{user_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()

# =====================================================
# CONVERSATION HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Log ke admin
    await log_user_start(update, context)

    # Bersihkan data & timeout lama
    if user_id in user_data:
        del user_data[user_id]
    clear_all_timeouts(context, user_id)

    # Set timeout untuk step URL
    set_step_timeout(context, chat_id, user_id, 'URL')

    await update.message.reply_text(
        "🎓 *K12 Teacher Verification Bot*\n\n"
        "Send your SheerID verification URL:\n\n"
        "`https://services.sheerid.com/verify/.../verificationId=...`\n\n"
        "Example:\n"
        "`https://services.sheerid.com/verify/68d47554...`\n\n"
        "*⏰ Kamu punya 5 menit untuk kirim link*",
        parse_mode='Markdown'
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima URL SheerID"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    match = re.search(r'verificationId=([a-f0-9]{24})', url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ *Invalid URL!*\n\n"
            "Please send a valid SheerID verification URL.\n"
            "Format: `verificationId=...`\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode='Markdown'
        )
        set_step_timeout(context, chat_id, user_id, 'URL')
        return SHEERID_URL

    verification_id = match.group(1)
    user_data[user_id] = {'verification_id': verification_id}

    # Hapus timeout URL, set timeout NAME
    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, 'NAME')

    await update.message.reply_text(
        f"✅ *Verification ID:* `{verification_id}`\n\n"
        "What's your *full name*?\n"
        "Example: Elizabeth Bradly\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode='Markdown'
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima nama lengkap"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    full_name = update.message.text.strip()

    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Please provide *first name AND last name*\n"
            "Example: John Smith\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode='Markdown'
        )
        set_step_timeout(context, chat_id, user_id, 'NAME')
        return NAME

    user_data.setdefault(user_id, {})
    user_data[user_id]['first_name'] = parts[0]
    user_data[user_id]['last_name'] = ' '.join(parts[1:])
    user_data[user_id]['full_name'] = full_name

    # Pindah ke EMAIL
    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, 'EMAIL')

    await update.message.reply_text(
        f"✅ *Name:* {full_name}\n\n"
        "What's your *school email address*?\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode='Markdown'
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima email"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    email = update.message.text.strip()

    if '@' not in email or '.' not in email:
        await update.message.reply_text(
            "❌ Invalid email format!\n"
            "Please provide a valid school email address.\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode='Markdown'
        )
        set_step_timeout(context, chat_id, user_id, 'EMAIL')
        return EMAIL

    user_data.setdefault(user_id, {})
    user_data[user_id]['email'] = email

    # Pindah ke SCHOOL
    clear_all_timeouts(context, user_id)
    set_step_timeout(context, chat_id, user_id, 'SCHOOL')

    await update.message.reply_text(
        f"✅ *Email:* `{email}`\n\n"
        "What's your *school name*?\n"
        "Example: The Clinton School\n\n"
        "*⏰ Kamu punya 5 menit*",
        parse_mode='Markdown'
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima nama sekolah dan melakukan pencarian"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    school_name = update.message.text.strip()
    user_data.setdefault(user_id, {})
    user_data[user_id]['school_name'] = school_name

    # Perpanjang timeout SCHOOL
    set_step_timeout(context, chat_id, user_id, 'SCHOOL')

    msg = await update.message.reply_text(
        f"⚙️ Searching for schools matching: *{school_name}*\n"
        "Please wait...",
        parse_mode='Markdown'
    )

    schools = await search_schools(school_name)

    if not schools:
        await msg.edit_text(
            "❌ *No schools found!*\n\n"
            "Try a different school name:\n\n"
            "*⏰ Kamu punya 5 menit lagi*",
            parse_mode='Markdown'
        )
        return SCHOOL

    await msg.delete()
    await display_schools(update, schools, user_id)
    
    # Hapus timeout SCHOOL setelah tampil list
    clear_all_timeouts(context, user_id)
    
    return ConversationHandler.END

# =====================================================
# SCHOOL SEARCH FUNCTIONS
# =====================================================

async def search_schools(query: str) -> list:
    """Search schools menggunakan SheerID Organization Search API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        all_schools = []

        for school_type in ['K12', 'HIGH_SCHOOL']:
            try:
                params = {
                    'country': 'US',
                    'type': school_type,
                    'name': query
                }

                print(f"\n📡 Searching {school_type} schools...")
                print(f"Query: {query}")

                response = await client.get(ORGSEARCH_URL, params=params)

                if response.status_code != 200:
                    print(f"❌ API error for {school_type}: {response.status_code}")
                    continue

                data = response.json()

                if not isinstance(data, list):
                    print(f"❌ API return bukan list untuk {school_type}")
                    continue

                print(f"✅ {school_type}: Found {len(data)} schools")
                all_schools.extend(data)

            except Exception as e:
                print(f"❌ Error searching {school_type}: {e}")
                continue

        # Remove duplicates berdasarkan ID
        seen_ids = set()
        unique_schools = []
        for school in all_schools:
            school_id = school.get('id')
            if school_id and school_id not in seen_ids:
                seen_ids.add(school_id)
                unique_schools.append(school)

        print(f"\n📊 Total unique schools: {len(unique_schools)}")
        return unique_schools[:20]

async def display_schools(update, schools, user_id):
    """Display hasil pencarian sekolah dengan inline keyboard"""
    text = "🏫 *SCHOOL SEARCH RESULTS*\n\n"
    text += f"Query: `{user_data[user_id]['school_name']}`\n"
    text += f"Found: *{len(schools)}* schools\n\n"

    keyboard = []

    for idx, school in enumerate(schools):
        user_data[user_id][f'school_{idx}'] = school

        name = school.get('name', 'Unknown')
        city = school.get('city', '')
        state = school.get('state', '')
        school_type = school.get('type', 'SCHOOL')

        location = f"{city}, {state}" if city and state else state or 'US'

        text += f"{idx+1}. *{name}*\n"
        text += f"   📍 {location}\n"
        text += f"   └─ Type: `{school_type}`\n\n"

        button_text = f"{idx+1}. {name[:40]}{'...' if len(name) > 40 else ''}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"sel_{user_id}_{idx}"
            )
        ])

    text += "\n👆 *Click button to select school*"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# =====================================================
# BUTTON CALLBACK HANDLER
# =====================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle school selection dari inline button"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    user_id = int(parts[1])
    school_idx = int(parts[2])

    if user_id not in user_data:
        await query.edit_message_text(
            "❌ *Session expired*\n\n"
            "Please /start again",
            parse_mode='Markdown'
        )
        return

    school = user_data[user_id][f'school_{school_idx}']
    school_name = school.get('name')
    school_type = school.get('type', 'K12')
    school_id = school.get('id')

    await query.edit_message_text(
        f"✅ *Selected School:*\n"
        f"Name: {school_name}\n"
        f"Type: `{school_type}`\n"
        f"ID: `{school_id}`\n\n"
        f"⚙️ *Generating documents...*",
        parse_mode='Markdown'
    )

    verification_id = user_data[user_id]['verification_id']
    first_name = user_data[user_id]['first_name']
    last_name = user_data[user_id]['last_name']
    full_name = user_data[user_id]['full_name']
    email = user_data[user_id]['email']

    try:
        print(f"\n📄 Generating documents for {full_name}...")

        id_card, faculty_id = generate_faculty_id(full_name, email, school_name)
        pay_stub = generate_pay_stub(full_name, email, school_name, faculty_id)
        letter = generate_employment_letter(full_name, email, school_name)

        print(f"✅ Documents generated successfully")
        print(f"Faculty ID: {faculty_id}")

        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()

        await query.edit_message_text(
            f"✅ *Documents generated*\n\n"
            f"⚙️ *Submitting to SheerID...*",
            parse_mode='Markdown'
        )

        result = await submit_sheerid(
            verification_id, first_name, last_name, email, school,
            pdf_bytes, png_bytes
        )

        # Log hasil ke admin
        await log_verification_result(
            ADMIN_CHAT_ID, user_id, full_name, school_name, email, 
            faculty_id, result['success'], result.get('message', '')
        )

        if result['success']:
            await query.message.reply_photo(
                photo=image_to_bytes(id_card),
                caption=f"📇 *Faculty ID Card*\n`{faculty_id}`",
                parse_mode='Markdown'
            )

            await query.message.reply_photo(
                photo=image_to_bytes(pay_stub),
                caption="💰 *Payroll Statement*",
                parse_mode='Markdown'
            )

            await query.message.reply_photo(
                photo=image_to_bytes(letter),
                caption="📄 *Employment Verification Letter*",
                parse_mode='Markdown'
            )

            await query.message.reply_text(
                f"✅ *UPLOAD DOC SUCCESS!*\n\n"
                f"👤 *Name:* {full_name}\n"
                f"🏫 *School:* {school_name}\n"
                f"📧 *Email:* `{email}`\n"
                f"🆔 *Faculty ID:* `{faculty_id}`\n\n"
                f"🔗 *Status:* UNDER REVIEW\n\n"
                f"Type /start for another verification",
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text(
                f"❌ *VERIFICATION FAILED*\n\n"
                f"Error: {result.get('message')}\n\n"
                f"Please try again or contact support.",
                parse_mode='Markdown'
            )

        # Bersihkan data user setelah selesai
        del user_data[user_id]

    except Exception as e:
        print(f"❌ Error in button_callback: {e}")
        await query.message.reply_text(
            f"❌ *Error occurred:*\n`{str(e)}`",
            parse_mode='Markdown'
        )

# =====================================================
# SHEERID SUBMISSION (TIDAK DIUBAH)
# =====================================================

async def submit_sheerid(
    verification_id: str,
    first_name: str,
    last_name: str,
    email: str,
    school: dict,
    pdf_data: bytes,
    png_data: bytes
) -> dict:
    """Submit verification ke SheerID API - IDENTIK dengan aslinya"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n🚀 Starting SheerID submission...")
            print(f"Verification ID: {verification_id}")

            age = random.randint(25, 60)
            birth_date = (datetime.now() - timedelta(days=age*365)).strftime('%Y-%m-%d')
            device_fp = ''.join(random.choice('0123456789abcdef') for _ in range(32))

            # STEP 2: Submit Personal Info
            step2_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/collectTeacherPersonalInfo"
            step2_body = {
                'firstName': first_name,
                'lastName': last_name,
                'birthDate': birth_date,
                'email': email,
                'organization': {
                    'id': int(school['id']),
                    'name': school['name']
                },
                'deviceFingerprintHash': device_fp,
                'locale': 'en-US'
            }

            print(f"\n📝 Step 2: Submitting personal info...")
            step2_resp = await client.post(step2_url, json=step2_body)

            if step2_resp.status_code != 200:
                error_msg = f'Step 2 failed: {step2_resp.status_code}'
                print(f"❌ {error_msg}")
                print(f"Response: {step2_resp.text[:300]}")
                return {'success': False, 'message': error_msg}

            print(f"✅ Step 2 success: Personal info submitted")

            # STEP 3: Skip SSO
            print(f"\n🔄 Step 3: Skipping SSO...")
            sso_resp = await client.delete(
                f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/sso"
            )
            print(f"✅ Step 3 success: SSO skipped ({sso_resp.status_code})")

            # STEP 4: Request Upload URLs
            step4_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/docUpload"
            step4_body = {
                'files': [
                    {
                        'fileName': 'paystub.pdf',
                        'mimeType': 'application/pdf',
                        'fileSize': len(pdf_data)
                    },
                    {
                        'fileName': 'faculty_id.png',
                        'mimeType': 'image/png',
                        'fileSize': len(png_data)
                    }
                ]
            }

            print(f"\n📤 Step 4: Requesting upload URLs...")
            step4_resp = await client.post(step4_url, json=step4_body)

            if step4_resp.status_code != 200:
                error_msg = f'Step 4 failed: {step4_resp.status_code}'
                print(f"❌ {error_msg}")
                return {'success': False, 'message': error_msg}

            step4_data = step4_resp.json()
            documents = step4_data.get('documents', [])

            if len(documents) < 2:
                error_msg = 'No upload URLs received from SheerID'
                print(f"❌ {error_msg}")
                return {'success': False, 'message': error_msg}

            print(f"✅ Step 4 success: Received {len(documents)} upload URLs")

            # STEP 5: Upload Documents to S3
            print(f"\n☁️ Step 5: Uploading documents to S3...")

            pdf_url = documents[0]['uploadUrl']
            pdf_upload = await client.put(
                pdf_url,
                content=pdf_data,
                headers={'Content-Type': 'application/pdf'}
            )
            print(f"  ✓ PDF uploaded: {pdf_upload.status_code}")

            png_url = documents[1]['uploadUrl']
            png_upload = await client.put(
                png_url,
                content=png_data,
                headers={'Content-Type': 'image/png'}
            )
            print(f"  ✓ PNG uploaded: {png_upload.status_code}")

            # STEP 6: Complete Upload
            print(f"\n✔️ Step 6: Completing upload...")
            complete_resp = await client.post(
                f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/completeDocUpload"
            )
            print(f"✅ Upload completed: {complete_resp.status_code}")

            print(f"\n🎉 Verification submitted successfully!")
            return {'success': True, 'message': 'Submitted successfully'}

        except httpx.TimeoutException:
            error_msg = 'Request timeout - please try again'
            print(f"❌ {error_msg}")
            return {'success': False, 'message': error_msg}

        except Exception as e:
            error_msg = f'Submission error: {str(e)}'
            print(f"❌ {error_msg}")
            return {'success': False, 'message': str(e)}

# =====================================================
# CANCEL HANDLER
# =====================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /cancel command"""
    user_id = update.effective_user.id

    if user_id in user_data:
        del user_data[user_id]

    clear_all_timeouts(context, user_id)

    await update.message.reply_text(
        "❌ *Operation cancelled*\n\n"
        "Type /start to begin again",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# =====================================================
# MAIN FUNCTION
# =====================================================

def main():
    """Main function untuk menjalankan bot"""

    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not set!")
        print("Set it with: export BOT_TOKEN='your_bot_token'")
        return

    print("\n" + "="*70)
    print("🎓 K12 TEACHER VERIFICATION BOT - FULL FEATURES")
    print("="*70)
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"📡 Admin Chat ID: {ADMIN_CHAT_ID}")
    print(f"🌐 SheerID URL: {SHEERID_BASE_URL}")
    print(f"🔍 Org Search URL: {ORGSEARCH_URL}")
    print(f"⏰ Timeout per step: {STEP_TIMEOUT}s")
    print("="*70 + "\n")

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=None,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Bot is starting...")
    print("✅ Bot is running! Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
