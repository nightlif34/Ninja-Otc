import os
import logging
import string
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

AWAITING_TON_WALLET, AWAITING_BANK_CARD = range(2)
AWAITING_DEAL_AMOUNT, AWAITING_DEAL_DESCRIPTION = range(2, 4)

def generate_deal_id(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💼 Управление реквизитами", callback_data="manage_payment")],
        [InlineKeyboardButton("💸 Создать сделку", callback_data="create_deal")],
        [InlineKeyboardButton("🌐 Изменить язык", callback_data="change_language")],
        [InlineKeyboardButton("🧠 Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="main_menu")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_or_update_user(user.id, user.username)
    
    if context.args and len(context.args) > 0:
        deal_id = context.args[0]
        await handle_deal_join(update, context, deal_id)
        return
    
    welcome_text = (
        "👋 Добро пожаловать в Ninja OTC – надёжный P2P-гарант! 💼\n"
        "Покупайте и продавайте всё, что угодно – безопасно и быстро!\n"
        "От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска.\n\n"
        "⚙️ Что вас ждёт:\n"
        "🔹 Удобное управление реквизитами\n"
        "🔹 Реферальная система\n"
        "🔹 Безопасные сделки с гарантией\n\n"
        "👇 Выберите нужный раздел ниже"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())

async def handle_deal_join(update: Update, context: ContextTypes.DEFAULT_TYPE, deal_id: str):
    deal = db.get_deal(deal_id)
    
    if not deal:
        await update.message.reply_text("❌ Сделка не найдена.")
        return
    
    buyer = update.effective_user
    db.create_or_update_user(buyer.id, buyer.username)
    
    if buyer.id == deal['seller_id']:
        await update.message.reply_text("❌ Вы не можете присоединиться к своей собственной сделке.")
        return
    
    if deal['buyer_id'] is not None and deal['buyer_id'] != buyer.id:
        await update.message.reply_text("❌ К этой сделке уже присоединился другой покупатель.")
        return
    
    if deal['buyer_id'] is None:
        db.set_deal_buyer(deal_id, buyer.id)
    
    seller = db.get_user(deal['seller_id'])
    seller_username = f"@{seller['username']}" if seller['username'] else f"ID {seller['user_id']}"
    
    buyer_user = db.get_user(buyer.id)
    buyer_deals = buyer_user['successful_deals'] if buyer_user else 0
    
    deal_info = (
        f"💳 Информация о сделке #{deal_id}\n"
        f"👤 Вы покупатель в сделке.\n"
        f"📌 Продавец: {seller_username} (ID {deal['seller_id']})\n"
        f"• Успешные сделки: {seller['successful_deals']}\n"
        f"• Вы покупаете: {deal['description']}\n"
        f"🏦 Адрес для оплаты: {deal['payment_address']}\n"
        f"💰 Сумма к оплате: {deal['amount']} {deal['payment_type']}\n"
        f"📝 Комментарий к платежу (мемо): `{deal_id}` (можно скопировать)\n\n"
        f"⚠️ Пожалуйста, убедитесь в правильности данных перед оплатой.\n"
        f"Комментарий (мемо) обязателен!"
    )
    
    keyboard = [[InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_payment_{deal_id}")]]
    
    await update.message.reply_text(deal_info, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    buyer_username = f"@{buyer.username}" if buyer.username else f"ID {buyer.id}"
    seller_notification = (
        f"Пользователь {buyer_username} присоединился к сделке #{deal_id}\n"
        f"- Успешные сделки: {buyer_deals}\n"
        f"⚠️ Проверьте, что это тот же пользователь, с которым вы вели диалог ранее! "
        f"Не переводите подарок до получения подтверждения оплаты в этом чате!"
    )
    
    try:
        await context.bot.send_message(chat_id=deal['seller_id'], text=seller_notification)
    except Exception as e:
        logger.error(f"Failed to notify seller: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        await show_main_menu(update, context)
    elif query.data == "manage_payment":
        await show_payment_management(update, context)
    elif query.data == "create_deal":
        await show_deal_creation(update, context)
    elif query.data == "change_language":
        await show_language_change(update, context)
    elif query.data == "support":
        await show_support(update, context)
    elif query.data == "add_ton_wallet":
        await request_ton_wallet(update, context)
    elif query.data == "add_bank_card":
        await request_bank_card(update, context)
    elif query.data.startswith("deal_type_"):
        await handle_deal_type_selection(update, context)
    elif query.data.startswith("confirm_payment_"):
        await handle_payment_confirmation_button(update, context)
    elif query.data.startswith("confirm_receipt_"):
        await handle_receipt_confirmation(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    welcome_text = (
        "👋 Добро пожаловать в Ninja OTC – надёжный P2P-гарант! 💼\n"
        "Покупайте и продавайте всё, что угодно – безопасно и быстро!\n"
        "От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска.\n\n"
        "⚙️ Что вас ждёт:\n"
        "🔹 Удобное управление реквизитами\n"
        "🔹 Реферальная система\n"
        "🔹 Безопасные сделки с гарантией\n\n"
        "👇 Выберите нужный раздел ниже"
    )
    
    await query.edit_message_text(welcome_text, reply_markup=get_main_menu_keyboard())

async def show_payment_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = db.get_user(query.from_user.id)
    
    ton_wallet = user['ton_wallet'] if user and user['ton_wallet'] else "не указан"
    bank_card = user['bank_card'] if user and user['bank_card'] else "не указана"
    
    text = (
        "💼 Управление реквизитами\n\n"
        f"TON-кошелёк: {ton_wallet}\n"
        f"Банковская карта: {bank_card}"
    )
    
    keyboard = [
        [InlineKeyboardButton("Добавить/изменить TON-кошелёк", callback_data="add_ton_wallet")],
        [InlineKeyboardButton("Добавить/изменить карту", callback_data="add_bank_card")],
        [InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def request_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['awaiting'] = 'ton_wallet'
    await query.edit_message_text(
        "Пожалуйста, введите ваш TON-кошелёк:",
        reply_markup=get_back_button()
    )

async def request_bank_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['awaiting'] = 'bank_card'
    await query.edit_message_text(
        "Пожалуйста, введите вашу банковскую карту:",
        reply_markup=get_back_button()
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if 'awaiting' in context.user_data:
        awaiting_type = context.user_data['awaiting']
        
        if awaiting_type == 'ton_wallet':
            db.update_user_payment_details(user_id, ton_wallet=text)
            await update.message.reply_text(
                "✅ TON-кошелёк успешно сохранён!",
                reply_markup=get_back_button()
            )
            del context.user_data['awaiting']
        
        elif awaiting_type == 'bank_card':
            db.update_user_payment_details(user_id, bank_card=text)
            await update.message.reply_text(
                "✅ Банковская карта успешно сохранена!",
                reply_markup=get_back_button()
            )
            del context.user_data['awaiting']
        
        elif awaiting_type == 'deal_amount':
            context.user_data['deal_amount'] = text
            context.user_data['awaiting'] = 'deal_description'
            await update.message.reply_text(
                "Пожалуйста, введите описание товара/подарка:",
                reply_markup=get_back_button()
            )
        
        elif awaiting_type == 'deal_description':
            description = text
            amount = context.user_data.get('deal_amount')
            deal_type = context.user_data.get('deal_type')
            
            if not amount or not description:
                await update.message.reply_text(
                    "❌ Ошибка создания сделки. Попробуйте снова.",
                    reply_markup=get_back_button()
                )
                del context.user_data['awaiting']
                return
            
            user = db.get_user(user_id)
            
            if deal_type == 'ton':
                payment_address = user['ton_wallet'] if user and user['ton_wallet'] else None
                payment_type = "TON"
            elif deal_type == 'card':
                payment_address = user['bank_card'] if user and user['bank_card'] else None
                payment_type = "RUB"
            elif deal_type == 'stars':
                payment_address = user['ton_wallet'] if user and user['ton_wallet'] else None
                payment_type = "Stars"
            else:
                payment_address = None
                payment_type = "Unknown"
            
            if not payment_address:
                await update.message.reply_text(
                    f"❌ Сначала добавьте реквизиты для оплаты в разделе 'Управление реквизитами'.",
                    reply_markup=get_back_button()
                )
                del context.user_data['awaiting']
                return
            
            deal_id = generate_deal_id()
            max_retries = 5
            created = False
            
            for _ in range(max_retries):
                if db.create_deal(deal_id, user_id, amount, description, payment_type, payment_address):
                    created = True
                    break
                deal_id = generate_deal_id()
            
            if not created:
                await update.message.reply_text(
                    "❌ Ошибка создания сделки. Попробуйте снова позже.",
                    reply_markup=get_back_button()
                )
                del context.user_data['awaiting']
                return
            
            deal_link = f"https://t.me/NinjaOTCRobot?start={deal_id}"
            
            await update.message.reply_text(
                f"✅ Сделка создана!\n\n"
                f"ID сделки: #{deal_id}\n"
                f"Тип: {payment_type}\n"
                f"Сумма: {amount}\n"
                f"Описание: {description}\n\n"
                f"Ссылка для покупателя:\n{deal_link}",
                reply_markup=get_back_button()
            )
            
            del context.user_data['awaiting']
            del context.user_data['deal_amount']
            del context.user_data['deal_type']

async def show_deal_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("На TON-кошелёк", callback_data="deal_type_ton")],
        [InlineKeyboardButton("На карту", callback_data="deal_type_card")],
        [InlineKeyboardButton("На Stars", callback_data="deal_type_stars")],
        [InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "💸 Создание сделки\n\nВыберите тип сделки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_deal_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    deal_type = query.data.replace("deal_type_", "")
    
    context.user_data['deal_type'] = deal_type
    context.user_data['awaiting'] = 'deal_amount'
    
    await query.edit_message_text(
        "Пожалуйста, введите сумму:",
        reply_markup=get_back_button()
    )

async def show_language_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "🌐 Изменение языка\n\nВ настоящее время доступен только русский язык.",
        reply_markup=get_back_button()
    )

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "🧠 Поддержка\n\nНапишите нам: @SupCryptOtcRobot",
        reply_markup=get_back_button()
    )

async def handle_payment_confirmation_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⚠️ Оплата не найдена", show_alert=True)

async def handle_receipt_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    deal_id = query.data.replace("confirm_receipt_", "")
    
    deal = db.get_deal(deal_id)
    if not deal:
        await query.answer("❌ Сделка не найдена")
        return
    
    if deal['buyer_id'] != query.from_user.id:
        await query.answer("❌ Только покупатель может подтвердить получение", show_alert=True)
        return
    
    if deal['status'] != 'payment_confirmed':
        await query.answer("❌ Оплата ещё не подтверждена", show_alert=True)
        return
    
    db.complete_deal(deal_id)
    
    await query.edit_message_text(
        f"✅ Вы подтвердили получение товара. Сделка #{deal_id} завершена."
    )
    
    try:
        await context.bot.send_message(
            chat_id=deal['seller_id'],
            text=f"✅ Покупатель подтвердил получение товара. Сделка #{deal_id} успешно завершена."
        )
    except Exception as e:
        logger.error(f"Failed to notify seller: {e}")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_admin_or_higher(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Использование: /buy <deal_id>")
        return
    
    deal_id = context.args[0]
    deal = db.get_deal(deal_id)
    
    if not deal:
        await update.message.reply_text(f"❌ Сделка #{deal_id} не найдена.")
        return
    
    db.confirm_payment(deal_id)
    
    await update.message.reply_text(f"✅ Оплата по сделке #{deal_id} подтверждена.")
    
    try:
        buyer_id = deal['buyer_id']
        await context.bot.send_message(
            chat_id=deal['seller_id'],
            text=f"✅ Оплата по сделке #{deal_id} подтверждена. Можете отправить товар покупателю."
        )
        
        if buyer_id:
            keyboard = [[InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"confirm_receipt_{deal_id}")]]
            await context.bot.send_message(
                chat_id=buyer_id,
                text=f"✅ Оплата подтверждена! Ожидайте получения товара по сделке #{deal_id}.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Failed to send notifications: {e}")

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Только владельцы могут добавлять администраторов.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Использование: /add admin <user_id>")
        return
    
    if context.args[0] != "admin":
        await update.message.reply_text("❌ Использование: /add admin <user_id>")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /add admin <user_id>")
        return
    
    try:
        admin_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
        return
    
    if db.add_admin(admin_id, user_id):
        await update.message.reply_text(f"✅ Пользователь {admin_id} добавлен в администраторы.")
    else:
        await update.message.reply_text(f"❌ Пользователь {admin_id} уже является администратором.")

async def del_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Только владельцы могут удалять администраторов.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Использование: /del admin <user_id>")
        return
    
    if context.args[0] != "admin":
        await update.message.reply_text("❌ Использование: /del admin <user_id>")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /del admin <user_id>")
        return
    
    try:
        admin_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя.")
        return
    
    if db.is_owner(admin_id):
        await update.message.reply_text("❌ Нельзя удалить владельца.")
        return
    
    if db.remove_admin(admin_id):
        await update.message.reply_text(f"✅ Пользователь {admin_id} удалён из администраторов.")
    else:
        await update.message.reply_text(f"❌ Пользователь {admin_id} не является администратором.")

async def set_my_deals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Только владельцы могут устанавливать количество сделок.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Использование: /set_my_deals <число>")
        return
    
    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверное число.")
        return
    
    if count < 0:
        await update.message.reply_text("❌ Число должно быть положительным.")
        return
    
    db.create_or_update_user(user_id, update.effective_user.username)
    
    if db.set_user_successful_deals(user_id, count):
        await update.message.reply_text(f"✅ Количество успешных сделок установлено: {count}")
    else:
        await update.message.reply_text("❌ Ошибка при обновлении данных.")

async def show_deals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Только владельцы могут просматривать все сделки.")
        return
    
    deals = db.get_all_deals()
    
    if not deals:
        await update.message.reply_text("📋 Сделок пока нет.")
        return
    
    text = "📋 Все сделки:\n\n"
    
    for deal in deals[:20]:
        seller = db.get_user(deal['seller_id'])
        seller_username = f"@{seller['username']}" if seller and seller['username'] else f"ID {deal['seller_id']}"
        
        buyer_username = "не присоединился"
        if deal['buyer_id']:
            buyer = db.get_user(deal['buyer_id'])
            buyer_username = f"@{buyer['username']}" if buyer and buyer['username'] else f"ID {deal['buyer_id']}"
        
        status_map = {
            'pending': 'ожидание',
            'payment_confirmed': 'оплата подтверждена',
            'completed': 'завершено'
        }
        status = status_map.get(deal['status'], deal['status'])
        
        text += f"Сделка #{deal['deal_id']}\n"
        text += f"Продавец: {seller_username}\n"
        text += f"Покупатель: {buyer_username}\n"
        text += f"Сумма: {deal['amount']} {deal['payment_type']}\n"
        text += f"Статус: {status}\n\n"
    
    if len(deals) > 20:
        text += f"... и ещё {len(deals) - 20} сделок"
    
    await update.message.reply_text(text)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        print("❌ Ошибка: Переменная окружения TELEGRAM_BOT_TOKEN не установлена!")
        print("Пожалуйста, добавьте токен вашего Telegram бота в Secrets.")
        return
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("add", add_admin_command))
    application.add_handler(CommandHandler("del", del_admin_command))
    application.add_handler(CommandHandler("set_my_deals", set_my_deals_command))
    application.add_handler(CommandHandler("show_deals", show_deals_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("Bot started successfully!")
    print("✅ Бот Ninja OTC запущен успешно!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
