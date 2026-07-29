from apscheduler.schedulers.background import BackgroundScheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from flask import Flask
from flask_cors import CORS 
from threading import Thread
from multiprocessing import Process
from telegram.ext import (
    CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, ApplicationBuilder,
    CallbackQueryHandler
)
from telegram import Bot

from db import (
    reset_hours_if_25th, execute_query, 
    send_report_managers, mismatch_hours,
)
# import routes
from routes import main

import time 
import asyncio

# Web App URL 
WEB_APP_URL = "https://staffhours.roboticsclub-eg.com/HTML/start.html"
# WEB_APP_URL = "https://staffhours.roboticsclub-eg.com/HTML/hostinger.html" 

BLOCKED_USERS = [6301513509, 6776001473]

# Telegram Bot Token
TOKEN_INSTRUCTOR = "7599846821:AAHzq6O49ozV2MhXhDc-xDes1o2K_hzmIPw"
TOKEN_MANAGER = "8209629905:AAEdvxOKjoii9BIo3Z6w6N1ZtqeaNO3GJQk"
TOKEN_TOP_MANAGER = "7731581469:AAFHs5aHAeKXseZvC7az2ONxT3LnJZ8AS4s"

FULL_NAME = range(2)
WAITING_FOR_NAME = 3
WAITING_FOR_CITY = 4
BRANCHES = 5
CITY, BRANCH = range(2)

# ---------------------------
# Instructors Bot Functions 👨‍🏫 
# ---------------------------
async def start_instructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data['employee_id'] = user.id
    context.user_data['first_name'] = user.first_name
    context.user_data['last_name'] = user.last_name
    context.user_data['username'] = user.username 

    if user.id in BLOCKED_USERS:
        update.message.reply_text("Sorry, you are not authorized to use this bot.🚫")
        return
    else:
        await update.message.reply_text("Welcome! Please enter your FULL NAME in english: ")
        return FULL_NAME
    
async def get_full_name_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['full_name'] = update.message.text.strip()

    # City selection via buttons (added Online)
    keyboard = [
        [InlineKeyboardButton("Alexandria", callback_data="city_Alexandria")],
        [InlineKeyboardButton("Beheira", callback_data="city_Beheira")],
        [InlineKeyboardButton("Dakahlia", callback_data="city_Dakahlia")],
        [InlineKeyboardButton("Kafr El-Shaikh", callback_data="city_Kafr El-Shaikh")],
        [InlineKeyboardButton("Cairo", callback_data="city_Cairo")],
        # [InlineKeyboardButton("Online", callback_data="city_Online")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select your City:", reply_markup=reply_markup)
    return CITY

async def select_city_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_city = query.data.split("_", 1)[1]
    context.user_data['city'] = selected_city
    data = context.user_data

    execute_query("""
        INSERT INTO employee_info (employee_id, first_name, last_name, username, full_name, city)
        VALUES (:employee_id, :first_name, :last_name, :username, :full_name, :city)
        ON DUPLICATE KEY UPDATE first_name=:first_name, last_name=:last_name, username=:username, full_name=:full_name, city=:city
    """, {
        "employee_id": data['employee_id'],
        "first_name": data['first_name'],
        "last_name": data['last_name'],
        "username": data['username'],
        "full_name": data['full_name'],
        "city": selected_city
    }, fetch=False)

    # Instead of finishing here, go to branch selection
    return await handle_city_branch_selection_intstructor(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Canceled.")
    return ConversationHandler.END

async def change_name_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter your FULL NAME in english: ")
    return WAITING_FOR_NAME

async def update_name_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    employee_id = update.effective_user.id

    execute_query(
        "UPDATE employee_info SET full_name = :full_name WHERE employee_id = :employee_id", 
        {"full_name": new_name, "employee_id": employee_id},
        fetch=False
    )

    await update.message.reply_text("Your name has been updated. ✅ ")
    return ConversationHandler.END

async def change_city_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Alexandria", callback_data="updatecity_Alexandria")],
        [InlineKeyboardButton("Beheira", callback_data="updatecity_Beheira")],
        [InlineKeyboardButton("Dakahlia", callback_data="updatecity_Dakahlia")],
        [InlineKeyboardButton("Kafr El-Shaikh", callback_data="updatecity_Kafr El-Shaikh")],
        [InlineKeyboardButton("Cairo", callback_data="city_Cairo")],
        # [InlineKeyboardButton("Online", callback_data="city_Online")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select your new city:", reply_markup=reply_markup)
    return WAITING_FOR_CITY

async def handle_branch_selection_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    branch_id = int(query.data.split("_")[1])
    employee_id = context.user_data['employee_id']

    # Prevent duplicate
    if branch_id not in context.user_data['selected_branch_ids']:
        context.user_data['selected_branch_ids'].append(branch_id)

        # Save to instructor_branches table
        execute_query(
            "INSERT IGNORE INTO instructor_branches (employee_id, branch_id) VALUES (:employee_id, :branch_id)",
            {"employee_id": employee_id, "branch_id": branch_id},
            fetch=False
        )
        print('here')

    await query.edit_message_text(
        f"✅ Branch saved successfully!\n\n"
        "⚙️ You can make further changes ⚙️:\n"
        "• Edit your name: /change_name\n"
        "• Edit your city: /change_city\n"
        "• Edit your branch: /change_branch\n"
        "• Add another branch: /add_branch\n"
        "• Cancel the process: /cancel\n\n"
        "✨ You're all set! 😎 Tap the button below to continue:", 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Start", web_app={"url": f"{WEB_APP_URL}?employee_id={employee_id}&v={int(time.time())}"})]
        ])
    )
    return ConversationHandler.END

