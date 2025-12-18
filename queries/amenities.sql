SELECT
    ta.name AS amenity_type,
    a.price AS amenity_price
FROM amenities a
JOIN types_amenities ta ON a.types_amenities_id = ta.id
JOIN hotels h ON a.hotel_id = h.id
WHERE a.hotel_id = 1
ORDER BY ta.name, a.price;
