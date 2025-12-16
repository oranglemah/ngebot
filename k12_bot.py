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

BOT_TOKEN = os.environ.get('BOT_TOKEN')
SHEERID_BASE_URL = "https://services.sheerid.com"
ORGSEARCH_URL = "https://orgsearch.sheerid.net/rest/organization/search"

# States
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "Send your SheerID verification URL:\n\n"
        "https://services.sheerid.com/verify/.../verificationId=..."
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    match = re.search(r'verificationId=([a-f0-9]{24})', url, re.IGNORECASE)
    if not match:
        await update.message.reply_text("❌ Invalid URL!\n\nSend URL again:")
        return SHEERID_URL
    
    verification_id = match.group(1)
    user_data[user_id] = {'verification_id': verification_id}
    
    await update.message.reply_text(
        f"✅ Verification ID: {verification_id}\n\n"
        "What's your full name?\n(Example: Elizabeth Bradly)"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    
    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ Need first AND last name")
        return NAME
    
    user_data[user_id]['first_name'] = parts[0]
    user_data[user_id]['last_name'] = ' '.join(parts[1:])
    user_data[user_id]['full_name'] = full_name
    
    await update.message.reply_text(f"✅ Name: {full_name}\n\nSchool email?")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]['email'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Email: {user_data[user_id]['email']}\n\nSchool name?"
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    school_name = update.message.text.strip()
    user_data[user_id]['school_name'] = school_name
    
    msg = await update.message.reply_text("⚙️ Searching schools...")
    
    schools = await search_schools(school_name)
    
    if not schools:
        await msg.edit_text("❌ No schools found!\n\nTry different name:")
        return SCHOOL
    
    await msg.delete()
    await display_schools(update, schools, user_id)
    return ConversationHandler.END

async def search_schools(query: str) -> list:
    """Search schools - K12 dan HIGH_SCHOOL"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Parameter HANYA query, seperti API asli
            params = {'query': query}
            
            response = await client.get(ORGSEARCH_URL, params=params)
            
            if response.status_code != 200:
                print(f"API error: {response.status_code}")
                return []
            
            data = response.json()
            
            if not isinstance(data, list):
                print(f"API return bukan list")
                return []
            
            print(f"=== API return {len(data)} results ===")
            
            # Filter: Hanya K12 dan HIGH_SCHOOL
            filtered = []
            for school in data:
                school_type = school.get('type', '')
                
                # Accept K12 atau HIGH_SCHOOL
                if school_type in ['K12', 'HIGH_SCHOOL']:
                    filtered.append(school)
            
            print(f"Filtered: {len(filtered)} K12/HIGH_SCHOOL schools")
            return filtered[:20]  # Max 20
            
        except Exception as e:
            print(f"Search error: {e}")
            return []

async def display_schools(update, schools, user_id):
    """Display school results dengan TYPE"""
    
    text = "⚙️ SCHOOL SEARCH RESULTS\n\n"
    text += f"Query: {user_data[user_id]['school_name']}\n"
    text += f"Found: {len(schools)} results\n\n"
    
    keyboard = []
    
    for idx, school in enumerate(schools):
        user_data[user_id][f'school_{idx}'] = school
        
        name = school.get('name', 'Unknown')
        city = school.get('city', '')
        state = school.get('state', '')
        school_type = school.get('type', 'SCHOOL')
        
        location = f"{city}, {state}" if city and state else state or 'US'
        
        # Format seperti bot yang berhasil
        text += f"{idx+1}. {name}\n"
        text += f"   📍 {location}\n"
        text += f"   └─Type: {school_type}\n\n"
        
        # Button
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {name[:45]}",
                callback_data=f"sel_{user_id}_{idx}"
            )
        ])
    
    text += f"📝 Reply dengan nomor sekolah yang dipilih (misal: 1)"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle school selection"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    user_id = int(parts[1])
    school_idx = int(parts[2])
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Session expired. /start again")
        return
    
    school = user_data[user_id][f'school_{school_idx}']
    school_name = school.get('name')
    school_type = school.get('type', 'K12')
    
    await query.edit_message_text(
        f"✅ Selected: {school_name}\n"
        f"Type: {school_type}\n\n"
        f"⚙️ Submitting..."
    )
    
    # Get user data
    verification_id = user_data[user_id]['verification_id']
    first_name = user_data[user_id]['first_name']
    last_name = user_data[user_id]['last_name']
    full_name = user_data[user_id]['full_name']
    email = user_data[user_id]['email']
    
    try:
        # Generate docs
        id_card, faculty_id = generate_faculty_id(full_name, email, school_name)
        pay_stub = generate_pay_stub(full_name, email, school_name, faculty_id)
        letter = generate_employment_letter(full_name, email, school_name)
        
        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()
        
        # Submit to SheerID
        result = await submit_sheerid(
            verification_id, first_name, last_name, email, school,
            pdf_bytes, png_bytes
        )
        
        if result['success']:
            # Send docs
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
                f"✅ VERIFIKASI SUKSES!\n\n"
                f"👤 {full_name}\n"
                f"🏫 {school_name}\n"
                f"📧 {email}\n\n"
                f"🔗 Status: SUCCESS\n\n"
                "/start untuk verifikasi lain"
            )
        else:
            await query.message.reply_text(
                f"❌ VERIFICATION FAILED!\n\n{result.get('message')}"
            )
            
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {str(e)}")

async def submit_sheerid(
    verification_id: str,
    first_name: str,
    last_name: str,
    email: str,
    school: dict,
    pdf_data: bytes,
    png_data: bytes
) -> dict:
    """Submit ke SheerID API"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Generate birth date
            age = random.randint(25, 60)
            birth_date = (datetime.now() - timedelta(days=age*365)).strftime('%Y-%m-%d')
            device_fp = ''.join(random.choice('0123456789abcdef') for _ in range(32))
            
            # Step 2: Personal info
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
            
            step2_resp = await client.post(step2_url, json=step2_body)
            
            if step2_resp.status_code != 200:
                return {
                    'success': False,
                    'message': f'Step 2 failed: {step2_resp.status_code}'
                }
            
            # Step 3: Skip SSO
            await client.delete(
                f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/sso"
            )
            
            # Step 4: Request upload URLs
            step4_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/docUpload"
            step4_body = {
                'files': [
                    {'fileName': 'doc.pdf', 'mimeType': 'application/pdf', 'fileSize': len(pdf_data)},
                    {'fileName': 'doc.png', 'mimeType': 'image/png', 'fileSize': len(png_data)}
                ]
            }
            
            step4_resp = await client.post(step4_url, json=step4_body)
            step4_data = step4_resp.json()
            
            documents = step4_data.get('documents', [])
            if len(documents) < 2:
                return {'success': False, 'message': 'No upload URLs'}
            
            # Upload to S3
            await client.put(
                documents[0]['uploadUrl'],
                content=pdf_data,
                headers={'Content-Type': 'application/pdf'}
            )
            await client.put(
                documents[1]['uploadUrl'],
                content=png_data,
                headers={'Content-Type': 'image/png'}
            )
            
            # Complete
            await client.post(
                f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/completeDocUpload"
            )
            
            return {'success': True, 'message': 'Submitted successfully'}
            
        except Exception as e:
            return {'success': False, 'message': str(e)}

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled")
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
    
    print("🎓 K12 Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
