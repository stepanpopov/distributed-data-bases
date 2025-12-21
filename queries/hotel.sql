-- Запрос для получения информации об отелях
SELECT 
    h.id as hotel_id,
    h.name as hotel_name,
    c.city_name,
    c.country_name_code,
    h.address,
    ch.star_rating,
    h.phone_number,
    h.email,
    h.check_in_time,
    h.check_out_time
FROM hotels h
JOIN cities c ON h.city_id = c.id
JOIN categories_hotel ch ON h.star_rating_id = ch.id
ORDER BY c.city_name, ch.star_rating DESC;
