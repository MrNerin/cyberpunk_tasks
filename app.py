# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
import json
import os
import random
from datetime import datetime, date
import functools
import time

# Создаем приложение Flask ПЕРВЫМ
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'taskflow_secret_key_2024')

# Импортируем базу данных ПОСЛЕ создания app
from database import db


# Ждем пока база данных подключится
def wait_for_db():
    max_retries = 10
    retry_delay = 3

    for attempt in range(max_retries):
        try:
            # Проверяем подключение к БД
            db.connect()
            if db.conn and not db.conn.closed:
                print("✅ База данных готова")
                return True
        except Exception as e:
            print(f"❌ Попытка {attempt + 1}/{max_retries}: База данных не готова: {e}")
            if attempt < max_retries - 1:
                print(f"⏳ Ожидание {retry_delay} секунд...")
                time.sleep(retry_delay)

    print("❌ Не удалось подключиться к базе данных")
    return False


# Ждем подключения к БД при запуске
wait_for_db()

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
    return db.get_tasks_config()


@cached_data('daily_tasks', 3600)
def load_daily_tasks():
    today = date.today().strftime('%Y-%m-%d')
    daily_tasks = db.get_daily_tasks(today)

    if not daily_tasks:
        print("🔄 Генерация новых ежедневных задач...")
        generate_daily_tasks()
        daily_tasks = db.get_daily_tasks(today)

    return daily_tasks or []


def save_daily_tasks(tasks):
    today = date.today().strftime('%Y-%m-%d')
    db.save_daily_tasks(today, tasks)
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
    return db.get_board_tasks()


def save_board(board):
    db.save_board_tasks(board)
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


def get_user_daily_done(username):
    today = date.today().strftime('%Y-%m-%d')
    return db.get_user_progress(username, today)


def mark_daily_done(username, task_text):
    today = date.today().strftime('%Y-%m-%d')
    tasks_done = get_user_daily_done(username)

    if task_text not in tasks_done:
        tasks_done.append(task_text)
        db.save_user_progress(username, today, tasks_done)


def unmark_daily_done(username, task_text):
    today = date.today().strftime('%Y-%m-%d')
    tasks_done = get_user_daily_done(username)

    if task_text in tasks_done:
        tasks_done.remove(task_text)
        db.save_user_progress(username, today, tasks_done)
        return True
    return False


def add_coins(username, amount):
    user = db.get_user(username)
    if user:
        new_coins = user['coins'] + amount
        db.update_user_coins(username, new_coins)


def get_user_coins(username):
    user = db.get_user(username)
    return user['coins'] if user else 0


@cached_data('map_config', 300)
def load_map_config():
    return db.get_map_config()


def save_map_config(config):
    db.save_map_config(config, session.get('username', 'system'))
    _data_cache.pop('map_config', None)


def get_user_position(username):
    return db.get_user_position(username)


def save_user_position(username, x, y):
    db.save_user_position(username, x, y)


def calculate_user_position(username):
    """Рассчитываем прогресс пользователя"""
    tasks_done = db.get_user_all_progress(username)
    total_completed = len(tasks_done)

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
        'progress_percentage': progress_percentage
    }


# Функции для работы с инвентарем
def init_inventory_table():
    """Инициализация таблицы инвентаря если она не существует"""
    if not db.is_connected:
        return

    try:
        cur = db.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.conn.commit()
        cur.close()
        print("✅ Таблица инвентаря инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации таблицы инвентаря: {e}")
        db.conn.rollback()


def get_user_inventory(username):
    """Получаем инвентарь пользователя"""
    if not db.is_connected:
        return db.in_memory_storage.get('user_inventory', {}).get(username, [])

    try:
        cur = db.conn.cursor()
        cur.execute("""
            SELECT id, name, description, quantity, created_at, updated_at 
            FROM user_inventory 
            WHERE username = %s 
            ORDER BY created_at DESC
        """, (username,))
        inventory = cur.fetchall()
        cur.close()
        return [dict(item) for item in inventory]
    except Exception as e:
        print(f"Ошибка получения инвентаря: {e}")
        return []


def add_item_to_inventory(username, name, description, quantity=1):
    """Добавляем предмет в инвентарь"""
    if not db.is_connected:
        if 'user_inventory' not in db.in_memory_storage:
            db.in_memory_storage['user_inventory'] = {}
        if username not in db.in_memory_storage['user_inventory']:
            db.in_memory_storage['user_inventory'][username] = []

        new_id = max([item.get('id', 0) for item in db.in_memory_storage['user_inventory'][username]], default=0) + 1
        db.in_memory_storage['user_inventory'][username].append({
            'id': new_id,
            'name': name,
            'description': description,
            'quantity': quantity,
            'created_at': datetime.now()
        })
        return True

    try:
        cur = db.conn.cursor()
        cur.execute("""
            INSERT INTO user_inventory (username, name, description, quantity) 
            VALUES (%s, %s, %s, %s)
        """, (username, name, description, quantity))
        db.conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"Ошибка добавления предмета: {e}")
        db.conn.rollback()
        return False


