-- ===========================================
-- НАСТРОЙКА ЦЕНТРАЛЬНОГО УЗЛА (ГОЛОВНОЙ ОФИС)
-- ===========================================

-- 1. Создание пользователя для репликации
CREATE ROLE repuser REPLICATION LOGIN PASSWORD 'hotel_repl_2024';

-- 2. Предоставление прав на чтение справочных таблиц
GRANT SELECT ON hotels TO repuser;
GRANT SELECT ON cities TO repuser;
GRANT SELECT ON categories_hotel TO repuser;
GRANT SELECT ON categories_room TO repuser;
GRANT SELECT ON positions TO repuser;
GRANT SELECT ON loyalty_cards TO repuser;
GRANT SELECT ON types_amenities TO repuser;
GRANT SELECT ON guests TO repuser;

-- 3. Создание публикации для репликации с основной копией (РОК)
-- Справочные данные, которые изменяются только в центре
CREATE PUBLICATION pub_reference_data FOR
    TABLE ONLY hotels,
    TABLE ONLY cities,
    TABLE ONLY categories_hotel,
    TABLE ONLY categories_room,
    TABLE ONLY positions,
    TABLE ONLY loyalty_cards,
    TABLE ONLY types_amenities;
