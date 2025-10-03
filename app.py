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

    if 'username' in session:
        user_daily_done = get_user_daily_done(session['username'])

    return render_template('index.html',
                         daily=daily,
                         board=board_data,
                         today_date=today_date,
                         user_daily_done=user_daily_done)

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
                response.set_cookie('remembered_user', username, max_age=30*24*60*60)
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
    return render_template('admin.html', tasks=tasks, board=board)

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

@app.route('/mark_daily_done', methods=['POST'])
def mark_daily_done_route():
    if 'username' not in session:
        return redirect(url_for('login'))

    task_text = request.form.get('task')
    if task_text:
        mark_daily_done(session['username'], task_text)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_files()
    print("🚀 TaskFlow запущен: http://localhost:5000")
    print("👤 Админ: admin / password")
    app.run(debug=True, host='0.0.0.0', port=5000)
