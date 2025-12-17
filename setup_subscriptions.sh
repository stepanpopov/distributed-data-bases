#!/bin/bash

echo "Настройка подписок репликации для сети отелей..."
echo "Ожидание готовности всех узлов..."

check_node_ready() {
    local container=$1
    local max_attempts=60
    local attempt=1

    echo "Проверка готовности узла $container..."
    while [ $attempt -le $max_attempts ]; do
        if docker exec $container psql -U postgres -d hotel_management -c "SELECT 1;" >/dev/null 2>&1; then
            echo "✅ Узел $container готов"
            return 0
        fi
        echo "Ожидание узла $container (попытка $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    echo "❌ ОШИБКА: Узел $container не готов после $max_attempts попыток"
    return 1
}


execute_sql() {
    local container=$1
    local sql=$2
    local description=$3
    local max_attempts=3
    local attempt=1

    echo "$description в $container..."

    while [ $attempt -le $max_attempts ]; do
        if docker exec -i $container psql -U postgres -d hotel_management -c "$sql" >/dev/null 2>&1; then
            echo "✅ $description выполнено успешно"
            return 0
        fi
        echo "⚠️  Попытка $attempt/$max_attempts не удалась, повтор через 2 сек..."
        sleep 0
        ((attempt++))
    done

    echo "❌ ОШИБКА: $description не выполнено после $max_attempts попыток"
    echo "SQL: $sql"
    return 1
}

echo "Проверка готовности всех узлов..."
check_node_ready "hotel_central_node" || exit 1
check_node_ready "hotel_filial1_node" || exit 1
check_node_ready "hotel_filial2_node" || exit 1
check_node_ready "hotel_filial3_node" || exit 1

echo ""
echo "Все узлы готовы! Начинаем настройку подписок репликации..."
echo ""



echo "=== НАСТРОЙКА ПОДПИСОК НА СПРАВОЧНЫЕ ДАННЫЕ (РОК) ==="
echo "Филиалы подписываются на справочники с центрального узла"
echo ""

for filial in "hotel_filial1_node" "hotel_filial2_node" "hotel_filial3_node"; do
    case $filial in
        "hotel_filial1_node") hotel_name="Москва"; filial_id="filial1" ;;
        "hotel_filial2_node") hotel_name="Санкт-Петербург"; filial_id="filial2" ;;
        "hotel_filial3_node") hotel_name="Казань"; filial_id="filial3" ;;
    esac

    echo "Настройка подписки для филиала в $hotel_name ($filial)..."
    execute_sql "$filial" "
        CREATE SUBSCRIPTION sub_reference_data_${filial_id}
        CONNECTION 'host=postgres-central port=5432 dbname=hotel_management user=repuser password=hotel_repl_2024'
        PUBLICATION pub_reference_data
        WITH (copy_data = true, synchronous_commit = on);" "Подписка на справочные данные" || exit 1

    echo "⏱Ожидание стабилизации подписки..."
    sleep 0
    echo ""
done


echo "=== НАСТРОЙКА ПОДПИСОК ЦЕНТРА НА ДАННЫЕ ФИЛИАЛОВ (РКД) ==="
echo "Центральный узел консолидирует операционные данные со всех филиалов"
echo ""


declare -A filials=(
    ["filial1"]="postgres-filial1"
    ["filial2"]="postgres-filial2"
    ["filial3"]="postgres-filial3"
)

declare -A filial_names=(
    ["filial1"]="Москвы"
    ["filial2"]="Санкт-Петербурга"
    ["filial3"]="Казани"
)


publications=(
    "pub_rooms_data:rooms"
    "pub_employees_data:employees"
    "pub_reservations_data:reservations"
    "pub_amenities_data:amenities"
    "pub_payments_data:payments"
)

for filial_key in "${!filials[@]}"; do
    filial_host="${filials[$filial_key]}"
    filial_name="${filial_names[$filial_key]}"

    echo "Настройка подписок на данные филиала $filial_name ($filial_host)..."

    for pub_info in "${publications[@]}"; do
        IFS=':' read -r pub_name table_description <<< "$pub_info"

        execute_sql "hotel_central_node" "
            CREATE SUBSCRIPTION sub_${filial_key}_${table_description}
            CONNECTION 'host=${filial_host} port=5432 dbname=hotel_management user=repuser password=hotel_repl_2024'
            PUBLICATION ${pub_name}
            WITH (synchronous_commit = on);" "Подписка на $table_description из $filial_name" || exit 1

        sleep 0
    done

    echo "Ожидание стабилизации подписок..."
    sleep 0
    echo ""
done


echo "=== НАСТРОЙКА РЕПЛИКАЦИИ ГОСТЕЙ МЕЖДУ ВСЕМИ УЗЛАМИ (РБОК) ==="
echo "Все филиалы синхронизируют данные гостей друг с другом"
echo ""


