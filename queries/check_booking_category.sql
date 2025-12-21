-- Параметры поиска
-- Отель: 1 (Hotel Central Moscow)
-- Категория номера: 1 (Стандарт)
-- Даты: 2024-05-15 - 2024-05-18

WITH room_availability AS (
    SELECT 
        r.id as room_id,
        r.room_number,
        CASE 
            WHEN EXISTS (
                SELECT 1 
                FROM details_reservations dr
                JOIN reservations res ON dr.reservation_id = res.id
                WHERE dr.room_id = r.id
                  AND res.status IN ('confirmed', 'pending')
                  AND NOT (res.end_date <= '2024-05-15' OR res.start_date >= '2024-05-18')
            ) THEN 0  -- Занят
            ELSE 1    -- Доступен
        END as is_available
    FROM rooms r
    WHERE r.hotel_id = 1 
      AND r.categories_room_id = 1
)
SELECT 
    COUNT(*) as total_rooms,
    SUM(is_available) as available_rooms_count,
    COUNT(*) - SUM(is_available) as occupied_rooms_count
FROM room_availability;
