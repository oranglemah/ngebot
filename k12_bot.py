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
SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

# States untuk ConversationHandler
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)

# Storage untuk data user
user_data = {}

# =====================================================
# CONVERSATION HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    await update.message.reply_text(
        "🎓 *K12 Teacher Verification Bot*\n\n"
        "Send your SheerID verification URL:\n\n"
        "`https://services.sheerid.com/verify/.../verificationId=...`\n\n"
        "Example:\n"
        "`https://services.sheerid.com/verify/68d47554...`",
        parse_mode='Markdown'
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima URL SheerID"""
    user_id = update.effective_user.id
    url = update.message.text.strip()

    # Extract verification ID dari URL
    match = re.search(r'verificationId=([a-f0-9]{24})', url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ *Invalid URL!*\n\n"
            "Please send a valid SheerID verification URL.\n"
            "Format: `verificationId=...`",
            parse_mode='Markdown'
        )
        return SHEERID_URL

    verification_id = match.group(1)
    user_data[user_id] = {'verification_id': verification_id}

    await update.message.reply_text(
        f"✅ *Verification ID:* `{verification_id}`\n\n"
        "What's your *full name*?\n"
        "Example: Elizabeth Bradly",
        parse_mode='Markdown'
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima nama lengkap"""
    user_id = update.effective_user.id
    full_name = update.message.text.strip()

    # Validasi nama (minimal 2 kata)
    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Please provide *first name AND last name*\n"
            "Example: John Smith",
            parse_mode='Markdown'
        )
        return NAME

    # Simpan data nama
    user_data[user_id]['first_name'] = parts[0]
    user_data[user_id]['last_name'] = ' '.join(parts[1:])
    user_data[user_id]['full_name'] = full_name

    await update.message.reply_text(
        f"✅ *Name:* {full_name}\n\n"
        "What's your *school email address*?",
        parse_mode='Markdown'
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima email"""
    user_id = update.effective_user.id
    email = update.message.text.strip()

    # Validasi format email sederhana
    if '@' not in email or '.' not in email:
        await update.message.reply_text(
            "❌ Invalid email format!\n"
            "Please provide a valid school email address.",
            parse_mode='Markdown'
        )
        return EMAIL

    user_data[user_id]['email'] = email

    await update.message.reply_text(
        f"✅ *Email:* `{email}`\n\n"
        "What's your *school name*?\n"
        "Example: The Clinton School",
        parse_mode='Markdown'
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk menerima nama sekolah dan melakukan pencarian"""
    user_id = update.effective_user.id
    school_name = update.message.text.strip()
    user_data[user_id]['school_name'] = school_name

    # Kirim status searching
    msg = await update.message.reply_text(
        f"⚙️ Searching for schools matching: *{school_name}*\n"
        "Please wait...",
        parse_mode='Markdown'
    )

    # Search schools
    schools = await search_schools(school_name)

    if not schools:
        await msg.edit_text(
            "❌ *No schools found!*\n\n"
            "Try a different school name:",
            parse_mode='Markdown'
        )
        return SCHOOL

    # Delete searching message
    await msg.delete()

    # Display hasil pencarian
    await display_schools(update, schools, user_id)
    return ConversationHandler.END

# =====================================================
# SCHOOL SEARCH FUNCTIONS
# =====================================================

async def search_schools(query: str) -> list:
    """
    Search schools menggunakan SheerID Organization Search API
    Mencari K12 dan HIGH_SCHOOL schools
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        all_schools = []

        # Search untuk setiap tipe sekolah
        for school_type in ['K12', 'HIGH_SCHOOL']:
            try:
                # Parameter API yang BENAR
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
                    print(f"Response: {response.text[:200]}")
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

                # Print detail sekolah
                name = school.get('name', 'Unknown')
                s_type = school.get('type', 'N/A')
                city = school.get('city', 'N/A')
                state = school.get('state', 'N/A')
                print(f"  ✓ {name} ({s_type}) - {city}, {state}")

        print(f"\n📊 Total unique schools: {len(unique_schools)}")
        return unique_schools[:20]  # Maksimal 20 hasil

async def display_schools(update, schools, user_id):
    """Display hasil pencarian sekolah dengan inline keyboard"""

    text = "🏫 *SCHOOL SEARCH RESULTS*\n\n"
    text += f"Query: `{user_data[user_id]['school_name']}`\n"
    text += f"Found: *{len(schools)}* schools\n\n"

    keyboard = []

    for idx, school in enumerate(schools):
        # Simpan data sekolah ke user_data
        user_data[user_id][f'school_{idx}'] = school

        # Extract school info
        name = school.get('name', 'Unknown')
        city = school.get('city', '')
        state = school.get('state', '')
        school_type = school.get('type', 'SCHOOL')

        # Format lokasi
        location = f"{city}, {state}" if city and state else state or 'US'

        # Tambahkan ke text display
        text += f"{idx+1}. *{name}*\n"
        text += f"   📍 {location}\n"
        text += f"   └─ Type: `{school_type}`\n\n"

        # Buat inline button
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

    # Parse callback data
    parts = query.data.split('_')
    user_id = int(parts[1])
    school_idx = int(parts[2])

    # Validasi session
    if user_id not in user_data:
        await query.edit_message_text(
            "❌ *Session expired*\n\n"
            "Please /start again",
            parse_mode='Markdown'
        )
        return

    # Get selected school
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

    # Get user data
    verification_id = user_data[user_id]['verification_id']
    first_name = user_data[user_id]['first_name']
    last_name = user_data[user_id]['last_name']
    full_name = user_data[user_id]['full_name']
    email = user_data[user_id]['email']

    try:
        # Generate dokumen-dokumen
        print(f"\n📄 Generating documents for {full_name}...")

        id_card, faculty_id = generate_faculty_id(full_name, email, school_name)
        pay_stub = generate_pay_stub(full_name, email, school_name, faculty_id)
        letter = generate_employment_letter(full_name, email, school_name)

        print(f"✅ Documents generated successfully")
        print(f"Faculty ID: {faculty_id}")

        # Convert ke bytes untuk upload
        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()

        # Update status
        await query.edit_message_text(
            f"✅ *Documents generated*\n\n"
            f"⚙️ *Submitting to SheerID...*",
            parse_mode='Markdown'
        )

        # Submit ke SheerID
        result = await submit_sheerid(
            verification_id, first_name, last_name, email, school,
            pdf_bytes, png_bytes
        )

        if result['success']:
            # Kirim dokumen-dokumen
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

            # Send success message
            await query.message.reply_text(
                f"✅ *VERIFICATION SUCCESS!*\n\n"
                f"👤 *Name:* {full_name}\n"
                f"🏫 *School:* {school_name}\n"
                f"📧 *Email:* `{email}`\n"
                f"🆔 *Faculty ID:* `{faculty_id}`\n\n"
                f"🔗 *Status:* SUCCESS\n\n"
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

    except Exception as e:
        print(f"❌ Error in button_callback: {e}")
        await query.message.reply_text(
            f"❌ *Error occurred:*\n`{str(e)}`",
            parse_mode='Markdown'
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
    png_data: bytes
) -> dict:
    """
    Submit verification ke SheerID API
    Multi-step process:
    1. Submit personal info
    2. Skip SSO
    3. Request upload URLs
    4. Upload documents to S3
    5. Complete upload
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n🚀 Starting SheerID submission...")
            print(f"Verification ID: {verification_id}")

            # Generate data tambahan
            age = random.randint(25, 60)
            birth_date = (datetime.now() - timedelta(days=age*365)).strftime('%Y-%m-%d')
            device_fp = ''.join(random.choice('0123456789abcdef') for _ in range(32))

            # =========================================
            # STEP 2: Submit Personal Info
            # =========================================
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

            # =========================================
            # STEP 3: Skip SSO
            # =========================================
            print(f"\n🔄 Step 3: Skipping SSO...")
            sso_resp = await client.delete(
                f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/sso"
            )
            print(f"✅ Step 3 success: SSO skipped ({sso_resp.status_code})")

            # =========================================
            # STEP 4: Request Upload URLs
            # =========================================
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

            # =========================================
            # STEP 5: Upload Documents to S3
            # =========================================
            print(f"\n☁️ Step 5: Uploading documents to S3...")

            # Upload PDF
            pdf_url = documents[0]['uploadUrl']
            pdf_upload = await client.put(
                pdf_url,
                content=pdf_data,
                headers={'Content-Type': 'application/pdf'}
            )
            print(f"  ✓ PDF uploaded: {pdf_upload.status_code}")

            # Upload PNG
            png_url = documents[1]['uploadUrl']
            png_upload = await client.put(
                png_url,
                content=png_data,
                headers={'Content-Type': 'image/png'}
            )
            print(f"  ✓ PNG uploaded: {png_upload.status_code}")

            # =========================================
            # STEP 6: Complete Upload
            # =========================================
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

    # Clear user data
    if user_id in user_data:
        del user_data[user_id]

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

    # Validasi BOT_TOKEN
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not set!")
        print("Set it with: export BOT_TOKEN='your_bot_token'")
        return

    print("\n" + "="*60)
    print("🎓 K12 TEACHER VERIFICATION BOT")
    print("="*60)
    print(f"Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"SheerID URL: {SHEERID_BASE_URL}")
    print(f"Org Search URL: {ORGSEARCH_URL}")
    print("="*60 + "\n")

    # Build application
    app = Application.builder().token(BOT_TOKEN).build()

    # Setup Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))

    # Start bot
    print("🚀 Bot is starting...")
    print("✅ Bot is running! Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)

# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == '__main__':
    main()
