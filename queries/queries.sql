-- Создание бронирования

-- 1. Проверка доступности номера на указанные даты
WITH available_rooms AS (
    SELECT r.id
    FROM rooms r
    WHERE r.hotel_id = 1
    AND r.categories_room_id = 1
    AND NOT EXISTS (
        SELECT 1
        FROM reservations res
        JOIN details_reservations dr ON dr.reservation_id = res.id
        WHERE dr.room_id = r.id
        AND res.status IN ('confirmed', 'pending')
        AND (
            (res.start_date <= '2024-05-15' AND res.end_date >= '2024-05-10') OR
            (res.start_date >= '2024-05-10' AND res.start_date < '2024-05-15')
        )
    )
    LIMIT 1
)
-- 2. Создание бронирования
INSERT INTO reservations (
    hotel_id,
    employee_id,
    create_date,
    status,
    total_price,
    payments_status,
    payer_id,
    start_date,
    end_date
)
VALUES (
    1,
    NULL, -- employee_id (NULL если бронирование через сайт)
    NOW(),
    'pending',
    (SELECT price_per_night * 5 FROM categories_room WHERE id = 1),
    'unpaid',
    1, -- payer_id (гость, который платит)
    '2024-05-10',
    '2024-05-15'
)
RETURNING id INTO reservation_id_var;
-- 3. Создание деталей бронирования
INSERT INTO details_reservations (
    reservation_id,
    room_id,
    guest_id,
    requested_room_category,
    total_guest_number
)
VALUES (
    reservation_id_var,
    (SELECT id FROM available_rooms), -- room_id (NULL если номер не выбран сразу)
    1,
    1,
    2
)
RETURNING id INTO detail_id_var;
-- 4. Привязка гостей к бронированию
INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
VALUES
    (detail_id_var, 1),
    (detail_id_var, 2);


-- Оплата бронирования
-- 1. Создание записи о платеже
INSERT INTO payments (
    reservation_id,
    payments_sum,
    payments_date,
    payments_method
)
VALUES (
    1,
    15000.00,
    CURRENT_DATE,
    'card'
);
-- 2. Обновление статуса бронирования
UPDATE reservations
SET
    payments_status = 'paid',
    status = 'confirmed'
WHERE id = 1;
-- -- 3. Начисление бонусных баллов (например, 1% от суммы) -- если делаем
-- UPDATE guests g
-- SET bonus_points = g.bonus_points + (15000 * 0.01)
-- FROM reservations r
-- WHERE g.id = r.payer_id
-- AND r.id = 1;


-- Регистрация гостей и привязка номера к бронированию
-- 1. Выбор свободного номера нужной категории на даты бронирования
WITH free_room AS (
    SELECT r.id
    FROM rooms r
    WHERE r.hotel_id = (SELECT hotel_id FROM reservations WHERE id = 1)
    AND r.categories_room_id = (SELECT requested_room_category FROM details_reservations WHERE reservation_id = 1)
    AND NOT EXISTS (
        SELECT 1
        FROM details_reservations dr2
        JOIN reservations res2 ON dr2.reservation_id = res2.id
        WHERE dr2.room_id = r.id
        AND res2.status IN ('confirmed', 'pending')
        AND res2.id != 1
        AND (
            (res2.start_date <= (SELECT end_date FROM reservations WHERE id = 1)
             AND res2.end_date >= (SELECT start_date FROM reservations WHERE id = 1))
        )
    )
    LIMIT 1
)
-- 2. Привязка конкретного номера к бронированию
UPDATE details_reservations dr
SET room_id = (SELECT id FROM free_room)
WHERE dr.reservation_id = 1
RETURNING dr.id INTO detail_id_var;
-- 3. Добавление новых гостей (если нужно)
INSERT INTO guests (
    first_name,
    last_name,
    phone_number,
    birth_date
)
VALUES (
    'Алексей',
    'Смирнов',
    '+79003334455',
    '1992-07-20'
)
RETURNING id INTO new_guest_id_var;
-- 4. Привязка нового гостя к бронированию
INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
VALUES (detail_id_var, new_guest_id_var);
-- 5. Обновление статуса бронирования
UPDATE reservations
SET status = 'confirmed'
WHERE id = 1;


