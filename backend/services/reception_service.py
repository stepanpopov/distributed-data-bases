import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from datetime import time
from decimal import Decimal

logger = logging.getLogger(__name__)

class ReceptionService:
    """Сервис для работы ресепшена"""

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

    def get_cities_with_reservations_count(self) -> List[Dict]:
        """Получить список городов с количеством бронирований"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT DISTINCT c.city_name, COUNT(r.id) as reservations_count
                    FROM cities c
                    LEFT JOIN hotels h ON c.id = h.city_id
                    LEFT JOIN reservations r ON r.hotel_id = h.id AND r.status IN ('pending', 'confirmed')
                    GROUP BY c.id, c.city_name
                    ORDER BY c.city_name
                """)

                cities = cursor.fetchall()
                cities_list = []
                for city in cities:
                    city_dict = {
                        'city_name': city['city_name'],
                        'reservations_count': city['reservations_count']
                    }
                    cities_list.append(city_dict)

                return cities_list
        except Exception as e:
            logger.error(f"Error getting cities with reservations count: {e}")
            return []

    def get_city_reservations(self, city_name: str) -> List[Dict]:
        """Получить все бронирования города"""
        try:
            # Определяем филиальную БД для получения бронирований
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                db_name = db_mapping[city_name]
            else:
                db_name = 'central'

            # Получаем бронирования из соответствующей филиальной БД
            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    SELECT r.id, r.hotel_id, r.create_date, r.start_date, r.end_date,
                           r.status, r.total_price, r.payments_status, r.payer_id,
                           g.first_name, g.last_name, g.phone_number, g.email,
                           h.name as hotel_name,
                           dr.requested_room_category, dr.total_guest_number, dr.room_id,
                           cr.category_name,
                           COUNT(rrg.guest_id) as registered_guests_count
                    FROM reservations r
                    JOIN guests g ON r.payer_id = g.id
                    JOIN hotels h ON r.hotel_id = h.id
                    LEFT JOIN details_reservations dr ON dr.reservation_id = r.id
                    LEFT JOIN categories_room cr ON dr.requested_room_category = cr.id
                    LEFT JOIN room_reservation_guests rrg ON rrg.room_reservation_id = dr.id
                    WHERE r.status IN ('pending', 'confirmed')
                    GROUP BY r.id, r.hotel_id, r.create_date, r.start_date, r.end_date,
                             r.status, r.total_price, r.payments_status, r.payer_id,
                             g.first_name, g.last_name, g.phone_number, g.email,
                             h.name, dr.requested_room_category, dr.total_guest_number,
                             dr.room_id, cr.category_name
                    ORDER BY r.create_date DESC
                """)

                reservations = cursor.fetchall()

                # Конвертируем в нужный формат
                reservations_list = []
                for res in reservations:
                    res_dict = dict(res)
                    res_dict = self._convert_to_serializable(res_dict)
                    reservations_list.append(res_dict)

                return reservations_list

        except Exception as e:
            logger.error(f"Error getting city reservations for {city_name}: {e}")
            return []

    def get_reservation_details_with_payment(self, reservation_id: int) -> Optional[Dict]:
        """Получить детали бронирования с информацией об оплате"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT r.*, g.first_name, g.last_name, g.phone_number, g.email,
                           g.document, g.loyalty_card_id, g.bonus_points,
                           h.name as hotel_name, h.city_id, c.city_name,
                           dr.requested_room_category, dr.total_guest_number, dr.room_id,
                           cr.category_name,
                           rm.room_number, rm.floor, rm.view,
                           (r.end_date - r.start_date) as nights
                    FROM reservations r
                    JOIN guests g ON r.payer_id = g.id
                    JOIN hotels h ON r.hotel_id = h.id
                    JOIN cities c ON h.city_id = c.id
                    LEFT JOIN details_reservations dr ON dr.reservation_id = r.id
                    LEFT JOIN categories_room cr ON dr.requested_room_category = cr.id
                    LEFT JOIN rooms rm ON dr.room_id = rm.id
                    WHERE r.id = %s
                """, (reservation_id,))

                reservation = cursor.fetchone()
                if reservation:
                    res_dict = dict(reservation)
                    return self._convert_to_serializable(res_dict)
                return None

        except Exception as e:
            logger.error(f"Error getting reservation details: {e}")
            return None

    def get_payment_info_for_reservation(self, reservation_id: int) -> Dict[str, Any]:
        """Получить информацию об оплате для бронирования"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT r.*, h.name as hotel_name, g.first_name, g.last_name
                    FROM reservations r
                    JOIN hotels h ON r.hotel_id = h.id
                    JOIN guests g ON r.payer_id = g.id
                    WHERE r.id = %s
                """, (reservation_id,))

                reservation = cursor.fetchone()
                if reservation:
                    return self._convert_to_serializable(dict(reservation))
                return {}

        except Exception as e:
            logger.error(f"Error getting payment info for reservation: {e}")
            return {}