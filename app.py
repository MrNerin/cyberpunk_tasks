# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, make_response
import json
import os
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'cyberpunk_secret_key_123'

# Пользователи
users = {
    "admin": {"password": "password", "role": "admin"},
    "user1": {"password": "pass1", "role": "user"}
}

# Создаем базовые файлы если их нет
def init_files():
    if not os.path.exists('tasks.json'):
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump({
                "button1": ["Изучить Python", "Прочитать документацию"],
                "button2": ["Создать проект", "Написать тесты"],
                "button3": ["Изучить алгоритмы", "Попрактиковать английский"]
            }, f, ensure_ascii=False, indent=2)

    if not os.path.exists('tasks_board.json'):
        with open('tasks_board.json', 'w', encoding='utf-8') as f:
            json.dump([], f)

    if not os.path.exists('user_progress.json'):
        with open('user_progress.json', 'w', encoding='utf-8') as f:
            json.dump({}, f)

# Загрузка данных
def load_tasks():
    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"button1": [], "button2": [], "button3": []}

def load_board():
    try:
        with open('tasks_board.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_board(board):
    with open('tasks_board.json', 'w', encoding='utf-8') as f:
        json.dump(board, f, ensure_ascii=False, indent=2)

# === МАРШРУТЫ ===

@app.route('/')
def index():
    tasks = load_tasks()
    board = load_board()

    # Собираем все задачи для daily
    all_tasks = []
    for key in tasks:
        all_tasks.extend(tasks[key])

    # Берем первые 3 как daily
    daily = all_tasks[:3]

    return render_template('index.html',
                         daily=daily,
                         board=board,
                         user_daily_done=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            return redirect(url_for('index'))
        else:
            return "Неверный логин или пароль"

    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Вход</title>
        <style>
            body { background: #0a0a15; color: #00ffff; font-family: monospace; padding: 50px; }
            .container { max-width: 400px; margin: 0 auto; background: rgba(18,18,37,0.9); padding: 30px; border: 1px solid #00ffff; }
            input, button { width: 100%; padding: 10px; margin: 10px 0; background: #121225; color: white; border: 1px solid #00ffff; }
            button { background: #0066cc; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚪 ВХОД В СИСТЕМУ</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="Логин" required>
                <input type="password" name="password" placeholder="Пароль" required>
                <button type="submit">ВОЙТИ</button>
            </form>
            <p>Тестовые аккаунты:</p>
            <p>• admin / password</p>
            <p>• user1 / pass1</p>
            <a href="/" style="color: #00ffff;">← На главную</a>
        </div>
    </body>
    </html>
    '''

@app.route('/admin')
def admin():
    # Проверка авторизации и прав
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return "Доступ запрещен. Требуются права администратора."

    tasks = load_tasks()
    board = load_board()

    return render_template('admin.html', tasks=tasks, daily=[], board=board)

@app.route('/admin/save', methods=['POST'])
def admin_save():
    if 'username' not in session or session.get('role') != 'admin':
        return "Доступ запрещен"

    # Сохраняем задачи
    new_tasks = {
        "button1": [t for t in request.form.getlist('button1[]') if t.strip()],
        "button2": [t for t in request.form.getlist('button2[]') if t.strip()],
        "button3": [t for t in request.form.getlist('button3[]') if t.strip()]
    }

    with open('tasks.json', 'w', encoding='utf-8') as f:
        json.dump(new_tasks, f, ensure_ascii=False, indent=2)

    # Добавляем задания на доску
    board_tasks = request.form.getlist('board_tasks[]')
    difficulties = request.form.getlist('board_difficulties[]')

    board = load_board()
    for i, task_text in enumerate(board_tasks):
        if task_text.strip():
            new_id = max([t.get('id', 0) for t in board], default=0) + 1
            difficulty = difficulties[i] if i < len(difficulties) else "Средняя"

            board.append({
                "id": new_id,
                "text": task_text.strip(),
                "difficulty": difficulty,
                "status": "free",
                "user": None,
                "taken_at": None,
                "done_at": None
            })

    save_board(board)

    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_files()
    print("🚀 Киберпанк система запускается...")
    print("📊 Админка: http://127.0.0.1:5000/admin")
    print("🔑 Логин: admin / password")
    app.run(debug=True, host='0.0.0.0', port=5000)
