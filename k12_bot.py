from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import requests
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

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# SheerID Config
SHEERID_BASE_URL = "https://services.sheerid.com"

# States
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "Send me your SheerID verification URL.\n\n"
        "Example:\n"
        "https://services.sheerid.com/verify/.../verificationId=6940ec50aa44934ace09dc3d"
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    # Parse verification ID
    match = re.search(r'verificationId=([a-f0-9]{24})', url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ Invalid URL!\n\n"
            "Must contain: verificationId=...\n\n"
            "Send URL again:"
        )
        return SHEERID_URL
    
    verification_id = match.group(1)
    user_data[user_id] = {'verification_id': verification_id}
    
    await update.message.reply_text(
        f"✅ Verification ID: {verification_id}\n\n"
        "What's your full name?\n(Example: Allison Holtman)"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    
    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Need first AND last name\n\nExample: Allison Holtman"
        )
        return NAME
    
    user_data[user_id]['first_name'] = parts[0]
    user_data[user_id]['last_name'] = ' '.join(parts[1:])
    user_data[user_id]['full_name'] = full_name
    
    await update.message.reply_text(
        f"✅ Name: {full_name}\n\nWhat's your school email?"
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]['email'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Email: {user_data[user_id]['email']}\n\nWhat's your school name?"
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    school_name = update.message.text.strip()
    user_data[user_id]['school_name'] = school_name
    
    msg = await update.message.reply_text("🔍 Searching US schools...")
    
    schools = await search_schools(school_name)
    
    if not schools:
        await msg.edit_text("❌ No US schools found!\n\nTry different name:")
        return SCHOOL
    
    await msg.delete()
    await display_schools(update, schools, user_id)
    return ConversationHandler.END

async def search_schools(school_name):
    """Search K12/HIGH_SCHOOL in US only"""
    url = "https://orgsearch.sheerid.net/rest/organization/search"
    params = {'query': school_name}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return []
        
        schools = response.json()
        if not isinstance(schools, list):
            return []
        
        # Filter: US only + K12/HIGH_SCHOOL only
        filtered = []
        for school in schools:
            country = school.get('country', '')
            school_type = school.get('type', '')
            
            if country == 'US' and school_type in ['K12', 'HIGH_SCHOOL']:
                filtered.append(school)
        
        return filtered
    except:
        return []

async def display_schools(update, schools, user_id):
    """Display US K12/HIGH_SCHOOL schools"""
    text = f"🇺🇸 FOUND {len(schools)} US SCHOOLS\n\n"
    keyboard = []
    
    for idx, school in enumerate(schools[:15]):
        user_data[user_id][f'school_{idx}'] = school
        
        name = school.get('name', 'Unknown')
        city = school.get('city', '')
        state = school.get('state', '')
        school_type = school.get('type', 'K12')
        
        location = f"{city}, {state}" if city and state else state or 'US'
        
        text += f"{idx+1}. {name}\n"
        text += f"   📍 {location}\n"
        text += f"   🏷️ Type: {school_type}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {name[:45]}",
                callback_data=f"sel_{user_id}_{idx}"
            )
        ])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    user_id = int(parts[1])
    school_idx = int(parts[2])
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Session expired. /start again")
        return
    
    school = user_data[user_id][f'school_{school_idx}']
    
    await query.edit_message_text(
        f"✅ Selected: {school.get('name')}\n\n"
        f"⚙️ Step 1/4: Generating documents..."
    )
    
    # Get data
    verification_id = user_data[user_id]['verification_id']
    first_name = user_data[user_id]['first_name']
    last_name = user_data[user_id]['last_name']
    full_name = user_data[user_id]['full_name']
    email = user_data[user_id]['email']
    school_name = school.get('name')
    
    try:
        # Generate documents
        id_card, faculty_id = generate_faculty_id(full_name, email, school_name)
        pay_stub = generate_pay_stub(full_name, email, school_name, faculty_id)
        letter = generate_employment_letter(full_name, email, school_name)
        
        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()
        
        await query.message.reply_text("⚙️ Step 2/4: Submitting to SheerID...")
        
        # Submit to SheerID
        result = await submit_to_sheerid(
            verification_id, first_name, last_name, email, school,
            pdf_bytes, png_bytes
        )
        
        if result['success']:
            # Send documents
            await query.message.reply_photo(
                photo=image_to_bytes(id_card),
                caption=f"📇 Faculty ID\n{faculty_id}"
            )
            await query.message.reply_photo(
                photo=image_to_bytes(pay_stub),
                caption="💰 Pay Stub"
            )
            await query.message.reply_photo(
                photo=image_to_bytes(letter),
                caption="📄 Employment Letter"
            )
            
            await query.message.reply_text(
                f"✅ SUCCESS!\n\n"
                f"👤 {full_name}\n"
                f"🏫 {school_name}\n"
                f"📧 {email}\n\n"
                f"🔗 Status: {result.get('message')}\n\n"
                "/start to verify another"
            )
        else:
            await query.message.reply_text(
                f"❌ FAILED!\n\n"
                f"Error: {result.get('message')}\n\n"
                f"Details: {result.get('details', 'N/A')}"
            )
            
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

