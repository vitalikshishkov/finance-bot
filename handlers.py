from database import (
    is_authorized, is_admin, add_user, remove_user, make_admin,
    list_users, save_record, get_state, set_state, clear_state,
    clear_records, get_all_today_records, get_last_3days_records,
    get_today_totals, update_username,
)

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

import locale
from datetime import datetime, timedelta

# УБРАЛИ answer_callback из импорта — это было причиной ImportError
from max_api import send_message
from keyboards import main_menu_buttons, admin_menu_buttons
from export import export_to_excel

# Устанавливаем русскую локаль
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')


async def show_records(session, chat_id, user_id):
    rows = await get_last_3days_records()
    logging.info("Локальное сейчас: %s", datetime.now())
    logging.info("UTC сейчас: %s", datetime.utcnow())

    for r in rows:
        logging.info(
            "Запись: created_at=%s, parsed_date=%s",
            r["created_at"],
            (r["created_at"] or "").split(" ")[0]
        )

    if not rows:
        await send_message(session, user_id, "📋 Записей за последние 3 дня нет.", main_menu_buttons())
        return

    # Группируем записи по датам
    days = {}
    today = datetime.now().strftime("%Y-%m-%d")
    for r in rows:
        date = (r["created_at"] or "").split(" ")[0]
        if date not in days:
            days[date] = []
        days[date].append(r)

    text = "📋 Записи за последние 3 дня:\n\n"
    for date in sorted(days.keys(), reverse=True):
        date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y (%A)")
        day_label = "СЕГОДНЯ" if date == today else date_display.upper()
        text += f"📅 {day_label}:\n\n"

        day_income = day_expense = 0
        income_lines = []
        expense_lines = []

        for r in days[date]:
            author = f"@{r['username']}" if r["username"] else f"ID:{r['user_id']}"

            if r["type"] == "income":
                day_income += r["amount"]
                time_id_line = f"  ⏰ {r['created_at'][11:]} | {author}"
                main_line = f"  💰 +{r['amount']:,} ₽".replace(",", " ")
                if r["comment"]:
                    main_line += f" | {r['comment']}"
                income_lines.append(f"{time_id_line}\n{main_line}\n")

            else:
                day_expense += r["amount"]
                time_id_line = f"  ⏰ {r['created_at'][11:]} | {author}"
                main_line = f"  💸 -{r['amount']:,} ₽".replace(",", " ")
                parts = []
                if r["counterparty"]:
                    parts.append(r["counterparty"])
                if r["payment_method"]:
                    parts.append(r["payment_method"])
                if r["comment"]:
                    parts.append(r["comment"])
                if parts:
                    main_line += " | " + " · ".join(parts)
                expense_lines.append(f"{time_id_line}\n{main_line}\n\n")

        if income_lines:
            text += "💰 ДОХОДЫ:\n"
            text += "".join(income_lines)

        if income_lines and expense_lines:
            text += "────────────────────\n"
        elif income_lines or expense_lines:
            text += "────────────────────\n"

        if expense_lines:
            text += "💸 РАСХОДЫ:\n"
            text += "".join(expense_lines)

        text += f"  Итог за день: +{day_income:,} ₽ / -{day_expense:,} ₽\n\n\n".replace(",", " ")

    today_income, today_expense = await get_today_totals()
    balance = today_income - today_expense
    sign = "+" if balance >= 0 else ""
    text += f"📊 Profit за сегодня: {sign}{balance:,} ₽\n".replace(",", " ")
    text += f"   Доходы: {today_income:,} ₽ | Расходы: {today_expense:,} ₽\n".replace(",", " ")

    await send_message(session, user_id, text, main_menu_buttons())


# Вспомогательная функция для callback (можно оставить, если используешь отдельно)
async def handle_callback(session, payload, user_id, chat_id):
    if payload == "view":
        await show_records(session, chat_id, user_id)


async def admin_list_users(session, chat_id, user_id):
    users = await list_users()
    if not users:
        await send_message(session, user_id, "Список пуст.")
        return
    text = "📋 Пользователи бота:\n\n"
    for u in users:
        crown = " 👑" if u["is_admin"] else ""
        name = u["username"] or ""
        text += f"• ID: {u['user_id']}{crown}"
        if name:
            text += f" | @{name}"
        text += "\n"
    await send_message(session, user_id, text, admin_menu_buttons())


