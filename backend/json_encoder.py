import json
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID

class CustomJSONEncoder(json.JSONEncoder):
    """Кастомный JSON Encoder для обработки специальных типов"""

    def default(self, obj):
        # Обработка даты и времени
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.strftime('%H:%M:%S')
        # Обработка Decimal
        elif isinstance(obj, Decimal):
            return float(obj)
        # Обработка UUID
        elif isinstance(obj, UUID):
            return str(obj)
        # Обработка bytes
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        # Вызов родительского метода для остальных типов
        return super().default(obj)
