import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode("utf-8")
        elif hasattr(obj, "__dict__"):
            return self._convert_to_serializable(dict(obj))
        return obj

    def process_payment(self, payment_data: dict[str, Any]) -> dict[str, Any]:
        try:
            reservation_id = payment_data.get("reservation_id")
            amount = payment_data.get("amount")
            payment_method = payment_data.get("method", "card")

            if not reservation_id or not amount:
                return {"error": "Missing required fields", "status": 400}

            city_name = None
            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT c.city_name, r.*, g.loyalty_card_id, g.bonus_points
                    FROM reservations r
                    JOIN hotels h ON r.hotel_id = h.id
                    JOIN cities c ON h.city_id = c.id
                    JOIN guests g ON r.payer_id = g.id
                    WHERE r.id = %s
                """,
                    (reservation_id,),
                )

                reservation_data = cursor.fetchone()
                if reservation_data:
                    city_name = reservation_data["city_name"]

            if not city_name:
                return {"error": "Reservation not found", "status": 404}

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
                    SELECT r.*, g.loyalty_card_id, g.bonus_points
                    FROM reservations r
                    JOIN guests g ON r.payer_id = g.id
                    WHERE r.id = %s
                """,
                    (reservation_id,),
                )

                reservation = cursor.fetchone()

                if not reservation:
                    return {
                        "error": "Reservation not found in filial DB",
                        "status": 404,
                    }

                if reservation["payments_status"] == "paid":
                    return {"error": "Reservation already paid", "status": 400}

                final_amount = self._apply_loyalty_discount(
                    amount, reservation["loyalty_card_id"], reservation["bonus_points"]
                )

                cursor.execute(
                    """
                    UPDATE reservations
                    SET payments_status = 'paid', status = 'confirmed', total_price = %s
                    WHERE id = %s
                """,
                    (final_amount, reservation_id),
                )

                cursor.execute(
                    """
                    INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method)
                    VALUES (%s, %s, CURRENT_DATE, %s)
                """,
                    (reservation_id, final_amount, payment_method),
                )

                bonus_points = int(final_amount * 0.01)
                cursor.execute(
                    """
                    UPDATE guests
                    SET bonus_points = bonus_points + %s
                    WHERE id = %s
                """,
                    (bonus_points, reservation["payer_id"]),
                )

                self._update_loyalty_card(reservation["payer_id"])

            logger.info(f"Payment processed for reservation {reservation_id}: {final_amount} in {primary_db}")

            return {
                "success": True,
                "message": "Payment processed successfully",
                "amount_paid": final_amount,
                "bonus_points_added": int(final_amount * 0.01),
            }

        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            return {"error": str(e), "status": 500}

    def get_payment_history(self, guest_id: int, limit: int = 10) -> list:
        try:
            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT p.*, r.start_date, r.end_date, h.name as hotel_name
                    FROM payments p
                    JOIN reservations r ON p.reservation_id = r.id
                    JOIN hotels h ON r.hotel_id = h.id
                    WHERE r.payer_id = %s
                    ORDER BY p.payments_date DESC
                    LIMIT %s
                """,
                    (guest_id, limit),
                )

                payments = cursor.fetchall()
                result = []
                for payment in payments:
                    payment_dict = dict(payment)
                    payment_dict = self._convert_to_serializable(payment_dict)
                    result.append(payment_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting payment history: {e}")
            return []

    def _apply_loyalty_discount(self, amount: float, loyalty_card_id: int | None, bonus_points: int = 0) -> float:
        try:
            if not loyalty_card_id:
                return amount

            with self.db.get_cursor("central") as cursor:
                cursor.execute(
                    """
                    SELECT discount, req_bonus_amount
                    FROM loyalty_cards
                    WHERE id = %s
                """,
                    (loyalty_card_id,),
                )

                card = cursor.fetchone()
                if not card:
                    return amount

                if bonus_points >= card["req_bonus_amount"]:
                    discount = float(card["discount"]) / 100
                    discounted_amount = float(amount) * (1 - discount)
                    return round(discounted_amount, 2)

            return amount

        except Exception as e:
            logger.error(f"Error applying loyalty discount: {e}")
            return amount

    def _update_loyalty_card(self, guest_id: int) -> None:
        try:
            with self.db.get_cursor("central") as cursor:
                cursor.execute("SELECT bonus_points FROM guests WHERE id = %s", (guest_id,))
                guest = cursor.fetchone()

                if not guest:
                    return

                bonus_points = guest["bonus_points"]

                cursor.execute(
                    """
                    SELECT id FROM loyalty_cards
                    WHERE req_bonus_amount <= %s
                    ORDER BY req_bonus_amount DESC
                    LIMIT 1
                """,
                    (bonus_points,),
                )

                new_card = cursor.fetchone()
                if new_card:
                    cursor.execute(
                        """
                        UPDATE guests
                        SET loyalty_card_id = %s
                        WHERE id = %s AND (loyalty_card_id IS NULL OR loyalty_card_id != %s)
                    """,
                        (new_card["id"], guest_id, new_card["id"]),
                    )

        except Exception as e:
            logger.error(f"Error updating loyalty card: {e}")