-- Проверка доступности номера конкретной категории на конкретную дату
CREATE OR REPLACE FUNCTION check_room_availability(
    p_hotel_id INTEGER,
    p_category_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    room_id INTEGER,
    room_number VARCHAR(10),
    floor INTEGER,
    view VARCHAR(30),
    is_available BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        r.room_number,
        r.floor,
        r.view,
        NOT EXISTS (
            SELECT 1
            FROM details_reservations dr
            JOIN reservations res ON dr.reservation_id = res.id
            WHERE dr.room_id = r.id
            AND res.status IN ('confirmed', 'pending')
            AND (
                (res.start_date <= p_end_date AND res.end_date >= p_start_date)
            )
        ) AS is_available
    FROM rooms r
    WHERE r.hotel_id = p_hotel_id
    AND r.categories_room_id = p_category_id;
END;
-- Использование функции
-- SELECT * FROM check_room_availability(1, 1, '2024-05-10', '2024-05-15'); -- вписать в запросы выше


-- Юзер:
-- Главная страница -> Список отелей -> Нажимаешь на отель и в нем список номер (категорий номеров) -> нажимаешь забронировать -> нажимаешь оплатить
-- Главная страница - список отелей
SELECT
    h.id,
    h.name,
    c.city_name,
    ch.star_rating,
    h.location_coeff_room,
    MIN(cr.price_per_night * h.location_coeff_room) as min_price
FROM hotels h
JOIN cities c ON h.city_id = c.id
JOIN categories_hotel ch ON h.star_rating_id = ch.id
LEFT JOIN rooms r ON r.hotel_id = h.id
LEFT JOIN categories_room cr ON r.categories_room_id = cr.id
GROUP BY h.id, c.city_name, ch.star_rating, h.location_coeff_room;
-- Список категорий номеров в отеле
SELECT DISTINCT
    cr.id,
    cr.category_name,
    cr.guests_capacity,
    cr.price_per_night * h.location_coeff_room as final_price,
    cr.description
FROM rooms r
JOIN hotels h ON r.hotel_id = h.id
JOIN categories_room cr ON r.categories_room_id = cr.id
WHERE h.id = 1;


-- Админ:
-- изменение инфы по отелю в виде формы
-- Получение информации об отеле
SELECT
    h.*,
    c.city_name,
    ch.star_rating
FROM hotels h
JOIN cities c ON h.city_id = c.id
JOIN categories_hotel ch ON h.star_rating_id = ch.id
WHERE h.id = 1;
-- Обновление информации об отеле
UPDATE hotels
SET
    name = 'Новое название',
    address = 'Новый адрес',
    phone_number = '+74951112233',
    email = 'new@hotel.ru',
    check_in_time = '14:00',
    check_out_time = '12:00',
    description = 'Новое описание'
WHERE id = 1;


-- Сотрудник ресепшена:
-- просмотр списка бронирований в виде таблицы -- у каждой брони кнопка зарегистрировать гостей
-- Просмотр списка бронирований
SELECT
    r.id as reservation_id,
    r.create_date,
    r.start_date,
    r.end_date,
    r.status,
    r.payments_status,
    r.total_price,
    g.first_name || ' ' || g.last_name as guest_name,
    COUNT(DISTINCT drg.guest_id) as total_guests,
    STRING_AGG(cr.category_name, ', ') as room_categories
FROM reservations r
JOIN guests g ON r.payer_id = g.id
LEFT JOIN details_reservations dr ON dr.reservation_id = r.id
LEFT JOIN room_reservation_guests drg ON drg.room_reservation_id = dr.id
LEFT JOIN categories_room cr ON dr.requested_room_category = cr.id
WHERE r.hotel_id = 1
AND r.start_date >= CURRENT_DATE
GROUP BY r.id, g.first_name, g.last_name
ORDER BY r.start_date;
-- Получение деталей конкретного бронирования для регистрации
SELECT
    r.id as reservation_id,
    g.first_name || ' ' || g.last_name as guest_name,
    g.phone_number,
    g.document,
    cr.category_name as requested_category,
    dr.total_guest_number,
    rm.room_number,
    EXISTS(
        SELECT 1
        FROM room_reservation_guests rrg
        WHERE rrg.room_reservation_id = dr.id
    ) as is_registered
FROM reservations r
JOIN details_reservations dr ON dr.reservation_id = r.id
JOIN guests g ON dr.guest_id = g.id
JOIN categories_room cr ON dr.requested_room_category = cr.id
LEFT JOIN rooms rm ON dr.room_id = rm.id
WHERE r.id = 1;-- Создание бронирования

-- 1. Проверка доступности номера на указанные даты
WITH available_rooms AS (
    SELECT r.id
    FROM rooms r
    WHERE r.hotel_id = 1
    AND r.categories_room_id = 1
    AND NOT EXISTS (
        SELECT 1
        FROM reservations res
        JOIN details_reservations dr ON dr.reservation_id = res.id
        WHERE dr.room_id = r.id
        AND res.status IN ('confirmed', 'pending')
        AND (
            (res.start_date <= '2024-05-15' AND res.end_date >= '2024-05-10') OR
            (res.start_date >= '2024-05-10' AND res.start_date < '2024-05-15')
        )
    )
    LIMIT 1
)
-- 2. Создание бронирования
INSERT INTO reservations (
    hotel_id,
    employee_id,
    create_date,
    status,
    total_price,
    payments_status,
    payer_id,
    start_date,
    end_date
)
VALUES (
    1,
    NULL, -- employee_id (NULL если бронирование через сайт)
    NOW(),
    'pending',
    (SELECT price_per_night * 5 FROM categories_room WHERE id = 1),
    'unpaid',
    1, -- payer_id (гость, который платит)
    '2024-05-10',
    '2024-05-15'
)
RETURNING id INTO reservation_id_var;
-- 3. Создание деталей бронирования
INSERT INTO details_reservations (
    reservation_id,
    room_id,
    guest_id,
    requested_room_category,
    total_guest_number
)
VALUES (
    reservation_id_var,
    (SELECT id FROM available_rooms), -- room_id (NULL если номер не выбран сразу)
    1,
    1,
    2
)
RETURNING id INTO detail_id_var;
-- 4. Привязка гостей к бронированию
INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
VALUES
    (detail_id_var, 1),
    (detail_id_var, 2);


-- Оплата бронирования
-- 1. Создание записи о платеже
INSERT INTO payments (
    reservation_id,
    payments_sum,
    payments_date,
    payments_method
)
VALUES (
    1,
    15000.00,
    CURRENT_DATE,
    'card'
);
-- 2. Обновление статуса бронирования
UPDATE reservations
SET
    payments_status = 'paid',
    status = 'confirmed'
WHERE id = 1;
-- -- 3. Начисление бонусных баллов (например, 1% от суммы) -- если делаем
-- UPDATE guests g
-- SET bonus_points = g.bonus_points + (15000 * 0.01)
-- FROM reservations r
-- WHERE g.id = r.payer_id
-- AND r.id = 1;


-- Регистрация гостей и привязка номера к бронированию
-- 1. Выбор свободного номера нужной категории на даты бронирования
WITH free_room AS (
    SELECT r.id
    FROM rooms r
    WHERE r.hotel_id = (SELECT hotel_id FROM reservations WHERE id = 1)
    AND r.categories_room_id = (SELECT requested_room_category FROM details_reservations WHERE reservation_id = 1)
    AND NOT EXISTS (
        SELECT 1
        FROM details_reservations dr2
        JOIN reservations res2 ON dr2.reservation_id = res2.id
        WHERE dr2.room_id = r.id
        AND res2.status IN ('confirmed', 'pending')
        AND res2.id != 1
        AND (
            (res2.start_date <= (SELECT end_date FROM reservations WHERE id = 1)
             AND res2.end_date >= (SELECT start_date FROM reservations WHERE id = 1))
        )
    )
    LIMIT 1
)
-- 2. Привязка конкретного номера к бронированию
UPDATE details_reservations dr
SET room_id = (SELECT id FROM free_room)
WHERE dr.reservation_id = 1
RETURNING dr.id INTO detail_id_var;
-- 3. Добавление новых гостей (если нужно)
INSERT INTO guests (
    first_name,
    last_name,
    phone_number,
    birth_date
)
VALUES (
    'Алексей',
    'Смирнов',
    '+79003334455',
    '1992-07-20'
)
RETURNING id INTO new_guest_id_var;
-- 4. Привязка нового гостя к бронированию
INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
VALUES (detail_id_var, new_guest_id_var);
-- 5. Обновление статуса бронирования
UPDATE reservations
SET status = 'confirmed'
WHERE id = 1;


-- Проверка доступности номера конкретной категории на конкретную дату
CREATE OR REPLACE FUNCTION check_room_availability(
    p_hotel_id INTEGER,
    p_category_id INTEGER,
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    room_id INTEGER,
    room_number VARCHAR(10),
    floor INTEGER,
    view VARCHAR(30),
    is_available BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.id,
        r.room_number,
        r.floor,
        r.view,
        NOT EXISTS (
            SELECT 1
            FROM details_reservations dr
            JOIN reservations res ON dr.reservation_id = res.id
            WHERE dr.room_id = r.id
            AND res.status IN ('confirmed', 'pending')
            AND (
                (res.start_date <= p_end_date AND res.end_date >= p_start_date)
            )
        ) AS is_available
    FROM rooms r
    WHERE r.hotel_id = p_hotel_id
    AND r.categories_room_id = p_category_id;
END;
-- Использование функции
-- SELECT * FROM check_room_availability(1, 1, '2024-05-10', '2024-05-15'); -- вписать в запросы выше


-- Юзер:
-- Главная страница -> Список отелей -> Нажимаешь на отель и в нем список номер (категорий номеров) -> нажимаешь забронировать -> нажимаешь оплатить
-- Главная страница - список отелей
SELECT
    h.id,
    h.name,
    c.city_name,
    ch.star_rating,
    h.location_coeff_room,
    MIN(cr.price_per_night * h.location_coeff_room) as min_price
FROM hotels h
JOIN cities c ON h.city_id = c.id
JOIN categories_hotel ch ON h.star_rating_id = ch.id
LEFT JOIN rooms r ON r.hotel_id = h.id
LEFT JOIN categories_room cr ON r.categories_room_id = cr.id
GROUP BY h.id, c.city_name, ch.star_rating, h.location_coeff_room;
-- Список категорий номеров в отеле
SELECT DISTINCT
    cr.id,
    cr.category_name,
    cr.guests_capacity,
    cr.price_per_night * h.location_coeff_room as final_price,
    cr.description
FROM rooms r
JOIN hotels h ON r.hotel_id = h.id
JOIN categories_room cr ON r.categories_room_id = cr.id
WHERE h.id = 1;


-- Админ:
-- изменение инфы по отелю в виде формы
-- Получение информации об отеле
SELECT
    h.*,
    c.city_name,
    ch.star_rating
FROM hotels h
JOIN cities c ON h.city_id = c.id
JOIN categories_hotel ch ON h.star_rating_id = ch.id
WHERE h.id = 1;
-- Обновление информации об отеле
UPDATE hotels
SET
    name = 'Новое название',
    address = 'Новый адрес',
    phone_number = '+74951112233',
    email = 'new@hotel.ru',
    check_in_time = '14:00',
    check_out_time = '12:00',
    description = 'Новое описание'
WHERE id = 1;


-- Сотрудник ресепшена:
-- просмотр списка бронирований в виде таблицы -- у каждой брони кнопка зарегистрировать гостей
-- Просмотр списка бронирований
SELECT
    r.id as reservation_id,
    r.create_date,
    r.start_date,
    r.end_date,
    r.status,
    r.payments_status,
    r.total_price,
    g.first_name || ' ' || g.last_name as guest_name,
    COUNT(DISTINCT drg.guest_id) as total_guests,
    STRING_AGG(cr.category_name, ', ') as room_categories
FROM reservations r
JOIN guests g ON r.payer_id = g.id
LEFT JOIN details_reservations dr ON dr.reservation_id = r.id
LEFT JOIN room_reservation_guests drg ON drg.room_reservation_id = dr.id
LEFT JOIN categories_room cr ON dr.requested_room_category = cr.id
WHERE r.hotel_id = 1
AND r.start_date >= CURRENT_DATE
GROUP BY r.id, g.first_name, g.last_name
ORDER BY r.start_date;
-- Получение деталей конкретного бронирования для регистрации
SELECT
    r.id as reservation_id,
    g.first_name || ' ' || g.last_name as guest_name,
    g.phone_number,
    g.document,
    cr.category_name as requested_category,
    dr.total_guest_number,
    rm.room_number,
    EXISTS(
        SELECT 1
        FROM room_reservation_guests rrg
        WHERE rrg.room_reservation_id = dr.id
    ) as is_registered
FROM reservations r
JOIN details_reservations dr ON dr.reservation_id = r.id
JOIN guests g ON dr.guest_id = g.id
JOIN categories_room cr ON dr.requested_room_category = cr.id
LEFT JOIN rooms rm ON dr.room_id = rm.id
WHERE r.id = 1;
