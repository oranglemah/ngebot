from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
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
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 K12 Teacher Verification Bot\n\n"
        "Format:\n"
        "/k12\n"
        "Your Full Name\n"
        "Your School Email\n"
        "School Name\n\n"
        "Example:\n"
        "/k12\n"
        "Amanda Austin\n"
        "aaustin@dasd.org\n"
        "Downingtown STEM Academy"
    )

async def k12_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.split('\n')
    
    if len(message_text) < 4:
        await update.message.reply_text(
            "❌ Format tidak lengkap!\n\n"
            "Format:\n"
            "/k12\n"
            "Your Full Name\n"
            "Your School Email\n"
            "School Name"
        )
        return
    
    full_name = message_text[1].strip()
    email = message_text[2].strip()
    school_name = message_text[3].strip()
    
    user_data[user_id] = {
        'full_name': full_name,
        'email': email,
        'school_name': school_name
    }
    
    await update.message.reply_text(
        f"📋 Data Received:\n"
        f"👤 Name: {full_name}\n"
        f"📧 Email: {email}\n"
        f"🏫 School: {school_name}\n\n"
        f"🔍 Searching schools..."
    )
    
    schools = await search_schools(school_name)
    
    if schools:
        k12_schools = [s for s in schools if s.get('type') == 'K12']
        if k12_schools:
            await display_school_options(update, k12_schools, user_id)
        else:
            await update.message.reply_text("❌ No K12 schools found!")
    else:
        await update.message.reply_text("❌ School not found!")

async def search_schools(school_name):
    url = "https://orgsearch.sheerid.net/rest/organization/search"
    params = {'query': school_name, 'organizationType': 'K12'}
    
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
    keyboard = []
    message = f"🏫 SCHOOL SEARCH RESULTS\n\n"
    message += f"Query: {user_data[user_id]['school_name']}\n"
    message += f"Found: {len(schools)} results\n\n"
    
    for idx, school in enumerate(schools[:6]):
        user_data[user_id][f'school_{idx}'] = school
        
        school_info = f"{school.get('name')} ({school.get('city')}, {school.get('state')})"
        message += f"{idx+1}. {school_info}\n   └Type: K12\n\n"
        
        button = [InlineKeyboardButton(
            f"{idx+1}. {school.get('name')[:45]}",
            callback_data=f"select_{user_id}_{idx}"
        )]
        keyboard.append(button)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Reply dengan nomor sekolah yang dipilih (misal: 1)",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, user_id_str, school_idx = query.data.split('_')
    user_id = int(user_id_str)
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Data expired, /k12 again")
        return
    
    selected_school = user_data[user_id][f'school_{school_idx}']
    school_name = selected_school['name']
    
    await query.edit_message_text(
        f"✅ Selected: {school_name}\n"
        f"Type: K12\n\n"
        f"⚙️ Generating documents..."
    )
    
    teacher_name = user_data[user_id]['full_name']
    teacher_email = user_data[user_id]['email']
    
    # Generate documents
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
        f"✅ VERIFIKASI SUKSES!\n\n"
        f"👤 {teacher_name}\n"
        f"🏫 {school_name}\n"
        f"📧 {teacher_email}\n\n"
        f"🔗 Status: SUCCESS"
    )

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN tidak ditemukan!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("k12", k12_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🎓 K12 Teacher Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
