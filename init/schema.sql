-- Типы удобств
CREATE TABLE types_amenities (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Города
CREATE TABLE cities (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    city_name VARCHAR(100) NOT NULL,
    country_name_code CHAR(3) NOT NULL
);

-- Категории отелей
CREATE TABLE categories_hotel (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    star_rating SMALLINT NOT NULL CHECK (star_rating BETWEEN 1 AND 5),
    rating_coeff NUMERIC(5,2) NOT NULL
);

-- Категории номеров
CREATE TABLE categories_room (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    category_name VARCHAR(255) NOT NULL UNIQUE,
    guests_capacity INTEGER NOT NULL CHECK (guests_capacity > 0),
    price_per_night NUMERIC(10,2) NOT NULL CHECK (price_per_night >= 0),
    description VARCHAR(255)
);

-- Карты лояльности
CREATE TABLE loyalty_cards (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    program_name VARCHAR(100) NOT NULL UNIQUE,
    req_bonus_amount INTEGER NOT NULL CHECK (req_bonus_amount >= 0),
    discount NUMERIC(5,2) NOT NULL CHECK (discount >= 0)
);

-- Должности
CREATE TABLE positions (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    position_name VARCHAR(100) NOT NULL UNIQUE
);

-- Отели (moved before employees to fix dependency)
CREATE TABLE hotels (
    id SERIAL PRIMARY KEY, -- Центральный узел - оставляем SERIAL
    name VARCHAR(100) NOT NULL,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    address VARCHAR(150) NOT NULL,
    phone_number VARCHAR(30) NOT NULL UNIQUE,
    email VARCHAR(30) NOT NULL UNIQUE,
    star_rating_id INTEGER NOT NULL REFERENCES categories_hotel(id),
    check_in_time TIME,
    check_out_time TIME,
    location_coeff_room NUMERIC(5,2),
    description VARCHAR(300) 
);

-- Гости
CREATE TABLE guests (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,    
    middle_name VARCHAR(50),
    phone_number VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    birth_date DATE NOT NULL,
    document VARCHAR(255),
    loyalty_card_id INTEGER REFERENCES loyalty_cards(id),
    bonus_points INTEGER DEFAULT 0 CHECK (bonus_points >= 0)
);
-- Уникальность документа только для непустых значений
CREATE UNIQUE INDEX uq_guests_document_not_null
ON guests(document)
WHERE document IS NOT NULL;
-- Уникальность email только для непустых значений
CREATE UNIQUE INDEX uq_guests_email_not_null
ON guests(email)
WHERE email IS NOT NULL;

-- Сотрудники
CREATE TABLE employees (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50),
    position_id INTEGER NOT NULL REFERENCES positions(id),
    phone_number VARCHAR(20)  NOT NULL,
    email VARCHAR(255),
    employment_date DATE NOT NULL,
    fired_date DATE,
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    salary NUMERIC(12,2) NOT NULL CHECK (salary >= 0)
);
-- Уникальность email только для непустых значений
CREATE UNIQUE INDEX uq_employees_email_not_null
ON employees(email)
WHERE email IS NOT NULL;

-- Номера
CREATE TABLE rooms (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    categories_room_id INTEGER NOT NULL REFERENCES categories_room(id),
    room_number VARCHAR(10)  NOT NULL,
    floor INTEGER NOT NULL,
    view VARCHAR(30),
    UNIQUE (hotel_id, room_number)
);

-- Удобства
CREATE TABLE amenities (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    types_amenities_id INTEGER NOT NULL REFERENCES types_amenities(id),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0)
);

-- Бронирование
CREATE TABLE reservations (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    employee_id INTEGER REFERENCES employees(id),
    create_date TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('confirmed', 'pending', 'cancelled')),
    total_price NUMERIC(12,2),
    payments_status VARCHAR(50) NOT NULL CHECK (payments_status IN ('paid', 'unpaid')),
    payer_id INTEGER NOT NULL REFERENCES guests(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL CHECK (end_date >= start_date)
);

-- Детали бронирования
CREATE TABLE details_reservations (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    reservation_id INTEGER NOT NULL REFERENCES reservations(id),
    room_id INTEGER REFERENCES rooms(id),
    guest_id INTEGER NOT NULL REFERENCES guests(id),
    requested_room_category INTEGER NOT NULL REFERENCES categories_room(id),
    total_guest_number INTEGER NOT NULL CHECK (total_guest_number > 0),
    UNIQUE (reservation_id, room_id, guest_id)
);

-- Платежи
CREATE TABLE payments (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    reservation_id INTEGER NOT NULL REFERENCES reservations(id),
    payments_sum NUMERIC(12,2) NOT NULL CHECK (payments_sum >= 0),
    payments_date DATE NOT NULL,
    payments_method VARCHAR(50) NOT NULL CHECK (payments_method IN ('cash', 'card', 'online'))
);

-- Распределение гостей по комнатам
CREATE TABLE room_reservation_guests (
    room_reservation_id INTEGER NOT NULL REFERENCES details_reservations(id),
    guest_id INTEGER NOT NULL REFERENCES guests(id),
    PRIMARY KEY (room_reservation_id, guest_id)
);

-- Платежи за удобства
CREATE TABLE payments_amenities (
    id BIGINT GENERATED ALWAYS AS IDENTITY 
        (START WITH 1 INCREMENT BY 3) PRIMARY KEY, -- Узлы филиалов: 1,2,3 + 3n
    hotel_amenities_id INTEGER NOT NULL REFERENCES amenities(id),
    payment_id INTEGER NOT NULL REFERENCES payments(id),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    total_amenities_price NUMERIC(12,2) NOT NULL CHECK (total_amenities_price >= 0)
);
