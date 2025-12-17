-- ===========================================
-- ЗАПОЛНЕНИЕ ДАННЫХ ДЛЯ ЦЕНТРАЛЬНОГО УЗЛА
-- Содержит только справочные данные (без гостей)
-- ===========================================

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

-- Отели
-- Содержит данные обо всех отелях сети
INSERT INTO hotels (name, city_id, address, phone_number, email, star_rating_id, check_in_time, check_out_time, location_coeff_room, description)
VALUES
('Hotel Central Moscow', 1, 'ул. Тверская, 10', '+74951230001',
 'central@hotel.ru', 1, '14:00', '12:00', 1.25,
 'Отель в центральном районе Москвы'),
('Neva Palace', 2, 'Невский проспект, 50', '+78125550002',
 'info@nevapalace.ru', 2, '14:00', '12:00', 1.15,
 'Комфортабельный отель рядом с историческим центром'),
('Kazan Grand', 3, 'ул. Баумана, 25', '+78435550003',
 'info@kazangrand.ru', 3, '15:00', '11:00', 1.10,
 'Роскошный отель в историческом центре Казани');

