# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
import json
import os
import random
from datetime import datetime, date
import functools
from database import db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'taskflow_secret_key_2024')

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

    return render_template('map.html',
                           total_completed=user_position['total_completed'],
                           current_level=user_position['current_level'],
                           user_position=(saved_position['x'], saved_position['y']),
                           progress_percentage=user_position['progress_percentage'],
                           user_coins=user_coins,
                           map_config=map_config)


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


# API маршруты
@app.route('/api/map/config')
def api_map_config():
    config = load_map_config()
    return jsonify(config)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 RGG QUEST запущен: http://localhost:{port}")
    print(f"🗺️  Редактор карты: http://localhost:{port}/map_editor")
    print("👤 Админ: admin / password")
    print("👥 Пользователи: user1 / pass1, user2 / pass2")
    app.run(host='0.0.0.0', port=port, debug=True)