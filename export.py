import logging
import os
from datetime import datetime
from openpyxl import Workbook
import yadisk

from config import YADISK_TOKEN
from database import get_all_records

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def export_to_excel():
    logging.info("Начинаем процесс экспорта данных")
    
    try:
        rows = await get_all_records()
        if not rows:
            logging.warning("Нет данных для экспорта")
            return None, "Нет данных для экспорта."

        logging.info("Создаем файл Excel")
        wb = Workbook()
        ws = wb.active
        ws.title = "Финансовые записи"
        headers = ["ID польз.", "Имя пользователя", "Год", "Месяц", "День", "Время",
                  "Тип", "Сумма", "Контрагент", "Способ оплаты", "Комментарий"]
        ws.append(headers)

        for row in rows:
            dt = row["created_at"] or ""
            parts = dt.split(" ")
            date_parts = parts[0].split("-") if parts[0] else ["", "", ""]
            time_part = parts[1] if len(parts) > 1 else ""

            ws.append([
                row["user_id"],
                row["username"] or "",
                date_parts[0],
                date_parts[1],
                date_parts[2],
                time_part,
                "Доход" if row["type"] == "income" else "Расход",
                row["amount"],
                row["counterparty"] or "",
                row["payment_method"] or "",
                row["comment"] or ""
            ])

        logging.info("Форматируем столбцы")
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_len + 2

        filename = f"export_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)
        logging.info(f"Файл сохранен локально: {filename}")

        yd_path = None
        if YADISK_TOKEN and YADISK_TOKEN != "ВАШ_ТОКЕН_ЯНДЕКС_ДИСКА":
            try:
                logging.info("Начинаем загрузку на Яндекс Диск")
                client = yadisk.Client(token=YADISK_TOKEN)
                with client:
                    if not client.exists("/finance_bot_exports"):
                        client.mkdir("/finance_bot_exports")
                    yd_path = f"/finance_bot_exports/{filename}"
                    client.upload(filename, yd_path, overwrite=True)
                    logging.info(f"Файл загружен на Яндекс Диск: {yd_path}")
            except Exception as e:
                logging.error(f"Ошибка загрузки на Яндекс Диск: {str(e)}")
                yd_path = None

        if os.path.exists(filename):
            os.remove(filename)
            logging.info(f"Локальный файл {filename} удален")

        return filename, yd_path

    except Exception as e:
        logging.error(f"Произошла ошибка при экспорте: {str(e)}")
        return None, f"Ошибка при экспорте данных: {str(e)}"
