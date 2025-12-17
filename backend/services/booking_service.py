import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class BookingService:
    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.strftime("%H:%M:%S")
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode("utf-8")
        elif hasattr(obj, "__dict__"):
            return self._convert_to_serializable(dict(obj))
        return obj

    def create_booking(self, booking_data: dict[str, Any]) -> dict[str, Any]:
        try:
            hotel_id = booking_data.get("hotel_id")
            guest_id = booking_data.get("guest_id")
            room_category_id = booking_data.get("room_category_id")
            start_date = booking_data.get("start_date")
            end_date = booking_data.get("end_date")

            if not all([hotel_id, guest_id, room_category_id, start_date, end_date]):
                missing_fields = []
                if not hotel_id:
                    missing_fields.append("hotel_id")
                if not guest_id:
                    missing_fields.append("guest_id")
                if not room_category_id:
                    missing_fields.append("room_category_id")
                if not start_date:
                    missing_fields.append("start_date")
                if not end_date:
                    missing_fields.append("end_date")

                return {
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "status": 400,
                }

            city_name = self._get_city_by_hotel(hotel_id)
            if not city_name:
                return {"error": "Hotel not found", "status": 404}

            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT id FROM categories_room WHERE id = %s
                """,
                    (room_category_id,),
                )

                if not cursor.fetchone():
                    return {"error": "Room category not found", "status": 404}

            availability_check = self._check_room_availability_for_booking(
                hotel_id, room_category_id, start_date, end_date
            )

            if not availability_check["available"]:
                return {
                    "error": f"No available rooms of this category for the selected dates. Available: {availability_check['available_count']}, Required: 1",
                    "status": 409,
                }

            total_price = self._calculate_total_price(
                hotel_id,
                room_category_id,
                start_date,
                end_date,
                booking_data.get("total_guests", 1),
            )

            if city_name in ["Москва", "Санкт-Петербург", "Казань"]:
                db_mapping = {
                    "Москва": "filial1",
                    "Санкт-Петербург": "filial2",
                    "Казань": "filial3",
                }
                primary_db = db_mapping[city_name]
            else:
                primary_db = "central"

            with self.db.get_cursor(primary_db) as cursor:
                cursor.execute(
                    """
                    INSERT INTO reservations (
                        hotel_id, create_date, status, total_price,
                        payments_status, payer_id, start_date, end_date
                    ) VALUES (
                        %s, NOW(), 'pending', %s, 'unpaid', %s, %s, %s
                    ) RETURNING id
                """,
                    (hotel_id, total_price, guest_id, start_date, end_date),
                )

                result = cursor.fetchone()
                if not result:
                    return {"error": "Failed to create reservation", "status": 500}

                reservation_id = result["id"]

                cursor.execute(
                    """
                    INSERT INTO details_reservations (
                        reservation_id, guest_id, requested_room_category, total_guest_number
                    ) VALUES (%s, %s, %s, %s) RETURNING id
                """,
                    (
                        reservation_id,
                        guest_id,
                        room_category_id,
                        booking_data.get("total_guests", 1),
                    ),
                )

                detail_result = cursor.fetchone()
                if not detail_result:
                    return {
                        "error": "Failed to create reservation details",
                        "status": 500,
                    }

                detail_id = detail_result["id"]

                cursor.execute(
                    """
                    INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                    VALUES (%s, %s)
                """,
                    (detail_id, guest_id),
                )

                for additional_guest_id in booking_data.get("additional_guests", []):
                    cursor.execute(
                        """
                        INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                        VALUES (%s, %s)
                    """,
                        (detail_id, additional_guest_id),
                    )

            logger.info(f"Booking {reservation_id} created successfully in {primary_db}")

            return {
                "success": True,
                "reservation_id": reservation_id,
                "total_price": total_price,
                "message": "Booking created successfully",
            }

        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            return {"error": str(e), "status": 500}

    def get_reservations(self, hotel_id: int, status: str = "pending") -> list[dict]:
        try:
            city_name = self._get_city_by_hotel(hotel_id)

            if city_name in ["Москва", "Санкт-Петербург", "Казань"]:
                db_mapping = {
                    "Москва": "filial1",
                    "Санкт-Петербург": "filial2",
                    "Казань": "filial3",
                }
                db_name = db_mapping.get(city_name, "central")
            else:
                db_name = "central"

            with self.db.get_cursor(db_name) as cursor:
                cursor.execute(
                    """
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
                """,
                    (hotel_id, status),
                )

                reservations = cursor.fetchall()
                result = []
                for res in reservations:
                    res_dict = dict(res)
                    res_dict = self._convert_to_serializable(res_dict)
                    result.append(res_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting reservations: {e}")
            return []

    def get_reservation_details(self, reservation_id: int) -> dict[str, Any]:
        try:
            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
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
                """,
                    (reservation_id,),
                )

                reservation = cursor.fetchone()
                if reservation:
                    res_dict = dict(reservation)
                    return self._convert_to_serializable(res_dict)
                return {}

        except Exception as e:
            logger.error(f"Error getting reservation details: {e}")
            return {}

    def register_guests(self, reservation_id: int, room_id: int, guest_ids: list[int]) -> dict[str, Any]:
        try:
            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT r.id, r.hotel_id, r.payer_id, r.start_date, r.end_date
                    FROM reservations r
                    WHERE r.id = %s
                """,
                    (reservation_id,),
                )
                reservation = cursor.fetchone()

                if not reservation:
                    return {"error": "Reservation not found", "status": 404}

                hotel_id = reservation["hotel_id"]
                payer_guest_id = reservation["payer_id"]
                start_date = reservation["start_date"]
                end_date = reservation["end_date"]

            city_name = self._get_city_by_hotel(hotel_id)
            if city_name in ["Москва", "Санкт-Петербург", "Казань"]:
                db_mapping = {
                    "Москва": "filial1",
                    "Санкт-Петербург": "filial2",
                    "Казань": "filial3",
                }
                db_name = db_mapping[city_name]
            else:
                db_name = "central"

            with self.db.get_cursor(db_name) as cursor:
                cursor.execute(
                    "SELECT id FROM rooms WHERE id = %s AND hotel_id = %s",
                    (room_id, hotel_id),
                )
                room = cursor.fetchone()

                if not room:
                    return {"error": "Room not found in this hotel", "status": 400}

                cursor.execute(
                    """
                    SELECT res.id, res.start_date, res.end_date
                    FROM reservations res
                    JOIN details_reservations dr ON dr.reservation_id = res.id
                    WHERE dr.room_id = %s
                    AND res.status IN ('confirmed', 'pending')
                    AND res.id != %s
                    AND NOT (res.end_date <= %s OR res.start_date >= %s)
                """,
                    (room_id, reservation_id, start_date, end_date),
                )

                conflicting_reservation = cursor.fetchone()
                if conflicting_reservation:
                    return {
                        "error": f"Room is already occupied by another reservation (ID: {conflicting_reservation['id']}) for these dates",
                        "status": 409,
                    }

                cursor.execute(
                    """
                    UPDATE details_reservations
                    SET room_id = %s
                    WHERE reservation_id = %s
                """,
                    (room_id, reservation_id),
                )

                cursor.execute(
                    """
                    SELECT id FROM details_reservations WHERE reservation_id = %s
                """,
                    (reservation_id,),
                )

                detail = cursor.fetchone()
                if not detail:
                    return {"error": "Booking details not found", "status": 400}

                detail_id = detail["id"]

                cursor.execute(
                    """
                    INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                    VALUES (%s, %s)
                    ON CONFLICT (room_reservation_id, guest_id) DO NOTHING
                """,
                    (detail_id, payer_guest_id),
                )

                for guest_id in guest_ids:
                    if guest_id != payer_guest_id:
                        cursor.execute("SELECT id FROM guests WHERE id = %s", (guest_id,))
                        if cursor.fetchone():
                            cursor.execute(
                                """
                                INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
                                VALUES (%s, %s)
                                ON CONFLICT (room_reservation_id, guest_id) DO NOTHING
                            """,
                                (detail_id, guest_id),
                            )

                cursor.execute(
                    """
                    UPDATE reservations
                    SET status = 'confirmed'
                    WHERE id = %s
                """,
                    (reservation_id,),
                )

            logger.info(f"Guests registered for reservation {reservation_id} in {db_name}, assigned room {room_id}")
            return {"success": True, "message": "Guests registered successfully"}

        except Exception as e:
            logger.error(f"Error registering guests: {e}")
            return {"error": str(e), "status": 500}

    def _get_city_by_hotel(self, hotel_id: int) -> str | None:
        try:
            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT c.city_name
                    FROM hotels h
                    JOIN cities c ON h.city_id = c.id
                    WHERE h.id = %s
                """,
                    (hotel_id,),
                )

                result = cursor.fetchone()
                return result["city_name"] if result else None

        except Exception as e:
            logger.error(f"Error getting city by hotel: {e}")
            return None

    def _calculate_total_price(
        self,
        hotel_id: int,
        room_category_id: int,
        start_date: str,
        end_date: str,
        total_guests: int,
    ) -> float:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            nights = (end - start).days

            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT cr.price_per_night, h.location_coeff_room
                    FROM categories_room cr
                    JOIN hotels h ON h.id = %s
                    WHERE cr.id = %s
                """,
                    (hotel_id, room_category_id),
                )

                result = cursor.fetchone()
                if not result:
                    raise ValueError("Room category not found")

                price_per_night = float(result["price_per_night"])
                location_coeff = float(result["location_coeff_room"] or 1.0)

                total_price = price_per_night * location_coeff * nights

                cursor.execute(
                    """
                    SELECT guests_capacity FROM categories_room WHERE id = %s
                """,
                    (room_category_id,),
                )

                capacity_result = cursor.fetchone()
                if capacity_result and total_guests > capacity_result["guests_capacity"]:
                    extra_guests = total_guests - capacity_result["guests_capacity"]
                    total_price += total_price * 0.2 * extra_guests

                return round(total_price, 2)

        except Exception as e:
            logger.error(f"Error calculating price: {e}")
            return 1000 * nights

    def _check_room_availability_for_booking(
        self, hotel_id: int, room_category_id: int, start_date: str, end_date: str
    ) -> dict[str, Any]:
        try:
            city_name = self._get_city_by_hotel(hotel_id)

            if city_name in ["Москва", "Санкт-Петербург", "Казань"]:
                db_mapping = {
                    "Москва": "filial1",
                    "Санкт-Петербург": "filial2",
                    "Казань": "filial3",
                }
                db_name = db_mapping.get(city_name, "central")
            else:
                db_name = "central"

            with self.db.get_cursor(db_name) as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*) as total_rooms
                    FROM rooms r
                    WHERE r.hotel_id = %s AND r.categories_room_id = %s
                """,
                    (hotel_id, room_category_id),
                )

                total_result = cursor.fetchone()
                total_rooms = total_result["total_rooms"] if total_result else 0

                cursor.execute(
                    """
                    SELECT COUNT(*) as reserved_rooms
                    FROM reservations res
                    JOIN details_reservations dr ON dr.reservation_id = res.id
                    WHERE res.hotel_id = %s
                    AND dr.requested_room_category = %s
                    AND res.status IN ('confirmed', 'pending')
                    AND NOT (res.end_date <= %s OR res.start_date >= %s)
                """,
                    (hotel_id, room_category_id, start_date, end_date),
                )

                reserved_result = cursor.fetchone()
                reserved_rooms = reserved_result["reserved_rooms"] if reserved_result else 0

                available_rooms_count = max(0, total_rooms - reserved_rooms)

                return {
                    "available": available_rooms_count > 0,
                    "available_count": available_rooms_count,
                    "total_rooms": total_rooms,
                    "reserved_rooms": reserved_rooms,
                }

        except Exception as e:
            logger.error(f"Error checking room availability for booking: {e}")
            return {
                "available": False,
                "available_count": 0,
                "total_rooms": 0,
                "reserved_rooms": 0,
                "error": str(e),
            }
