from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_cors import CORS
from database import db_manager
import logging
from datetime import datetime

# Импорт сервисов
from services.booking_service import BookingService
from services.payment_service import PaymentService
from services.availability_service import AvailabilityService
from services.hotel_service import HotelService

app = Flask(__name__)
CORS(app)
app.secret_key = 'your-secret-key-here'  # Для flash сообщений

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация сервисов
booking_service = BookingService(db_manager)
payment_service = PaymentService(db_manager)
availability_service = AvailabilityService(db_manager)
hotel_service = HotelService(db_manager)

# ========== HTML ПУНКТЫ ==========

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/hotels')
def hotels_list():
    """Список отелей (HTML)"""
    city = request.args.get('city')
    hotels = hotel_service.get_all_hotels(city)
    return render_template('hotels.html', hotels=hotels)

@app.route('/hotels/<int:hotel_id>')
def hotel_detail(hotel_id):
    """Страница отеля с номерами"""
    hotel = hotel_service.get_hotel_details(hotel_id)
    if not hotel:
        return render_template('404.html'), 404

    # Получаем доступные категории номеров
    rooms = hotel_service.get_hotel_rooms(hotel_id)
    amenities = hotel_service.get_hotel_amenities(hotel_id)

    return render_template('hotel_detail.html',
                         hotel=hotel,
                         rooms=rooms,
                         amenities=amenities)