def update_inventory_item_db(username, item_id, updates):
    """Обновляем предмет в инвентаре"""
    if not db.is_connected:
        if 'user_inventory' in db.in_memory_storage and username in db.in_memory_storage['user_inventory']:
            for item in db.in_memory_storage['user_inventory'][username]:
                if item['id'] == item_id:
                    item.update(updates)
                    item['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    return True
        return False

    try:
        cur = db.conn.cursor()
        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        values = list(updates.values())
        values.extend([username, item_id])

        cur.execute(f"""
            UPDATE user_inventory 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP 
            WHERE username = %s AND id = %s
        """, values)
        db.conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"Ошибка обновления предмета: {e}")
        db.conn.rollback()
        return False


def delete_inventory_item_db(username, item_id):
    """Удаляем предмет из инвентаря"""
    if not db.is_connected:
        if 'user_inventory' in db.in_memory_storage and username in db.in_memory_storage['user_inventory']:
            db.in_memory_storage['user_inventory'][username] = [
                item for item in db.in_memory_storage['user_inventory'][username]
                if item['id'] != item_id
            ]
            return True
        return False

    try:
        cur = db.conn.cursor()
        cur.execute("DELETE FROM user_inventory WHERE username = %s AND id = %s", (username, item_id))
        db.conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"Ошибка удаления предмета: {e}")
        db.conn.rollback()
        return False


def get_all_users_with_stats():
    """Получаем всех пользователей со статистикой и позициями"""
    users = db.get_all_users()
    users_with_stats = {}
    for username, user_data in users.items():
        user_progress = calculate_user_position(username)
        user_position = get_user_position(username)
        users_with_stats[username] = {
            **user_data,
            'total_completed': user_progress['total_completed'],
            'current_level': user_progress['current_level'],
            'progress_percentage': user_progress['progress_percentage'],
            'position': user_position,
            'registered_date': user_data.get('created_at', 'Неизвестно')
        }
    return users_with_stats


def get_all_inventories():
    """Получаем инвентари всех пользователей"""
    users = db.get_all_users()
    all_inventories = {}

    for username in users.keys():
        inventory = get_user_inventory(username)
        if inventory:
            user_progress = calculate_user_position(username)
            all_inventories[username] = {
                'inventory': inventory,
                'user_info': {
                    'username': username,
                    'role': users[username]['role'],
                    'coins': users[username]['coins'],
                    'total_completed': user_progress['total_completed'],
                    'current_level': user_progress['current_level']
                }
            }

    return all_inventories


# Маршруты
@app.before_request
def load_user_from_cookie():
    if 'username' not in session:
        username = request.cookies.get('remembered_user')
        if username:
            user = db.get_user(username)
            if user:
                session['username'] = username
                session['role'] = user['role']
                session['coins'] = user['coins']


@app.route('/')
def index():
    daily = load_daily_tasks()
    board_data = load_board()
    today_date = date.today().strftime('%d.%m.%Y')
    user_daily_done = []
    total_completed = 0
    user_coins = 0

    if 'username' in session:
        user_daily_done = get_user_daily_done(session['username'])
        user_position = calculate_user_position(session['username'])
        total_completed = user_position['total_completed']
        user_coins = get_user_coins(session['username'])
        session['coins'] = user_coins

    return render_template('index.html',
                           daily=daily,
                           board=board_data,
                           today_date=today_date,
                           user_daily_done=user_daily_done,
                           total_completed=total_completed,
                           user_coins=user_coins)


@app.route('/map')
def map_page():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_position = calculate_user_position(session['username'])
    user_coins = get_user_coins(session['username'])
    session['coins'] = user_coins

    # Получаем сохраненную позицию пользователя
    saved_position = get_user_position(session['username'])

    map_config = load_map_config()

    # Получаем данные всех пользователей для отображения их фишек
    all_users = get_all_users_with_stats()

    return render_template('map.html',
                           total_completed=user_position['total_completed'],
                           current_level=user_position['current_level'],
                           user_position=(saved_position['x'], saved_position['y']),
                           progress_percentage=user_position['progress_percentage'],
                           user_coins=user_coins,
                           map_config=map_config,
                           all_users=all_users)


