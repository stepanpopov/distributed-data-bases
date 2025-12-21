BEGIN;

-- Параметры бронирования
-- Отель: 1 (Hotel Central Moscow)
-- Категория номера: 1 (Стандарт)
-- Гость: 1 (Иван Иванов)
-- Сотрудник: 1 (Анна Кузнецова)
-- Даты: 2024-05-15 - 2024-05-18

-- Найдем доступный номер нужной категории
WITH available_rooms AS (
    SELECT r.id as room_id, r.room_number
    FROM rooms r
    WHERE r.hotel_id = 1 
      AND r.categories_room_id = 1
      AND r.id NOT IN (
          -- Исключаем уже забронированные номера на эти даты
          SELECT DISTINCT dr.room_id
          FROM details_reservations dr
          JOIN reservations res ON dr.reservation_id = res.id
          WHERE res.status IN ('confirmed', 'pending')
            AND NOT (res.end_date <= '2024-05-15' OR res.start_date >= '2024-05-18')
            AND dr.room_id IS NOT NULL
      )
    LIMIT 1
),
-- Рассчитаем цену бронирования
booking_price AS (
    SELECT 
        cr.price_per_night * 3 * h.location_coeff_room * ch.rating_coeff as total_price
    FROM categories_room cr
    JOIN hotels h ON h.id = 1
    JOIN categories_hotel ch ON h.star_rating_id = ch.id
    WHERE cr.id = 1
),
-- Создаем бронирование
new_reservation AS (
    INSERT INTO reservations (
        hotel_id, employee_id, create_date, status, 
        total_price, payments_status, payer_id, start_date, end_date
    )
    SELECT 
        1,
        1,
        NOW(),
        'pending',
        bp.total_price,
        'unpaid',
        1,
        '2024-05-15',
        '2024-05-18'
    FROM booking_price bp
    RETURNING id, total_price
)
-- Создаем детали бронирования
INSERT INTO details_reservations (
    reservation_id, room_id, guest_id, 
    requested_room_category, total_guest_number
)
SELECT 
    nr.id,
    ar.room_id,
    1,
    1,
    2
FROM new_reservation nr, available_rooms ar;

-- Добавляем гостя в комнату
INSERT INTO room_reservation_guests (room_reservation_id, guest_id)
SELECT 
    dr.id,
    1
FROM details_reservations dr
JOIN reservations r ON dr.reservation_id = r.id
WHERE r.create_date >= NOW() - INTERVAL '1 minute'
  AND dr.guest_id = 1
ORDER BY dr.id DESC
LIMIT 1;

-- Показываем результат
SELECT 
    r.id as reservation_id,
    r.total_price,
    rm.room_number,
    cr.category_name,
    r.start_date,
    r.end_date,
    r.status
FROM reservations r
JOIN details_reservations dr ON r.id = dr.reservation_id
JOIN rooms rm ON dr.room_id = rm.id
JOIN categories_room cr ON rm.categories_room_id = cr.id
WHERE r.id = (SELECT MAX(id) FROM reservations);

COMMIT;
