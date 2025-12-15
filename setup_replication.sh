#!/bin/bash

# ===========================================
# СКРИПТ НАСТРОЙКИ РЕПЛИКАЦИИ ПОСЛЕ ЗАПУСКА
# ===========================================

echo "Настройка репликации для сети отелей..."
echo "Ожидание готовности всех узлов..."

# Функция для проверки готовности узла
check_node_ready() {
    local container=$1
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec $container psql -U postgres -d hotel_management -c "SELECT 1;" >/dev/null 2>&1; then
            echo "Узел $container готов"
            return 0
        fi
        echo "Ожидание узла $container (попытка $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done
    
    echo "ОШИБКА: Узел $container не готов после $max_attempts попыток"
    return 1
}

# Функция для выполнения SQL команды
execute_sql() {
    local container=$1
    local sql=$2
    echo "Выполнение SQL в $container..."
    docker exec -i $container psql -U postgres -d hotel_management -c "$sql"
    if [ $? -eq 0 ]; then
        echo "✓ SQL выполнен успешно в $container"
    else
        echo "✗ Ошибка выполнения SQL в $container"
        return 1
    fi
}

# Проверяем готовность всех узлов
echo "Проверка готовности узлов..."
check_node_ready "hotel_central_node" || exit 1
check_node_ready "hotel_filial1_node" || exit 1
check_node_ready "hotel_filial2_node" || exit 1
check_node_ready "hotel_filial3_node" || exit 1

echo "Все узлы готовы. Начинаем настройку репликации..."

# 1. Сначала настраиваем подписки филиалов на справочные данные (РОК)
echo "=== Настройка подписок филиалов на справочные данные (РОК) ==="

for filial in "hotel_filial1_node" "hotel_filial2_node" "hotel_filial3_node"; do
    echo "Настройка подписки на справочные данные для $filial..."
    execute_sql "$filial" "
    CREATE SUBSCRIPTION sub_reference_data
    CONNECTION 'dbname=hotel_management host=192.168.1.10 user=repuser password=hotel_repl_2024'
    PUBLICATION pub_reference_data;" || exit 1
done

# 2. Настройка подписок центрального узла на данные филиалов (РКД)
echo "=== Настройка подписок центрального узла на данные филиалов (РКД) ==="

# Подписки на данные от филиала 1
echo "Настройка подписок на данные от филиала 1..."
execute_sql "hotel_central_node" "
CREATE SUBSCRIPTION sub_filial1_rooms
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_rooms_data;

CREATE SUBSCRIPTION sub_filial1_employees
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_employees_data;

CREATE SUBSCRIPTION sub_filial1_reservations
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_reservations_data;

CREATE SUBSCRIPTION sub_filial1_amenities
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_amenities_data;

CREATE SUBSCRIPTION sub_filial1_payments
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_payments_data;" || exit 1

# Подписки на данные от филиала 2
echo "Настройка подписок на данные от филиала 2..."
execute_sql "hotel_central_node" "
CREATE SUBSCRIPTION sub_filial2_rooms
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_rooms_data;

CREATE SUBSCRIPTION sub_filial2_employees
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_employees_data;

CREATE SUBSCRIPTION sub_filial2_reservations
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_reservations_data;

CREATE SUBSCRIPTION sub_filial2_amenities
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_amenities_data;

CREATE SUBSCRIPTION sub_filial2_payments
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_payments_data;" || exit 1

# Подписки на данные от филиала 3
echo "Настройка подписок на данные от филиала 3..."
execute_sql "hotel_central_node" "
CREATE SUBSCRIPTION sub_filial3_rooms
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_rooms_data;

CREATE SUBSCRIPTION sub_filial3_employees
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_employees_data;

CREATE SUBSCRIPTION sub_filial3_reservations
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_reservations_data;

CREATE SUBSCRIPTION sub_filial3_amenities
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_amenities_data;

CREATE SUBSCRIPTION sub_filial3_payments
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_payments_data;" || exit 1

# 3. Настройка репликации гостей между филиалами (РБОК)
echo "=== Настройка репликации гостей между филиалами (РБОК) ==="

echo "Настройка синхронизации гостей для филиала 1..."
execute_sql "hotel_filial1_node" "
CREATE SUBSCRIPTION sub_guests_from_filial2
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

CREATE SUBSCRIPTION sub_guests_from_filial3
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;" || exit 1

echo "Настройка синхронизации гостей для филиала 2..."
execute_sql "hotel_filial2_node" "
CREATE SUBSCRIPTION sub_guests_from_filial1
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

CREATE SUBSCRIPTION sub_guests_from_filial3
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;" || exit 1

echo "Настройка синхронизации гостей для филиала 3..."
execute_sql "hotel_filial3_node" "
CREATE SUBSCRIPTION sub_guests_from_filial1
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

CREATE SUBSCRIPTION sub_guests_from_filial2
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;" || exit 1

# 4. Настройка подписки центра на гостей от всех филиалов
echo "Настройка подписки центра на гостей от всех филиалов..."
execute_sql "hotel_central_node" "
CREATE SUBSCRIPTION sub_filial1_guests
CONNECTION 'dbname=hotel_management host=192.168.1.100 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

CREATE SUBSCRIPTION sub_filial2_guests
CONNECTION 'dbname=hotel_management host=192.168.1.101 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;

CREATE SUBSCRIPTION sub_filial3_guests
CONNECTION 'dbname=hotel_management host=192.168.1.102 user=repuser password=hotel_repl_2024'
PUBLICATION pub_guests_data;" || exit 1

echo ""
echo "🎉 Репликация настроена успешно!"
echo ""
echo "Архитектура репликации:"
echo "📊 РОК (Репликация с основной копией): Справочники → Филиалы"
echo "📈 РКД (Репликация с консолидацией данных): Операционные данные → Центр"
echo "🔄 РБОК (Репликация без основной копии): Гости ↔ Между всеми узлами"
echo ""
echo "Подключения к узлам:"
echo "🏢 Центральный узел: localhost:5432"
echo "🏨 Филиал 1 (Москва): localhost:5433"
echo "🏨 Филиал 2 (СПб): localhost:5434"
echo "🏨 Филиал 3 (Казань): localhost:5435"
echo ""
echo "Пользователь: postgres"
echo "Пароль: password"
echo "База данных: hotel_management"