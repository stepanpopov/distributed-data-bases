import os

class Config:
    # Database URLs для распределенной БД
    CENTRAL_DB_URL = os.getenv('CENTRAL_DB_URL',
                              'postgresql://postgres:password@localhost:5432/hotel_management')
    FILIAL1_DB_URL = os.getenv('FILIAL1_DB_URL',
                              'postgresql://postgres:password@localhost:5433/hotel_management')
    FILIAL2_DB_URL = os.getenv('FILIAL2_DB_URL',
                              'postgresql://postgres:password@localhost:5434/hotel_management')
    FILIAL3_DB_URL = os.getenv('FILIAL3_DB_URL',
                              'postgresql://postgres:password@localhost:5435/hotel_management')

    # Маппинг городов к БД
    CITY_TO_DB = {
        'Москва': 'filial1',
        'Санкт-Петербург': 'filial2',
        'Казань': 'filial3'
    }

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
