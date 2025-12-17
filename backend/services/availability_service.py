import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from decimal import Decimal

logger = logging.getLogger(__name__)

class AvailabilityService:
    """Сервис для проверки доступности номеров"""

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
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif hasattr(obj, '__dict__'):
            # Для объектов Row из psycopg2
            return self._convert_to_serializable(dict(obj))
        return obj

    def check_room_availability(self, hotel_id: int, room_category_id: int,
                               start_date: str, end_date: str) -> Dict[str, Any]:
        """Проверить доступность номеров конкретной категории на даты"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()

            if start >= end:
                return {'error': 'End date must be after start date', 'status': 400}

            # Определяем город отеля для правильного выбора БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Номера и бронирования хранятся в филиальных БД (РКД)
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                db_name = db_mapping.get(city_name, 'central')
            else:
                db_name = 'central'

            with self.db.get_cursor(db_name) as cursor:
                # Находим доступные номера
                cursor.execute("""
                    SELECT r.id, r.room_number, r.floor, r.view,
                           COUNT(*) OVER() as total_available
                    FROM rooms r
                    WHERE r.hotel_id = %s
                    AND r.categories_room_id = %s
                    AND NOT EXISTS (
                        SELECT 1
                        FROM reservations res
                        JOIN details_reservations dr ON dr.reservation_id = res.id
                        WHERE dr.room_id = r.id
                        AND res.status IN ('confirmed', 'pending')
                        AND (
                            (res.start_date <= %s AND res.end_date >= %s)
                        )
                    )
                    ORDER BY r.room_number
                    LIMIT 10
                """, (hotel_id, room_category_id, end_date, start_date))

                available_rooms = cursor.fetchall()

            # Информация о категории номера берется из центральной БД (справочник - РОК)
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT id, category_name, guests_capacity, price_per_night, description
                    FROM categories_room
                    WHERE id = %s
                """, (room_category_id,))

                room_info = cursor.fetchone()

                # Получаем коэффициент местоположения отеля (справочник - РОК)
                cursor.execute("""
                    SELECT location_coeff_room FROM hotels WHERE id = %s
                """, (hotel_id,))

                hotel_info = cursor.fetchone()
                location_coeff = hotel_info['location_coeff_room'] if hotel_info else 1.0

                # Рассчитываем цену за период
                nights = (end - start).days
                price_per_night = room_info['price_per_night'] if room_info else 0
                total_price = price_per_night * location_coeff * nights

                result = {
                    'available': len(available_rooms) > 0,
                    'available_rooms_count': len(available_rooms),
                    'total_price': round(total_price, 2),
                    'price_per_night': round(price_per_night * location_coeff, 2),
                    'nights': nights,
                    'room_info': self._convert_to_serializable(dict(room_info)) if room_info else {},
                    'available_rooms': [self._convert_to_serializable(dict(room)) for room in available_rooms[:5]]
                }

                return result

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {'error': 'Invalid date format. Use YYYY-MM-DD', 'status': 400}
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {'error': str(e), 'status': 500}

    def get_available_room_categories(self, hotel_id: int, start_date: str,
                                     end_date: str) -> List[Dict]:
        """Получить все доступные категории номеров на даты"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()

            if start >= end:
                return []

            # Определяем город отеля для правильного выбора БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Номера и бронирования в филиальных БД (РКД)
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                db_name = db_mapping.get(city_name, 'central')
            else:
                db_name = 'central'

            # Сначала получаем доступные номера по категориям из филиальной БД
            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    SELECT r.categories_room_id, COUNT(DISTINCT r.id) as available_rooms_count
                    FROM rooms r
                    WHERE r.hotel_id = %s
                    AND NOT EXISTS (
                        SELECT 1
                        FROM reservations res
                        JOIN details_reservations dr ON dr.reservation_id = res.id
                        WHERE dr.room_id = r.id
                        AND res.status IN ('confirmed', 'pending')
                        AND (
                            (res.start_date <= %s AND res.end_date >= %s)
                        )
                    )
                    GROUP BY r.categories_room_id
                    HAVING COUNT(DISTINCT r.id) > 0
                """, (hotel_id, end_date, start_date))

                available_categories = cursor.fetchall()

            if not available_categories:
                return []

            # Получаем информацию о категориях из центральной БД (справочник - РОК)
            category_ids = [cat['categories_room_id'] for cat in available_categories]
            available_counts = {cat['categories_room_id']: cat['available_rooms_count'] for cat in available_categories}

            with self.db.get_cursor('central') as cursor:
                # Получаем информацию о категориях и коэффициент местоположения
                cursor.execute("""
                    SELECT cr.id, cr.category_name, cr.guests_capacity, 
                           cr.price_per_night, cr.description,
                           h.location_coeff_room
                    FROM categories_room cr
                    JOIN hotels h ON h.id = %s
                    WHERE cr.id = ANY(%s)
                    ORDER BY cr.price_per_night
                """, (hotel_id, category_ids))

                categories = cursor.fetchall()

                # Добавляем расчет цены за период
                nights = (end - start).days
                result = []

                for category in categories:
                    category_dict = dict(category)
                    
                    # Добавляем количество доступных номеров
                    category_dict['available_rooms_count'] = available_counts.get(category['id'], 0)
                    
                    # Рассчитываем цены
                    location_coeff = float(category['location_coeff_room'] or 1.0)
                    price_per_night = float(category['price_per_night'])
                    
                    category_dict['price_for_period'] = round(
                        price_per_night * location_coeff * nights, 2
                    )
                    category_dict['price_per_night_with_coeff'] = round(
                        price_per_night * location_coeff, 2
                    )

                    # Конвертируем
                    category_dict = self._convert_to_serializable(category_dict)
                    result.append(category_dict)

                return result

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting available categories: {e}")
            return []

    def find_available_rooms(self, hotel_id: int, room_category_id: int,
                            start_date: str, end_date: str, limit: int = 5) -> List[Dict]:
        """Найти конкретные доступные номера"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()

            if start >= end:
                return []

            # Определяем город отеля для правильного выбора БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Номера и бронирования в филиальных БД (РКД)
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                db_name = db_mapping.get(city_name, 'central')
            else:
                db_name = 'central'

            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    SELECT r.*, cr.category_name, cr.guests_capacity, cr.price_per_night
                    FROM rooms r
                    JOIN categories_room cr ON r.categories_room_id = cr.id
                    WHERE r.hotel_id = %s
                    AND r.categories_room_id = %s
                    AND NOT EXISTS (
                        SELECT 1
                        FROM reservations res
                        JOIN details_reservations dr ON dr.reservation_id = res.id
                        WHERE dr.room_id = r.id
                        AND res.status IN ('confirmed', 'pending')
                        AND (
                            (res.start_date <= %s AND res.end_date >= %s)
                        )
                    )
                    ORDER BY r.room_number
                    LIMIT %s
                """, (hotel_id, room_category_id, end_date, start_date, limit))

                rooms = cursor.fetchall()
                # Конвертируем
                result = []
                for room in rooms:
                    room_dict = dict(room)
                    room_dict = self._convert_to_serializable(room_dict)
                    result.append(room_dict)

                return result

        except Exception as e:
            logger.error(f"Error finding available rooms: {e}")
            return []

    def _get_city_by_hotel(self, hotel_id: int) -> Optional[str]:
        """Получить название города по ID отеля (из центральной БД - справочник)"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT c.city_name
                    FROM hotels h
                    JOIN cities c ON h.city_id = c.id
                    WHERE h.id = %s
                """, (hotel_id,))

                result = cursor.fetchone()
                return result['city_name'] if result else None

        except Exception as e:
            logger.error(f"Error getting city by hotel: {e}")
            return None