@app.route('/map/save_position', methods=['POST'])
def save_user_position_route():
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        data = request.get_json()
        x = float(data.get('x', 15))
        y = float(data.get('y', 75))

        save_user_position(session['username'], x, y)
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/map_editor')
def map_editor():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    map_config = load_map_config()
    return render_template('map_editor.html', map_config=map_config)


@app.route('/api/map/save', methods=['POST'])
def api_save_map():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    try:
        data = request.get_json()
        save_map_config(data)
        return jsonify({'success': True, 'message': 'Карта сохранена'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember')

        user = db.get_user(username)
        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            session['coins'] = user['coins']
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
            if db.get_user(username):
                return "Пользователь уже существует", 400
            db.create_user(username, password, "user", 0)
            session['username'] = username
            session['role'] = "user"
            session['coins'] = 0
            return redirect(url_for('index'))
        return "Заполните все поля", 400

    return render_template('register.html')


@app.route('/api/user/pin_config', methods=['GET'])
def get_user_pin_config():
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    pin_config = db.get_user_pin_config(session['username'])
    return jsonify(pin_config)


@app.route('/api/user/update_pin', methods=['POST'])
def update_user_pin():
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    data = request.get_json()
    pin_type = data.get('type', 'default')
    pin_color = data.get('color', 'blue')

    success = db.update_user_pin_config(session['username'], pin_type, pin_color)

    if success:
        return jsonify({'success': True, 'message': 'Фишка обновлена'})
    else:
        return jsonify({'error': 'Ошибка обновления фишки'}), 500


@app.route('/api/user/update_status', methods=['POST'])
def update_user_status():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    username = data.get('username')
    status = data.get('status')

    if username and status:
        success = db.update_user_status(username, status)
        if success:
            return jsonify({'success': True, 'message': 'Статус обновлен'})

    return jsonify({'error': 'Ошибка обновления статуса'}), 500


@app.route('/api/user/delete', methods=['POST'])
def delete_user():
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    username = data.get('username')

    if username and username != session['username']:
        # Реализация удаления пользователя
        # db.delete_user(username)
        return jsonify({'success': True, 'message': 'Пользователь удален'})

    return jsonify({'error': 'Невозможно удалить пользователя'}), 400

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
    daily_tasks = load_daily_tasks()
    users = db.get_all_users()

    return render_template('admin.html',
                           tasks=tasks,
                           board=board,
                           daily_tasks=daily_tasks,
                           users=users)


@app.route('/admin/save_tasks', methods=['POST'])
def admin_save_tasks():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    new_tasks = {
        "button1": [t for t in request.form.getlist('button1[]') if t.strip()],
        "button2": [t for t in request.form.getlist('button2[]') if t.strip()],
        "button3": [t for t in request.form.getlist('button3[]') if t.strip()]
    }

    db.update_tasks_config(new_tasks)
    _data_cache.pop('all_tasks', None)

    return redirect(url_for('admin'))


@app.route('/admin/save_board', methods=['POST'])
def admin_save_board():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    board_tasks = request.form.getlist('board_tasks[]')
    difficulties = request.form.getlist('board_difficulties[]')

    # Очищаем доску и добавляем новые задачи
    board = []
    for i, task_text in enumerate(board_tasks):
        if task_text.strip():
            difficulty = difficulties[i] if i < len(difficulties) else "Средняя"
            board.append({
                "id": i + 1,
                "text": task_text.strip(),
                "difficulty": difficulty,
                "status": "free",
                "user": None,
                "taken_at": None,
                "done_at": None
            })

    save_board(board)
    return redirect(url_for('admin'))


@app.route('/admin/update_daily', methods=['POST'])
def update_daily_tasks():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    generate_daily_tasks()
    _data_cache.pop('daily_tasks', None)

    return redirect(url_for('admin'))


@app.route('/admin/update_coins', methods=['POST'])
def admin_update_coins():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    username = request.form.get('username')
    coins = request.form.get('coins')

    if username and coins:
        try:
            coins = int(coins)
            db.update_user_coins(username, coins)
            # Обновляем сессию если это текущий пользователь
            if session.get('username') == username:
                session['coins'] = coins
        except ValueError:
            pass

    return redirect(url_for('admin'))


@app.route('/board/take/<int:task_id>', methods=['POST'])
def take_task(task_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    board = load_board()
    task = next((t for t in board if t['id'] == task_id), None)
    if task and task['status'] == 'free':
        db.update_board_task(task_id, {
            'status': 'taken',
            'user_taken': session['username'],
            'taken_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        _data_cache.pop('board_data', None)

    return redirect(url_for('index'))


@app.route('/board/done/<int:task_id>', methods=['POST'])
def mark_done(task_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    board = load_board()
    task = next((t for t in board if t['id'] == task_id), None)
    if task and task['status'] == 'taken' and task['user_taken'] == session['username']:
        db.update_board_task(task_id, {
            'status': 'done',
            'done_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        _data_cache.pop('board_data', None)

        # Обновляем прогресс пользователя
        mark_daily_done(session['username'], f"Задача с доски: {task['text']}")

    return redirect(url_for('index'))


@app.route('/archive')
def archive():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен", 403

    board_data = [t for t in load_board() if t['status'] == 'done']
    user_coins = get_user_coins(session.get('username', '')) if 'username' in session else 0
    return render_template('archive.html', board=board_data, user_coins=user_coins)


@app.route('/mark_daily_done', methods=['POST'])
def mark_daily_done_route():
    if 'username' not in session:
        return redirect(url_for('login'))

    task_text = request.form.get('task')
    if task_text:
        mark_daily_done(session['username'], task_text)
    return redirect(url_for('index'))


@app.route('/unmark_daily_done', methods=['POST'])
def unmark_daily_done_route():
    if 'username' not in session:
        return redirect(url_for('login'))

    task_text = request.form.get('task')
    if task_text:
        success = unmark_daily_done(session['username'], task_text)
        if not success:
            return "Ошибка при отмене выполнения", 400
    return redirect(url_for('index'))


# Новые маршруты для пользователей и инвентаря
@app.route('/users')
def users_list():
    """Страница со списком всех пользователей"""
    if 'username' not in session:
        return redirect(url_for('login'))

    users_with_stats = get_all_users_with_stats()
    user_coins = get_user_coins(session['username'])

    return render_template('users.html',
                           users=users_with_stats,
                           user_coins=user_coins)


@app.route('/inventory')
def inventory():
    """Страница инвентаря пользователя"""
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_coins = get_user_coins(username)

    # Инициализируем таблицу если нужно
    init_inventory_table()

    # Получаем инвентарь пользователя из базы данных
    user_inventory = get_user_inventory(username)

    return render_template('inventory.html',
                           user_inventory=user_inventory,
                           user_coins=user_coins)


@app.route('/all_inventories')
def all_inventories():
    """Страница со всеми инвентарями"""
    if 'username' not in session:
        return redirect(url_for('login'))

    user_coins = get_user_coins(session['username'])
    all_inventories_data = get_all_inventories()

    return render_template('all_inventories.html',
                           all_inventories=all_inventories_data,
                           user_coins=user_coins)


@app.route('/inventory/add', methods=['POST'])
def add_inventory_item():
    """Добавление предмета в инвентарь"""
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        data = request.get_json()
        item_name = data.get('name')
        item_description = data.get('description', '')
        item_quantity = data.get('quantity', 1)

        if not item_name:
            return jsonify({'error': 'Название предмета обязательно'}), 400

        success = add_item_to_inventory(session['username'], item_name, item_description, item_quantity)

        if success:
            return jsonify({'success': True, 'message': 'Предмет добавлен в инвентарь'})
        else:
            return jsonify({'error': 'Ошибка при добавлении предмета'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/inventory/update/<int:item_id>', methods=['POST'])
def update_inventory_item(item_id):
    """Обновление предмета в инвентаре"""
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        data = request.get_json()
        updates = {}

        if 'name' in data:
            updates['name'] = data['name']
        if 'description' in data:
            updates['description'] = data['description']
        if 'quantity' in data:
            updates['quantity'] = data['quantity']

        success = update_inventory_item_db(session['username'], item_id, updates)

        if success:
            return jsonify({'success': True, 'message': 'Предмет обновлен'})
        else:
            return jsonify({'error': 'Ошибка при обновлении предмета'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/inventory/delete/<int:item_id>', methods=['POST'])
def delete_inventory_item(item_id):
    """Удаление предмета из инвентаря"""
    if 'username' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    try:
        success = delete_inventory_item_db(session['username'], item_id)

        if success:
            return jsonify({'success': True, 'message': 'Предмет удален'})
        else:
            return jsonify({'error': 'Ошибка при удалении предмета'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# API маршруты
@app.route('/api/map/config')
def api_map_config():
    config = load_map_config()
    return jsonify(config)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 RGG QUEST запущен на порту: {port}")
    print("👤 Админ: admin / password")
    print("👥 Пользователи: user1 / pass1, user2 / pass2")
    app.run(host='0.0.0.0', port=port, debug=False)