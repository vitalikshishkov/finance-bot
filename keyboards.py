def main_menu_buttons():
    return [[
        {"type": "callback", "text": "💰 Доходы", "payload": "income"},
        {"type": "callback", "text": "💸 Расходы", "payload": "expense"}
    ], [
        {"type": "callback", "text": "📊 Свод", "payload": "view"},
        {"type": "callback", "text": "📤 Экспорт в Excel", "payload": "export"}
    ]]


def admin_menu_buttons():
    return [[
        {"type": "callback", "text": "➕ Добавить пользователя", "payload": "admin_add"},
        {"type": "callback", "text": "🗑 Удалить пользователя", "payload": "admin_remove"},
    ], [
        {"type": "callback", "text": "👑 Сделать админом", "payload": "admin_makeadmin"},
        {"type": "callback", "text": "📋 Список пользователей", "payload": "admin_list"},
    ], [
        {"type": "callback", "text": "⬅️ В главное меню", "payload": "menu"},
    ]]

def admin_menu_buttons():
    return [[
        {"type": "callback", "text": "➕ Добавить пользователя", "payload": "admin_add"},
        {"type": "callback", "text": "🗑 Удалить пользователя", "payload": "admin_remove"},
    ], [
        {"type": "callback", "text": "👑 Сделать админом", "payload": "admin_makeadmin"},
        {"type": "callback", "text": "📋 Список пользователей", "payload": "admin_list"},
    ], [
        {"type": "callback", "text": "🧹 Очистить записи", "payload": "admin_clear"},
    ], [
        {"type": "callback", "text": "⬅️ В главное меню", "payload": "menu"},
    ]]
