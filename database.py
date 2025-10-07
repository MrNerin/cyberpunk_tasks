import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.conn = None
        self.is_connected = False

    def connect(self):
        """Подключение к базе данных с повторными попытками"""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                # Получаем DATABASE_URL из переменных окружения Railway
                database_url = os.environ.get('DATABASE_URL')

                if not database_url:
                    logger.error("❌ DATABASE_URL не найден в переменных окружения")
                    time.sleep(retry_delay)
                    continue

                logger.info(f"🔄 Попытка подключения к PostgreSQL (попытка {attempt + 1}/{max_retries})...")

                # Конвертируем postgres:// в postgresql:// если нужно
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)

                # Парсим URL для логирования (без пароля)
                parsed_url = database_url.split('@')[-1] if '@' in database_url else database_url
                logger.info(f"🔗 Подключаемся к: {parsed_url}")

                self.conn = psycopg2.connect(
                    database_url,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )

                # Проверяем подключение
                cur = self.conn.cursor()
                cur.execute("SELECT 1")
                cur.close()

                self.is_connected = True
                logger.info("✅ Подключение к PostgreSQL установлено")
                self.init_tables()
                return

            except Exception as e:
                logger.error(f"❌ Попытка {attempt + 1}/{max_retries}: Ошибка подключения к PostgreSQL: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Повторная попытка через {retry_delay} секунд...")
                    time.sleep(retry_delay)
                else:
                    logger.error("❌ Не удалось подключиться к PostgreSQL после всех попыток")
                    # Создаем временное хранилище в памяти для демо
                    self.create_in_memory_storage()

    def create_in_memory_storage(self):
        """Создает временное хранилище в памяти при недоступности PostgreSQL"""
        logger.warning("🔄 Создаем временное хранилище в памяти (данные будут сброшены после перезапуска)")
        self.in_memory_storage = {
            'users': {
                "admin": {"password": "password", "role": "admin", "coins": 100},
                "user1": {"password": "pass1", "role": "user", "coins": 50},
                "user2": {"password": "pass2", "role": "user", "coins": 30}
            },
            'tasks_config': {
                "button1": ["Изучить новый фреймворк", "Прочитать документацию", "Написать тесты"],
                "button2": ["Создать прототип интерфейса", "Оптимизировать базу данных", "Настроить CI/CD"],
                "button3": ["Изучить алгоритмы", "Попрактиковаться в английском", "Посмотреть вебинар"]
            },
            'daily_tasks': {},
            'board_tasks': [],
            'user_progress': {},
            'map_config': {
                'start_point': {'x': 15, 'y': 75, 'type': 'start'},
                'active_points': [
                    {'x': 25, 'y': 70, 'type': 'active'},
                    {'x': 35, 'y': 65, 'type': 'active'},
                    {'x': 45, 'y': 60, 'type': 'active'}
                ],
                'checkpoints': [
                    {'x': 75, 'y': 45, 'type': 'checkpoint', 'name': "Первый уровень", 'required': 5, 'icon': "🎯"},
                    {'x': 85, 'y': 40, 'type': 'checkpoint', 'name': "Второй уровень", 'required': 10, 'icon': "⭐"}
                ],
                'end_point': {'x': 95, 'y': 35, 'type': 'end'},
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_by': 'system'
            },
            'user_positions': {}
        }

    def init_tables(self):
        """Инициализация таблиц только если подключение к БД установлено"""
        if not self.is_connected:
            logger.warning("⚠️ Пропускаем инициализацию таблиц - нет подключения к БД")
            return

        commands = [
            """
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) PRIMARY KEY,
                password VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                coins INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks_config (
                id SERIAL PRIMARY KEY,
                button1 JSONB NOT NULL,
                button2 JSONB NOT NULL,
                button3 JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id SERIAL PRIMARY KEY,
                date DATE UNIQUE NOT NULL,
                tasks JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS board_tasks (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                difficulty VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'free',
                user_taken VARCHAR(50),
                taken_at TIMESTAMP,
                done_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                tasks_done JSONB NOT NULL,
                UNIQUE(username, date)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS map_config (
                id SERIAL PRIMARY KEY,
                start_point JSONB NOT NULL,
                active_points JSONB NOT NULL,
                checkpoints JSONB NOT NULL,
                end_point JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR(50)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_positions (
                username VARCHAR(50) PRIMARY KEY,
                x FLOAT NOT NULL,
                y FLOAT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]

        try:
            cur = self.conn.cursor()
            for command in commands:
                cur.execute(command)
            self.conn.commit()
            cur.close()
            logger.info("✅ Таблицы инициализированы")
            self.insert_initial_data()
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации таблиц: {e}")

    def insert_initial_data(self):
        """Вставка начальных данных только если подключение к БД установлено"""
        if not self.is_connected:
            logger.warning("⚠️ Пропускаем вставку начальных данных - нет подключения к БД")
            return

        try:
            cur = self.conn.cursor()

            # Проверяем, есть ли уже пользователи
            cur.execute("SELECT COUNT(*) as count FROM users")
            if cur.fetchone()['count'] == 0:
                # Добавляем начальных пользователей
                users = [
                    ('admin', 'password', 'admin', 100),
                    ('user1', 'pass1', 'user', 50),
                    ('user2', 'pass2', 'user', 30)
                ]
                for user in users:
                    cur.execute(
                        "INSERT INTO users (username, password, role, coins) VALUES (%s, %s, %s, %s)",
                        user
                    )

            # Проверяем конфигурацию задач
            cur.execute("SELECT COUNT(*) as count FROM tasks_config")
            if cur.fetchone()['count'] == 0:
                default_tasks = {
                    "button1": ["Изучить новый фреймворк", "Прочитать документацию", "Написать тесты"],
                    "button2": ["Создать прототип интерфейса", "Оптимизировать базу данных", "Настроить CI/CD"],
                    "button3": ["Изучить алгоритмы", "Попрактиковаться в английском", "Посмотреть вебинар"]
                }
                cur.execute(
                    "INSERT INTO tasks_config (button1, button2, button3) VALUES (%s, %s, %s)",
                    (json.dumps(default_tasks['button1']),
                     json.dumps(default_tasks['button2']),
                     json.dumps(default_tasks['button3']))
                )

            # Проверяем конфигурацию карты
            cur.execute("SELECT COUNT(*) as count FROM map_config")
            if cur.fetchone()['count'] == 0:
                default_map = {
                    'start_point': {'x': 15, 'y': 75, 'type': 'start'},
                    'active_points': [
                        {'x': 25, 'y': 70, 'type': 'active'},
                        {'x': 35, 'y': 65, 'type': 'active'},
                        {'x': 45, 'y': 60, 'type': 'active'}
                    ],
                    'checkpoints': [
                        {'x': 75, 'y': 45, 'type': 'checkpoint', 'name': "Первый уровень", 'required': 5, 'icon': "🎯"},
                        {'x': 85, 'y': 40, 'type': 'checkpoint', 'name': "Второй уровень", 'required': 10, 'icon': "⭐"}
                    ],
                    'end_point': {'x': 95, 'y': 35, 'type': 'end'}
                }
                cur.execute(
                    "INSERT INTO map_config (start_point, active_points, checkpoints, end_point, updated_by) VALUES (%s, %s, %s, %s, %s)",
                    (json.dumps(default_map['start_point']),
                     json.dumps(default_map['active_points']),
                     json.dumps(default_map['checkpoints']),
                     json.dumps(default_map['end_point']),
                     'system')
                )

            self.conn.commit()
            cur.close()
            logger.info("✅ Начальные данные добавлены")

        except Exception as e:
            logger.error(f"❌ Ошибка добавления начальных данных: {e}")
            self.conn.rollback()

    # Методы для работы с пользователями
    def get_user(self, username):
        if not self.is_connected:
            return self.in_memory_storage['users'].get(username)

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            return user
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя {username}: {e}")
            return None

    def get_all_users(self):
        if not self.is_connected:
            return self.in_memory_storage['users']

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM users ORDER BY username")
            users = cur.fetchall()
            cur.close()
            return {user['username']: dict(user) for user in users}
        except Exception as e:
            logger.error(f"❌ Ошибка получения всех пользователей: {e}")
            return {}

    def update_user_coins(self, username, coins):
        if not self.is_connected:
            if username in self.in_memory_storage['users']:
                self.in_memory_storage['users'][username]['coins'] = coins
            return True

        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET coins = %s WHERE username = %s", (coins, username))
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления монет пользователя {username}: {e}")
            self.conn.rollback()
            return False

    def create_user(self, username, password, role='user', coins=0):
        if not self.is_connected:
            self.in_memory_storage['users'][username] = {
                'password': password,
                'role': role,
                'coins': coins
            }
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password, role, coins) VALUES (%s, %s, %s, %s)",
                (username, password, role, coins)
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка создания пользователя {username}: {e}")
            self.conn.rollback()
            return False

    # Методы для работы с задачами
    def get_tasks_config(self):
        if not self.is_connected:
            return self.in_memory_storage['tasks_config']

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM tasks_config ORDER BY id DESC LIMIT 1")
            config = cur.fetchone()
            cur.close()
            if config:
                return {
                    "button1": config['button1'],
                    "button2": config['button2'],
                    "button3": config['button3']
                }
            return {"button1": [], "button2": [], "button3": []}
        except Exception as e:
            logger.error(f"❌ Ошибка получения конфигурации задач: {e}")
            return {"button1": [], "button2": [], "button3": []}

    def update_tasks_config(self, tasks):
        if not self.is_connected:
            self.in_memory_storage['tasks_config'] = tasks
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO tasks_config (button1, button2, button3) VALUES (%s, %s, %s)",
                (json.dumps(tasks['button1']), json.dumps(tasks['button2']), json.dumps(tasks['button3']))
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления конфигурации задач: {e}")
            self.conn.rollback()
            return False

    def get_daily_tasks(self, date):
        if not self.is_connected:
            return self.in_memory_storage['daily_tasks'].get(date)

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT tasks FROM daily_tasks WHERE date = %s", (date,))
            result = cur.fetchone()
            cur.close()
            return result['tasks'] if result else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения ежедневных задач: {e}")
            return None

    def save_daily_tasks(self, date, tasks):
        if not self.is_connected:
            self.in_memory_storage['daily_tasks'][date] = tasks
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO daily_tasks (date, tasks) VALUES (%s, %s) ON CONFLICT (date) DO UPDATE SET tasks = %s",
                (date, json.dumps(tasks), json.dumps(tasks))
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения ежедневных задач: {e}")
            self.conn.rollback()
            return False

    def get_board_tasks(self):
        if not self.is_connected:
            return self.in_memory_storage['board_tasks']

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM board_tasks ORDER BY id")
            tasks = cur.fetchall()
            cur.close()
            return [dict(task) for task in tasks]
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач доски: {e}")
            return []

    def save_board_tasks(self, tasks):
        if not self.is_connected:
            self.in_memory_storage['board_tasks'] = tasks
            return True

        try:
            cur = self.conn.cursor()
            # Очищаем старые задачи
            cur.execute("DELETE FROM board_tasks")
            # Добавляем новые
            for task in tasks:
                cur.execute(
                    "INSERT INTO board_tasks (text, difficulty, status, user_taken, taken_at, done_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (task['text'], task['difficulty'], task['status'], task.get('user'), task.get('taken_at'),
                     task.get('done_at'))
                )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения задач доски: {e}")
            self.conn.rollback()
            return False

    def update_board_task(self, task_id, updates):
        if not self.is_connected:
            # Обновляем задачу в памяти
            for task in self.in_memory_storage['board_tasks']:
                if task['id'] == task_id:
                    task.update(updates)
                    break
            return True

        try:
            cur = self.conn.cursor()
            set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
            values = list(updates.values())
            values.append(task_id)
            cur.execute(f"UPDATE board_tasks SET {set_clause} WHERE id = %s", values)
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления задачи доски {task_id}: {e}")
            self.conn.rollback()
            return False

    # Методы для прогресса пользователей
    def get_user_progress(self, username, date):
        if not self.is_connected:
            user_progress = self.in_memory_storage['user_progress']
            key = f"{username}_{date}"
            return user_progress.get(key, [])

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT tasks_done FROM user_progress WHERE username = %s AND date = %s", (username, date))
            result = cur.fetchone()
            cur.close()
            return result['tasks_done'] if result else []
        except Exception as e:
            logger.error(f"❌ Ошибка получения прогресса пользователя {username}: {e}")
            return []

    def save_user_progress(self, username, date, tasks_done):
        if not self.is_connected:
            key = f"{username}_{date}"
            self.in_memory_storage['user_progress'][key] = tasks_done
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO user_progress (username, date, tasks_done) VALUES (%s, %s, %s) ON CONFLICT (username, date) DO UPDATE SET tasks_done = %s",
                (username, date, json.dumps(tasks_done), json.dumps(tasks_done))
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения прогресса пользователя {username}: {e}")
            self.conn.rollback()
            return False

    def get_user_all_progress(self, username):
        if not self.is_connected:
            all_tasks = []
            for key, tasks in self.in_memory_storage['user_progress'].items():
                if key.startswith(f"{username}_"):
                    all_tasks.extend(tasks)
            return all_tasks

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT tasks_done FROM user_progress WHERE username = %s", (username,))
            results = cur.fetchall()
            cur.close()
            all_tasks = []
            for result in results:
                all_tasks.extend(result['tasks_done'])
            return all_tasks
        except Exception as e:
            logger.error(f"❌ Ошибка получения всего прогресса пользователя {username}: {e}")
            return []

    # Методы для карты
    def get_map_config(self):
        if not self.is_connected:
            return self.in_memory_storage['map_config']

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM map_config ORDER BY id DESC LIMIT 1")
            config = cur.fetchone()
            cur.close()
            if config:
                return {
                    'start_point': config['start_point'],
                    'active_points': config['active_points'],
                    'checkpoints': config['checkpoints'],
                    'end_point': config['end_point'],
                    'updated_at': config['updated_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_by': config['updated_by']
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения конфигурации карты: {e}")
            return None

    def save_map_config(self, config, updated_by):
        if not self.is_connected:
            self.in_memory_storage['map_config'] = config
            self.in_memory_storage['map_config']['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.in_memory_storage['map_config']['updated_by'] = updated_by
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO map_config (start_point, active_points, checkpoints, end_point, updated_by) VALUES (%s, %s, %s, %s, %s)",
                (json.dumps(config['start_point']),
                 json.dumps(config['active_points']),
                 json.dumps(config['checkpoints']),
                 json.dumps(config['end_point']),
                 updated_by)
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения конфигурации карты: {e}")
            self.conn.rollback()
            return False

    def get_user_position(self, username):
        if not self.is_connected:
            return self.in_memory_storage['user_positions'].get(username, {'x': 15, 'y': 75})

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT x, y FROM user_positions WHERE username = %s", (username,))
            result = cur.fetchone()
            cur.close()
            return {'x': 15, 'y': 75} if not result else dict(result)
        except Exception as e:
            logger.error(f"❌ Ошибка получения позиции пользователя {username}: {e}")
            return {'x': 15, 'y': 75}

    def save_user_position(self, username, x, y):
        if not self.is_connected:
            self.in_memory_storage['user_positions'][username] = {'x': x, 'y': y}
            return True

        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO user_positions (username, x, y) VALUES (%s, %s, %s) ON CONFLICT (username) DO UPDATE SET x = %s, y = %s",
                (username, x, y, x, y)
            )
            self.conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения позиции пользователя {username}: {e}")
            self.conn.rollback()
            return False


# Глобальный объект базы данных
db = Database()