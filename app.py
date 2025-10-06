# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
import json
import os
import random
from datetime import datetime, date
import functools

app = Flask(__name__)
app.secret_key = 'taskflow_secret_key_2024'

# Пользователи
users = {
    "admin": {"password": "password", "role": "admin"},
    "user1": {"password": "pass1", "role": "user"},
    "user2": {"password": "pass2", "role": "user"}
}

# Хранилище позиций пользователей на карте
user_positions = {}

# Настройки карты (старые, для обратной совместимости)
MAP_SETTINGS = {
    'start_position': (15, 75),
    'points': [
        {'position': (15, 75), 'required': 0, 'name': 'Стартовый лагерь', 'icon': '🏕️'},
        {'position': (40, 50), 'required': 5, 'name': 'Лес знаний', 'icon': '🌲'},
        {'position': (60, 30), 'required': 10, 'name': 'Гора мастерства', 'icon': '🏔️'},
        {'position': (80, 20), 'required': 20, 'name': 'Замок эксперта', 'icon': '🏰'},
        {'position': (90, 10), 'required': 30, 'name': 'Космодром легенд', 'icon': '🚀'}
    ]
}


# Инициализация файлов
def init_files():
    default_tasks = {
        "button1": ["Изучить новый фреймворк", "Прочитать документацию", "Написать тесты"],
        "button2": ["Создать прототип интерфейса", "Оптимизировать базу данных", "Настроить CI/CD"],
        "button3": ["Изучить алгоритмы", "Попрактиковаться в английском", "Посмотреть вебинар"]
    }

    if not os.path.exists('tasks.json'):
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(default_tasks, f, ensure_ascii=False, indent=2)

    if not os.path.exists('tasks_board.json'):
        with open('tasks_board.json', 'w', encoding='utf-8') as f:
            json.dump([], f)

    if not os.path.exists('user_progress.json'):
        with open('user_progress.json', 'w', encoding='utf-8') as f:
            json.dump({}, f)

    if not os.path.exists('daily_tasks.json'):
        generate_daily_tasks()

    # Создаем файл конфигурации карты если его нет
    if not os.path.exists('map_config.json'):
        default_map_config = {
            'start_point': {'x': 15, 'y': 75},
            'active_points': [
                {'x': 20, 'y': 80}, {'x': 25, 'y': 75}, {'x': 30, 'y': 70},
                {'x': 35, 'y': 65}, {'x': 40, 'y': 60}, {'x': 45, 'y': 55}
            ],
            'checkpoints': [
                {'x': 40, 'y': 50, 'name': "Лес знаний", 'required': 5, 'icon': "🌲"},
                {'x': 60, 'y': 30, 'name': "Гора мастерства", 'required': 10, 'icon': "🏔️"},
                {'x': 80, 'y': 20, 'name': "Замок эксперта", 'required': 20, 'icon': "🏰"}
            ],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': 'system'
        }
        with open('map_config.json', 'w', encoding='utf-8') as f:
            json.dump(default_map_config, f, ensure_ascii=False, indent=2)

    # Исправляем формат конфигурации если нужно
    fix_map_config_format()

    # Инициализируем позиции пользователей
    load_user_positions()


