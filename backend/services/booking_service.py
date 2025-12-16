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
            start_date = booking_data.get('start_date')
            end_date = booking_data.get('end_date')

            # Определяем город отеля
            city_name = self._get_city_by_hotel(hotel_id)
            if not city_name:
                return {'error': 'Hotel not found', 'status': 404}

            # Рассчитываем общую цену
            total_price = self._calculate_total_price(
                hotel_id,
                booking_data.get('room_category_id'),
                start_date,
                end_date,
                booking_data.get('total_guests', 1)
            )

            # Создаем бронирование в центральной БД
            with self.db.get_cursor('central') as cursor:
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

                reservation_id = cursor.fetchone()['id']

                # Создаем детали бронирования
                cursor.execute("""
                    INSERT INTO details_reservations (
                        reservation_id, guest_id, requested_room_category, total_guest_number
                    ) VALUES (%s, %s, %s, %s) RETURNING id
                """, (
                    reservation_id,
                    guest_id,
                    booking_data.get('room_category_id'),
                    booking_data.get('total_guests', 1)
                ))

                detail_id = cursor.fetchone()['id']

                # Привязываем дополнительных гостей
                for additional_guest_id in booking_data.get('additional_guests', []):
                    cursor.execute("""
                        INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                        VALUES (%s, %s)
                    """, (detail_id, additional_guest_id))

            # Реплицируем в городскую БД если нужно
            self._replicate_booking_to_city(reservation_id, booking_data, city_name, 'pending')

            logger.info(f"Booking {reservation_id} created successfully")

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
            with self.db.get_cursor('central') as cursor:
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
            with self.db.get_cursor('central') as cursor:
                # Проверяем существование бронирования
                cursor.execute("SELECT id, hotel_id FROM reservations WHERE id = %s", (reservation_id,))
                reservation = cursor.fetchone()

                if not reservation:
                    return {'error': 'Reservation not found', 'status': 404}

                hotel_id = reservation['hotel_id']

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

                # Добавляем гостей
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

                # Реплицируем изменения в городскую БД
                city_name = self._get_city_by_hotel(hotel_id)
                if city_name in ['Москва', 'Казань']:
                    db_name = 'moscow' if city_name == 'Москва' else 'kazan'

                    try:
                        with self.db.get_cursor(db_name) as city_cursor:
                            city_cursor.execute("""
                                UPDATE details_reservations
                                SET room_id = %s
                                WHERE reservation_id = %s
                            """, (room_id, reservation_id))

                            city_cursor.execute("""
                                UPDATE reservations
                                SET status = 'confirmed'
                                WHERE id = %s
                            """, (reservation_id,))

                            for guest_id in guest_ids:
                                city_cursor.execute("""
                                    INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                                    SELECT dr.id, %s
                                    FROM details_reservations dr
                                    WHERE dr.reservation_id = %s
                                    ON CONFLICT DO NOTHING
                                """, (guest_id, reservation_id))
                    except Exception as e:
                        logger.warning(f"Could not replicate to {db_name}: {e}")

            logger.info(f"Guests registered for reservation {reservation_id}")
            return {'success': True, 'message': 'Guests registered successfully'}

        except Exception as e:
            logger.error(f"Error registering guests: {e}")
            return {'error': str(e), 'status': 500}

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

    def _calculate_total_price(self, hotel_id: int, room_category_id: int,
                              start_date: str, end_date: str, total_guests: int) -> float:
        """Рассчитать общую стоимость бронирования"""
        try:
            # Преобразуем даты
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            nights = (end - start).days

            # Получаем цену за ночь и коэффициент местоположения
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

    def _replicate_booking_to_city(self, reservation_id: int, booking_data: Dict[str, Any],
                                  city_name: str, status: str = 'pending') -> bool:
        """Реплицировать бронирование в городскую БД"""
        if city_name not in ['Москва', 'Казань']:
            return False

        db_name = 'moscow' if city_name == 'Москва' else 'kazan'

        try:
            with self.db.get_cursor(db_name) as cursor:
                # Вставляем бронирование
                cursor.execute("""
                    INSERT INTO reservations (
                        id, hotel_id, create_date, status, total_price,
                        payments_status, payer_id, start_date, end_date
                    ) VALUES (
                        %s, %s, NOW(), %s, %s, 'unpaid', %s, %s, %s
                    ) ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        total_price = EXCLUDED.total_price,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date
                """, (
                    reservation_id,
                    booking_data.get('hotel_id'),
                    status,
                    booking_data.get('total_price', 0),
                    booking_data.get('guest_id'),
                    booking_data.get('start_date'),
                    booking_data.get('end_date')
                ))

                # Вставляем детали бронирования
                cursor.execute("""
                    INSERT INTO details_reservations (
                        reservation_id, guest_id, requested_room_category, total_guest_number
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (reservation_id, guest_id) DO UPDATE SET
                        requested_room_category = EXCLUDED.requested_room_category,
                        total_guest_number = EXCLUDED.total_guest_number
                """, (
                    reservation_id,
                    booking_data.get('guest_id'),
                    booking_data.get('room_category_id'),
                    booking_data.get('total_guests', 1)
                ))

                # Получаем ID деталей для привязки гостей
                cursor.execute("""
                    SELECT id FROM details_reservations WHERE reservation_id = %s
                """, (reservation_id,))

                detail = cursor.fetchone()
                if detail:
                    detail_id = detail['id']

                    # Добавляем основного гостя
                    cursor.execute("""
                        INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (detail_id, booking_data.get('guest_id')))

                    # Добавляем дополнительных гостей
                    for guest_id in booking_data.get('additional_guests', []):
                        cursor.execute("""
                            INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                        """, (detail_id, guest_id))

            logger.info(f"Booking {reservation_id} replicated to {db_name}")
            return True

        except Exception as e:
            logger.warning(f"Could not replicate booking to {db_name}: {e}")
            return False
