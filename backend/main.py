import asyncio
import aiohttp
import logging
from datetime import datetime, time, timedelta
import pytz
from backend.config import API_BASE, BOT_TOKEN
from backend.database import init_db
from backend.handlers import handle_update
from backend.export import export_to_excel  # Импортируем твою функцию экспорта

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def auto_export_scheduler():
    """
    Фоновая задача: проверяет время каждый час и запускает экспорт ровно в 09:00.
    Это проще и надежнее для твоего цикла while True, чем ставить APScheduler.
    """
    logger.info("Планировщик автоэкспорта запущен...")
    
    moscow_tz = pytz.timezone('Europe/Moscow')  # создаём часовой пояс один раз
    target_time = time(9, 0)                   # время запуска (09:00 по Москве)
    
    while True:
        # Получаем текущее время именно по Москве
        now = datetime.now(moscow_tz).time()
        
        if now.hour == target_time.hour and now.minute == target_time.minute:
            logger.info(f"Время автоэкспорта наступило (МСК): {now}")
            
            task = asyncio.create_task(run_export_safe())
            await task
            
            # Ждём минуту, чтобы не запустить дважды в одну и ту же минуту
            await asyncio.sleep(60) 
        else:
            # Спим 30 секунд между проверками
            await asyncio.sleep(30)

async def run_export_safe():
    """Обертка для безопасного запуска экспорта"""
    try:
        filename, yd_path = await export_to_excel()
        if filename:
            logger.info(f"[АВТОЭКСПОРТ] Файл создан: {filename}, загружен на Яндекс Диск: {yd_path}")
        else:
            logger.warning("[АВТОЭКСПОРТ] Нет данных для экспорта.")
    except Exception as e:
        logger.error(f"[АВТОЭКСПОРТ] Критическая ошибка: {e}", exc_info=True)

async def main():
    try:
        # 1. Инициализация базы данных
        logger.info("Инициализация базы данных")
        await init_db()
        
        # 2. ЗАПУСК АВТОЭКСПОРТА (в фоне!)
        # Эта задача будет работать параллельно с опросом обновлений
        asyncio.create_task(auto_export_scheduler())
        logger.info("Фоновая задача автоэкспорта запущена.")

        # 3. Запуск основного цикла бота (опрос обновлений)
        logger.info("Бот запущен. Начинаю опрос обновлений...")
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            marker = None
            while True:
                try:
                    params = {"limit": 100, "timeout": 30}
                    if marker:
                        params["marker"] = marker

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
                                await handle_update(session, update)
                            except Exception as e:
                                logger.error(f"Ошибка обработки обновления: {str(e)}")

                        if data.get("marker"):
                            marker = data["marker"]

                except asyncio.TimeoutError:
                    logger.warning("Произошел таймаут при получении обновлений")
                    continue
                except Exception as e:
                    logger.error(f"Критическая ошибка цикла опроса: {str(e)}")
                    await asyncio.sleep(5)

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {str(e)}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка запуска: {str(e)}")
