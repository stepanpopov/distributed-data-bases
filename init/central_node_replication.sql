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

-- 3. Создание триггеров для обработки конфликтов гостей (РБОК)
-- Функция для разрешения конфликтов по уникальности документов
CREATE OR REPLACE FUNCTION resolve_guest_conflicts()
RETURNS TRIGGER AS $$
BEGIN
    -- Если найден конфликт по документу, обновляем существующую запись
    IF EXISTS (SELECT 1 FROM guests WHERE document = NEW.document AND document IS NOT NULL) THEN
        UPDATE guests 
        SET first_name = NEW.first_name,
            last_name = NEW.last_name,
            middle_name = NEW.middle_name,
            phone_number = NEW.phone_number,
            email = NEW.email,
            birth_date = NEW.birth_date,
            loyalty_card_id = COALESCE(NEW.loyalty_card_id, loyalty_card_id),
            bonus_points = GREATEST(bonus_points, NEW.bonus_points)
        WHERE document = NEW.document;
        RETURN NULL; -- Предотвращаем вставку
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_resolve_guest_conflicts
    BEFORE INSERT ON guests
    FOR EACH ROW
    EXECUTE FUNCTION resolve_guest_conflicts();

-- 4. Создание публикации для репликации с основной копией (РОК)
-- Справочные данные, которые изменяются только в центре
CREATE PUBLICATION pub_reference_data FOR 
    TABLE ONLY hotels,
    TABLE ONLY cities, 
    TABLE ONLY categories_hotel,
    TABLE ONLY categories_room,
    TABLE ONLY positions,
    TABLE ONLY loyalty_cards,
    TABLE ONLY types_amenities;