def fix_map_config_format():
    """Исправляет формат конфигурации карты если нужно"""
    try:
        with open('map_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Исправляем названия полей
        fixed = False
        if 'startPoint' in config:
            config['start_point'] = config.pop('startPoint')
            fixed = True
        if 'activePoints' in config:
            config['active_points'] = config.pop('activePoints')
            fixed = True

        if fixed:
            config['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            config['updated_by'] = 'system_fix'
            with open('map_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print("Формат конфигурации карты исправлен")

    except Exception as e:
        print(f"Ошибка при исправлении формата конфигурации: {e}")


# Кэширование
_data_cache = {}
_cache_timeout = {}


def cached_data(key, timeout=60):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = datetime.now().timestamp()
            if (key in _data_cache and key in _cache_timeout and now < _cache_timeout[key]):
                return _data_cache[key]
            result = func(*args, **kwargs)
            _data_cache[key] = result
            _cache_timeout[key] = now + timeout
            return result

        return wrapper

    return decorator


# Функции данных
@cached_data('all_tasks', 300)
def load_tasks():
    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"button1": [], "button2": [], "button3": []}


@cached_data('daily_tasks', 3600)
def load_daily_tasks():
    try:
        with open('daily_tasks.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                data = {"date": date.today().strftime('%Y-%m-%d'), "tasks": data}
                save_daily_tasks(data)
            last_date = data.get("date")
            if last_date:
                last_date = datetime.strptime(last_date, '%Y-%m-%d').date()
                if last_date < date.today():
                    generate_daily_tasks()
                    _data_cache.pop('daily_tasks', None)
                    return load_daily_tasks()
            return data.get("tasks", [])
    except:
        generate_daily_tasks()
        return load_daily_tasks()


def save_daily_tasks(tasks):
    data = {"date": date.today().strftime('%Y-%m-%d'), "tasks": tasks}
    with open('daily_tasks.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _data_cache.pop('daily_tasks', None)


def generate_daily_tasks():
    tasks = load_tasks()
    all_tasks = []
    for key in tasks:
        all_tasks.extend(tasks[key])
    daily = random.sample(all_tasks, min(3, len(all_tasks)))
    save_daily_tasks(daily)


@cached_data('board_data', 30)
def load_board():
    try:
        with open('tasks_board.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def save_board(board):
    with open('tasks_board.json', 'w', encoding='utf-8') as f:
        json.dump(board, f, ensure_ascii=False, indent=2)
    _data_cache.pop('board_data', None)


def add_to_board(task_text, difficulty="Средняя"):
    board = load_board()
    new_id = max([t.get('id', 0) for t in board], default=0) + 1
    board.append({
        "id": new_id,
        "text": task_text,
        "difficulty": difficulty,
        "status": "free",
        "user": None,
        "taken_at": None,
        "done_at": None
    })
    save_board(board)


@cached_data('user_progress', 30)
def load_user_progress():
    try:
        with open('user_progress.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def save_user_progress(progress):
    with open('user_progress.json', 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    _data_cache.pop('user_progress', None)


def get_user_daily_done(username):
    progress = load_user_progress()
    today = date.today().strftime('%Y-%m-%d')
    return progress.get(username, {}).get(today, [])


def mark_daily_done(username, task_text):
    progress = load_user_progress()
    today = date.today().strftime('%Y-%m-%d')
    if username not in progress:
        progress[username] = {}
    if today not in progress[username]:
        progress[username][today] = []
    if task_text not in progress[username][today]:
        progress[username][today].append(task_text)
        save_user_progress(progress)


# Функции для работы с позициями пользователей
def load_user_positions():
    """Загружает позиции пользователей из файла"""
    global user_positions
    try:
        with open('user_positions.json', 'r', encoding='utf-8') as f:
            user_positions = json.load(f)
            return user_positions
    except FileNotFoundError:
        # Создаем начальные позиции для всех пользователей
        initial_positions = {}
        for username in users:
            initial_positions[username] = {
                "position": 0,
                "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        save_user_positions(initial_positions)
        return initial_positions
    except Exception as e:
        print(f"Error loading user positions: {e}")
        return {}


def save_user_positions(positions):
    """Сохраняет позиции пользователей в файл"""
    try:
        with open('user_positions.json', 'w', encoding='utf-8') as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving user positions: {e}")


def update_user_position(username, position):
    """Обновляет позицию пользователя"""
    global user_positions
    user_positions[username] = {
        "position": position,
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_user_positions(user_positions)
    return user_positions[username]


def get_user_position(username):
    """Получает позицию пользователя"""
    global user_positions
    return user_positions.get(username, {"position": 0, "updated_at": "2024-01-01 00:00:00"})


def get_all_users_positions():
    """Получает позиции всех пользователей"""
    global user_positions
    return user_positions


# Функция для загрузки конфигурации карты
@cached_data('map_config', 300)
def load_map_config():
    try:
        with open('map_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Гарантируем правильный формат
        if 'start_point' not in config:
            config['start_point'] = {'x': 15, 'y': 75}
        if 'active_points' not in config:
            config['active_points'] = []
        if 'checkpoints' not in config:
            config['checkpoints'] = []

        return config
    except FileNotFoundError:
        # Возвращаем конфигурацию по умолчанию если файла нет
        return {
            'start_point': {'x': 15, 'y': 75},
            'active_points': [
                {'x': 20, 'y': 80}, {'x': 25, 'y': 75}, {'x': 30, 'y': 70},
                {'x': 35, 'y': 65}, {'x': 40, 'y': 60}, {'x': 45, 'y': 55}
            ],
            'checkpoints': [
                {'x': 40, 'y': 50, 'name': "Лес знаний", 'required': 5, 'icon': "🌲"},
                {'x': 60, 'y': 30, 'name': "Гора мастерства", 'required': 10, 'icon': "🏔️"},
                {'x': 80, 'y': 20, 'name': "Замок эксперта", 'required': 20, 'icon': "🏰"}
            ],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': 'system'
        }
    except Exception as e:
        print(f"Error loading map config: {e}")
        return {
            'start_point': {'x': 15, 'y': 75},
            'active_points': [],
            'checkpoints': [],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': 'system'
        }


def calculate_user_position(username):
    """Рассчитываем позицию фишки на карте на основе прогресса"""
    progress = load_user_progress()
    user_data = progress.get(username, {})

    # Считаем общее количество выполненных задач
    total_completed = 0
    for date_tasks in user_data.values():
        total_completed += len(date_tasks)

    # Загружаем конфигурацию карты
    map_config = load_map_config()

    active_points = map_config.get('active_points', [])
    checkpoints = map_config.get('checkpoints', [])
    start_point = map_config.get('start_point', {'x': 15, 'y': 75})

    if not active_points:
        return {
            'total_completed': total_completed,
            'current_level': "Новичок",
            'user_position': (start_point.get('x', 15), start_point.get('y', 75)),
            'next_level_required': 1,
            'progress_percentage': 0
        }

    # Находим достигнутые контрольные точки
    reached_checkpoints = []
    for checkpoint in checkpoints:
        if total_completed >= checkpoint.get('required', 0):
            reached_checkpoints.append(checkpoint)

    # Если нет достигнутых точек, остаёмся на старте
    if not reached_checkpoints:
        position = (start_point.get('x', 15), start_point.get('y', 75))
        next_required = checkpoints[0].get('required', 1) if checkpoints else 1
    else:
        # Берём последнюю достигнутую точку
        last_checkpoint = reached_checkpoints[-1]
        position = (last_checkpoint.get('x', 15), last_checkpoint.get('y', 75))

        # Ищем следующую точку
        next_checkpoint = next((cp for cp in checkpoints if cp.get('required', 0) > total_completed), None)
        next_required = next_checkpoint.get('required', 0) if next_checkpoint else 0

    # Определяем уровень
    if total_completed < 5:
        level = "Новичок"
    elif total_completed < 10:
        level = "Исследователь"
    elif total_completed < 20:
        level = "Мастер"
    elif total_completed < 30:
        level = "Эксперт"
    else:
        level = "Легенда"

    progress_percentage = min(100, int((total_completed / 30) * 100))

    return {
        'total_completed': total_completed,
        'current_level': level,
        'user_position': position,
        'next_level_required': next_required,
        'progress_percentage': progress_percentage
    }


# Маршруты
@app.before_request
def load_user_from_cookie():
    if 'username' not in session:
        username = request.cookies.get('remembered_user')
        if username and username in users:
            session['username'] = username
            session['role'] = users[username]['role']


@app.route('/')
def index():
    daily = load_daily_tasks()
    board_data = load_board()
    today_date = date.today().strftime('%d.%m.%Y')
    user_daily_done = []
    total_completed = 0

    if 'username' in session:
        user_daily_done = get_user_daily_done(session['username'])
        user_position = calculate_user_position(session['username'])
        total_completed = user_position['total_completed']

    return render_template('index.html',
                           daily=daily,
                           board=board_data,
                           today_date=today_date,
                           user_daily_done=user_daily_done,
                           total_completed=total_completed)


@app.route('/map')
def map_page():
    if 'username' not in session:
        user_position = {
            'total_completed': 0,
            'current_level': "Новичок",
            'user_position': (15, 75),
            'next_level_required': 5,
            'progress_percentage': 0
        }
        map_config = load_map_config()
        all_users_positions = {}
    else:
        user_position = calculate_user_position(session['username'])
        map_config = load_map_config()
        all_users_positions = get_all_users_positions()

    # Получаем точки из конфигурации
    active_points = map_config.get('active_points', [])
    checkpoints = map_config.get('checkpoints', [])
    start_point = map_config.get('start_point', {'x': 15, 'y': 75})

    # Создаем объединенный массив всех точек (стартовая + активные)
    all_points = []

    # Добавляем стартовую точку первой
    all_points.append({
        'x': start_point.get('x', 15),
        'y': start_point.get('y', 75)
    })

    # Добавляем все активные точки
    all_points.extend(active_points)

    print(f"DEBUG: Start position: {start_point}")
    print(f"DEBUG: Total points: {len(all_points)}")
    print(f"DEBUG: First point: {all_points[0]}")
    print(f"DEBUG: Active points: {len(active_points)}")

    return render_template('map.html',
                           total_completed=user_position['total_completed'],
                           current_level=user_position['current_level'],
                           user_position=user_position['user_position'],
                           next_level_required=user_position['next_level_required'],
                           progress_percentage=user_position['progress_percentage'],
                           start_position=(start_point.get('x', 15), start_point.get('y', 75)),
                           active_points=active_points,
                           all_points=all_points,  # Передаем все точки включая стартовую
                           checkpoints=checkpoints,
                           all_users_positions=all_users_positions,
                           current_user=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember')

        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            response = make_response(redirect(url_for('index')))
            if remember:
                response.set_cookie('remembered_user', username, max_age=30 * 24 * 60 * 60)
            return response
        return "Неверный логин или пароль", 401

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username and password:
            if username in users:
                return "Пользователь уже существует", 400
            users[username] = {"password": password, "role": "user"}
            session['username'] = username
            session['role'] = "user"
            # Создаем начальную позицию для нового пользователя
            update_user_position(username, 0)
            return redirect(url_for('index'))
        return "Заполните все поля", 400

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('index')))
    response.set_cookie('remembered_user', '', expires=0)
    return response


@app.route('/admin')
def admin():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    tasks = load_tasks()
    board = load_board()
    map_config = load_map_config()

    return render_template('admin.html',
                           tasks=tasks,
                           board=board,
                           map_config=map_config)


@app.route('/admin/save', methods=['POST'])
def admin_save():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    new_tasks = {
        "button1": [t for t in request.form.getlist('button1[]') if t.strip()],
        "button2": [t for t in request.form.getlist('button2[]') if t.strip()],
        "button3": [t for t in request.form.getlist('button3[]') if t.strip()]
    }

    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(new_tasks, f, ensure_ascii=False, indent=2)
    _data_cache.pop('all_tasks', None)

    board_tasks = request.form.getlist('board_tasks[]')
    difficulties = request.form.getlist('board_difficulties[]')
    board = load_board()

    for i, task_text in enumerate(board_tasks):
        if task_text.strip():
            difficulty = difficulties[i] if i < len(difficulties) else "Средняя"
            add_to_board(task_text.strip(), difficulty)

    return redirect(url_for('admin'))


@app.route('/admin/save_map', methods=['POST'])
def admin_save_map():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    try:
        # Получаем данные из формы
        start_point = request.form.get('start_point')
        active_points = request.form.get('active_points')
        checkpoints = request.form.get('checkpoints')

        # Парсим JSON данные
        map_data = {
            'start_point': json.loads(start_point) if start_point else {'x': 15, 'y': 75},
            'active_points': json.loads(active_points) if active_points else [],
            'checkpoints': json.loads(checkpoints) if checkpoints else [],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': session['username']
        }

        # Сохраняем в файл
        with open('map_config.json', 'w', encoding='utf-8') as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)

        # Обновляем кэш
        _data_cache.pop('map_config', None)

        return redirect(url_for('admin'))

    except Exception as e:
        return f"Ошибка при сохранении карты: {str(e)}", 500


@app.route('/admin/update_daily', methods=['POST'])
def update_daily_tasks():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    generate_daily_tasks()
    _data_cache.pop('daily_tasks', None)

    return redirect(url_for('admin'))


@app.route('/board/take/<int:task_id>', methods=['POST'])
def take_task(task_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    board = load_board()
    task = next((t for t in board if t['id'] == task_id), None)
    if task and task['status'] == 'free':
        task['status'] = 'taken'
        task['user'] = session['username']
        task['taken_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_board(board)

    return redirect(url_for('index'))


@app.route('/board/done/<int:task_id>', methods=['POST'])
def mark_done(task_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    board = load_board()
    task = next((t for t in board if t['id'] == task_id), None)
    if task and task['status'] == 'taken' and task['user'] == session['username']:
        task['status'] = 'done'
        task['done_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_board(board)

    return redirect(url_for('index'))


@app.route('/archive')
def archive():
    board_data = [t for t in load_board() if t['status'] == 'done']
    return render_template('archive.html', board=board_data)

@app.route('/rules')
def rules():
    current_date = datetime.now().strftime('%d.%m.%Y')
    return render_template('rules.html', current_date=current_date)


@app.route('/mark_daily_done', methods=['POST'])
def mark_daily_done_route():
    if 'username' not in session:
        return redirect(url_for('login'))

    task_text = request.form.get('task')
    if task_text:
        mark_daily_done(session['username'], task_text)
    return redirect(url_for('index'))


# API для работы с позициями пользователей
@app.route('/api/user/position', methods=['POST'])
def save_user_position():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    position = data.get('position', 0)

    # Проверяем валидность позиции
    map_config = load_map_config()
    active_points = map_config.get('active_points', [])
    if position < 0 or position >= len(active_points):
        return jsonify({'error': 'Invalid position'}), 400

    updated_position = update_user_position(session['username'], position)

    return jsonify({
        'success': True,
        'position': updated_position['position'],
        'updated_at': updated_position['updated_at']
    })


@app.route('/api/users/positions')
def get_users_positions():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    positions = get_all_users_positions()
    return jsonify(positions)


@app.route('/api/user/current_position')
def get_current_user_position():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    position = get_user_position(session['username'])
    return jsonify(position)


# Маршрут для загрузки конфигурации карты (API)
@app.route('/api/map/config')
def api_map_config():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    config = load_map_config()
    return jsonify(config)


if __name__ == '__main__':
    init_files()
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 TaskFlow запущен: http://localhost:{port}")
    print("🗺️  Редактор карты: http://localhost:{port}/admin")
    print("👤 Админ: admin / password")
    app.run(host='0.0.0.0', port=port)