declare -A filial_containers=(
    ["hotel_filial1_node"]="postgres-filial1:Москва"
    ["hotel_filial2_node"]="postgres-filial2:Санкт-Петербург"
    ["hotel_filial3_node"]="postgres-filial3:Казань"
)

for subscriber_container in "${!filial_containers[@]}"; do
    IFS=':' read -r subscriber_host subscriber_city <<< "${filial_containers[$subscriber_container]}"

    case $subscriber_container in
        "hotel_filial1_node") subscriber_id="filial1" ;;
        "hotel_filial2_node") subscriber_id="filial2" ;;
        "hotel_filial3_node") subscriber_id="filial3" ;;
    esac

    echo "Настройка подписок на гостей для филиала $subscriber_city..."

    for publisher_container in "${!filial_containers[@]}"; do
        if [ "$subscriber_container" != "$publisher_container" ]; then
            IFS=':' read -r publisher_host publisher_city <<< "${filial_containers[$publisher_container]}"

            case $publisher_container in
                "hotel_filial1_node") publisher_id="filial1" ;;
                "hotel_filial2_node") publisher_id="filial2" ;;
                "hotel_filial3_node") publisher_id="filial3" ;;
            esac

            sub_name="sub_guests_${subscriber_id}_from_${publisher_id}"

            execute_sql "$subscriber_container" "
                CREATE SUBSCRIPTION $sub_name
                CONNECTION 'host=${publisher_host} port=5432 dbname=hotel_management user=repuser password=hotel_repl_2024'
                PUBLICATION pub_guests_data
                WITH (copy_data = false, synchronous_commit = on, origin = none);" "Подписка на гостей из $publisher_city" || exit 1

            sleep 0
        fi
    done

    echo "Ожидание стабилизации подписок на гостей..."
    sleep 0
    echo ""
done

echo "Настройка подписок центрального узла на гостей со всех филиалов..."
for filial_container in "${!filial_containers[@]}"; do
    IFS=':' read -r filial_host filial_city <<< "${filial_containers[$filial_container]}"

    sub_name="sub_guests_from_$(echo $filial_host | sed 's/postgres-filial/filial/')"

    execute_sql "hotel_central_node" "
        CREATE SUBSCRIPTION $sub_name
        CONNECTION 'host=${filial_host} port=5432 dbname=hotel_management user=repuser password=hotel_repl_2024'
        PUBLICATION pub_guests_data
        WITH (synchronous_commit = on, origin = none);" "Подписка центра на гостей из $filial_city" || exit 1

    sleep 0
done

echo ""
echo "==============================================="
echo "ЗАГРУЗКА ОПЕРАЦИОННЫХ ДАННЫХ НА ФИЛИАЛЫ"
echo "==============================================="
echo ""

echo "Загрузка операционных данных на филиалы..."


echo "Загрузка данных филиала Москва..."
if docker exec -i hotel_filial1_node psql -U postgres -d hotel_management < ./init/fill_operations_node1.sql >/dev/null 2>&1; then
    echo "✅ Данные филиала Москва загружены успешно"
else
    echo "❌ ОШИБКА: Не удалось загрузить данные филиала Москва"
    exit 1
fi

echo "Загрузка данных филиала Санкт-Петербург..."
if docker exec -i hotel_filial2_node psql -U postgres -d hotel_management < ./init/fill_operations_node2.sql >/dev/null 2>&1; then
    echo "✅ Данные филиала Санкт-Петербург загружены успешно"
else
    echo "❌ ОШИБКА: Не удалось загрузить данные филиала Санкт-Петербург"
    exit 1
fi

echo "Загрузка данных филиала Казань..."
if docker exec -i hotel_filial3_node psql -U postgres -d hotel_management < ./init/fill_operations_node3.sql >/dev/null 2>&1; then
    echo "✅ Данные филиала Казань загружены успешно"
else
    echo "❌ ОШИБКА: Не удалось загрузить данные филиала Казань"
    exit 1
fi

echo ""
echo "==============================================="
echo "РЕПЛИКАЦИЯ НАСТРОЕНА УСПЕШНО!"
echo "==============================================="
echo ""
echo "Архитектура репликации:"
echo "   📚 РОК (Репликация с основной копией):"
echo "      └── Справочники: Центр → Филиалы"
echo "   📈 РКД (Репликация с консолидацией данных):"
echo "      └── Операционные данные: Филиалы → Центр"
echo "   👥 РБОК (Репликация без основной копии):"
echo "      └── Гости: Все узлы ↔ Все узлы"
echo ""
echo "🔌 Подключения к узлам:"
echo "   🏢 Центральный узел:     localhost:5432"
echo "   🏨 Филиал Москва:        localhost:5433"
echo "   🏨 Филиал Санкт-Петербург: localhost:5434"
echo "   🏨 Филиал Казань:        localhost:5435"
echo ""
echo "👤 Авторизация:"
echo "   Пользователь: postgres"
echo "   Пароль: password"
echo "   База данных: hotel_management"
echo ""
echo "✅ Система готова к работе!"