import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер для работы с распределенной БД"""

    def __init__(self):
        self.connections = {}
        self._connect_all()

    def _connect_all(self):
        """Установка соединений со всеми БД"""
        databases = {
            'central': Config.CENTRAL_DB_URL,
            'filial1': Config.FILIAL1_DB_URL,
            'filial2': Config.FILIAL2_DB_URL,
            'filial3': Config.FILIAL3_DB_URL
        }

        for name, url in databases.items():
            try:
                conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
                self.connections[name] = conn
                logger.info(f"Connected to {name} database")
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
                self.connections[name] = None

    def get_db_by_city(self, city_name):
        """Получить соединение с БД по названию города"""
        db_name = Config.CITY_TO_DB.get(city_name, 'central')
        return self.connections.get(db_name)

    def get_central_db(self):
        """Получить соединение с центральной БД"""
        return self.connections.get('central')

    @contextmanager
    def get_cursor(self, db_name='central'):
        """Контекстный менеджер для курсора"""
        conn = self.connections.get(db_name)
        if not conn or conn.closed:
            self._connect_all()
            conn = self.connections.get(db_name)

        if not conn:
            raise Exception(f"Database {db_name} not available")

        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error in {db_name}: {e}")
            raise
        finally:
            cursor.close()

db_manager = DatabaseManager()
