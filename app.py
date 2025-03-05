from telegram import Update, ChatMemberUpdated
from telegram.ext import Application, CommandHandler, ContextTypes, filters
import requests
from datetime import datetime, timedelta, time
from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Your bot token
BOT_TOKEN = '8003565462:AAGzg586C-eoeNeJFwVO9lpeHQu77h1apGg'

# Admin IDs who are allowed to use admin commands
ADMIN_IDS = [5112593221]
admin_expiry = {}

# Default values for user requests
user_data = {}
# Biến toàn cục để lưu thông tin promotion theo nhóm
group_promotions = {}
# Biến lưu thông tin số lượt/ngày và thời hạn sử dụng bot của các nhóm
allowed_groups_info = {}

# List of groups allowed to use the bot
allowed_groups = set([-1002264505847])  # Automatically allow this group
# Flask App
app = Flask(__name__)

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "Bot is running", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
# Function to reset daily requests for all users
def reset_daily_requests():
    now = datetime.now()
    for user_id, data in user_data.items():
        if not data['vip']:
            data['daily_requests'] = 1
        elif data['expiry_date'] < now:
            data['vip'] = False
            data['daily_requests'] = 1

# Function to allow a group to use the bot
async def allow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command. \n BUY ACCESS FROM ☠️ @mohd1_aaqib ✔️")
        return

    chat_id = update.effective_chat.id

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /allow <daily_limit> <days>")
        return

    try:
        # Lấy số lượt và thời hạn từ tham số
        daily_limit = int(context.args[0])
        days = int(context.args[1])

        # Thêm nhóm vào danh sách allowed_groups
        allowed_groups.add(chat_id)

        # Cập nhật thông tin nhóm
        expiry_date = datetime.now() + timedelta(days=days)
        allowed_groups_info[chat_id] = {
            "daily_limit": daily_limit,
            "expiry_date": expiry_date,
            "remaining_today": daily_limit,  # Khởi tạo lượt sử dụng trong ngày
        }

        await update.message.reply_text(
            f"✅ This group is allowed to use the bot with the following settings:\n"
            f"◼️Daily Limit: {daily_limit} requests/day\n"
            f"◼️Valid for: {days} days (Expires on {expiry_date.strftime('%Y-%m-%d')})\n"
            f"◼️OWNER - ☠️ @mohd1_aaqib ✔️"
        )
    except ValueError:
        await update.message.reply_text("Please provide valid numbers for daily limit and days.")

# Command to check user's remaining daily requests and VIP status
async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_info = user_data.get(user_id, None)

    if not user_info:
        # Initialize user as free user
        user_data[user_id] = {'likes': 0, 'daily_requests': 1, 'expiry_date': None, 'vip': False}
        user_info = user_data[user_id]

    # Free request status
    free_request_status = f"✅ {user_info['daily_requests']}/1" if user_info['daily_requests'] > 0 else "❌ 0/1"
    
    # VIP status and daily limits
    vip_status = "✅ Yes" if user_info['vip'] else "❌ NO"
    remaining_requests = f"✅ {user_info['likes']}/99" if user_info['vip'] else "❌ 0/0"

    # Reset time for daily requests (Sri Lanka Time)
    reset_time = "1:30 AM Sri Lankan Time"

    message = (
        f"📊 Daily Free Request: {free_request_status}\n"
        f"🔹 Likes Access: {vip_status}\n"
        f"🕒 Next Reset Time: {reset_time}\n\n"
        f"🔸 Admin Allowed Amount: {remaining_requests}\n"
        f"📅 Access Expires At: {user_info['expiry_date'].strftime('%d/%m/%Y') if user_info['vip'] else 'N/A'}"
    )

    await update.message.reply_text(message)

# Command to set promotion text for a group
async def set_promotion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command.")
        return

    chat_id = update.effective_chat.id

    if len(context.args) < 1:
        await update.message.reply_text("Usage: /setpromotion <text>")
        return

    promotion_text = update.message.text.split(" ", 1)[1]

    # Tạo một cấu trúc để lưu nội dung văn bản và nút URL
    if "[SUBSCRIBE]" in promotion_text:
        button_url = promotion_text.split("buttonurl:")[-1].strip()
        group_promotions[chat_id] = {
            "text": promotion_text.split("[SUBSCRIBE]")[0].strip(),
            "button_url": button_url
        }
    else:
        group_promotions[chat_id] = {"text": promotion_text, "button_url": None}

    await update.message.reply_text(f"Promotion text has been set:\n{promotion_text}")