@app.route('/hotels/<int:hotel_id>/book')
def booking_form(hotel_id):
    """Форма бронирования"""
    hotel = hotel_service.get_hotel_details(hotel_id)
    if not hotel:
        return render_template('404.html'), 404

    # Получаем параметры из URL
    room_category_id = request.args.get('room_category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    room_category = None
    if room_category_id:
        # Получаем информацию о категории номера
        try:
            with db_manager.get_cursor('central') as cursor:
                cursor.execute("SELECT * FROM categories_room WHERE id = %s", (room_category_id,))
                room_category = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error getting room category: {e}")

    return render_template('booking.html',
                         hotel=hotel,
                         room_category=room_category,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/book', methods=['POST'])
def create_booking_html():
    """Создать бронирование (HTML форма)"""
    try:
        # Получаем данные из формы
        hotel_id = request.form.get('hotel_id')
        guest_id = request.form.get('guest_id')
        room_category_id = request.form.get('room_category_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        total_guests = request.form.get('total_guests', 1)
        guest_name = request.form.get('guest_name')
        guest_email = request.form.get('guest_email')
        guest_phone = request.form.get('guest_phone')

        # Создаем гостя, если нужно
        if guest_id == 'new':
            # Создаем нового гостя
            with db_manager.get_cursor('central') as cursor:
                cursor.execute("""
                    INSERT INTO guests (first_name, last_name, phone_number, email, birth_date)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (
                    guest_name.split()[0] if guest_name else 'Гость',
                    guest_name.split()[-1] if guest_name else '',
                    guest_phone,
                    guest_email,
                    '2000-01-01'  # По умолчанию
                ))
                guest_id = cursor.fetchone()['id']

        # Создаем бронирование
        booking_data = {
            'hotel_id': hotel_id,
            'guest_id': guest_id,
            'room_category_id': room_category_id,
            'start_date': start_date,
            'end_date': end_date,
            'total_guests': int(total_guests)
        }

        result = booking_service.create_booking(booking_data)

        if 'error' in result:
            flash(f'Ошибка при бронировании: {result["error"]}', 'error')
            return redirect(url_for('booking_form', hotel_id=hotel_id))

        flash('Бронирование успешно создано!', 'success')
        return redirect(url_for('payment_form', reservation_id=result['reservation_id']))

    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('booking_form', hotel_id=hotel_id))

@app.route('/payment/<int:reservation_id>')
def payment_form(reservation_id):
    """Форма оплаты"""
    try:
        with db_manager.get_cursor('central') as cursor:
            cursor.execute("""
                SELECT r.*, h.name as hotel_name, g.first_name, g.last_name
                FROM reservations r
                JOIN hotels h ON r.hotel_id = h.id
                JOIN guests g ON r.payer_id = g.id
                WHERE r.id = %s
            """, (reservation_id,))

            reservation = cursor.fetchone()

            if not reservation:
                return render_template('404.html', message='Бронирование не найдено'), 404

            return render_template('payment.html', reservation=reservation)
    except Exception as e:
        logger.error(f"Error getting reservation: {e}")
        return render_template('error.html', error=str(e))

@app.route('/pay', methods=['POST'])
def process_payment_html():
    """Обработать оплату (HTML форма)"""
    try:
        reservation_id = request.form.get('reservation_id')
        amount = request.form.get('amount')
        method = request.form.get('method', 'card')

        # Валидация параметров
        if not reservation_id:
            flash('Ошибка: не указан номер бронирования', 'error')
            return redirect(url_for('index'))

        if not amount:
            flash('Ошибка: не указана сумма оплаты', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        # Проверяем, что сумма является числом
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                flash('Ошибка: сумма оплаты должна быть больше нуля', 'error')
                return redirect(url_for('payment_form', reservation_id=reservation_id))
        except (ValueError, TypeError):
            flash('Ошибка: некорректная сумма оплаты', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        # Проверяем, что метод оплаты корректен
        if method not in ['cash', 'card', 'online']:
            flash('Ошибка: некорректный метод оплаты', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        payment_data = {
            'reservation_id': int(reservation_id),
            'amount': amount_float,
            'method': method
        }

        result = payment_service.process_payment(payment_data)

        if 'error' in result:
            flash(f'Ошибка при оплате: {result["error"]}', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        flash('Оплата прошла успешно!', 'success')
        return redirect(url_for('index'))

    except ValueError as e:
        logger.error(f"Validation error in payment: {e}")
        flash('Ошибка: некорректные данные для оплаты', 'error')
        return redirect(url_for('payment_form', reservation_id=reservation_id if reservation_id else 1))
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('payment_form', reservation_id=reservation_id if reservation_id else 1))

@app.route('/admin')
def admin_dashboard():
    """Админская панель - выбор города"""
    try:
        # Получаем список всех городов из центральной БД (справочник)
        with db_manager.get_cursor('central') as cursor:
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
            
        return render_template('admin_dashboard.html', cities=cities_list)
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        return render_template('error.html', error=str(e))

@app.route('/admin/<city_name>')
def admin_city(city_name):
    """Админка города - список отелей"""
    try:
        hotels = hotel_service.get_all_hotels(city_name)
        if not hotels:
            flash(f'В городе {city_name} нет отелей', 'warning')
            return redirect(url_for('admin_dashboard'))
            
        return render_template('admin_city.html', city_name=city_name, hotels=hotels)
    except Exception as e:
        logger.error(f"Error loading admin city {city_name}: {e}")
        return render_template('error.html', error=str(e))

@app.route('/admin/hotels/<int:hotel_id>')
def admin_hotel(hotel_id):
    """Админка отеля"""
    hotel = hotel_service.get_hotel_details(hotel_id)
    if not hotel:
        return render_template('404.html'), 404

    return render_template('admin_hotel.html', hotel=hotel)

@app.route('/admin/hotels/<int:hotel_id>/update', methods=['POST'])
def update_hotel_html(hotel_id):
    """Обновить информацию об отеле"""
    try:
        hotel_data = {
            'name': request.form.get('name'),
            'address': request.form.get('address'),
            'phone_number': request.form.get('phone_number'),
            'email': request.form.get('email'),
            'check_in_time': request.form.get('check_in_time'),
            'check_out_time': request.form.get('check_out_time'),
            'description': request.form.get('description')
        }

        result = hotel_service.update_hotel(hotel_id, hotel_data)

        if 'error' in result:
            flash(f'Ошибка: {result["error"]}', 'error')
        else:
            flash('Информация об отеле обновлена!', 'success')

        return redirect(url_for('admin_hotel', hotel_id=hotel_id))

    except Exception as e:
        logger.error(f"Error updating hotel: {e}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('admin_hotel', hotel_id=hotel_id))

@app.route('/reception/<int:hotel_id>')
def reception_desk(hotel_id):
    """Страница ресепшена"""
    hotel = hotel_service.get_hotel_details(hotel_id)
    if not hotel:
        return render_template('404.html'), 404

    reservations = booking_service.get_reservations(hotel_id, 'pending')

    return render_template('reception.html',
                         hotel=hotel,
                         reservations=reservations)

@app.route('/reception/register-guests', methods=['POST'])
def register_guests_html():
    """Зарегистрировать гостей (HTML форма)"""
    try:
        reservation_id = request.form.get('reservation_id')
        room_id = request.form.get('room_id')
        guest_ids = request.form.getlist('guest_ids')  # Для множественного выбора

        result = booking_service.register_guests(
            int(reservation_id),
            int(room_id),
            [int(gid) for gid in guest_ids]
        )

        if 'error' in result:
            flash(f'Ошибка: {result["error"]}', 'error')
        else:
            flash('Гости успешно зарегистрированы!', 'success')

        # Получаем hotel_id для редиректа
        with db_manager.get_cursor('central') as cursor:
            cursor.execute("SELECT hotel_id FROM reservations WHERE id = %s", (reservation_id,))
            hotel_id = cursor.fetchone()['hotel_id']

        return redirect(url_for('reception_desk', hotel_id=hotel_id))

    except Exception as e:
        logger.error(f"Error registering guests: {e}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('reception_desk', hotel_id=1))

# ========== API ПУНКТЫ (для AJAX) ==========

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности API"""
    try:
        return jsonify({
            'status': 'healthy',
            'message': 'API is running',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/hotels', methods=['GET'])
def get_hotels_api():
    """Получить список отелей (API)"""
    city = request.args.get('city')
    hotels = hotel_service.get_all_hotels(city)
    return jsonify(hotels)

@app.route('/api/check-availability', methods=['GET'])
def check_availability_api():
    """Проверить доступность номера (API)"""
    hotel_id = request.args.get('hotel_id')
    room_category_id = request.args.get('room_category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not all([hotel_id, room_category_id, start_date, end_date]):
        return jsonify({'error': 'Missing required parameters'}), 400

    result = availability_service.check_room_availability(
        int(hotel_id), int(room_category_id), start_date, end_date
    )

    if 'error' in result:
        return jsonify(result), result.get('status', 400)

    return jsonify(result)

# ========== ВСПОМОГАТЕЛЬНЫЕ ПУНКТЫ ==========

@app.route('/api/available-rooms/<int:hotel_id>')
def get_available_rooms_api(hotel_id):
    """Получить доступные номера для регистрации"""
    room_category_id = request.args.get('room_category_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not all([room_category_id, start_date, end_date]):
        return jsonify({'error': 'Missing parameters'}), 400

    rooms = availability_service.find_available_rooms(
        hotel_id, int(room_category_id), start_date, end_date
    )

    return jsonify(rooms)

def _get_db_by_hotel_city(hotel_id):
    """Вспомогательная функция для определения БД по городу отеля"""
    try:
        with db_manager.get_cursor('central') as cursor:
            cursor.execute("""
                SELECT c.city_name
                FROM hotels h
                JOIN cities c ON h.city_id = c.id
                WHERE h.id = %s
            """, (hotel_id,))
            
            result = cursor.fetchone()
            if result:
                city_name = result['city_name']
                db_mapping = {
                    'Москва': 'filial1',
                    'Санкт-Петербург': 'filial2',
                    'Казань': 'filial3'
                }
                return db_mapping.get(city_name, 'central')
            return 'central'
    except Exception:
        return 'central'

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error=str(e)), 500

@app.route('/api/reservations/<int:reservation_id>', methods=['GET'])
def get_reservation_api(reservation_id):
    """Получить информацию о бронировании (API)"""
    try:
        with db_manager.get_cursor('central') as cursor:
            cursor.execute("""
                SELECT r.*, g.first_name, g.last_name, g.phone_number,
                       h.name as hotel_name
                FROM reservations r
                JOIN guests g ON r.payer_id = g.id
                JOIN hotels h ON r.hotel_id = h.id
                WHERE r.id = %s
            """, (reservation_id,))

            reservation = cursor.fetchone()
            if reservation:
                return jsonify(dict(reservation))
            return jsonify({'error': 'Reservation not found'}), 404
    except Exception as e:
        logger.error(f"Error getting reservation: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
