import aiohttp
from config import API_BASE, BOT_TOKEN

async def send_message(session, user_id, text, buttons=None):
    payload = {"text": text}
    if buttons:
        payload["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": buttons}
            }
        ]

    try:
        async with session.post(
            f"{API_BASE}/messages",
            headers={"Authorization": BOT_TOKEN, "Content-Type": "application/json"},
            params={"user_id": user_id},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            result = await resp.json()
            print(f"send_message: статус={resp.status}, ответ={result}")
            return result
    except Exception as e:
        print(f"send_message ОШИБКА: {e}")
        return None
