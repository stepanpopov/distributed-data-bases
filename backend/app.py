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
from services.guest_service import GuestService
from services.reception_service import ReceptionService

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
guest_service = GuestService(db_manager)
reception_service = ReceptionService(db_manager)

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

    # Используем сервис для получения категорий номеров
    rooms = hotel_service.get_hotel_room_categories_with_counts(hotel_id)
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
        # Используем сервис для получения информации о категории номера
        room_category = hotel_service.get_room_category_details(int(room_category_id))

    return render_template('booking.html',
                         hotel=hotel,
                         room_category=room_category,
                         room_category_id=room_category_id,
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

        # Проверяем наличие room_category_id
        if not room_category_id:
            flash('Ошибка: не выбрана категория номера', 'error')
            return redirect(url_for('booking_form', hotel_id=hotel_id))

        # Определяем город отеля для выбора БД
        city_name = booking_service._get_city_by_hotel(int(hotel_id))
        if not city_name:
            flash('Отель не найден', 'error')
            return redirect(url_for('booking_form', hotel_id=hotel_id))

        # Определяем филиальную БД для создания операционных данных
        if city_name in ['Москва', 'Санкт-Петербург', 'Казань']:
            db_mapping = {
                'Москва': 'filial1',
                'Санкт-Петербург': 'filial2',
                'Казань': 'filial3'
            }
            primary_db = db_mapping[city_name]
        else:
            primary_db = 'central'

        # Создаем гостя через сервис, если нужно
        if guest_id == 'new':
            if not all([guest_name, guest_phone]):
                flash('Для нового гостя необходимо указать имя и телефон', 'error')
                return redirect(url_for('booking_form', hotel_id=hotel_id))

            # Используем GuestService для создания нового гостя
            guest_data = {
                'full_name': guest_name,
                'phone_number': guest_phone,
                'email': guest_email,
                'birth_date': '2000-01-01'  # Дата по умолчанию
            }
            
            guest_result = guest_service.create_guest(guest_data, primary_db)
            if 'error' in guest_result:
                flash(f'Ошибка создания гостя: {guest_result["error"]}', 'error')
                return redirect(url_for('booking_form', hotel_id=hotel_id))
            
            guest_id = guest_result['guest_id']
            logger.info(f"Создан новый гость с ID: {guest_id} в БД {primary_db}")
        else:
            # Используем существующего гостя
            try:
                guest_id = int(guest_id)
            except ValueError:
                flash('Неверный ID гостя', 'error')
                return redirect(url_for('booking_form', hotel_id=hotel_id))

        # Создаем бронирование через сервис
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
        # Используем ReceptionService для получения информации об оплате
        reservation = reception_service.get_payment_info_for_reservation(reservation_id)
        
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

        # Обрабатываем оплату
        result = payment_service.process_payment(payment_data)

        # Детальное логирование для отладки
        logger.info(f"Payment result for reservation {reservation_id}: {result}")

        # Проверяем результат ПЕРЕД показом сообщений
        if 'error' in result:
            logger.warning(f"Payment error for reservation {reservation_id}: {result['error']}")
            flash(f'Ошибка при оплате: {result["error"]}', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        # Проверяем, что операция действительно успешна
        if not result.get('success'):
            logger.warning(f"Payment failed for reservation {reservation_id}: no success flag")
            flash('Произошла ошибка при обработке платежа', 'error')
            return redirect(url_for('payment_form', reservation_id=reservation_id))

        # Только если всё успешно, показываем сообщение об успехе
        logger.info(f"Payment successful for reservation {reservation_id}")
        flash(f'Оплата прошла успешно! Сумма: {result.get("amount_paid", amount_float)} руб.', 'success')
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
        # Используем HotelService для получения городов с отелями
        cities_list = hotel_service.get_cities_with_hotels_count()
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

        # Получаем hotel_id через ReceptionService
        reservation_info = reception_service.get_payment_info_for_reservation(int(reservation_id))
        hotel_id = reservation_info.get('hotel_id', 1) if reservation_info else 1

        return redirect(url_for('reception_desk', hotel_id=hotel_id))

    except Exception as e:
        logger.error(f"Error registering guests: {e}")
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('reception_desk', hotel_id=1))

@app.route('/reception')
def reception_dashboard():
    """Панель ресепшена - выбор города"""
    try:
        # Используем ReceptionService для получения городов с количеством бронирований
        cities_list = reception_service.get_cities_with_reservations_count()
        return render_template('reception_dashboard.html', cities=cities_list)
    except Exception as e:
        logger.error(f"Error loading reception dashboard: {e}")
        return render_template('error.html', error=str(e))

@app.route('/reception/<city_name>')
def reception_city(city_name):
    """Ресепшен города - список бронирований"""
    try:
        # Используем ReceptionService для получения бронирований города
        reservations_list = reception_service.get_city_reservations(city_name)
        return render_template('reception_city.html',
                             city_name=city_name,
                             reservations=reservations_list)
    except Exception as e:
        logger.error(f"Error loading reception city {city_name}: {e}")
        return render_template('error.html', error=str(e))

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

@app.route('/hotels/<int:hotel_id>/rooms', methods=['GET'])
def get_hotel_rooms(hotel_id):
    """Получить доступные категории номеров в отеле"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if start_date and end_date:
            # Если есть даты, проверяем доступность категорий
            categories = availability_service.get_available_room_categories(
                hotel_id, start_date, end_date
            )
        else:
            # Если дат нет, показываем все категории номеров отеля
            categories = hotel_service.get_hotel_room_categories_with_counts(hotel_id)
            
            # Добавляем поле available_rooms_count для совместимости с API
            for category in categories:
                category['available_rooms_count'] = category.get('room_count', 0)
                category['price_per_night_with_coeff'] = category.get('price_per_night', 0)

        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error getting hotel rooms: {e}")
        return jsonify({'error': str(e)}), 500

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
        # Используем ReceptionService для получения информации о бронировании
        reservation = reception_service.get_payment_info_for_reservation(reservation_id)
        if reservation:
            return jsonify(reservation)
        return jsonify({'error': 'Reservation not found'}), 404
    except Exception as e:
        logger.error(f"Error getting reservation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reservation/<int:reservation_id>')
def reservation_details(reservation_id):
    """Страница деталей бронирования"""
    try:
        # Используем ReceptionService для получения детальной информации о бронировании
        reservation_dict = reception_service.get_reservation_details_with_payment(reservation_id)

        if not reservation_dict:
            return render_template('404.html'), 404

        # Получаем город для навигации
        city_name = reservation_dict.get('city_name')

        return render_template('reservation_details.html',
                             reservation=reservation_dict,
                             city_name=city_name)

    except Exception as e:
        logger.error(f"Error getting reservation details: {e}")
        return render_template('error.html', error=str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
