import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class AvailabilityService:
    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode("utf-8")
        elif hasattr(obj, "__dict__"):
            return self._convert_to_serializable(dict(obj))
        return obj

    def check_room_availability(
        self, hotel_id: int, room_category_id: int, start_date: str, end_date: str
    ) -> dict[str, Any]:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

            if start >= end:
                return {"error": "End date must be after start date", "status": 400}

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

                available_rooms = []
                if available_rooms_count > 0:
                    cursor.execute(
                        """
                        SELECT r.id, r.room_number, r.floor, r.view
                        FROM rooms r
                        WHERE r.hotel_id = %s
                        AND r.categories_room_id = %s
                        ORDER BY r.room_number
                        LIMIT 5
                    """,
                        (hotel_id, room_category_id),
                    )

                    available_rooms = cursor.fetchall()

            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT id, category_name, guests_capacity, price_per_night, description
                    FROM categories_room
                    WHERE id = %s
                """,
                    (room_category_id,),
                )

                room_info = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT location_coeff_room FROM hotels WHERE id = %s
                """,
                    (hotel_id,),
                )

                hotel_info = cursor.fetchone()
                location_coeff = hotel_info["location_coeff_room"] if hotel_info else 1.0

                nights = (end - start).days
                price_per_night = room_info["price_per_night"] if room_info else 0
                total_price = price_per_night * location_coeff * nights

                result = {
                    "available": available_rooms_count > 0,
                    "available_rooms_count": available_rooms_count,
                    "total_rooms": total_rooms,
                    "reserved_rooms": reserved_rooms,
                    "total_price": round(total_price, 2),
                    "price_per_night": round(price_per_night * location_coeff, 2),
                    "nights": nights,
                    "room_info": self._convert_to_serializable(dict(room_info)) if room_info else {},
                    "available_rooms": [self._convert_to_serializable(dict(room)) for room in available_rooms],
                }

                return result

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {"error": "Invalid date format. Use YYYY-MM-DD", "status": 400}
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {"error": str(e), "status": 500}

    def get_available_room_categories(self, hotel_id: int, start_date: str, end_date: str) -> list[dict]:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

            if start >= end:
                return []

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
                    WITH room_counts AS (
                        SELECT
                            r.categories_room_id,
                            COUNT(*) as total_rooms
                        FROM rooms r
                        WHERE r.hotel_id = %s
                        GROUP BY r.categories_room_id
                    ),
                    reserved_counts AS (
                        SELECT
                            dr.requested_room_category,
                            COUNT(*) as reserved_rooms
                        FROM reservations res
                        JOIN details_reservations dr ON dr.reservation_id = res.id
                        WHERE res.hotel_id = %s
                        AND res.status IN ('confirmed', 'pending')
                        AND NOT (res.end_date <= %s OR res.start_date >= %s)
                        GROUP BY dr.requested_room_category
                    )
                    SELECT
                        rc.categories_room_id,
                        rc.total_rooms,
                        COALESCE(rsc.reserved_rooms, 0) as reserved_rooms,
                        (rc.total_rooms - COALESCE(rsc.reserved_rooms, 0)) as available_rooms_count
                    FROM room_counts rc
                    LEFT JOIN reserved_counts rsc ON rc.categories_room_id = rsc.requested_room_category
                    WHERE (rc.total_rooms - COALESCE(rsc.reserved_rooms, 0)) > 0
                """,
                    (hotel_id, hotel_id, start_date, end_date),
                )

                available_categories = cursor.fetchall()

            if not available_categories:
                return []

            category_ids = [cat["categories_room_id"] for cat in available_categories]
            available_counts = {cat["categories_room_id"]: cat["available_rooms_count"] for cat in available_categories}

            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT cr.id, cr.category_name, cr.guests_capacity,
                           cr.price_per_night, cr.description,
                           h.location_coeff_room
                    FROM categories_room cr
                    JOIN hotels h ON h.id = %s
                    WHERE cr.id = ANY(%s)
                    ORDER BY cr.price_per_night
                """,
                    (hotel_id, category_ids),
                )

                categories = cursor.fetchall()

                nights = (end - start).days
                result = []

                for category in categories:
                    category_dict = dict(category)

                    category_dict["available_rooms_count"] = available_counts.get(category["id"], 0)

                    location_coeff = float(category["location_coeff_room"] or 1.0)
                    price_per_night = float(category["price_per_night"])

                    category_dict["price_for_period"] = round(price_per_night * location_coeff * nights, 2)
                    category_dict["price_per_night_with_coeff"] = round(price_per_night * location_coeff, 2)

                    category_dict = self._convert_to_serializable(category_dict)
                    result.append(category_dict)

                return result

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting available categories: {e}")
            return []

    def find_available_rooms(
        self,
        hotel_id: int,
        room_category_id: int,
        start_date: str,
        end_date: str,
        limit: int = 5,
    ) -> list[dict]:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

            if start >= end:
                return []

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
                    SELECT r.*, cr.category_name, cr.guests_capacity, cr.price_per_night
                    FROM rooms r
                    JOIN categories_room cr ON r.categories_room_id = cr.id
                    WHERE r.hotel_id = %s
                    AND r.categories_room_id = %s
                    ORDER BY r.room_number
                    LIMIT %s
                """,
                    (hotel_id, room_category_id, limit),
                )

                rooms = cursor.fetchall()
                result = []
                for room in rooms:
                    room_dict = dict(room)
                    room_dict = self._convert_to_serializable(room_dict)
                    result.append(room_dict)

                return result

        except Exception as e:
            logger.error(f"Error finding available rooms: {e}")
            return []

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