async def change_branch_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee_id = update.effective_user.id

    # Get city from DB
    result = execute_query(
        "SELECT city FROM employee_info WHERE employee_id = :employee_id",
        {"employee_id": employee_id}
    )

    if not result:
        message = "You need to register first with /start."
        if update.message:
            await update.message.reply_text(message)
        else:
            await update.callback_query.edit_message_text(message)
        return ConversationHandler.END

    city = result[0][0].strip().split("_")[-1]  # remove whitespace + keep last part
    print(f"[DEBUG] City for employee_id {employee_id}: '{city}'")

    # Fetch branches in that city
    branches = execute_query(
        "SELECT branch_id, branch FROM branches WHERE LOWER(city) = :city",
        {"city": city.lower()}
    )
    print(f"[DEBUG] Fetched branches for city '{city}': {branches}")

    if not branches:
        message = f"No branches found for city: {city}"
        if update.message:
            await update.message.reply_text(message)
        else:
            await update.callback_query.edit_message_text(message)
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(branch[1], callback_data=f"branch_{branch[0]}")] for branch in branches]
    keyboard.append([InlineKeyboardButton("Online", callback_data="branch_8")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "Select your correct Branch (you can choose more than one):", 
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "Select your correct Branch (you can choose more than one):", 
            reply_markup=reply_markup
        )

    context.user_data['selected_branch_ids'] = []
    return BRANCHES

async def handle_city_branch_selection_intstructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    employee_id = context.user_data.get('employee_id') or update.effective_user.id
    context.user_data['employee_id'] = employee_id  

    new_city = query.data.split("_", 1)[1]
    context.user_data['city'] = new_city

    # Update city
    execute_query(
        "UPDATE employee_info SET city = :city WHERE employee_id = :employee_id",
        {"city": new_city, "employee_id": employee_id},
        fetch=False
    )

    # Fetch branches in new city
    branches = execute_query(
        "SELECT branch_id, branch FROM branches WHERE LOWER(city) = :city",
        {"city": new_city.lower()}
    )

    if not branches:
        await query.edit_message_text(f"No branches found for city: {new_city}")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(branch[1], callback_data=f"branch_{branch[0]}")] for branch in branches]
    keyboard.append([InlineKeyboardButton("Online", callback_data="branch_8")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Select your correct Branch (you can choose more than one):", 
        reply_markup=reply_markup
    )
    context.user_data['selected_branch_ids'] = []
    return BRANCHES

async def add_branch_instructor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee_id = update.effective_user.id

    # Get user's city
    result = execute_query(
        "SELECT city FROM employee_info WHERE employee_id = :employee_id",
        {"employee_id": employee_id}
    )

    if not result:
        await update.message.reply_text("You need to register first with /start.")
        return ConversationHandler.END

    city = result[0][0].strip()

    # Fetch branches in that city
    branches = execute_query(
        "SELECT branch_id, branch FROM branches WHERE LOWER(city) = :city",
        {"city": city.lower()}
    )

    if not branches:
        await update.message.reply_text(f"No branches found for city: {city}")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(branch[1], callback_data=f"branch_{branch[0]}")] for branch in branches]
    keyboard.append([InlineKeyboardButton("Online", callback_data="branch_8")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data['employee_id'] = employee_id
    context.user_data['selected_branch_ids'] = []

    await update.message.reply_text(
        "Select the branch you want to add:", 
        reply_markup=reply_markup
    )
    return BRANCHES

# ---------------------------
# Managers Bot Functions 🏙️
# ---------------------------
async def start_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data['employee_id'] = user.id
    context.user_data['first_name'] = user.first_name
    context.user_data['last_name'] = user.last_name
    context.user_data['username'] = user.username

    # Step 1: Ask for City
    cities = execute_query("SELECT DISTINCT city FROM branches", fetch=True)
    if not cities:
        await update.message.reply_text("⚠️ No cities found in database.")
        return ConversationHandler.END

    keyboard = []
    for city in sorted({c[0] for c in cities}):
        keyboard.append([InlineKeyboardButton(city, callback_data=f"city_{city}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if user.id in BLOCKED_USERS:
        await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END 
    else:
        await update.message.reply_text("🌍 Please select your City:", reply_markup=reply_markup)
        return CITY

async def select_city_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_city = query.data.split("_", 1)[1]
    context.user_data['city'] = selected_city

    # Step 2: Ask for Branch (filtered by city)
    branches = execute_query("SELECT branch FROM branches WHERE city = :city", {"city": selected_city}, fetch=True)
    if not branches:
        await query.edit_message_text("⚠️ No branches found for this city.")
        return ConversationHandler.END

    keyboard = []
    for branch in sorted({b[0] for b in branches}):
        keyboard.append([InlineKeyboardButton(branch, callback_data=f"branch_{branch}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"🏢 You selected city: {selected_city}\n\nNow choose your Branch:", reply_markup=reply_markup)
    return BRANCH

async def select_branch_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_branch = query.data.split("_", 1)[1]
    context.user_data['branch'] = selected_branch
    data = context.user_data

    # Step 3: Insert into employee_info with hours_per_month = -1.00
    execute_query("""
        INSERT INTO employee_info 
        (employee_id, first_name, last_name, username, full_name, city, hours_per_month, status)
        VALUES (:employee_id, :first_name, :last_name, :username, :full_name, :city, :hours_per_month, :status)
        ON DUPLICATE KEY UPDATE 
            first_name=:first_name, 
            last_name=:last_name,
            username=:username,
            full_name=:full_name,
            city=:city,
            hours_per_month=:hours_per_month,
            status=:status
    """, {
        "employee_id": data['employee_id'],
        "first_name": data['first_name'],
        "last_name": data['last_name'],
        "username": data['username'],
        "full_name": selected_branch,   # Branch stored in full_name
        "city": data['city'],
        "hours_per_month": -1.00,       # Default value
        "status": 0
    }, fetch=False)

    employee_id = data['employee_id']

    await query.edit_message_text(
        f"✅ Registration completed!\n\n"
        f"🌍 City: {data['city']}\n"
        f"🏢 Branch: {selected_branch}\n\n"
        "✨ You're all set 👍! Tap below to open the app 👇:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Open App 🚀", web_app={"url": f"{WEB_APP_URL}?employee_id={employee_id}&v={int(time.time())}"})
        ]])
    )
    return ConversationHandler.END

async def change_name_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee_id = update.effective_user.id

    # Get current city for this employee
    employee = execute_query(
        "SELECT city FROM employee_info WHERE employee_id = :employee_id",
        {"employee_id": employee_id},
        fetch=True
    )
    if not employee:
        await update.message.reply_text("⚠️ You are not registered yet. Use /start first.")
        return ConversationHandler.END

    current_city = employee[0][0]

    # Fetch branches for the city
    branches = execute_query("SELECT branch_name FROM branches WHERE city = :city", {"city": current_city}, fetch=True)
    if not branches:
        await update.message.reply_text(f"⚠️ No branches found for city {current_city}.")
        return ConversationHandler.END

    keyboard = []
    for branch in sorted({b[0] for b in branches}):
        keyboard.append([InlineKeyboardButton(branch, callback_data=f"changename_{branch}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🏢 Select your new Branch (City: {current_city}):", reply_markup=reply_markup)
    return WAITING_FOR_NAME

async def update_name_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_branch = query.data.split("_", 1)[1]
    employee_id = update.effective_user.id

    execute_query(
        "UPDATE employee_info SET full_name = :branch WHERE employee_id = :employee_id",
        {"branch": new_branch, "employee_id": employee_id},
        fetch=False
    )

    await query.edit_message_text(f"✅ Your branch has been updated to: {new_branch}")
    return ConversationHandler.END

async def change_city_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch unique cities
    cities = execute_query("SELECT DISTINCT city FROM branches WHERE branch_id != 8", fetch=True)
    if not cities:
        await update.message.reply_text("⚠️ No cities found in database.")
        return ConversationHandler.END

    keyboard = []
    for city in sorted({c[0] for c in cities}):
        keyboard.append([InlineKeyboardButton(city, callback_data=f"updatecity_{city}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌍 Select your new City:", reply_markup=reply_markup)
    return WAITING_FOR_CITY

async def update_city_selection_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_city = query.data.split("_", 1)[1]
    context.user_data['new_city'] = new_city

    # Fetch branches for the new city
    branches = execute_query("SELECT branch_name FROM branches WHERE city = :city", {"city": new_city}, fetch=True)
    if not branches:
        await query.edit_message_text(f"⚠️ No branches found for {new_city}.")
        return ConversationHandler.END

    keyboard = []
    for branch in sorted({b[0] for b in branches}):
        keyboard.append([InlineKeyboardButton(branch, callback_data=f"updatebranch_{branch}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"🏢 You selected city: {new_city}\nNow choose your new Branch:", reply_markup=reply_markup)
    return WAITING_FOR_NAME

async def update_branch_after_city_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_branch = query.data.split("_", 1)[1]
    employee_id = update.effective_user.id
    new_city = context.user_data.get('new_city')

    # Update both city + branch
    execute_query(
        "UPDATE employee_info SET city = :city, full_name = :branch WHERE employee_id = :employee_id",
        {"city": new_city, "branch": new_branch, "employee_id": employee_id},
        fetch=False
    )

    await query.edit_message_text(f"✅ Your city has been updated to {new_city} and branch to {new_branch}")
    return ConversationHandler.END

# ---------------------------
# Top Managers Bot Functions 👨‍💼
# ---------------------------
async def start_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data['employee_id'] = user.id
    context.user_data['first_name'] = user.first_name
    context.user_data['last_name'] = user.last_name
    context.user_data['username'] = user.username

    if user.id in BLOCKED_USERS:
        await update.message.reply_text("🚫 Sorry, you are not authorized to use this bot.")
        return ConversationHandler.END 
    else:
        await update.message.reply_text("➡️ Welcome Manager 👋! Please enter your FULL NAME in English:")
        return FULL_NAME

async def get_full_name_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['full_name'] = update.message.text.strip()

    # Fetch unique cities from branches table
    cities = execute_query("SELECT DISTINCT city FROM branches WHERE branch_id != 8", fetch=True)

    if not cities:
        await update.message.reply_text("⚠️ No cities found in database.")
        return ConversationHandler.END

    # Build city buttons dynamically
    keyboard = []
    for city in sorted({c[0] for c in cities}):
        keyboard.append([InlineKeyboardButton(city, callback_data=f"city_{city}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select your City:", reply_markup=reply_markup)
    return CITY

async def select_city_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_city = query.data.split("_", 1)[1]
    context.user_data['city'] = selected_city
    data = context.user_data

    # Insert / Update manager info with default values
    execute_query("""
        INSERT INTO employee_info 
        (employee_id, first_name, last_name, username, full_name, city, hours_per_month, status)
        VALUES (:employee_id, :first_name, :last_name, :username, :full_name, :city, :hours_per_month, :status)
        ON DUPLICATE KEY UPDATE 
            first_name=:first_name, 
            last_name=:last_name,
            username=:username,
            full_name=:full_name,
            city=:city,
            hours_per_month=:hours_per_month,
            status=:status
    """, {
        "employee_id": data['employee_id'],
        "first_name": data['first_name'],
        "last_name": data['last_name'],
        "username": data['username'],
        "full_name": data['full_name'],
        "city": selected_city,
        "hours_per_month": -2,
        "status": 0
    }, fetch=False)

    employee_id = data['employee_id'] 

    # Send confirmation message
    await query.edit_message_text(
        f"You have been successfully registered as a manager! ✅\n\n"
        "⚙️ You can make changes if needed ⚙️:\n"
        "• Edit your name: /change_name\n"
        "• Edit your city: /change_city\n"
        "• Cancel: /cancel\n\n"
        "✨ You're all set 👍! Tap below to open the app 👇:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Open App 🚀", web_app={"url": f"{WEB_APP_URL}?employee_id={employee_id}&v={int(time.time())}"})]
        ])
    )
    return ConversationHandler.END

async def cancel_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration canceled.")
    return ConversationHandler.END

async def change_name_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔃Please enter your new FULL NAME in English:")
    return WAITING_FOR_NAME

async def update_name_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    employee_id = update.effective_user.id

    execute_query(
        "UPDATE employee_info SET full_name = :full_name WHERE employee_id = :employee_id",
        {"full_name": new_name, "employee_id": employee_id},
        fetch=False
    )

    await update.message.reply_text("✅ Your name has been updated successfully.")
    return ConversationHandler.END

async def change_city_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch unique cities from branches table
    cities = execute_query("SELECT DISTINCT city FROM branches WHERE branch_id != 8", fetch=True)

    if not cities:
        await update.message.reply_text("⚠️ No cities found in database.")
        return ConversationHandler.END

    keyboard = []
    for city in sorted({c[0] for c in cities}):
        keyboard.append([InlineKeyboardButton(city, callback_data=f"updatecity_{city}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("➡️ Select your new city:", reply_markup=reply_markup)
    return WAITING_FOR_CITY

async def update_city_selection_top_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    new_city = query.data.split("_", 1)[1]
    employee_id = update.effective_user.id

    execute_query(
        "UPDATE employee_info SET city = :city WHERE employee_id = :employee_id",
        {"city": new_city, "employee_id": employee_id},
        fetch=False
    )

    await query.edit_message_text(f"✅ Your city has been updated to: {new_city}")
    return ConversationHandler.END

# Create Flask app
app = Flask(__name__) 
CORS(app)
app.register_blueprint(main)

# ---------------------------
# Instructors Bot 👨‍🏫
# ---------------------------
def build_instructor_bot():
    bot_app = ApplicationBuilder().token(TOKEN_INSTRUCTOR).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_instructor)],
        states={ 
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name_intstructor)],
            CITY: [CallbackQueryHandler(select_city_intstructor, pattern=r"^city_")],
            BRANCHES: [CallbackQueryHandler(handle_branch_selection_intstructor, pattern=r"^branch_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(conv_handler)

    change_name_conv = ConversationHandler(
        entry_points=[CommandHandler("change_name", change_name_intstructor)],
        states={WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_name_intstructor)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(change_name_conv)

    change_city_conv = ConversationHandler(
        entry_points=[CommandHandler("change_city", change_city_intstructor)],
        states={
            WAITING_FOR_CITY: [CallbackQueryHandler(handle_city_branch_selection_intstructor, pattern=r"^updatecity_")],
            BRANCHES: [CallbackQueryHandler(handle_branch_selection_intstructor, pattern=r"^branch_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(change_city_conv)

    change_branch_conv = ConversationHandler(
        entry_points=[CommandHandler("change_branch", change_branch_intstructor)],
        states={BRANCHES: [CallbackQueryHandler(handle_branch_selection_intstructor, pattern=r"^branch_")]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(change_branch_conv)
 
    add_branch_conv = ConversationHandler(
        entry_points=[CommandHandler("add_branch", add_branch_instructor)],
        states={BRANCHES: [CallbackQueryHandler(handle_branch_selection_intstructor, pattern=r"^branch_")]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(add_branch_conv)

    return bot_app


# ---------------------------
# Branch Managers Bot 🏙️ 
# ---------------------------
def build_manager_bot():
    bot_app = ApplicationBuilder().token(TOKEN_MANAGER).build()

    manager_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_manager)],
        states={
            CITY: [CallbackQueryHandler(select_city_manager, pattern=r"^city_")],
            BRANCH: [CallbackQueryHandler(select_branch_manager, pattern=r"^branch_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(manager_conv)

    # Change branch only (/change_name)
    change_name_conv = ConversationHandler(
        entry_points=[CommandHandler("change_name", change_name_manager)],
        states={
            WAITING_FOR_NAME: [CallbackQueryHandler(update_name_manager, pattern=r"^changename_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(change_name_conv)

    # Change city + branch (/change_city)
    change_city_conv = ConversationHandler(
        entry_points=[CommandHandler("change_city", change_city_manager)],
        states={
            WAITING_FOR_CITY: [CallbackQueryHandler(update_city_selection_manager, pattern=r"^updatecity_")],
            WAITING_FOR_NAME: [CallbackQueryHandler(update_branch_after_city_manager, pattern=r"^updatebranch_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bot_app.add_handler(change_city_conv)
    return bot_app

# ---------------------------
# Top Managers Bot 👨‍💼
# ---------------------------
def build_top_manager_bot():
    bot_app = ApplicationBuilder().token(TOKEN_TOP_MANAGER).build()

    # Conversation for manager registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_top_manager)],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name_top_manager)],
            CITY: [CallbackQueryHandler(select_city_top_manager, pattern=r"^city_")]
        }, 
        fallbacks=[CommandHandler("cancel", cancel_top_manager)],
    )
    bot_app.add_handler(conv_handler)

    # Change name handler
    change_name_conv = ConversationHandler(
        entry_points=[CommandHandler("change_name", change_name_top_manager)],
        states={WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_name_top_manager)]},
        fallbacks=[CommandHandler("cancel", cancel_top_manager)],
    )
    bot_app.add_handler(change_name_conv)

    # Change city handler
    change_city_conv = ConversationHandler(
        entry_points=[CommandHandler("change_city", change_city_top_manager)],
        states={WAITING_FOR_CITY: [CallbackQueryHandler(update_city_selection_top_manager, pattern=r"^updatecity_")]},
        fallbacks=[CommandHandler("cancel", cancel_top_manager)],
    )
    bot_app.add_handler(change_city_conv)
    return bot_app

# ---------------------------
# Run All Bots in Parallel
# ---------------------------
def run_flask():
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)


def run_instructor():
    app = build_instructor_bot()
    app.run_polling()

def run_manager():
    app = build_manager_bot()
    app.run_polling()

def run_top_manager():
    app = build_top_manager_bot()
    app.run_polling()

def run_flask_server():
    run_flask()

# def send_blocked_message(token):
#     async def _send():
#         bot = Bot(token=token)
#         await bot.send_message(chat_id=6776001473, text="Sorry you are not authorized to use this bot 🚫")
#     asyncio.run(_send())

def send_statistical_report(token):
    async def _send():
        bot = Bot(token=token)

        # List of top managers' chat IDs
        chat_ids = [1189998133, 1172724089, 7883174419, 7926944424, 923349608] #942958403 
        # chat_ids = [1189998133] 

        # Message with hyperlink
        message_text = (
            # '\n\n<b>  رمضان مبارك 🌙 , تقبل الله صيامكم وطاعاتكم 🕌🤲 </b>\n\n'
            '<b>التقرير الشهري</b>\n\n'
            '<b>إبريل 2026</b>\n\n'
            '<a href="https://canva.link/tejwrru0f4swky2">انقر هنا لفتح التقرير</a>'
            #'\n\n<b>Please send Feedback to the developer from the App, to improve the report next month</b>\n\n'
        )

        # Send message to each manager
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")
                print(f"Report sent to chat ID: {chat_id}")
            except Exception as e:
                print(f"Failed to send to {chat_id}: {e}")

    asyncio.run(_send())

# def Eid_Al_Fitr(token):
#     async def _send():
#         bot = Bot(token=token)

#         # List of top Instructors' chat IDs
#         #chat_ids = [1189998133, 6946191019, 6601479202, 2089853213, 1321959723] 
#         chat_ids = [1189998133, 6601479202] 

#         # Message with hyperlink
#         message_text = (
#             '\n\n<b>عيد مبارك م/أحمد 🕌</b>\n\n'
#             '<b>شكرا علي مجهودك واجتهادك في العمل معانا م/ أحمد -  تتمني لك الشركة عيدًا سعيدًا وإجازة ممتعة ومريحة💚💚</b>\n\n'
#         )

#         # Send message to each manager
#         for chat_id in chat_ids:
#             try:
#                 await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")
#                 print(f"Celebration message sent to chat ID: {chat_id}")
#             except Exception as e:
#                 print(f"Failed to send to {chat_id}: {e}")

#     asyncio.run(_send())

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Build all bots 
    instructor_bot = build_instructor_bot()
    manager_bot = build_manager_bot()
    top_manager_bot = build_top_manager_bot()

    # Scheduler jobs
    scheduler = BackgroundScheduler()

    # Reset hours on 25th of each month at 23:59 → 21:59
    scheduler.add_job(reset_hours_if_25th, 'cron', day=25, hour=21, minute=59)
  
    # Send to Branch Managers' Bot
    # scheduler.add_job(send_report_managers, 'cron', hour=22, minute=0, args=[manager_bot])
    scheduler.add_job(mismatch_hours, 'cron', hour=20, minute=0, args=[manager_bot])

    # Send to Top Managers' Bot
    # scheduler.add_job(send_report_managers, 'cron', hour=22, minute=0, args=[top_manager_bot])
    scheduler.add_job(mismatch_hours, 'cron', hour=20, minute=0, args=[top_manager_bot])
    # scheduler.add_job(send_statistical_report, 'cron', day=27, hour=11, minute=15, args=[TOKEN_TOP_MANAGER])
    # scheduler.add_job(Eid_Al_Fitr, 'cron', day = 20, hour=2, minute=32, args=[TOKEN_INSTRUCTOR])

    from datetime import datetime
    now = datetime.now()
    print(now.strftime("Scheduler started at %Y-%m-%d %H:%M:%S"))
    # scheduler.add_job(send_blocked_message, 'cron', hour=20, minute=50, args=[TOKEN_TOP_MANAGER]) 
    
    scheduler.start()

    processes = [ 
        Process(target=run_instructor), 
        Process(target=run_manager),
        Process(target=run_top_manager),
        Process(target=run_flask_server),
    ]

    for p in processes:
        p.start()

    for p in processes:
        p.join() 
