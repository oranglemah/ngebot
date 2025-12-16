from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import requests
import httpx
import re
import os
from datetime import datetime
from document_generator import (
    generate_faculty_id, 
    generate_pay_stub, 
    generate_employment_letter,
    image_to_bytes
)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Config SheerID
PROGRAM_ID = "68d47554aa292d20b9bec8f7"
SHEERID_BASE_URL = "https://services.sheerid.com"

# States
NAME, EMAIL, SCHOOL, SHEERID_URL = range(4)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "I will help you verify your K12 teacher status with SheerID.\n\n"
        "First, please send me your SheerID verification URL.\n\n"
        "Format: https://services.sheerid.com/verify/.../verificationId=..."
    )
    return SHEERID_URL

async def get_sheerid_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse SheerID URL dan extract verification ID"""
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    # Parse verification ID
    match = re.search(r'verificationId=([a-f0-9]{24})', url, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ Invalid SheerID URL!\n\n"
            "URL must contain: verificationId=...\n\n"
            "Try again:"
        )
        return SHEERID_URL
    
    verification_id = match.group(1)
    user_data[user_id] = {'verification_id': verification_id}
    
    await update.message.reply_text(
        f"✅ Verification ID: {verification_id}\n\n"
        "What's your full name?\n"
        "(Example: Allison Holtman)"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    
    # Split name
    parts = full_name.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Please provide first and last name\n\n"
            "Example: Allison Holtman"
        )
        return NAME
    
    first_name = parts[0]
    last_name = ' '.join(parts[1:])
    
    user_data[user_id]['first_name'] = first_name
    user_data[user_id]['last_name'] = last_name
    user_data[user_id]['full_name'] = full_name
    
    await update.message.reply_text(
        f"✅ Name: {full_name}\n\n"
        "What's your school email?"
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id]['email'] = update.message.text.strip()
    
    await update.message.reply_text(
        f"✅ Email: {user_data[user_id]['email']}\n\n"
        "What's your school name?"
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    school_name = update.message.text.strip()
    user_data[user_id]['school_name'] = school_name
    
    msg = await update.message.reply_text("🔍 Searching schools...")
    
    schools = await search_schools(school_name)
    
    if not schools or len(schools) == 0:
        await msg.edit_text(
            "❌ No schools found!\n\nTry different name:"
        )
        return SCHOOL
    
    await msg.delete()
    await display_schools(update, schools, user_id)
    return ConversationHandler.END

async def search_schools(school_name):
    """Search SheerID organizations"""
    url = "https://orgsearch.sheerid.net/rest/organization/search"
    params = {'query': school_name}
    headers = {'Accept': 'application/json'}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json() if isinstance(response.json(), list) else []
        return []
    except:
        return []

async def display_schools(update, schools, user_id):
    """Display school options"""
    text = f"🏫 FOUND {len(schools)} SCHOOLS\n\n"
    keyboard = []
    
    for idx, school in enumerate(schools[:15]):
        user_data[user_id][f'school_{idx}'] = school
        name = school.get('name', 'Unknown')
        location = f"{school.get('city', '')}, {school.get('state', '')}"
        
        text += f"{idx+1}. {name}\n   📍 {location}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {name[:50]}",
                callback_data=f"sel_{user_id}_{idx}"
            )
        ])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle school selection and submit to SheerID"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    user_id = int(parts[1])
    school_idx = int(parts[2])
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Session expired. /start again")
        return
    
    school = user_data[user_id][f'school_{school_idx}']
    school_name = school.get('name', 'Unknown')
    
    await query.edit_message_text(
        f"✅ Selected: {school_name}\n\n"
        f"⚙️ Step 1/4: Generating documents..."
    )
    
    # Get data
    verification_id = user_data[user_id]['verification_id']
    first_name = user_data[user_id]['first_name']
    last_name = user_data[user_id]['last_name']
    email = user_data[user_id]['email']
    
    try:
        # Step 1: Generate documents
        id_card, faculty_id = generate_faculty_id(
            user_data[user_id]['full_name'], email, school_name
        )
        pay_stub = generate_pay_stub(
            user_data[user_id]['full_name'], email, school_name, faculty_id
        )
        letter = generate_employment_letter(
            user_data[user_id]['full_name'], email, school_name
        )
        
        pdf_bytes = image_to_bytes(pay_stub).getvalue()
        png_bytes = image_to_bytes(id_card).getvalue()
        
        await query.message.reply_text("⚙️ Step 2/4: Submitting teacher info to SheerID...")
        
        # Step 2: Submit to SheerID API
        result = await submit_to_sheerid(
            verification_id=verification_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            school=school,
            pdf_data=pdf_bytes,
            png_data=png_bytes
        )
        
        if result['success']:
            # Send documents to user
            await query.message.reply_photo(
                photo=image_to_bytes(id_card),
                caption=f"📇 Faculty ID\n{faculty_id}"
            )
            
            await query.message.reply_photo(
                photo=image_to_bytes(pay_stub),
                caption=f"💰 Pay Stub"
            )
            
            await query.message.reply_photo(
                photo=image_to_bytes(letter),
                caption="📄 Employment Letter"
            )
            
            await query.message.reply_text(
                f"✅ VERIFICATION SUBMITTED!\n\n"
                f"👤 {user_data[user_id]['full_name']}\n"
                f"🏫 {school_name}\n"
                f"📧 {email}\n\n"
                f"🔗 Status: {result.get('message', 'Pending Review')}\n\n"
                f"Verification ID: {verification_id}\n\n"
                "/start to verify another"
            )
        else:
            await query.message.reply_text(
                f"❌ VERIFICATION FAILED!\n\n"
                f"Error: {result.get('message', 'Unknown error')}"
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
    """Submit verification to SheerID API"""
    
    client = httpx.AsyncClient(timeout=30.0)
    
    try:
        # Prepare school data
        school_id = school.get('id')
        school_id_extended = school.get('idExtended', str(school_id))
        school_name = school.get('name')
        
        # Step 2: Submit personal info
        step2_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/collectTeacherPersonalInfo"
        step2_body = {
            'firstName': first_name,
            'lastName': last_name,
            'birthDate': '1985-06-15',  # Generate atau fixed
            'email': email,
            'phoneNumber': '',
            'organization': {
                'id': school_id,
                'idExtended': school_id_extended,
                'name': school_name
            },
            'locale': 'en-US',
            'metadata': {
                'verificationId': verification_id
            }
        }
        
        step2_resp = await client.post(step2_url, json=step2_body)
        if step2_resp.status_code != 200:
            return {'success': False, 'message': f'Step 2 failed: {step2_resp.status_code}'}
        
        # Step 3: Skip SSO
        step3_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/sso"
        await client.delete(step3_url)
        
        # Step 4: Request upload URLs
        step4_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/docUpload"
        step4_body = {
            'files': [
                {'fileName': 'document.pdf', 'mimeType': 'application/pdf', 'fileSize': len(pdf_data)},
                {'fileName': 'document.png', 'mimeType': 'image/png', 'fileSize': len(png_data)}
            ]
        }
        
        step4_resp = await client.post(step4_url, json=step4_body)
        step4_data = step4_resp.json()
        
        documents = step4_data.get('documents', [])
        if len(documents) < 2:
            return {'success': False, 'message': 'Failed to get upload URLs'}
        
        # Step 5: Upload to S3
        pdf_upload_url = documents[0]['uploadUrl']
        png_upload_url = documents[1]['uploadUrl']
        
        await client.put(pdf_upload_url, content=pdf_data, headers={'Content-Type': 'application/pdf'})
        await client.put(png_upload_url, content=png_data, headers={'Content-Type': 'image/png'})
        
        # Step 6: Complete upload
        step6_url = f"{SHEERID_BASE_URL}/rest/v2/verification/{verification_id}/step/completeDocUpload"
        await client.post(step6_url)
        
        await client.aclose()
        
        return {
            'success': True,
            'message': 'Documents submitted, pending review',
            'verification_id': verification_id
        }
        
    except Exception as e:
        await client.aclose()
        return {'success': False, 'message': str(e)}

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. /start to begin")
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
    
    print("🎓 K12 Bot with SheerID integration started...")
    app.run_polling()

if __name__ == '__main__':
    main()
