SELECT 
    r.status,
    r.payments_status,
    h.name as hotel_name,
    rm.room_number,
    rm.floor,
    cr.category_name as room_category,
    guest.first_name || ' ' || guest.last_name as guest_name,
    dr.total_guest_number as gn,
    r.start_date,
    r.end_date,
    r.total_price
FROM reservations r
JOIN hotels h ON r.hotel_id = h.id
JOIN details_reservations dr ON r.id = dr.reservation_id
JOIN rooms rm ON dr.room_id = rm.id
JOIN categories_room cr ON rm.categories_room_id = cr.id
JOIN guests guest ON r.payer_id = guest.id
WHERE 
    r.status IN ('confirmed', 'pending')
    -- AND r.end_date >= CURRENT_DATE
ORDER BY 
    r.start_date ASC,
    h.name,
    rm.room_number;