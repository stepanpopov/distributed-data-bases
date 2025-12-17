import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from datetime import time
from decimal import Decimal

logger = logging.getLogger(__name__)

class BookingService:
    """Сервис для управления бронированиями"""

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
            # Для объектов Row из psycopg2
            return self._convert_to_serializable(dict(obj))
        return obj

    def create_booking(self, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание нового бронирования"""
        try:
            hotel_id = booking_data.get('hotel_id')
            guest_id = booking_data.get('guest_id')
            room_category_id = booking_data.get('room_category_id')
            start_date = booking_data.get('start_date')
            end_date = booking_data.get('end_date')

            # Валидация обязательных полей
            if not all([hotel_id, guest_id, room_category_id, start_date, end_date]):
                missing_fields = []
                if not hotel_id: missing_fields.append('hotel_id')
                if not guest_id: missing_fields.append('guest_id') 
                if not room_category_id: missing_fields.append('room_category_id')
                if not start_date: missing_fields.append('start_date')
                if not end_date: missing_fields.append('end_date')
                
                return {
                    'error': f'Missing required fields: {", ".join(missing_fields)}', 
                    'status': 400
                }

            # Определяем город отеля
            city_name = self._get_city_by_hotel(hotel_id)
            if not city_name:
                return {'error': 'Hotel not found', 'status': 404}

            # Проверяем, что категория номера существует (справочник из центральной БД)
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT id FROM categories_room WHERE id = %s
                """, (room_category_id,))
                
                if not cursor.fetchone():
                    return {'error': 'Room category not found', 'status': 404}

            # Рассчитываем общую цену
            total_price = self._calculate_total_price(
                hotel_id,
                room_category_id,
                start_date,
                end_date,
                booking_data.get('total_guests', 1)
            )

            # Определяем БД для создания операционных данных (РКД - создаем в филиале)
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                primary_db = db_mapping[city_name]
            else:
                primary_db = 'central'

            # Создаем операционные данные в филиальной БД (они автоматически реплицируются в центр)
            with self.db.get_cursor(primary_db) as cursor:
                # Создаем бронирование
                cursor.execute("""
                    INSERT INTO reservations (
                        hotel_id, create_date, status, total_price,
                        payments_status, payer_id, start_date, end_date
                    ) VALUES (
                        %s, NOW(), 'pending', %s, 'unpaid', %s, %s, %s
                    ) RETURNING id
                """, (
                    hotel_id,
                    total_price,
                    guest_id,
                    start_date,
                    end_date
                ))

                result = cursor.fetchone()
                if not result:
                    return {'error': 'Failed to create reservation', 'status': 500}
                
                reservation_id = result['id']

                # Создаем детали бронирования
                cursor.execute("""
                    INSERT INTO details_reservations (
                        reservation_id, guest_id, requested_room_category, total_guest_number
                    ) VALUES (%s, %s, %s, %s) RETURNING id
                """, (
                    reservation_id,
                    guest_id,
                    room_category_id,
                    booking_data.get('total_guests', 1)
                ))

                detail_result = cursor.fetchone()
                if not detail_result:
                    return {'error': 'Failed to create reservation details', 'status': 500}
                
                detail_id = detail_result['id']

                # Создаем локальные данные room_reservation_guests только в филиальной БД
                cursor.execute("""
                    INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                    VALUES (%s, %s)
                """, (detail_id, guest_id))

                # Привязываем дополнительных гостей
                for additional_guest_id in booking_data.get('additional_guests', []):
                    cursor.execute("""
                        INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                        VALUES (%s, %s)
                    """, (detail_id, additional_guest_id))

            # Операционные данные автоматически реплицируются в центр через РКД
            logger.info(f"Booking {reservation_id} created successfully in {primary_db}")

            return {
                'success': True,
                'reservation_id': reservation_id,
                'total_price': total_price,
                'message': 'Booking created successfully'
            }

        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return {'error': str(e), 'status': 500}

    def get_reservations(self, hotel_id: int, status: str = 'pending') -> List[Dict]:
        """Получить список бронирований для отеля"""
        try:
            # Определяем город отеля для выбора правильной БД
            city_name = self._get_city_by_hotel(hotel_id)
            
            # Бронирования и room_reservation_guests - локальные данные филиала
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
                    SELECT r.*, g.first_name, g.last_name, g.phone_number,
                           h.name as hotel_name,
                           COUNT(drg.guest_id) as total_guests
                    FROM reservations r
                    JOIN guests g ON r.payer_id = g.id
                    JOIN hotels h ON r.hotel_id = h.id
                    LEFT JOIN details_reservations dr ON dr.reservation_id = r.id
                    LEFT JOIN room_reservation_guests drg ON drg.room_reservation_id = dr.id
                    WHERE r.hotel_id = %s AND r.status = %s
                    GROUP BY r.id, g.first_name, g.last_name, g.phone_number, h.name
                    ORDER BY r.create_date DESC
                """, (hotel_id, status))

                reservations = cursor.fetchall()
                # Конвертируем
                result = []
                for res in reservations:
                    res_dict = dict(res)
                    res_dict = self._convert_to_serializable(res_dict)
                    result.append(res_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting reservations: {e}")
            return []

    def get_reservation_details(self, reservation_id: int) -> Dict[str, Any]:
        """Получить детали бронирования"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT r.*, g.first_name, g.last_name, g.phone_number,
                           h.name as hotel_name, h.city_id
                    FROM reservations r
                    JOIN guests g ON r.payer_id = g.id
                    JOIN hotels h ON r.hotel_id = h.id
                    WHERE r.id = %s
                """, (reservation_id,))

                reservation = cursor.fetchone()
                if reservation:
                    res_dict = dict(reservation)
                    return self._convert_to_serializable(res_dict)
                return {}

        except Exception as e:
            logger.error(f"Error getting reservation details: {e}")
            return {}

    def register_guests(self, reservation_id: int, room_id: int, guest_ids: List[int]) -> Dict[str, Any]:
        """Зарегистрировать гостей и привязать номер"""
        try:
            # Сначала определяем, в какой БД находится бронирование
            with self.db.get_cursor('central') as cursor:
                cursor.execute("SELECT id, hotel_id FROM reservations WHERE id = %s", (reservation_id,))
                reservation = cursor.fetchone()

                if not reservation:
                    return {'error': 'Reservation not found', 'status': 404}

                hotel_id = reservation['hotel_id']

            # Определяем филиальную БД для работы с локальными данными
            city_name = self._get_city_by_hotel(hotel_id)
            if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                db_name = db_mapping[city_name]
            else:
                db_name = 'central'

            # Все операции с room_reservation_guests выполняем в филиальной БД
            with self.db.get_cursor(db_name) as cursor:
                # Проверяем, что номер принадлежит отелю
                cursor.execute("SELECT id FROM rooms WHERE id = %s AND hotel_id = %s", (room_id, hotel_id))
                room = cursor.fetchone()

                if not room:
                    return {'error': 'Room not found in this hotel', 'status': 400}

                # Привязываем номер к бронированию
                cursor.execute("""
                    UPDATE details_reservations
                    SET room_id = %s
                    WHERE reservation_id = %s
                """, (room_id, reservation_id))

                # Получаем ID деталей бронирования
                cursor.execute("""
                    SELECT id FROM details_reservations WHERE reservation_id = %s
                """, (reservation_id,))

                detail = cursor.fetchone()
                if not detail:
                    return {'error': 'Booking details not found', 'status': 400}

                detail_id = detail['id']

                # Добавляем гостей в ЛОКАЛЬНУЮ таблицу room_reservation_guests
                for guest_id in guest_ids:
                    cursor.execute("""
                        INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                        VALUES (%s, %s)
                        ON CONFLICT (room_reservation_id, guest_id) DO NOTHING
                    """, (detail_id, guest_id))

                # Обновляем статус бронирования
                cursor.execute("""
                    UPDATE reservations
                    SET status = 'confirmed'
                    WHERE id = %s
                """, (reservation_id,))

            logger.info(f"Guests registered for reservation {reservation_id} in {db_name}")
            return {'success': True, 'message': 'Guests registered successfully'}

        except Exception as e:
            logger.error(f"Error registering guests: {e}")
            return {'error': str(e), 'status': 500}

    def _get_city_by_hotel(self, hotel_id: int) -> Optional[str]:
        """Получить название города по ID отеля (РОК - справочник из центральной БД)"""
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

    def _calculate_total_price(self, hotel_id: int, room_category_id: int,
                              start_date: str, end_date: str, total_guests: int) -> float:
        """Рассчитать общую стоимость бронирования (используем справочники из центральной БД)"""
        try:
            # Преобразуем даты
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            nights = (end - start).days

            # Получаем цену за ночь и коэффициент местоположения (РОК - справочники из центральной БД)
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT cr.price_per_night, h.location_coeff_room
                    FROM categories_room cr
                    JOIN hotels h ON h.id = %s
                    WHERE cr.id = %s
                """, (hotel_id, room_category_id))

                result = cursor.fetchone()
                if not result:
                    raise ValueError("Room category not found")

                price_per_night = float(result['price_per_night'])
                location_coeff = float(result['location_coeff_room'] or 1.0)

                # Рассчитываем общую стоимость
                total_price = price_per_night * location_coeff * nights

                # Учитываем количество гостей (если больше стандартного)
                cursor.execute("""
                    SELECT guests_capacity FROM categories_room WHERE id = %s
                """, (room_category_id,))

                capacity_result = cursor.fetchone()
                if capacity_result and total_guests > capacity_result['guests_capacity']:
                    # Доплата за дополнительных гостей (например, 20% за каждого лишнего)
                    extra_guests = total_guests - capacity_result['guests_capacity']
                    total_price += total_price * 0.2 * extra_guests

                return round(total_price, 2)

        except Exception as e:
            logger.error(f"Error calculating price: {e}")
            # Возвращаем примерную цену в случае ошибки
            return 1000 * nights
