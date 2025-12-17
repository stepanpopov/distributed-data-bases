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