async def handle_update(session, update):
    update_type = update.get("update_type", "")
    print(f"Получен update: {update_type}")

    # --- Запуск бота (кнопка "Начать пользоваться") ---
    if update_type == "bot_started":
        msg = update.get("message", {}) or update.get("payload", {}) or {}
        recipient = msg.get("recipient", {}) if isinstance(msg, dict) else {}
        sender = update.get("user", {}) or msg.get("sender", {}) if isinstance(msg, dict) else {}
        chat_id = recipient.get("chat_id")
        user_id = sender.get("user_id", chat_id)

        print(f"bot_started: user_id={user_id}, chat_id={chat_id}")

        if not await is_authorized(user_id):
            await send_message(session, user_id,
                f"⛔ Нет доступа.\n\nВаш ID: {user_id}\n"
                "Обратитесь к админу, чтобы вас добавили."
            )
            return

        admin = await is_admin(user_id)
        await clear_state(user_id)
        buttons = main_menu_buttons()
        if admin:
            buttons.append([{"type": "callback", "text": "🔧 Админ-панель", "payload": "admin"}])
        await send_message(session, user_id,
            "Привет! Я бот учёта доходов и расходов.\nВыберите действие:", buttons)
        return

    # --- Callback (нажатие кнопки) ---
    if update_type == "message_callback":
        cb = update.get("callback", {})
        callback_id = cb.get("callback_id")
        payload = cb.get("payload", "")
        user = cb.get("user", {})
        user_id = user.get("user_id")
        msg = update.get("message", {})
        recipient = msg.get("recipient", {})
        chat_id = recipient.get("chat_id")

        print(f"Callback: payload={payload}, user_id={user_id}, chat_id={chat_id}")

        # ВАЖНО: сначала проверка прав. Убрали преждевременный send_message, который вызывал ошибку
        if not await is_authorized(user_id):
            await send_message(session, user_id,
                f"⛔ Нет доступа.\n\nВаш ID: {user_id}\n"
                "Обратитесь к админу, чтобы вас добавили."
            )
            return

        admin = await is_admin(user_id)

        if payload == "income":
            await set_state(user_id, "income_amount")
            await send_message(session, user_id, "💰 Введите сумму дохода:")

        elif payload == "expense":
            await set_state(user_id, "expense_counterparty")
            await send_message(session, user_id, "💸 Введите имя КОНТРАГЕНТА:")

        elif payload == "expense_cash":
            _, data = await get_state(user_id)
            data["payment_method"] = "Нал"
            await set_state(user_id, "expense_comment", data)
            await send_message(session, user_id, "Введите комментарий (или «-» если нет):")

        elif payload == "expense_card":
            _, data = await get_state(user_id)
            data["payment_method"] = "Безнал"
            await set_state(user_id, "expense_comment", data)
            await send_message(session, user_id, "Введите комментарий (или «-» если нет):")

        elif payload == "menu":
            await clear_state(user_id)
            buttons = main_menu_buttons()
            if admin:
                buttons.append([{"type": "callback", "text": "🔧 Админ-панель", "payload": "admin"}])
            await send_message(session, user_id, "Выберите действие:", buttons)

        elif payload == "view":
            await show_records(session, chat_id, user_id)

        elif payload == "export":
            filename, yd_path = await export_to_excel()
            if filename is None:
                await send_message(session, user_id, yd_path)
            elif yd_path:
                await send_message(session, user_id,
                    f"Файл экспортирован!\nЯндекс Диск: {yd_path}", main_menu_buttons())
            else:
                await send_message(session, user_id,
                    f"Файл сохранён локально: {filename}", main_menu_buttons())

        # --- Админ-панель ---
        elif payload == "admin" and admin:
            await clear_state(user_id)
            await send_message(session, user_id, "🔧 Админ-панель:", admin_menu_buttons())

        elif payload == "admin_add" and admin:
            await set_state(user_id, "admin_add_user")
            await send_message(session, user_id,
                "Введите ID пользователя для добавления.\n"
                "Пользователь должен сначала написать боту /start — "
                "тогда бот покажет ему его ID.")

        elif payload == "admin_remove" and admin:
            await set_state(user_id, "admin_remove_user")
            await send_message(session, user_id, "Введите ID пользователя для удаления:")

        elif payload == "admin_makeadmin" and admin:
            await set_state(user_id, "admin_make_admin")
            await send_message(session, user_id, "Введите ID пользователя, которого сделать админом:")

        elif payload == "admin_clear" and admin:
            await set_state(user_id, "admin_clear_confirm")
            await send_message(session, user_id,
                "⚠️ Очистить ВСЕ записи в базе?\n\n"
                "Напишите «ДА» для подтверждения или нажмите кнопку для отмены.",
                [[{"type": "callback", "text": "⬅️ Отмена", "payload": "admin"}]])

        elif payload == "admin_list" and admin:
            await admin_list_users(session, chat_id, user_id)

    # --- Текстовые сообщения ---
    elif update_type == "message_created":
        msg = update.get("message", {})
        recipient = msg.get("recipient", {})
        sender = msg.get("sender", {})
        chat_id = recipient.get("chat_id")
        user_id = sender.get("user_id", chat_id)
        text = (msg.get("body") or {}).get("text", "").strip()
        username = (msg.get("sender") or {}).get("username", "")

        print(f"Сообщение от user_id={user_id}, chat_id={chat_id}, text={text}")

        auth = await is_authorized(user_id)
        print(f"Авторизован: {auth}")

        if not auth:
            await send_message(session, user_id,
                f"⛔ Нет доступа.\n\nВаш ID: {user_id}\n"
                "Обратитесь к админу, чтобы вас добавили."
            )
            return

        await update_username(user_id, username)

        admin = await is_admin(user_id)
        state, data = await get_state(user_id)
        print(f"State: {state}, Admin: {admin}")

        if text == "/start":
            await clear_state(user_id)
            buttons = main_menu_buttons()
            if admin:
                buttons.append([{"type": "callback", "text": "🔧 Админ-панель", "payload": "admin"}])
            await send_message(session, user_id,
                "Привет! Я бот учёта доходов и расходов.\nВыберите действие:", buttons)
            return

        # --- Админ: добавление пользователя ---
        if state == "admin_add_user" and admin:
            try:
                new_id = int(text.strip())
            except ValueError:
                await send_message(session, user_id, "Нужно число. Введите ID:")
                return
            await add_user(new_id, "", user_id)
            await clear_state(user_id)
            await send_message(session, user_id,
                f"✅ Пользователь {new_id} добавлен!", admin_menu_buttons())

        # --- Админ: удаление пользователя ---
        elif state == "admin_remove_user" and admin:
            try:
                target_id = int(text.strip())
            except ValueError:
                await send_message(session, user_id, "Нужно число. Введите ID:")
                return
            removed = await remove_user(target_id)
            await clear_state(user_id)
            if removed:
                await send_message(session, user_id,
                    f"✅ Пользователь {target_id} удалён.", admin_menu_buttons())
            else:
                await send_message(session, user_id,
                    f"Не удалось удалить. Возможно, ID не найден или это админ.",
                    admin_menu_buttons())

        # --- Админ: назначение админа ---
        elif state == "admin_make_admin" and admin:
            try:
                target_id = int(text.strip())
            except ValueError:
                await send_message(session, user_id, "Нужно число. Введите ID:")
                return
            await add_user(target_id, "", user_id)
            await make_admin(target_id)
            await clear_state(user_id)
            await send_message(session, user_id,
                f"✅ Пользователь {target_id} теперь админ!", admin_menu_buttons())

        # --- Админ: очистка записей ---
        elif state == "admin_clear_confirm" and admin:
            if text.upper() == "ДА":
                count = await clear_records()
                await clear_state(user_id)
                await send_message(session, user_id,
                    f"🧹 Удалено записей: {count}", admin_menu_buttons())
            else:
                await clear_state(user_id)
                await send_message(session, user_id,
                    "Очистка отменена.", admin_menu_buttons())
                
        # --- Доходы ---
        elif state == "income_amount":
            try:
                amount = float(text.replace(",", ".").replace(" ", ""))
            except ValueError:
                await send_message(session, user_id, "Введите число, например: 5000")
                return
            data["amount"] = amount
            await set_state(user_id, "income_comment", data)
            await send_message(session, user_id, "Введите комментарий (или «-» если нет):")

        elif state == "income_comment":
            comment = "" if text == "-" else text
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"Сохраняем запись: {current_time}")
            await save_record({
                "type": "income", "amount": data["amount"],
                "counterparty": None, "payment_method": None,
                "comment": comment, "user_id": user_id,
                "created_at": current_time
            })
            await clear_state(user_id)
            await send_message(session, user_id,
                f"✅ Доход {data['amount']} ₽ записан!", main_menu_buttons())

        # --- Расходы ---
        elif state == "expense_counterparty":
            check = text.replace(" ", "").replace("-", "").replace(".", "")
            if not check.isalpha():
                await send_message(session, user_id,
                    "❌ Имя контрагента должно содержать только буквы.\n"
                    "Введите имя контрагента:")
                return
            data["counterparty"] = text
            await set_state(user_id, "expense_amount", data)
            await send_message(session, user_id, "Введите сумму расхода:")

        elif state == "expense_amount":
            try:
                amount = float(text.replace(",", ".").replace(" ", ""))
            except ValueError:
                await send_message(session, user_id, "Введите число, например: 1500")
                return
            data["amount"] = amount
            await set_state(user_id, "expense_payment", data)
            await send_message(session, user_id, "Выберите способ оплаты:", [[
                {"type": "callback", "text": "💵 Наличные", "payload": "expense_cash"},
                {"type": "callback", "text": "💳 Безнал", "payload": "expense_card"}
            ]])

        elif state == "expense_comment":
            comment = "" if text == "-" else text
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"Сохраняем запись: {current_time}")
            await save_record({
                "type": "expense", "amount": data["amount"],
                "counterparty": data.get("counterparty"),
                "payment_method": data.get("payment_method"),
                "comment": comment, "user_id": user_id,
                "created_at": current_time
            })
            await clear_state(user_id)
            await send_message(session, user_id,
                f"✅ Расход {data['amount']} ₽ ({data.get('payment_method')}) записан!",
                main_menu_buttons())
