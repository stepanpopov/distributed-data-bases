-- ===========================================
-- ЗАПОЛНЕНИЕ ОПЕРАЦИОННЫХ ДАННЫХ ДЛЯ УЗЛА 2 (Neva Palace - Санкт-Петербург)
-- START WITH 2 INCREMENT BY 3 (2, 5, 8, 11...)
-- Справочные данные получаются через репликацию с центрального узла
-- ===========================================

-- Настройка IDENTITY для узла 2 (ID: 2, 5, 8, 11...)
-- Правильная настройка для INCREMENT BY 3
ALTER SEQUENCE guests_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE employees_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE rooms_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE amenities_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE reservations_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE details_reservations_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE payments_id_seq RESTART WITH 2 INCREMENT BY 3;
ALTER SEQUENCE payments_amenities_id_seq RESTART WITH 2 INCREMENT BY 3;

-- Гости отеля 2 (ID будут: 2, 5)
INSERT INTO guests (first_name, last_name, middle_name, phone_number, email, birth_date, document, loyalty_card_id, bonus_points)
VALUES
('Мария', 'Петрова', 'Сергеевна', '+79005556677', 'maria@mail.ru',
 '1995-10-05', '4511 234567', 2, 1500),
('Анна', 'Морозова', 'Игоревна', '+79002223344', 'anna@mail.ru',
 '1993-04-25', '4515 567890', 3, 2200);

-- Номера для отеля 2 (Neva Palace) - ID будут: 2, 5, 8, 11, 14, 17, 20
INSERT INTO rooms (hotel_id, categories_room_id, room_number, floor, view) VALUES
(2, 1, '103', 1, 'На парк'),
(2, 1, '104', 1, 'На Неву'),
(2, 1, '105', 1, 'На внутренний двор'),
(2, 2, '203', 2, 'На Невский проспект'),
(2, 2, '204', 2, 'На Зимний дворец'),
(2, 3, '303', 3, 'Панорамный вид на Неву'),
(2, 3, '304', 3, 'Люкс с видом на Эрмитаж');

-- Удобства для отеля 2 - ID будут: 2, 5, 8, 11
INSERT INTO amenities (hotel_id, types_amenities_id, price) VALUES
(2, 1, 800.00),  -- Бассейн платный - ID=2
(2, 2, 600.00),  -- Парковка - ID=5
(2, 3, 2000.00), -- Спа премиум - ID=8
(2, 4, 300.00);  -- Тренажерный зал - ID=11

-- Сотрудники отеля 2 - ID будут: 2, 5, 8, 11
INSERT INTO employees (first_name, last_name, middle_name, position_id, phone_number, email, employment_date, fired_date, hotel_id, salary)
VALUES
('Павел', 'Сидоров', 'Игоревич', 4, '+78125550123', 'director@neva.ru',
 '2022-06-01', NULL, 2, 160000),
('Ольга', 'Волкова', 'Дмитриевна', 1, '+78125550124', 'admin@neva.ru',
 '2023-03-15', NULL, 2, 68000),
('Дмитрий', 'Козлов', 'Александрович', 2, '+78125550125', 'manager@neva.ru',
 '2023-05-20', NULL, 2, 77000),
('Екатерина', 'Федорова', 'Сергеевна', 3, '+78125550126', 'service@neva.ru',
 '2023-07-10', NULL, 2, 48000);

-- Бронирования для отеля 2 - ID будут: 2, 5, 8
INSERT INTO reservations (hotel_id, employee_id, create_date, status, total_price, payments_status, payer_id, start_date, end_date)
VALUES
(2, 2, '2024-04-01 12:00:00', 'confirmed', 22000.00, 'paid', 2, '2024-04-20', '2024-04-25'),
(2, 5, '2024-04-15 14:30:00', 'pending', 35000.00, 'unpaid', 5, '2024-05-10', '2024-05-15'),
(2, 2, '2024-05-01 16:15:00', 'confirmed', 18000.00, 'paid', 2, '2024-06-01', '2024-06-03');

-- Детали бронирования - ID будут: 2, 5, 8
INSERT INTO details_reservations (reservation_id, room_id, guest_id, requested_room_category, total_guest_number)
VALUES
(2, 2, 2, 1, 1),
(5, 5, 5, 3, 2),
(8, 8, 2, 2, 1);

-- Платежи - ID будут: 2, 5
INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method) VALUES
(2, 22000.00, '2024-04-05', 'card'),
(8, 18000.00, '2024-05-03', 'online');

-- Распределение гостей по комнатам
INSERT INTO room_reservation_guests (room_reservation_id, guest_id) VALUES
(2, 2),
(5, 5),
(8, 2);

-- Платежи за удобства - ID будут: 2, 5
INSERT INTO payments_amenities (hotel_amenities_id, payment_id, quantity, total_amenities_price) VALUES
(2, 2, 1, 800.00),  -- Бассейн (amenities ID=2, payment ID=2)
(5, 2, 1, 600.00),  -- Парковка (amenities ID=5, payment ID=2)
(8, 5, 1, 2000.00); -- Спа (amenities ID=8, payment ID=5)