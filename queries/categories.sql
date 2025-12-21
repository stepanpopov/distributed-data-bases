SELECT 
    id AS "ID категории",
    category_name AS "Название категории",
    guests_capacity AS "Вместимость",
    price_per_night AS "Цена за ночь",
    description AS "Описание"
FROM categories_room
ORDER BY price_per_night ASC;
