import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

class PaymentService:
    """Сервис для обработки платежей"""

    def __init__(self, db_manager):
        self.db = db_manager

    def _convert_to_serializable(self, obj):
        """Преобразовать объект в сериализуемый формат для HTML"""
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (datetime)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')
        elif hasattr(obj, '__dict__'):
            # Для объектов Row из psycopg2
            return self._convert_to_serializable(dict(obj))
        return obj

    def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработать оплату бронирования"""
        try:
            reservation_id = payment_data.get('reservation_id')
            amount = payment_data.get('amount')
            payment_method = payment_data.get('method', 'card')

            if not reservation_id or not amount:
                return {'error': 'Missing required fields', 'status': 400}

            # Получаем информацию о бронировании
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT r.*, c.city_name, g.loyalty_card_id, g.bonus_points
                    FROM reservations r
                    JOIN hotels h ON r.hotel_id = h.id
                    JOIN cities c ON h.city_id = c.id
                    JOIN guests g ON r.payer_id = g.id
                    WHERE r.id = %s
                """, (reservation_id,))

                reservation = cursor.fetchone()

                if not reservation:
                    return {'error': 'Reservation not found', 'status': 404}

                # Проверяем, не оплачено ли уже
                if reservation['payments_status'] == 'paid':
                    return {'error': 'Reservation already paid', 'status': 400}

                city_name = reservation['city_name']

                # Применяем скидку по карте лояльности если есть
                final_amount = self._apply_loyalty_discount(
                    amount,
                    reservation['loyalty_card_id'],
                    reservation['bonus_points']
                )

                # Обновляем статус бронирования
                cursor.execute("""
                    UPDATE reservations
                    SET payments_status = 'paid', status = 'confirmed', total_price = %s
                    WHERE id = %s
                """, (final_amount, reservation_id))

                # Создаем запись о платеже
                cursor.execute("""
                    INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method)
                    VALUES (%s, %s, CURRENT_DATE, %s)
                """, (reservation_id, final_amount, payment_method))

                # Начисляем бонусные баллы (1% от суммы)
                bonus_points = int(final_amount * 0.01)
                cursor.execute("""
                    UPDATE guests
                    SET bonus_points = bonus_points + %s
                    FROM reservations
                    WHERE guests.id = reservations.payer_id AND reservations.id = %s
                """, (bonus_points, reservation_id))

                # Проверяем обновление карты лояльности
                self._update_loyalty_card(reservation['payer_id'])

            # Реплицируем в городскую БД если нужно
            if city_name in ['Москва', 'Казань']:
                self._replicate_payment_to_city(reservation_id, final_amount, payment_method, city_name)

            logger.info(f"Payment processed for reservation {reservation_id}: {final_amount}")

            return {
                'success': True,
                'message': 'Payment processed successfully',
                'amount_paid': final_amount,
                'bonus_points_added': int(final_amount * 0.01)
            }

        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            return {'error': str(e), 'status': 500}

    def get_payment_history(self, guest_id: int, limit: int = 10) -> list:
        """Получить историю платежей гостя"""
        try:
            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT p.*, r.start_date, r.end_date, h.name as hotel_name
                    FROM payments p
                    JOIN reservations r ON p.reservation_id = r.id
                    JOIN hotels h ON r.hotel_id = h.id
                    WHERE r.payer_id = %s
                    ORDER BY p.payments_date DESC
                    LIMIT %s
                """, (guest_id, limit))

                payments = cursor.fetchall()
                # Конвертируем
                result = []
                for payment in payments:
                    payment_dict = dict(payment)
                    payment_dict = self._convert_to_serializable(payment_dict)
                    result.append(payment_dict)

                return result

        except Exception as e:
            logger.error(f"Error getting payment history: {e}")
            return []

    def _apply_loyalty_discount(self, amount: float, loyalty_card_id: Optional[int],
                               bonus_points: int = 0) -> float:
        """Применить скидку по карте лояльности"""
        try:
            if not loyalty_card_id:
                return amount

            with self.db.get_cursor('central') as cursor:
                cursor.execute("""
                    SELECT discount, req_bonus_amount
                    FROM loyalty_cards
                    WHERE id = %s
                """, (loyalty_card_id,))

                card = cursor.fetchone()
                if not card:
                    return amount

                # Проверяем, достаточно ли бонусных баллов
                if bonus_points >= card['req_bonus_amount']:
                    discount = card['discount'] / 100  # Проценты в долю
                    discounted_amount = amount * (1 - discount)
                    return round(discounted_amount, 2)

            return amount

        except Exception as e:
            logger.error(f"Error applying loyalty discount: {e}")
            return amount

    def _update_loyalty_card(self, guest_id: int) -> None:
        """Обновить карту лояльности гостя на основе бонусных баллов"""
        try:
            with self.db.get_cursor('central') as cursor:
                # Получаем текущие баллы гостя
                cursor.execute("SELECT bonus_points FROM guests WHERE id = %s", (guest_id,))
                guest = cursor.fetchone()

                if not guest:
                    return

                bonus_points = guest['bonus_points']

                # Находим подходящую карту лояльности
                cursor.execute("""
                    SELECT id FROM loyalty_cards
                    WHERE req_bonus_amount <= %s
                    ORDER BY req_bonus_amount DESC
                    LIMIT 1
                """, (bonus_points,))

                new_card = cursor.fetchone()
                if new_card:
                    cursor.execute("""
                        UPDATE guests
                        SET loyalty_card_id = %s
                        WHERE id = %s AND (loyalty_card_id IS NULL OR loyalty_card_id != %s)
                    """, (new_card['id'], guest_id, new_card['id']))

        except Exception as e:
            logger.error(f"Error updating loyalty card: {e}")

    def _replicate_payment_to_city(self, reservation_id: int, amount: float,
                                  method: str, city_name: str) -> bool:
        """Реплицировать платеж в городскую БД"""
        if city_name not in ['Москва', 'Казань']:
            return False

        db_name = 'moscow' if city_name == 'Москва' else 'kazan'

        try:
            with self.db.get_cursor(db_name) as cursor:
                cursor.execute("""
                    UPDATE reservations
                    SET payments_status = 'paid', status = 'confirmed'
                    WHERE id = %s
                """, (reservation_id,))

                cursor.execute("""
                    INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method)
                    VALUES (%s, %s, CURRENT_DATE, %s)
                """, (reservation_id, amount, method))

            logger.info(f"Payment for reservation {reservation_id} replicated to {db_name}")
            return True

        except Exception as e:
            logger.warning(f"Could not replicate payment to {db_name}: {e}")
            return False
