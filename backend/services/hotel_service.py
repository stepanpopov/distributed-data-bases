import logging
from typing import Dict, List, Optional, Any
from datetime import time, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

class HotelService:
    """Сервис для работы с отелями"""

    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        """Преобразовать объект в сериализуемый формат для HTML"""
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime, time)):
            # Для времени возвращаем строку в формате HH:MM
            if isinstance(obj, time):
                return obj.strftime('%H:%M')
            # Для datetime возвращаем строку
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif hasattr(obj, '__dict__'):
            # Для объектов Row из psycopg2
            return self._convert_to_serializable(dict(obj))
        return obj

    def get_all_hotels(self, city: Optional[str] = None) -> List[Dict]:
        """Получить список всех отелей"""
        try:
            with self.db.get_cursor('central') as cursor:
                if city:
                    cursor.execute("""
                        SELECT h.id, h.name, c.city_name, h.address,
                               h.phone_number, h.email, ch.star_rating,
                               h.check_in_time, h.check_out_time,
                               h.location_coeff_room, h.description
                        FROM hotels h
                        JOIN cities c ON h.city_id = c.id
                        JOIN categories_hotel ch ON h.star_rating_id = ch.id
                        WHERE c.city_name = %s
                        ORDER BY h.name
                    """, (city,))
                else:
                    cursor.execute("""
                        SELECT h.id, h.name, c.city_name, h.address,
                               h.phone_number, h.email, ch.star_rating,
                               h.check_in_time, h.check_out_time,
                               h.location_coeff_room, h.description
                        FROM hotels h
                        JOIN cities c ON h.city_id = c.id
                        JOIN categories_hotel ch ON h.star_rating_id = ch.id
                        ORDER BY c.city_name, h.name
                    """)

                hotels = cursor.fetchall()
                # Преобразуем Row объекты в словари и конвертируем
                result = []
                for hotel in hotels:
                    hotel_dict = dict(hotel)
                    hotel_dict = self._convert_to_serializable(hotel_dict)
                    result.append(hotel_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting hotels: {e}")
            return []

    def get_hotel_details(self, hotel_id: int) -> Optional[Dict]:
        """Получить детальную информацию об отеле"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT h.*, c.city_name, ch.star_rating, ch.rating_coeff
                    FROM hotels h
                    JOIN cities c ON h.city_id = c.id
                    JOIN categories_hotel ch ON h.star_rating_id = ch.id
                    WHERE h.id = %s
                """, (hotel_id,))

                hotel = cursor.fetchone()
                if hotel:
                    hotel_dict = dict(hotel)
                    return self._convert_to_serializable(hotel_dict)
                return None

        except Exception as e:
            logger.error(f"Error getting hotel details: {e}")
            return None

    def update_hotel(self, hotel_id: int, hotel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновить информацию об отеле"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    UPDATE hotels
                    SET name = %s, address = %s, phone_number = %s,
                        email = %s, check_in_time = %s, check_out_time = %s,
                        location_coeff_room = %s, description = %s
                    WHERE id = %s
                """, (
                    hotel_data.get('name'),
                    hotel_data.get('address'),
                    hotel_data.get('phone_number'),
                    hotel_data.get('email'),
                    hotel_data.get('check_in_time'),
                    hotel_data.get('check_out_time'),
                    hotel_data.get('location_coeff_room'),
                    hotel_data.get('description'),
                    hotel_id
                ))

                if cursor.rowcount == 0:
                    return {'error': 'Hotel not found', 'status': 404}

            logger.info(f"Hotel {hotel_id} updated successfully")
            return {'success': True, 'message': 'Hotel updated successfully'}

        except Exception as e:
            logger.error(f"Error updating hotel: {e}")
            return {'error': str(e), 'status': 500}

    def get_hotel_rooms(self, hotel_id: int) -> List[Dict]:
        """Получить все номера отеля"""
        try:
            # Определяем город отеля и соответствующую БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Номера хранятся в филиальных БД (РКД), поэтому читаем из соответствующей филиальной БД
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
                    SELECT r.*, cr.category_name, cr.guests_capacity,
                           cr.price_per_night, cr.description as room_description
                    FROM rooms r
                    JOIN categories_room cr ON r.categories_room_id = cr.id
                    WHERE r.hotel_id = %s
                    ORDER BY r.room_number
                """, (hotel_id,))

                rooms = cursor.fetchall()
                # Преобразуем в сериализуемый формат
                result = []
                for room in rooms:
                    room_dict = dict(room)
                    room_dict = self._convert_to_serializable(room_dict)
                    result.append(room_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting hotel rooms: {e}")
            return []

    def get_hotel_amenities(self, hotel_id: int) -> List[Dict]:
        """Получить удобства отеля"""
        try:
            # Определяем город отеля и соответствующую БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Удобства хранятся в филиальных БД (РКД)
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
                    SELECT a.*, ta.name as amenity_name
                    FROM amenities a
                    JOIN types_amenities ta ON a.types_amenities_id = ta.id
                    WHERE a.hotel_id = %s
                    ORDER BY ta.name
                """, (hotel_id,))

                amenities = cursor.fetchall()
                # Преобразуем в сериализуемый формат
                result = []
                for amenity in amenities:
                    amenity_dict = dict(amenity)
                    amenity_dict = self._convert_to_serializable(amenity_dict)
                    result.append(amenity_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting hotel amenities: {e}")
            return []

    def _get_city_by_hotel(self, hotel_id: int) -> Optional[str]:
        """Получить название города по ID отеля"""
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

    def get_hotel_room_categories_with_counts(self, hotel_id: int) -> List[Dict]:
        """Получить категории номеров отеля с количеством и ценами"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT DISTINCT cr.id as categories_room_id, cr.category_name, cr.guests_capacity,
                           cr.price_per_night, cr.description,
                           h.location_coeff_room,
                           COUNT(r.id) as total_rooms_count
                    FROM categories_room cr
                    JOIN hotels h ON h.id = %s
                    LEFT JOIN rooms r ON r.categories_room_id = cr.id AND r.hotel_id = %s
                    GROUP BY cr.id, cr.category_name, cr.guests_capacity,
                             cr.price_per_night, cr.description, h.location_coeff_room
                    HAVING COUNT(r.id) > 0
                    ORDER BY cr.price_per_night
                """, (hotel_id, hotel_id))

                rooms_data = cursor.fetchall()

                # Конвертируем в нужный формат с ценой, включающей коэффициент
                rooms = []
                for room in rooms_data:
                    room_dict = dict(room)
                    location_coeff = float(room['location_coeff_room'] or 1.0)
                    price_per_night = float(room['price_per_night'])

                    room_dict['price_per_night'] = round(price_per_night * location_coeff, 2)
                    room_dict['room_count'] = room['total_rooms_count']
                    room_dict = self._convert_to_serializable(room_dict)
                    rooms.append(room_dict)

                return rooms

        except Exception as e:
            logger.error(f"Error getting room categories with counts: {e}")
            return []

    def get_room_category_details(self, room_category_id: int) -> Optional[Dict]:
        """Получить детали категории номера"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("SELECT * FROM categories_room WHERE id = %s", (room_category_id,))
                room_category = cursor.fetchone()
                if room_category:
                    room_category = dict(room_category)
                    return self._convert_to_serializable(room_category)
                return None
        except Exception as e:
            logger.error(f"Error getting room category details: {e}")
            return None

    def get_cities_with_hotels_count(self) -> List[Dict]:
        """Получить список городов с количеством отелей"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT DISTINCT c.city_name, COUNT(h.id) as hotels_count
                    FROM cities c
                    LEFT JOIN hotels h ON c.id = h.city_id
                    GROUP BY c.id, c.city_name
                    ORDER BY c.city_name
                """)

                cities = cursor.fetchall()
                cities_list = []
                for city in cities:
                    city_dict = {
                        'city_name': city['city_name'],
                        'hotels_count': city['hotels_count']
                    }
                    cities_list.append(city_dict)

                return cities_list
        except Exception as e:
            logger.error(f"Error getting cities with hotels count: {e}")
            return []
