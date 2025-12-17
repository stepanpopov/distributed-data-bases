import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from datetime import time
from decimal import Decimal

logger = logging.getLogger(__name__)

class GuestService:
    """Сервис для работы с гостями"""

    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        """Преобразовать объект в сериализуемый формат для HTML"""
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.strftime('%H:%M:%S')
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif hasattr(obj, '__dict__'):
            return self._convert_to_serializable(dict(obj))
        return obj

    def create_guest(self, guest_data: Dict[str, Any], db_name: str = 'central') -> Dict[str, Any]:
        """Создать нового гостя"""
        try:
            first_name = guest_data.get('first_name', '')
            last_name = guest_data.get('last_name', '')
            phone_number = guest_data.get('phone_number')
            email = guest_data.get('email', '')
            birth_date = guest_data.get('birth_date', '2000-01-01')

            if not phone_number:
                return {'error': 'Phone number is required', 'status': 400}

            # Разбираем имя, если передано полное имя
            if guest_data.get('full_name') and not first_name and not last_name:
                name_parts = guest_data['full_name'].split()
                first_name = name_parts[0] if name_parts else 'Гость'
                last_name = name_parts[-1] if len(name_parts) > 1 else ''

            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    INSERT INTO guests (first_name, last_name, phone_number, email, birth_date)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (first_name, last_name, phone_number, email, birth_date))

                result = cursor.fetchone()
                if result:
                    guest_id = result['id']
                    logger.info(f"Created new guest with ID: {guest_id} in DB {db_name}")
                    return {
                        'success': True,
                        'guest_id': guest_id,
                        'message': 'Guest created successfully'
                    }
                else:
                    return {'error': 'Failed to create guest', 'status': 500}

        except Exception as e:
            logger.error(f"Error creating guest: {e}")
            return {'error': str(e), 'status': 500}

    def get_guest_details(self, guest_id: int, db_name: str = 'central') -> Optional[Dict]:
        """Получить информацию о госте"""
        try:
            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    SELECT * FROM guests WHERE id = %s
                """, (guest_id,))

                guest = cursor.fetchone()
                if guest:
                    guest_dict = dict(guest)
                    return self._convert_to_serializable(guest_dict)
                return None

        except Exception as e:
            logger.error(f"Error getting guest details: {e}")
            return None