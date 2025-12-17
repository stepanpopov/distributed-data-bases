-- ===========================================
-- ЗАПОЛНЕНИЕ ОПЕРАЦИОННЫХ ДАННЫХ ДЛЯ УЗЛА 3 (Kazan Grand - Казань)
-- Справочные данные получаются через репликацию с центрального узла
-- ===========================================

-- Настройка IDENTITY для узла 3 (ID: 3, 6, 9, 12...)
-- Правильная настройка для INCREMENT BY 3
ALTER SEQUENCE guests_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE employees_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE rooms_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE amenities_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE reservations_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE details_reservations_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE payments_id_seq RESTART WITH 3 INCREMENT BY 3;
ALTER SEQUENCE payments_amenities_id_seq RESTART WITH 3 INCREMENT BY 3;

-- Гости отеля 3 (ID: 3, 6)
INSERT INTO guests (first_name, last_name, middle_name, phone_number, email, birth_date, document, loyalty_card_id, bonus_points)
VALUES
('Александр', 'Сидоров', 'Петрович', '+79009998877', 'sidorov@mail.ru',
 '1988-07-20', '4512 789012', 2, 1200),
('Елена', 'Васильева', 'Андреевна', '+79003334455', 'elena@mail.ru',
 '1992-12-15', '4513 345678', 3, 3500);

-- Номера для отеля 3 (Kazan Grand) - ID: 3, 6, 9, 12, 15, 18, 21, 24
INSERT INTO rooms (hotel_id, categories_room_id, room_number, floor, view) VALUES
(3, 1, '106', 1, 'На сад'),
(3, 1, '107', 1, 'На улицу Баумана'),
(3, 1, '108', 1, 'На Кремль'),
(3, 2, '205', 2, 'На Кремль'),
(3, 2, '206', 2, 'На исторический центр'),
(3, 2, '207', 2, 'На Казанку'),
(3, 3, '305', 3, 'Люкс с видом на Кремль'),
(3, 3, '306', 3, 'Президентский люкс');

-- Удобства для отеля 3 - ID: 3, 6, 9, 12
INSERT INTO amenities (hotel_id, types_amenities_id, price) VALUES
(3, 1, 1000.00), -- Бассейн премиум - ID=3
(3, 2, 700.00),  -- Парковка - ID=6
(3, 3, 2500.00), -- Спа люкс - ID=9
(3, 4, 0.00);    -- Тренажерный зал бесплатно - ID=12

-- Сотрудники отеля 3 - ID: 3, 6, 9, 12
INSERT INTO employees (first_name, last_name, middle_name, position_id, phone_number, email, employment_date, fired_date, hotel_id, salary)
VALUES
('Рамиль', 'Хасанов', 'Маратович', 4, '+78435550125', 'director@kazangrand.ru',
 '2022-03-15', NULL, 3, 170000),
('Гульназ', 'Минниханова', 'Рустамовна', 1, '+78435550126', 'admin@kazangrand.ru',
 '2023-01-20', NULL, 3, 72000),
('Айрат', 'Сафин', 'Ильгизович', 2, '+78435550127', 'manager@kazangrand.ru',
 '2023-04-10', NULL, 3, 80000),
('Алсу', 'Гарипова', 'Азатовна', 3, '+78435550128', 'service@kazangrand.ru',
 '2023-06-01', NULL, 3, 50000);

-- Бронирования для отеля 3 - ID: 3, 6, 9
INSERT INTO reservations (hotel_id, employee_id, create_date, status, total_price, payments_status, payer_id, start_date, end_date)
VALUES
(3, 3, '2024-05-01 10:15:00', 'confirmed', 35000.00, 'paid', 3, '2024-06-01', '2024-06-05'),
(3, 6, '2024-05-10 16:45:00', 'pending', 28000.00, 'unpaid', 6, '2024-06-15', '2024-06-18'),
(3, 3, '2024-05-15 11:30:00', 'confirmed', 45000.00, 'paid', 3, '2024-07-01', '2024-07-03');

-- Детали бронирования - ID: 3, 6, 9
INSERT INTO details_reservations (reservation_id, room_id, guest_id, requested_room_category, total_guest_number)
VALUES
(3, 21, 3, 3, 2),
(6, 6, 6, 1, 1),
(9, 24, 3, 3, 4);

-- Платежи - ID: 3, 6
INSERT INTO payments (reservation_id, payments_sum, payments_date, payments_method) VALUES
(3, 35000.00, '2024-05-05', 'card'),
(9, 45000.00, '2024-05-18', 'online');

-- Распределение гостей по комнатам
INSERT INTO room_reservation_guests (room_reservation_id, guest_id) VALUES
(3, 3),
(6, 6),
(9, 3);

-- Платежи за удобства - ID: 3, 6
INSERT INTO payments_amenities (hotel_amenities_id, payment_id, quantity, total_amenities_price) VALUES
(3, 3, 1, 1000.00),  -- Бассейн (amenities ID=3, payment ID=3)
(9, 3, 1, 2500.00),  -- Спа (amenities ID=9, payment ID=3)
(6, 6, 1, 700.00);   -- Парковка (amenities ID=6, payment ID=6)
