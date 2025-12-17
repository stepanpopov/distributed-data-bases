import os

class Config:
    # Database URLs для распределенной БД
    # Используем внутренние Docker хосты для работы внутри контейнеров
    CENTRAL_DB_URL = os.getenv('CENTRAL_DB_URL',
                              'postgresql://postgres:password@postgres-central:5432/hotel_management')
    FILIAL1_DB_URL = os.getenv('FILIAL1_DB_URL',
                              'postgresql://postgres:password@postgres-filial1:5432/hotel_management')
    FILIAL2_DB_URL = os.getenv('FILIAL2_DB_URL',
                              'postgresql://postgres:password@postgres-filial2:5432/hotel_management')
    FILIAL3_DB_URL = os.getenv('FILIAL3_DB_URL',
                              'postgresql://postgres:password@postgres-filial3:5432/hotel_management')

    # Маппинг городов к БД
    CITY_TO_DB = {
        'Москва': 'filial1',
        'Санкт-Петербург': 'filial2',
        'Казань': 'filial3'
    }

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
