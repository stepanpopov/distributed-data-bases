-- ===========================================
-- ЗАПОЛНЕНИЕ ДАННЫХ ДЛЯ УЗЛА 1 (Hotel Central Moscow - Москва)
-- START WITH 1 INCREMENT BY 3 (1, 4, 7, 10...)
-- ===========================================

-- Настройка IDENTITY для узла 1
-- Для PostgreSQL нужно изменить параметры последовательности напрямую
SELECT setval(pg_get_serial_sequence('employees', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('rooms', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('amenities', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('reservations', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('details_reservations', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('payments', 'id'), 1, false);
SELECT setval(pg_get_serial_sequence('payments_amenities', 'id'), 1, false);

-- Гости отеля 1 (создаются на филиале, используют SERIAL)
INSERT INTO guests (first_name, last_name, middle_name, phone_number, email, birth_date, document, loyalty_card_id, bonus_points)
VALUES
('Иван', 'Иванов', 'Иванович', '+79001112233', 'ivanov@mail.ru',
 '1990-03-12', '4510 123456', 1, 300),
('Дмитрий', 'Кузнецов', 'Алексеевич', '+79006667788', 'dmitry@mail.ru',
 '1985-08-10', '4514 456789', 1, 800);

-- Номера для отеля 1 (Hotel Central Moscow) - ID будут: 1, 4, 7, 10, 13, 16
INSERT INTO rooms (hotel_id, categories_room_id, room_number, floor, view) VALUES
(1, 1, '101', 1, 'Вид на улицу'),
(1, 1, '102', 1, 'Вид на двор'),
(1, 2, '201', 2, 'На город'),
(1, 2, '202', 2, 'На Тверскую'),
(1, 3, '301', 3, 'Панорамный вид'),
(1, 3, '302', 3, 'Люкс с балконом');

-- Удобства для отеля 1 - ID будут: 1, 4, 7, 10
INSERT INTO amenities (hotel_id, types_amenities_id, price) VALUES
(1, 1, 0.00),   -- Бассейн бесплатно - ID=1
(1, 2, 500.00), -- Парковка платная - ID=4
(1, 3, 1500.00), -- Спа платное - ID=7
(1, 4, 0.00);   -- Тренажерный зал бесплатно - ID=10

-- Сотрудники отеля 1 - ID будут: 1, 4, 7, 10
INSERT INTO employees (first_name, last_name, middle_name, position_id, phone_number, email, employment_date, fired_date, hotel_id, salary)
VALUES
('Анна', 'Кузнецова', 'Олеговна', 4, '+79007776655', 'director@central.ru',
 '2022-01-10', NULL, 1, 150000),
('Игорь', 'Петров', 'Сергеевич', 1, '+79007776656', 'admin@central.ru',
 '2023-02-15', NULL, 1, 65000),
('Светлана', 'Морозова', 'Владимировна', 2, '+79007776657', 'manager@central.ru',
 '2023-03-20', NULL, 1, 75000),
('Марина', 'Соколова', 'Андреевна', 3, '+79007776658', 'service@central.ru',
 '2023-04-01', NULL, 1, 45000);

-- Бронирования для отеля 1 - ID будут: 1, 4
INSERT INTO reservations (hotel_id, employee_id, create_date, status, total_price, payments_status, payer_id, start_date, end_date)
VALUES
(1, 1, '2024-03-01 10:30:00', 'confirmed', 15000.00, 'paid', 1, '2024-03-10', '2024-03-15'),
(1, 4, '2024-03-15 14:20:00', 'pending', 25000.00, 'unpaid', 2, '2024-04-01', '2024-04-05');

-- Детали бронирования - ID будут: 1, 4
INSERT INTO details_reservations (reservation_id, room_id, guest_id, requested_room_category, total_guest_number)
VALUES
(1, 1, 1, 1, 2),
(4, 4, 2, 3, 1);

-- Платежи - ID = 1
INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method) VALUES
(1, 15000.00, '2024-03-05', 'card');

-- Распределение гостей по комнатам
INSERT INTO room_reservation_guests (room_reservation_id, guest_id) VALUES
(1, 1),
(4, 2);

-- Платежи за удобства - ID = 1
INSERT INTO payments_amenities (hotel_amenities_id, payment_id, quantity, total_amenities_price) VALUES
(4, 1, 1, 500.00),  -- Парковка (amenities ID=4, payment ID=1)
(7, 1, 1, 1500.00); -- Спа (amenities ID=7, payment ID=1)
