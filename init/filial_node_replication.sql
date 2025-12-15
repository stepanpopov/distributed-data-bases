-- ===========================================
-- НАСТРОЙКА УЗЛА ФИЛИАЛА (ОТЕЛЬ)
-- ===========================================

-- 1. Создание публикаций для репликации с консолидацией данных (РКД)
-- Данные, которые создаются локально и передаются в центр

-- Публикация данных о номерах
CREATE PUBLICATION pub_rooms_data FOR 
    TABLE ONLY rooms;

-- Публикация данных о сотрудниках
CREATE PUBLICATION pub_employees_data FOR 
    TABLE ONLY employees;

-- Публикация данных о бронированиях и их деталях
CREATE PUBLICATION pub_reservations_data FOR 
    TABLE ONLY reservations,
    TABLE ONLY details_reservations;

-- Публикация данных об удобствах
CREATE PUBLICATION pub_amenities_data FOR 
    TABLE ONLY amenities;

-- Публикация данных о платежах (консолидация каждые 3 часа)
CREATE PUBLICATION pub_payments_data FOR 
    TABLE ONLY payments;

-- Публикация данных о гостях для репликации без основной копии (РБОК)
CREATE PUBLICATION pub_guests_data FOR 
    TABLE ONLY guests;

-- 2. Создание того же пользователя для репликации
CREATE ROLE repuser REPLICATION LOGIN PASSWORD 'hotel_repl_2024';

-- 3. Предоставление прав на чтение локальных таблиц
GRANT SELECT ON rooms TO repuser;
GRANT SELECT ON employees TO repuser;
GRANT SELECT ON reservations TO repuser;
GRANT SELECT ON details_reservations TO repuser;
GRANT SELECT ON amenities TO repuser;
GRANT SELECT ON payments TO repuser;
GRANT SELECT ON guests TO repuser;

-- 4. Создание подписки на справочные данные от центрального узла (РОК)
CREATE SUBSCRIPTION sub_reference_data
CONNECTION 'dbname=hotel_management host=<CENTRAL_IP> user=repuser password=hotel_repl_2024'
PUBLICATION pub_reference_data;

-- 5. Создание подписки на данные о гостях от других узлов (РБОК)
-- Это для синхронизации гостей между всеми узлами
CREATE SUBSCRIPTION sub_guests_sync
CONNECTION 'dbname=hotel_management host=<OTHER_FILIAL_IP> user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

-- 6. Создание функций для ограничения локальных операций
-- Функция для проверки принадлежности отеля текущему филиалу
CREATE OR REPLACE FUNCTION check_hotel_ownership()
RETURNS TRIGGER AS $$
DECLARE
    local_hotel_id INTEGER;
BEGIN
    -- Получаем ID отеля для данного филиала (например, из конфигурации)
    SELECT current_setting('app.local_hotel_id')::INTEGER INTO local_hotel_id;
    
    -- Проверяем, что операция выполняется для "своего" отеля
    IF NEW.hotel_id != local_hotel_id THEN
        RAISE EXCEPTION 'Cannot modify data for hotel_id %, local hotel_id is %', 
                       NEW.hotel_id, local_hotel_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяем триггер к таблицам, привязанным к отелю
CREATE TRIGGER trigger_check_hotel_rooms
    BEFORE INSERT OR UPDATE ON rooms
    FOR EACH ROW
    EXECUTE FUNCTION check_hotel_ownership();

CREATE TRIGGER trigger_check_hotel_employees
    BEFORE INSERT OR UPDATE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION check_hotel_ownership();

CREATE TRIGGER trigger_check_hotel_reservations
    BEFORE INSERT OR UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION check_hotel_ownership();

CREATE TRIGGER trigger_check_hotel_amenities
    BEFORE INSERT OR UPDATE ON amenities
    FOR EACH ROW
    EXECUTE FUNCTION check_hotel_ownership();

-- 7. Создание функции для автоматического назначения hotel_id
CREATE OR REPLACE FUNCTION set_local_hotel_id()
RETURNS TRIGGER AS $$
DECLARE
    local_hotel_id INTEGER;
BEGIN
    -- Автоматически назначаем локальный hotel_id
    SELECT current_setting('app.local_hotel_id')::INTEGER INTO local_hotel_id;
    NEW.hotel_id := local_hotel_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяем к таблицам при вставке
CREATE TRIGGER trigger_set_hotel_rooms
    BEFORE INSERT ON rooms
    FOR EACH ROW
    EXECUTE FUNCTION set_local_hotel_id();

CREATE TRIGGER trigger_set_hotel_amenities
    BEFORE INSERT ON amenities
    FOR EACH ROW
    EXECUTE FUNCTION set_local_hotel_id();
    