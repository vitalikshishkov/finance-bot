import asyncio
import aiohttp
import logging

from config import API_BASE, BOT_TOKEN
from database import init_db
from handlers import handle_update

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def main():
    try:
        # Инициализация базы данных
        logging.info("Инициализация базы данных")
        await init_db()
        
        # Запуск бота
        logging.info("Бот запущен")
        
        # Убираем автоматический экспорт
        # export_to_excel()  # Если такая строка есть - закомментируйте её
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            marker = None
            while True:
                try:
                    params = {"limit": 100, "timeout": 30}
                    if marker:
                        params["marker"] = marker

                    logging.info("Получение обновлений")
                    async with session.get(
                        f"{API_BASE}/updates",
                        headers={"Authorization": BOT_TOKEN},
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=35)
                    ) as resp:
                        data = await resp.json()
                        updates = data.get("updates", [])

                        for update in updates:
                            try:
                                logging.debug(f"Обработка обновления: {update}")
                                await handle_update(session, update)
                            except Exception as e:
                                logging.error(f"Ошибка обработки обновления: {str(e)}")

                        if data.get("marker"):
                            marker = data["marker"]

                except asyncio.TimeoutError:
                    logging.warning("Произошел таймаут при получении обновлений")
                    continue
                except Exception as e:
                    logging.error(f"Критическая ошибка: {str(e)}")
                    await asyncio.sleep(5)

    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Ошибка при запуске: {str(e)}")
