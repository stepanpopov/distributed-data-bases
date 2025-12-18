#!/bin/bash

docker exec -i hotel_central_node psql -U postgres -d hotel_management < ./queries/active_bookings.sql
docker exec -i hotel_central_node psql -U postgres -d hotel_management < ./queries/check_booking_category.sql

docker exec -i hotel_filial1_node psql -U postgres -d hotel_management < ./queries/book.sql

docker exec -i hotel_central_node psql -U postgres -d hotel_management < ./queries/active_bookings.sql
docker exec -i hotel_central_node psql -U postgres -d hotel_management < ./queries/check_booking_category.sql