async def submit_to_sheerid(
    verification_id: str,
    first_name: str,
    last_name: str,
    email: str,
    school: dict,
    pdf_data: bytes,
    png_data: bytes
) -> dict:
    """Submit to SheerID API"""
    
    client = httpx.AsyncClient(timeout=30.0)
    
    try:
        # Generate birth date (teacher age 25-60)
        age = random.randint(25, 60)
        birth_date = (datetime.now() - timedelta(days=age*365)).strftime('%Y-%m-%d')
        
        # Generate device fingerprint
        device_fp = ''.join(random.choice('0123456789abcdef') for _ in range(32))
        
        # Step 2: Submit personal info
        step2_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/collectTeacherPersonalInfo"
        
        step2_body = {
            'firstName': first_name,
            'lastName': last_name,
            'birthDate': birth_date,
            'email': email,
            'organization': {
                'id': int(school.get('id')),
                'name': school.get('name')
            },
            'deviceFingerprintHash': device_fp,
            'locale': 'en-US'
        }
        
        print(f"Submitting: {step2_body}")
        
        step2_resp = await client.post(step2_url, json=step2_body)
        step2_data = step2_resp.json()
        
        print(f"Step 2 response: {step2_resp.status_code} - {step2_data}")
        
        if step2_resp.status_code != 200:
            error_detail = step2_data.get('errorIds', step2_data.get('message', 'Unknown'))
            return {
                'success': False,
                'message': f'Step 2 failed: {step2_resp.status_code}',
                'details': str(error_detail)
            }
        
        # Step 3: Skip SSO
        step3_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/sso"
        await client.delete(step3_url)
        
        # Step 4: Request upload URLs
        step4_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/docUpload"
        step4_body = {
            'files': [
                {'fileName': 'paystub.pdf', 'mimeType': 'application/pdf', 'fileSize': len(pdf_data)},
                {'fileName': 'id_card.png', 'mimeType': 'image/png', 'fileSize': len(png_data)}
            ]
        }
        
        step4_resp = await client.post(step4_url, json=step4_body)
        step4_data = step4_resp.json()
        
        documents = step4_data.get('documents', [])
        if len(documents) < 2:
            return {'success': False, 'message': 'No upload URLs'}
        
        # Upload to S3
        await client.put(documents[0]['uploadUrl'], content=pdf_data, headers={'Content-Type': 'application/pdf'})
        await client.put(documents[1]['uploadUrl'], content=png_data, headers={'Content-Type': 'image/png'})
        
        # Complete upload
        step6_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/completeDocUpload"
        await client.post(step6_url)
        
        await client.aclose()
        
        return {'success': True, 'message': 'Submitted, pending review'}
        
    except Exception as e:
        await client.aclose()
        return {'success': False, 'message': str(e), 'details': str(e)}

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. /start again")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("❌ No BOT_TOKEN!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SHEERID_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sheerid_url)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🎓 K12 Bot with SheerID started...")
    app.run_polling()

if __name__ == '__main__':
    main()
