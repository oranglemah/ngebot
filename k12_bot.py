from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import requests
import os
from datetime import datetime
from document_generator import (
    generate_faculty_id, 
    generate_pay_stub, 
    generate_employment_letter,
    image_to_bytes
)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# States
NAME, EMAIL, SCHOOL = range(3)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "Let's verify your K12 teacher status.\n\n"
        "What's your full name?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {'full_name': update.message.text.strip()}
    
    await update.message.reply_text(
        f"✅ Name: {user_data[user_id]['full_name']}\n\n"
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
    
    # Hit API
    schools = await search_schools(school_name)
    
    # Debug
    print(f"=== SEARCH DEBUG ===")
    print(f"Query: {school_name}")
    print(f"Results: {len(schools) if schools else 0}")
    if schools and len(schools) > 0:
        print(f"First school: {schools[0]}")
    
    # Jika tidak ada hasil
    if not schools or len(schools) == 0:
        await msg.edit_text(
            f"❌ No schools found!\n\n"
            f"Searched: {school_name}\n\n"
            "Try different name:"
        )
        return SCHOOL
    
    # Tampilkan hasil
    await msg.delete()
    await display_schools(update, schools, user_id)
    return ConversationHandler.END

async def search_schools(school_name):
    """Hit SheerID API - EXACT seperti di Network tab"""
    url = "https://orgsearch.sheerid.net/rest/organization/search"
    
    params = {
        'query': school_name
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        print(f"API URL: {response.url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # API return bisa list atau dict
            if isinstance(data, list):
                print(f"Got {len(data)} schools")
                return data
            elif isinstance(data, dict) and 'organizations' in data:
                print(f"Got {len(data['organizations'])} schools")
                return data['organizations']
            else:
                print(f"Unknown format: {type(data)}")
                return []
        else:
            print(f"Error: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return []
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return []

async def display_schools(update, schools, user_id):
    """Tampilkan list sekolah seperti di API"""
    
    # Build message
    text = f"🏫 FOUND {len(schools)} SCHOOLS\n\n"
    text += f"Query: {user_data[user_id]['school_name']}\n\n"
    
    # Build buttons
    keyboard = []
    
    for idx, school in enumerate(schools[:15]):  # Max 15
        # Save ke user_data
        user_data[user_id][f'school_{idx}'] = school
        
        # Parse data
        name = school.get('name', 'Unknown School')
        city = school.get('city', '')
        state = school.get('state', '')
        school_type = school.get('type', 'SCHOOL')
        
        # Format lokasi
        location = f"{city}, {state}" if city and state else city or state or "Unknown"
        
        # Add to message
        text += f"{idx+1}. {name}\n"
        text += f"   📍 {location}\n"
        text += f"   🏷️ {school_type}\n\n"
        
        # Button text (potong jika panjang)
        btn_text = name if len(name) <= 50 else name[:47] + "..."
        
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {btn_text}",
                callback_data=f"sel_{user_id}_{idx}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User pilih sekolah"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback
    parts = query.data.split('_')
    if len(parts) != 3:
        await query.edit_message_text("❌ Invalid selection")
        return
    
    user_id = int(parts[1])
    school_idx = int(parts[2])
    
    # Get data
    if user_id not in user_data or f'school_{school_idx}' not in user_data[user_id]:
        await query.edit_message_text("❌ Session expired. /start again")
        return
    
    school = user_data[user_id][f'school_{school_idx}']
    teacher_name = user_data[user_id]['full_name']
    teacher_email = user_data[user_id]['email']
    school_name = school.get('name', 'Unknown')
    
    await query.edit_message_text(
        f"✅ Selected:\n{school_name}\n\n"
        f"⚙️ Generating documents..."
    )
    
    # Generate docs
    try:
        id_card, faculty_id = generate_faculty_id(teacher_name, teacher_email, school_name)
        pay_stub = generate_pay_stub(teacher_name, teacher_email, school_name, faculty_id)
        letter = generate_employment_letter(teacher_name, teacher_email, school_name)
        
        # Send
        await query.message.reply_photo(
            photo=image_to_bytes(id_card),
            caption=f"📇 Faculty ID\n{faculty_id}"
        )
        
        await query.message.reply_photo(
            photo=image_to_bytes(pay_stub),
            caption=f"💰 Pay Stub - {datetime.now().strftime('%B %Y')}"
        )
        
        await query.message.reply_photo(
            photo=image_to_bytes(letter),
            caption="📄 Employment Letter"
        )
        
        await query.message.reply_text(
            f"✅ SUCCESS!\n\n"
            f"👤 {teacher_name}\n"
            f"🏫 {school_name}\n"
            f"📧 {teacher_email}\n\n"
            "/start to verify another"
        )
        
    except Exception as e:
        print(f"Error generating: {e}")
        await query.message.reply_text(f"❌ Error: {str(e)}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. /start to begin")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("❌ No BOT_TOKEN!")
        return
    
    # Check IP
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
        print(f"🌐 Server IP: {ip}")
    except:
        pass
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🎓 Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