# Command to add VIP status to a user (only accessible by admins)
async def add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command.\n BUY ACCESS FROM ☠️ @mohd1_aaqib ✔️")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        days = int(context.args[2])

        if user_id not in user_data:
            user_data[user_id] = {'likes': 0, 'daily_requests': 1, 'expiry_date': None, 'vip': False}

        # Update user VIP status
        user_data[user_id]['vip'] = True
        user_data[user_id]['likes'] = amount
        user_data[user_id]['expiry_date'] = datetime.now() + timedelta(days=days)

        await update.message.reply_text(
            f"✅ User ID {user_id} has been given {amount} requests per day for {days} days. VIP access granted."
        )
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add <user_id> <amount> <days>")

async def reset_handler(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now()
    # Reset số lượt của nhóm
    for chat_id, info in allowed_groups_info.items():
        if info["expiry_date"] > now:
            info["remaining_today"] = info["daily_limit"]
    # Reset số lượt của người dùng
    for user_id, data in user_data.items():
        if not data['vip']:
            data['daily_requests'] = 1
        elif data['expiry_date'] < now:
            data['vip'] = False
            data['daily_requests'] = 1
 #/out
async def out_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:  # Phải có thụt lề ở đây
        await update.message.reply_text("You do not have permission to use this command.")
        return

    try:
        user_id = int(context.args[0])
        if user_id in user_data:
            user_data[user_id]['vip'] = False
            user_data[user_id]['likes'] = 0
            user_data[user_id]['expiry_date'] = None
            await update.message.reply_text(f"✅ User ID {user_id} has been removed from VIP.")
        else:
            await update.message.reply_text(f"User ID {user_id} is not in the VIP list.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /out <user_id>")
 #/kick
async def kick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command.\n BUY ACCES FROM @mohd1_aaqib ❤")
        return

    try:
        user_id = int(context.args[0])
        if user_id in ADMIN_IDS:
            ADMIN_IDS.remove(user_id)
            await update.message.reply_text(f"✅ User ID {user_id} has been removed from the admin list💔.")
        else:
            await update.message.reply_text(f"User ID {user_id} is not an admin.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /kick <user_id>")
        #/remove
async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command.\n BUY ACCESS FORM @mohd1_aaqib 🖤")
        return

    chat_id = update.effective_chat.id

    if chat_id in allowed_groups:
        allowed_groups.remove(chat_id)
        allowed_groups_info.pop(chat_id, None)
        await update.message.reply_text(f"✅ Group {chat_id} has been removed from the allowed list💔")
    else:
        await update.message.reply_text(f"This group is not in the allowed list.")
        #/addadmin
        admin_expiry = {}

async def addadmin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You do not have permission to use this command. /n BUY ACCESS FROM @mohd1_aaqib 🩵")
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        expiry_date = datetime.now() + timedelta(days=days)

        ADMIN_IDS.append(user_id)
        admin_expiry[user_id] = expiry_date

        await update.message.reply_text(f"✅ User ID {user_id} has been added as an admin for {days} days.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addadmin <user_id> <days>")
# Command to handle the like request
# Update the like_handler to include promotion
async def like_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Kiểm tra nếu nhóm không được phép
    if chat_id not in allowed_groups:
        await update.message.reply_text(
            "This group is not allowed to use the bot. \n BUY ACCESS FROM @mohd1_aaqib 🩵"
        )
        return

    # Kiểm tra số lượt còn lại của nhóm
    group_info = allowed_groups_info.get(chat_id, None)
    if group_info:
        if group_info["remaining_today"] <= 0:
            await update.message.reply_text(
                "The Daily Request Amount has been Over. Please Wait till Cycle Reset or Contact @mohd1_aaqib to Upgrade Your Package!"
            )
            return

    # Kiểm tra số lượt còn lại của người dùng
    user_info = user_data.get(user_id, {'likes': 0, 'daily_requests': 1, 'vip': False})
    if user_info['daily_requests'] <= 0 and not user_info['vip']:
        await update.message.reply_text(
            "❌ You have exceeded your daily request limit. 📞 Please wait until the daily reset or contact @mohd1_aaqib to upgrade your package!"
        )
        return

    # Kiểm tra tham số đầu vào
    if len(context.args) != 2:
        await update.message.reply_text(
            "Please provide a valid region and UID. Example: /like ind 10000001"
        )
        return

    region = context.args[0]
    uid = context.args[1]
    api_url = f"https://likesapi.thory.in/like?user_id={user_id}&server_name={server_name}&key=2daysfree"
    response = requests.get(api_url)

    if response.status_code == 200:
        response_data = response.json() 
        
        # Xử lý nếu status = 3 (UID đã đạt giới hạn lượt like)
        if response_data.get("status") == 3:
            await update.message.reply_text(
                f"💔UID {uid} has already received Max Likes for Today💔. Please Try a different UID."
            )
        elif "LikesGivenByAPI" in response_data:
            # Lấy thông tin từ API
            likes_before = response_data.get("LikesbeforeCommand", 0)
            likes_after = response_data.get("LikesafterCommand", 0)
            likes_given = response_data.get("LikesGivenByAPI", 0)
            player_name = response_data.get("PlayerNickname", "Unknown")
            player_level = response_data.get("PlayerLevel", "Unknown")

            # Cập nhật số lượt của người dùng
            if user_info['vip']:
                user_info['likes'] -= 1
            else:
                user_info['daily_requests'] -= 1

            # Cập nhật số lượt của nhóm
            if chat_id in allowed_groups_info:
                allowed_groups_info[chat_id]["remaining_today"] -= 1

            # Lấy thông tin quảng bá
            promotion = group_promotions.get(chat_id, {})
            promotion_text = promotion.get("text", "")
            button_url = promotion.get("button_url", None)

            # Chuẩn bị bàn phím nếu có URL
            if button_url:
                keyboard = [[InlineKeyboardButton("SUBSCRIBE", url=button_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None

            # Hiển thị kết quả
            result_message = (
              
                f"🔷Player Name: {player_name}\n"
                f"🔸Player UID: {uid}\n"
                f"🔸Likes before: {likes_before}\n"
                f"🔸Likes after: {likes_after}\n"
                f"🔸Likes given: {likes_given}\n\n"
                f"{promotion_text}"
            )
            await update.message.reply_text(result_message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                "❌ERROR PLEASE TRY AGAIN AFTER 1 HOUR"
            )
    else:
        await update.message.reply_text(
            "An error occurred. Please check account region or try again later💔."
        )
 # Command to check remaining requests and days for a group
async def remain_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    # Kiểm tra nếu nhóm có trong danh sách được phép
    if chat_id not in allowed_groups_info:
        await update.message.reply_text("This group is not allowed to use the bot. /n USE VIP GROUP https://t.me/MOHD1LIKE . /n BUY ACCESS FORM 🖤 @mohd1_aaqib ✔️")
        return

    group_info = allowed_groups_info[chat_id]
    now = datetime.now()

    # Tính số ngày còn lại
    remaining_days = (group_info["expiry_date"] - now).days
    if remaining_days < 0:
        await update.message.reply_text("The Daily Request Amount has been Over💔. Please Wait till Cycle Reset or Contact ☠️ @mohd1_aaqib ✔️ to Upgrade Your Package!")
        return

    # Lấy thông tin số lượt còn lại
    remaining_requests = group_info.get("remaining_today", 0)
    daily_limit = group_info.get("daily_limit", 0)

    # Trả về kết quả theo mẫu
    message = (
        f"Remaining requests: {remaining_requests}/{daily_limit}\n"
        f"Remaining days: {remaining_days}"
    )
    await update.message.reply_text(message)
    # Lệnh /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name
    current_time = datetime.now().strftime("%I:%M:%S %p")
    current_date = datetime.now().strftime("%Y-%m-%d")

    welcome_message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Welcome, {user_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 User Details:
╭───────────────╮
├ 🆔 User ID: {user_id}
├ ⏰ Time: {current_time}
├ 📅 Date: {current_date}
╰───────────────╯

📖 Commands:
╭───────────────╮
├ 📜 /help: View all available commands
├ 🔄 /start: Restart the bot
├ 🚙 /info <vehicle number>: Get Vehicle Info
╰───────────────╯

🇬🇧 English: First, you have to join our support group. Then you can use the bot.

🇮🇳 हिंदी: सबसे पहले आपको हमारे सहायता समूह से जुड़ना होगा। उसके बाद आप इस बॉट का उपयोग कर सकते हैं.

🔗 Join Us: 
Click here to join our channel/group!

━━━━━━━━━━━━━━━━━━━━━━━━━━
😊 Enjoy your experience with the bot!
━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    keyboard = [
        [InlineKeyboardButton("🩵 SUBSCRIBE ON YT", url="https://www.youtube.com/@")],
        [InlineKeyboardButton("🔗 TELEGRAM CHANNEL", url="https://t.me/Mohd1like")],
        [InlineKeyboardButton("☠️DM ADMIN", url="https://t.me/mohd1_aaqib")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Lệnh /info để lấy thông tin xe
async def vehicle_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("💡 Enter your vehicle number to fetch its details.", parse_mode="Markdown")
        return

    vehicle_number = context.args[0].upper()
    api_url = f"https://vehicleinfo.taitanapi.workers.dev/?number={vehicle_number}"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = requests.get(api_url, timeout=5)
        data = response.json()

        if "data" not in data:
            await update.message.reply_text("💡 Enter your vehicle number to fetch its details.")
            return

        vehicle = data["data"]

        vehicle_message = f"""
╭─────────(🚗 *Vehicle Details* 🚗)──────────⦿
│▸ 🔢 *Vehicle Number:* `{vehicle.get('VEHICLE_NUM', 'N/A')}`
│▸ 🏢 *Brand:* `{vehicle.get('BRAND', 'N/A')}`
│▸ 🚙 *Model:* `{vehicle.get('VEHICLE_MODEL', 'N/A')}`
│▸ 👤 *Owner:* `{vehicle.get('NAME', 'N/A')}`
│▸ 🛡️ *Role:* `{vehicle.get('ROLE', 'N/A')}`
│▸ 🏦 *Insurance By:* `{vehicle.get('INSURANCE_BY', 'N/A')}`
│▸ 📅 *Insurance Expiry:* `{vehicle.get('date_of_insurance_expiry', 'N/A')}`
│▸ ⏳ *Days Left:* `{vehicle.get('DAYS_LEFT', 'N/A')}`
│▸ 👥 *Owner Number:* `{vehicle.get('OWNER_NUM', 'N/A')}`
│▸ 🏗️ *Commercial:* `{vehicle.get('isCommercial', 'N/A')}`
│▸ 🗓️ *Registration Date:* `{vehicle.get('REG_DATE', 'N/A')}`
│▸ 🤑 *Eligible for Sell:* `{vehicle.get('SELL_ELIGIBLE', 'N/A')}`
│▸ 🛍️ *Eligible for Buy:* `{vehicle.get('OWNER', 'N/A')}`
│▸ 🔍 *Probable Vehicle Number:* `{vehicle.get('VEHICLE_NUM', 'N/A')}`
│▸ 🎂 *Vehicle Age:* `{vehicle.get('AGE', 'N/A')}`
│▸ 🛡️ *Insurance Eligible:* `{vehicle.get('INSURANCE_ELIGIBLE', 'N/A')}`
│▸ ❌ *Is Expired:* `{vehicle.get('IS_EXPIRED', 'N/A')}`
│▸ ❌ *Insurance Expired:* `{vehicle.get('INSURANCE_EXPIRED', 'N/A')}`
│▸ 📍 *Pincode:* `{vehicle.get('PINCODE', 'N/A')}`
│▸ 🚘 *Probable Vehicle Type:* `{vehicle.get('VEHICLE_TYPE', 'N/A')}`
│▸ 📲 *Source App:* `{vehicle.get('SRC_APP', 'N/A')}`
│▸ 🛑 *Interstitial:* `{vehicle.get('INTERSTITIAL', 'N/A')}`
│▸ 👤 *User ID:* `{vehicle.get('USERID', 'N/A')}`
│▸ 📅 *Created At:* `{vehicle.get('CREATED_AT', 'N/A')}`
│▸ 📆 *Expiring Today:* `{vehicle.get('expiringtoday', 'N/A')}`
│▸ 📆 *Expiring in One Day:* `{vehicle.get('expiringinoneday', 'N/A')}`
│▸ 🚗 *Vehicle Type:* `{vehicle.get('VEHICLE_TYPE', 'N/A')}`
│▸ 🔒 *Is Logged:* `{vehicle.get('IS_LOGGED', 'N/A')}`
│▸ 📱 *App Open Count:* `{vehicle.get('APP_OPEN', 'N/A')}`
╰─────────({vehicle.get('NAME', 'N/A')})──────────⦿
        """
        keyboard = [
            [InlineKeyboardButton("🩵 SUBSCRIBE ON YT", url="https://www.youtube.com/@")],
            [InlineKeyboardButton("🔗 TELEGRAM CHANNEL", url="https://t.me/Mohd1like")],
            [InlineKeyboardButton("🔥  FREE FIRE LIKES", url="https://t.me/mohd1_aaqib")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(vehicle_message, parse_mode="Markdown", reply_markup=reply_markup)

    except Exception:
        await update.message.reply_text("⚠️ Đã xảy ra lỗi khi lấy thông tin. Vui lòng thử lại sau.")

# Main function to run the bot
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

    # Reset lúc 0:00 giờ Việt Nam (UTC+7)
    job_queue.run_daily(
    reset_handler,
    time=time(hour=17, minute=0))# 0:00 giờ Việt Nam là 17:00 UTC
# UTC+7 = 0:00 Việt Nam

    # Thêm các lệnh xử lý
    application.add_handler(CommandHandler("allow", allow_handler))
    application.add_handler(CommandHandler("check", check_handler))
    application.add_handler(CommandHan