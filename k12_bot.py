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

# Conversation states
NAME, EMAIL, SCHOOL = range(3)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start conversation"""
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "I will help you verify your K12 teacher status.\n\n"
        "Let's start! What's your full name?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get teacher name"""
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    
    user_data[user_id] = {'full_name': full_name}
    
    await update.message.reply_text(
        f"✅ Name: {full_name}\n\n"
        "What's your school email address?"
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get teacher email"""
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    user_data[user_id]['email'] = email
    
    await update.message.reply_text(
        f"✅ Email: {email}\n\n"
        "What's your school name?"
    )
    return SCHOOL

async def get_school(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search schools"""
    user_id = update.effective_user.id
    school_name = update.message.text.strip()
    
    user_data[user_id]['school_name'] = school_name
    
    await update.message.reply_text("🔍 Searching schools...")
    
    schools = await search_schools(school_name)
    
    if not schools:
        await update.message.reply_text(
            "❌ No schools found!\n\n"
            "Try another school name:"
        )
        return SCHOOL
    
    # Filter K12 dan HIGH_SCHOOL
    k12_schools = [s for s in schools if s.get('type') in ['K12', 'HIGH_SCHOOL']]
    
    if not k12_schools:
        await update.message.reply_text(
            "❌ No K12/High School found!\n\n"
            "Try another school name:"
        )
        return SCHOOL
    
    await display_school_options(update, k12_schools, user_id)
    return ConversationHandler.END

async def search_schools(school_name):
    """Query SheerID API"""
    url = "https://orgsearch.sheerid.net/rest/organization/search"
    params = {
        'query': school_name,
        'organizationType': 'K12'  # API tetap pakai K12, tapi return HIGH_SCHOOL juga
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        print(f"Error searching: {e}")
        return []

async def display_school_options(update, schools, user_id):
    """Display school list"""
    keyboard = []
    message = f"🏫 SCHOOL SEARCH RESULTS\n\n"
    message += f"Query: {user_data[user_id]['school_name']}\n"
    message += f"Found: {len(schools)} results\n\n"
    
    for idx, school in enumerate(schools[:10]):  # Tampilkan max 10
        user_data[user_id][f'school_{idx}'] = school
        
        school_name = school.get('name', 'Unknown')
        location = f"{school.get('city', '')}, {school.get('state', '')}"
        school_type = school.get('type', 'K12')
        
        message += f"{idx+1}. {school_name}\n"
        message += f"   📍 {location}\n"
        message += f"   🏷️ Type: {school_type}\n\n"
        
        button = [InlineKeyboardButton(
            f"{idx+1}. {school_name[:40]}",
            callback_data=f"select_{user_id}_{idx}"
        )]
        keyboard.append(button)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle school selection"""
    query = update.callback_query
    await query.answer()
    
    _, user_id_str, school_idx = query.data.split('_')
    user_id = int(user_id_str)
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Session expired. Please /start again")
        return
    
    selected_school = user_data[user_id][f'school_{school_idx}']
    school_name = selected_school['name']
    
    await query.edit_message_text(
        f"✅ Selected: {school_name}\n"
        f"Type: {selected_school.get('type', 'K12')}\n\n"
        f"⚙️ Generating documents..."
    )
    
    teacher_name = user_data[user_id]['full_name']
    teacher_email = user_data[user_id]['email']
    
    # Generate documents
    try:
        id_card, faculty_id = generate_faculty_id(teacher_name, teacher_email, school_name)
        pay_stub = generate_pay_stub(teacher_name, teacher_email, school_name, faculty_id)
        employment_letter = generate_employment_letter(teacher_name, teacher_email, school_name)
        
        # Send documents
        await query.message.reply_photo(
            photo=image_to_bytes(id_card),
            caption=f"📇 Faculty ID Card\n{faculty_id}"
        )
        
        await query.message.reply_photo(
            photo=image_to_bytes(pay_stub),
            caption=f"💰 Pay Stub - {datetime.now().strftime('%B %Y')}"
        )
        
        await query.message.reply_photo(
            photo=image_to_bytes(employment_letter),
            caption="📄 Employment Verification Letter"
        )
        
        await query.message.reply_text(
            f"✅ VERIFICATION SUCCESS!\n\n"
            f"👤 {teacher_name}\n"
            f"🏫 {school_name}\n"
            f"📧 {teacher_email}\n\n"
            f"🔗 Status: Documents Generated\n\n"
            "Type /start to verify another teacher."
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Error generating documents: {str(e)}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text(
        "❌ Cancelled.\n\n"
        "Type /start to begin again."
    )
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found!")
        return
    
    # Check server IP
    try:
        ip = requests.get('https://api.ipify.org').text
        print(f"🌐 Server IP: {ip}")
        print(f"🔗 Location: https://ipinfo.io/{ip}")
    except:
        pass
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            SCHOOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_school)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🎓 K12 Teacher Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
