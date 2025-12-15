-- Типы удобств
INSERT INTO types_amenities (name) VALUES
('Бассейн'),
('Парковка'),
('Спа'),
('Тренажерный зал');

-- Города
INSERT INTO cities (city_name, country_name_code) VALUES
('Москва', 'RUS'),
('Санкт-Петербург', 'RUS'),
('Казань', 'RUS');

-- Категории отелей
INSERT INTO categories_hotel (star_rating, rating_coeff) VALUES
(3, 1.00),
(4, 1.25),
(5, 1.50);

-- Категории номеров
INSERT INTO categories_room (category_name, guests_capacity, price_per_night, description) VALUES
('Стандарт', 2, 3500.00, 'Базовый двухместный номер'),
('Улучшенный', 3, 5000.00, 'Номер с улучшенным дизайном'),
('Люкс', 4, 9000.00, 'Высшая категория комфорта');

-- Карты лояльности
INSERT INTO loyalty_cards (program_name, req_bonus_amount, discount) VALUES
('Silver', 0, 5.0),
('Gold', 1000, 10.0),
('Platinum', 3000, 15.0);

-- Должности
INSERT INTO positions (position_name) VALUES
('Администратор'),
('Менеджер'),
('Горничная'),
('Директор');

--Гости
INSERT INTO guests (first_name, last_name, middle_name, phone_number, email, birth_date, document, loyalty_card_id, bonus_points)
VALUES
('Иван', 'Иванов', 'Иванович', '+79001112233', 'ivanov@mail.ru',
 '1990-03-12', '4510 123456', 1, 300),
('Мария', 'Петрова', 'Сергеевна', '+79005556677', NULL,
 '1995-10-05', NULL, NULL, 0);

-- Отели
INSERT INTO hotels (name, city_id, address, phone_number, email, star_rating_id, check_in_time, check_out_time, location_coeff_room, description)
VALUES
('Hotel Central', 1, 'ул. Тверская, 10', '+74951230001',
 'central@hotel.ru', 1, '14:00', '12:00', 1.25,
 'Отель в центральном районе Москвы'),
('Neva Palace', 2, 'Невский проспект, 50', '+78125550002',
 'info@nevapalace.ru', 2, '14:00', '12:00', 1.15,
 'Комфортабельный отель рядом с историческим центром');


-- Номера 
INSERT INTO rooms (hotel_id, categories_room_id, room_number, floor, view) VALUES
(1, 1, '101', 1, 'Вид на улицу'),
(1, 2, '202', 2, 'На город'),
(2, 1, '103', 1, 'На парк');

-- Удобства
INSERT INTO amenities (hotel_id, types_amenities_id, price) VALUES
(1, 1, 0.00),
(1, 2, 500.00),
(2, 3, 2000.00);

-- Сотрудники
INSERT INTO employees (first_name, last_name, middle_name, position_id, phone_number, email, employment_date, fired_date, hotel_id, salary)
VALUES
('Анна', 'Кузнецова', 'Олеговна', 1, '+79007776655', 'admin@central.ru',
 '2023-01-10', NULL, 1, 55000),
('Павел', 'Сидоров', 'Игоревич', 4, '+79009998877', 'director@neva.ru',
 '2022-06-01', NULL, 2, 120000);

--Бронирования
INSERT INTO reservations (hotel_id, employee_id, create_date, status, total_price, payments_status, payer_id, start_date, end_date)
VALUES
(1, 1, '2024-03-01 10:30:00', 'pending', 15000.00, 'unpaid', 1, '2024-03-10', '2024-03-15'),
(2, 2, '2024-04-01 12:00:00', 'confirmed', 22000.00, 'paid', 2, '2024-04-20', '2024-04-25');

-- Детали бронирования
INSERT INTO details_reservations (reservation_id, room_id, guest_id, requested_room_category, total_guest_number)
VALUES
(1, 1, 1, 1, 2),
(2, 3, 2, 3, 1);

-- Платежи
INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method) VALUES
(2, 22000.00, '2024-04-05', 'card');

-- Распределение гостей по комнатам
INSERT INTO room_reservation_guests (room_reservation_id, guest_id) VALUES
(1, 1),
(2, 2);

-- Платежи за удобства
INSERT INTO payments_amenities (hotel_amenities_id, payment_id, quantity, total_amenities_price) VALUES
(2, 1, 1, 500),
(3, 1, 1, 2000);

