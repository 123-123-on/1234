from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
import json
import requests
import os
import bcrypt
import secrets
from datetime import datetime, date, timedelta
from database import init_database, insert_default_data, migrate_database

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # 生成安全的密钥
CORS(app)

# 配置Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = '请先登录以访问此页面'
login_manager.login_message_category = 'info'

# 用户模型类
class User(UserMixin):
    def __init__(self, user_data):
        self._id = str(user_data['id'])
        self._username = user_data['username']
        self._email = user_data['email']
        self._full_name = user_data['full_name'] if user_data['full_name'] else ''
        self._avatar_url = user_data['avatar_url'] if user_data['avatar_url'] else ''
        self._is_active = bool(user_data['is_active']) if user_data['is_active'] is not None else True
        self._email_verified = bool(user_data['email_verified']) if user_data['email_verified'] is not None else False
        self._created_at = user_data['created_at'] if user_data['created_at'] else ''
        self._last_login = user_data['last_login'] if user_data['last_login'] else ''
    
    @property
    def id(self):
        return self._id
    
    @property
    def username(self):
        return self._username
    
    @property
    def email(self):
        return self._email
    
    @property
    def full_name(self):
        return self._full_name
    
    @property
    def avatar_url(self):
        return self._avatar_url
    
    @property
    def is_active(self):
        return self._is_active
    
    @property
    def email_verified(self):
        return self._email_verified
    
    @property
    def created_at(self):
        return self._created_at
    
    @property
    def last_login(self):
        return self._last_login

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login用户加载器"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ? AND is_active = 1', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data)
    return None

# 初始化数据库
init_database()
migrate_database()  # 迁移数据库添加时间字段
insert_default_data()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('settings.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_current_user_id():
    """获取当前登录用户的ID"""
    if current_user.is_authenticated:
        return int(current_user.id)
    return None

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/task_lists')
@login_required
def get_task_lists():
    """获取当前用户的任务列表"""
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 一次性获取当前用户任务列表及其统计信息
    cursor.execute('''
        SELECT 
            tl.id, tl.name, tl.icon, tl.color, tl.sort_order,
            COUNT(t.id) as total_tasks,
            COUNT(CASE WHEN t.completed = 1 THEN 1 END) as completed_tasks
        FROM task_lists tl
        LEFT JOIN tasks t ON tl.id = t.list_id
        WHERE tl.user_id = ?
        GROUP BY tl.id, tl.name, tl.icon, tl.color, tl.sort_order
        ORDER BY tl.sort_order
    ''', (user_id,))
    
    lists = cursor.fetchall()
    conn.close()
    
    result = []
    for task_list in lists:
        result.append({
            'id': task_list['id'],
            'name': task_list['name'],
            'icon': task_list['icon'],
            'color': task_list['color'],
            'sort_order': task_list['sort_order'],
            'total_tasks': task_list['total_tasks'] or 0,
            'completed_tasks': task_list['completed_tasks'] or 0
        })
    
    return jsonify(result)

@app.route('/api/tasks')
@login_required
def get_tasks():
    """获取当前用户的任务列表"""
    user_id = get_current_user_id()
    list_id = request.args.get('list_id')
    show_completed = request.args.get('show_completed', 'true').lower() == 'true'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if list_id:
        # 获取特定列表的任务
        query = '''
            SELECT id, title, description, completed, priority, due_date, 
                   start_time, end_time, list_id, created_at, updated_at, completed_at, is_important
            FROM tasks 
            WHERE list_id = ? AND user_id = ?
        '''
        params = [list_id, user_id]
    else:
        # 获取用户所有任务
        query = '''
            SELECT id, title, description, completed, priority, due_date, 
                   start_time, end_time, list_id, created_at, updated_at, completed_at, is_important
            FROM tasks
            WHERE user_id = ?
        '''
        params = [user_id]
    
    if not show_completed:
        query += ' AND completed = 0'
    
    query += ' ORDER BY is_important DESC, due_date ASC, created_at DESC'
    
    cursor.execute(query, params)
    tasks = cursor.fetchall()
    conn.close()
    
    result = []
    for task in tasks:
        result.append({
            'id': task['id'],
            'title': task['title'],
            'description': task['description'],
            'completed': bool(task['completed']),
            'priority': task['priority'],
            'due_date': task['due_date'],
            'start_time': task['start_time'],
            'end_time': task['end_time'],
            'list_id': task['list_id'],
            'created_at': task['created_at'],
            'updated_at': task['updated_at'],
            'completed_at': task['completed_at'],
            'is_important': bool(task['is_important'])
        })
    
    return jsonify(result)

@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_task(task_id):
    """处理单个任务的获取、更新和删除"""
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('''
            SELECT id, title, description, completed, priority, due_date, 
                   start_time, end_time, list_id, created_at, updated_at, completed_at, is_important
            FROM tasks 
            WHERE id = ? AND user_id = ?
        ''', (task_id, user_id))
        
        task = cursor.fetchone()
        conn.close()
        
        if task:
            return jsonify({
                'id': task['id'],
                'title': task['title'],
                'description': task['description'],
                'completed': bool(task['completed']),
                'priority': task['priority'],
                'due_date': task['due_date'],
                'start_time': task['start_time'],
                'end_time': task['end_time'],
                'list_id': task['list_id'],
                'created_at': task['created_at'],
                'updated_at': task['updated_at'],
                'completed_at': task['completed_at'],
                'is_important': bool(task['is_important'])
            })
        else:
            return jsonify({'error': '任务不存在'}), 404
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # 构建更新语句
        update_fields = []
        update_values = []
        
        for field in ['title', 'description', 'priority', 'due_date', 'start_time', 'end_time', 'list_id', 'is_important']:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])
        
        if 'completed' in data:
            update_fields.append("completed = ?")
            update_values.append(data['completed'])
            if data['completed']:
                update_fields.append("completed_at = ?")
                update_values.append(datetime.now().isoformat())
            else:
                update_fields.append("completed_at = ?")
                update_values.append(None)
        
        if not update_fields:
            return jsonify({'error': '没有要更新的字段'}), 400
        
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())
        update_values.append(task_id)
        update_values.append(user_id)
        
        cursor.execute(f'''
            UPDATE tasks 
            SET {', '.join(update_fields)}
            WHERE id = ? AND user_id = ?
        ''', update_values)
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        cursor.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})

@app.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    """创建新任务"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': '任务标题不能为空'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO tasks (title, description, priority, due_date, start_time, end_time, list_id, is_important, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        title,
        data.get('description', ''),
        data.get('priority', 'medium'),
        data.get('due_date'),
        data.get('start_time'),
        data.get('end_time'),
        data.get('list_id'),
        data.get('is_important', False),
        user_id
    ))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': task_id, 'success': True})

@app.route('/api/task_lists', methods=['POST'])
@login_required
def create_task_list():
    """创建新任务列表"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '列表名称不能为空'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取用户最大的排序顺序
    cursor.execute('SELECT MAX(sort_order) as max_order FROM task_lists WHERE user_id = ?', (user_id,))
    max_order = cursor.fetchone()['max_order'] or 0
    
    cursor.execute('''
        INSERT INTO task_lists (name, icon, color, sort_order, user_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        name,
        data.get('icon', '📋'),
        data.get('color', '#0078d4'),
        max_order + 1,
        user_id
    ))
    
    list_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': list_id, 'success': True})

@app.route('/api/task_lists/<int:list_id>', methods=['PUT', 'DELETE'])
@login_required
def handle_task_list(list_id):
    """处理任务列表的更新和删除"""
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'PUT':
        data = request.get_json()
        
        update_fields = []
        update_values = []
        
        for field in ['name', 'icon', 'color']:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])
        
        if not update_fields:
            return jsonify({'error': '没有要更新的字段'}), 400
        
        update_values.append(list_id)
        update_values.append(user_id)
        
        cursor.execute(f'''
            UPDATE task_lists 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        ''', update_values)
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        # 删除列表及其所有任务（只删除当前用户的）
        cursor.execute('DELETE FROM tasks WHERE list_id = ? AND user_id = ?', (list_id, user_id))
        cursor.execute('DELETE FROM task_lists WHERE id = ? AND user_id = ?', (list_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})

@app.route('/api/user_preferences', methods=['GET', 'PUT'])
@login_required
def handle_user_preferences():
    """处理当前用户偏好设置"""
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        prefs = cursor.fetchone()
        conn.close()
        
        if prefs:
            return jsonify({
                'theme': prefs['theme'],
                'language': prefs['language'],
                'accent_color': prefs['accent_color'],
                'font_size': prefs['font_size'],
                'animations_enabled': bool(prefs['animations_enabled']),
                'transparency_enabled': bool(prefs['transparency_enabled']),
                'view_mode': prefs['view_mode'],
                'show_completed': bool(prefs['show_completed']),
                'default_list_id': prefs['default_list_id']
            })
        else:
            # 如果没有偏好设置，创建默认设置
            cursor.execute('''
                INSERT INTO user_preferences (user_id, theme, language, accent_color)
                VALUES (?, 'light', 'zh-CN', '#0078d4')
            ''', (user_id,))
            conn.commit()
            conn.close()
            
            # 返回默认设置
            return jsonify({
                'theme': 'light',
                'language': 'zh-CN',
                'accent_color': '#0078d4',
                'font_size': 'medium',
                'animations_enabled': True,
                'transparency_enabled': True,
                'view_mode': 'list',
                'show_completed': True,
                'default_list_id': None
            })
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # 构建更新语句
        update_fields = []
        update_values = []
        
        for field in ['theme', 'language', 'accent_color', 'font_size', 
                     'animations_enabled', 'transparency_enabled', 
                     'view_mode', 'show_completed', 'default_list_id']:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])
        
        if not update_fields:
            return jsonify({'error': '没有要更新的字段'}), 400
        
        update_values.append(user_id)
        
        cursor.execute(f'''
            UPDATE user_preferences 
            SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
        ''', update_values)
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})

@app.route('/api/stats')
@login_required
def get_stats():
    """获取当前用户的任务统计信息"""
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 总任务数
    cursor.execute('SELECT COUNT(*) as total FROM tasks WHERE user_id = ?', (user_id,))
    total_tasks = cursor.fetchone()['total']
    
    # 已完成任务数
    cursor.execute('SELECT COUNT(*) as completed FROM tasks WHERE user_id = ? AND completed = 1', (user_id,))
    completed_tasks = cursor.fetchone()['completed']
    
    # 重要任务数
    cursor.execute('SELECT COUNT(*) as important FROM tasks WHERE user_id = ? AND is_important = 1 AND completed = 0', (user_id,))
    important_tasks = cursor.fetchone()['important']
    
    # 今日到期任务数
    today = date.today().isoformat()
    cursor.execute('SELECT COUNT(*) as today_due FROM tasks WHERE user_id = ? AND due_date = ? AND completed = 0', (user_id, today))
    today_due_tasks = cursor.fetchone()['today_due']
    
    # 本周到期任务数
    cursor.execute('''
        SELECT COUNT(*) as week_due 
        FROM tasks 
        WHERE user_id = ? AND due_date BETWEEN ? AND ? AND completed = 0
    ''', (user_id, today, date.fromordinal(date.today().toordinal() + 7).isoformat()))
    week_due_tasks = cursor.fetchone()['week_due']
    
    conn.close()
    
    return jsonify({
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': total_tasks - completed_tasks,
        'important_tasks': important_tasks,
        'today_due_tasks': today_due_tasks,
        'week_due_tasks': week_due_tasks,
        'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    })

@app.route('/api/search')
@login_required
def search_tasks():
    """搜索当前用户的任务"""
    user_id = get_current_user_id()
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': '缺少搜索查询'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.id, t.title, t.description, t.completed, t.priority, 
               t.due_date, t.list_id, tl.name as list_name, tl.icon as list_icon
        FROM tasks t
        LEFT JOIN task_lists tl ON t.list_id = tl.id
        WHERE t.user_id = ? AND (t.title LIKE ? OR t.description LIKE ?)
        ORDER BY t.is_important DESC, t.due_date ASC
    ''', (user_id, f'%{query}%', f'%{query}%'))
    
    results = cursor.fetchall()
    conn.close()
    
    search_results = []
    for result in results:
        search_results.append({
            'id': result['id'],
            'title': result['title'],
            'description': result['description'],
            'completed': bool(result['completed']),
            'priority': result['priority'],
            'due_date': result['due_date'],
            'list_id': result['list_id'],
            'list_name': result['list_name'],
            'list_icon': result['list_icon']
        })
    
    return jsonify(search_results)

# 日历周视图相关API
@app.route('/api/calendar/week')
@login_required
def get_calendar_week():
    """获取当前用户的周视图日历数据"""
    user_id = get_current_user_id()
    try:
        # 获取查询参数
        week_start = request.args.get('week_start')
        if not week_start:
            # 默认为本周开始
            today = date.today()
            days_since_monday = today.weekday()
            week_start = (today - timedelta(days=days_since_monday)).isoformat()
        
        week_start_date = date.fromisoformat(week_start)
        week_end_date = week_start_date + timedelta(days=6)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取指定周的用户任务
        cursor.execute('''
            SELECT t.id, t.title, t.description, t.completed, t.priority,
                   t.due_date, t.start_time, t.end_time, t.list_id, t.is_important,
                   tl.name as list_name, tl.icon as list_icon, tl.color as list_color
            FROM tasks t
            LEFT JOIN task_lists tl ON t.list_id = tl.id
            WHERE t.user_id = ? AND t.due_date BETWEEN ? AND ?
            ORDER BY t.due_date, t.start_time, t.is_important DESC
        ''', (user_id, week_start_date.isoformat(), week_end_date.isoformat()))
        
        tasks = cursor.fetchall()
        conn.close()
        
        # 构建周数据结构
        week_data = {
            'week_start': week_start_date.isoformat(),
            'week_end': week_end_date.isoformat(),
            'days': []
        }
        
        # 初始化一周的每一天
        for i in range(7):
            current_date = week_start_date + timedelta(days=i)
            week_data['days'].append({
                'date': current_date.isoformat(),
                'day_name': current_date.strftime('%A'),
                'tasks': []
            })
        
        # 将任务分配到对应的日期
        for task in tasks:
            task_date = date.fromisoformat(task['due_date']) if task['due_date'] else None
            if task_date:
                day_index = (task_date - week_start_date).days
                if 0 <= day_index < 7:
                    task_data = {
                        'id': task['id'],
                        'title': task['title'],
                        'description': task['description'],
                        'completed': bool(task['completed']),
                        'priority': task['priority'],
                        'start_time': task['start_time'],
                        'end_time': task['end_time'],
                        'list_id': task['list_id'],
                        'is_important': bool(task['is_important']),
                        'list_name': task['list_name'],
                        'list_icon': task['list_icon'],
                        'list_color': task['list_color']
                    }
                    week_data['days'][day_index]['tasks'].append(task_data)
        
        return jsonify(week_data)
        
    except Exception as e:
        print(f"获取周视图数据错误: {e}")
        return jsonify({'error': '获取周视图数据失败'}), 500

@app.route('/api/tasks/<int:task_id>/time', methods=['PUT'])
@login_required
def update_task_time(task_id):
    """更新当前用户的任务时间"""
    user_id = get_current_user_id()
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新用户任务时间
        cursor.execute('''
            UPDATE tasks 
            SET start_time = ?, end_time = ?, due_date = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
        ''', (
            data.get('start_time'),
            data.get('end_time'),
            data.get('due_date'),
            datetime.now().isoformat(),
            task_id,
            user_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"更新任务时间错误: {e}")
        return jsonify({'error': '更新任务时间失败'}), 500

@app.route('/api/tasks/batch', methods=['POST'])
@login_required
def batch_update_tasks():
    """批量更新当前用户的任务"""
    user_id = get_current_user_id()
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        success_count = 0
        for update in updates:
            task_id = update.get('id')
            if not task_id:
                continue
            
            # 构建更新字段
            update_fields = []
            update_values = []
            
            for field in ['title', 'description', 'priority', 'due_date', 
                         'start_time', 'end_time', 'list_id', 'completed', 'is_important']:
                if field in update:
                    update_fields.append(f"{field} = ?")
                    update_values.append(update[field])
            
            if update_fields:
                update_fields.append("updated_at = ?")
                update_values.append(datetime.now().isoformat())
                update_values.append(task_id)
                update_values.append(user_id)
                
                cursor.execute(f'''
                    UPDATE tasks 
                    SET {', '.join(update_fields)}
                    WHERE id = ? AND user_id = ?
                ''', update_values)
                success_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'updated_count': success_count
        })
        
    except Exception as e:
        print(f"批量更新任务错误: {e}")
        return jsonify({'error': '批量更新失败'}), 500

# AI助手相关API
# 全局变量存储对话历史
conversation_history = []

def load_ai_config():
    """加载AI配置"""
    try:
        with open('ai_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "assistant": {
                "name": "AI助手",
                "mode": "smart",
                "model": "gpt-3.5-turbo",
                "provider": "openai",
                "api_key": "",
                "api_base": "https://api.openai.com/v1",
                "max_tokens": 500,
                "temperature": 0.7,
                "system_prompt": "你是一个专业的任务管理AI助手，帮助用户高效管理他们的待办事项。你的任务是：\n1. 帮助用户创建、编辑和管理任务\n2. 提供任务优先级建议\n3. 协助制定时间管理计划\n4. 回答任务管理相关的问题\n5. 提供提高效率的建议\n\n请用友好、专业的语调回复，回复要简洁有用。如果用户询问任务相关的信息，你可以基于当前的任务数据回答。",
                "welcome_message": "你好！我是你的AI助手 👋\n我可以帮助你管理任务，比如：\n• 创建新任务\n• 查找特定任务\n• 管理任务优先级\n• 提供任务建议\n\n有什么可以帮助你的吗？",
                "typing_delay": {"min": 1000, "max": 2000},
                "timeout": 30,
                "retries": 3,
                "stream_response": False,
                "save_history": True
            },
            "features": {
                "task_creation": True,
                "task_categorization": True,
                "priority_suggestion": True,
                "time_management": True,
                "task_summary": True
            },
            "advanced": {
                "context_memory": 10,
                "cache_responses": True,
                "debug_mode": False,
                "fallback_to_rules": True
            }
        }

def add_to_conversation_history(role, content):
    """添加消息到对话历史"""
    global conversation_history
    
    # 添加新消息
    conversation_history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    # 限制历史记录长度
    config = load_ai_config()
    max_memory = config.get('advanced', {}).get('context_memory', 10)
    
    # 保留系统消息和最近的对话
    system_messages = [msg for msg in conversation_history if msg["role"] == "system"]
    user_assistant_messages = [msg for msg in conversation_history if msg["role"] in ["user", "assistant"]]
    
    # 只保留最近的用户和助手消息
    if len(user_assistant_messages) > max_memory:
        user_assistant_messages = user_assistant_messages[-max_memory:]
    
    # 重新组合历史记录
    conversation_history = system_messages + user_assistant_messages

def get_conversation_context():
    """获取对话上下文"""
    config = load_ai_config()
    max_memory = config.get('advanced', {}).get('context_memory', 10)
    
    # 获取最近的对话历史（不包括系统消息）
    context_messages = [msg for msg in conversation_history if msg["role"] in ["user", "assistant"]]
    
    # 如果历史记录超过限制，只返回最近的消息
    if len(context_messages) > max_memory:
        context_messages = context_messages[-max_memory:]
    
    return context_messages

def clear_conversation_history():
    """清空对话历史"""
    global conversation_history
    conversation_history = []

def save_ai_config(config):
    """保存AI配置"""
    try:
        with open('ai_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False

@app.route('/api/ai/config', methods=['GET', 'PUT'])
def handle_ai_config():
    """处理AI配置"""
    if request.method == 'GET':
        config = load_ai_config()
        # 隐藏API密钥
        if 'assistant' in config and 'api_key' in config['assistant']:
            config['assistant']['api_key'] = '***' if config['assistant']['api_key'] else ''
        return jsonify(config)
    
    elif request.method == 'PUT':
        data = request.get_json()
        current_config = load_ai_config()
        
        # 更新配置
        if 'assistant' in data:
            current_config['assistant'].update(data['assistant'])
        if 'features' in data:
            current_config['features'].update(data['features'])
        if 'ui' in data:
            current_config['ui'].update(data['ui'])
        
        # 如果API密钥是***，保持原值不变
        if data.get('assistant', {}).get('api_key') == '***':
            original_config = load_ai_config()
            current_config['assistant']['api_key'] = original_config['assistant'].get('api_key', '')
        
        if save_ai_config(current_config):
            return jsonify({'success': True})
        else:
            return jsonify({'error': '保存配置失败'}), 500

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """AI聊天接口"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': '消息不能为空'}), 400
        
        config = load_ai_config()
        api_key = config['assistant'].get('api_key', '')
        
        # 添加用户消息到历史记录
        add_to_conversation_history("user", user_message)
        
        # 如果没有配置API密钥，使用本地回复
        if not api_key:
            response = generate_local_response(user_message)
            add_to_conversation_history("assistant", response)
            return jsonify({
                'response': response,
                'source': 'local'
            })
        
        # 获取当前任务数据作为上下文
        task_context = get_task_context()
        
        # 构建增强的系统提示，包含AI操作接口说明
        enhanced_system_prompt = config['assistant']['system_prompt'] + f"""

**AI操作接口能力：**
你可以通过特殊的JSON格式指令来操作系统，这些指令会被系统识别并执行相应的数据库操作。

**支持的AI操作指令：**
1. **创建任务**：
   ```json
   {{"action": "create_task", "data": {{"title": "任务标题", "description": "描述", "priority": "high/medium/low", "due_date": "2025-01-01", "start_time": "14:30", "end_time": "15:30", "is_important": true, "list_name": "列表名称"}}}}
   ```

2. **创建列表**：
   ```json
   {{"action": "create_list", "data": {{"name": "列表名称", "icon": "📋", "color": "#0078d4"}}}}
   ```

3. **更新任务**：
   ```json
   {{"action": "update_task", "data": {{"task_id": 123, "title": "新标题", "completed": true}}}}
   ```

4. **删除任务**：
   ```json
   {{"action": "delete_task", "data": {{"task_id": 123}}}}
   ```

5. **搜索任务**：
   ```json
   {{"action": "search_tasks", "data": {{"query": "搜索关键词"}}}}
   ```

**使用方法：**
- 在回复中包含上述JSON指令
- 系统会自动识别并执行这些指令
- 执行结果会返回给你，你可以基于结果进行后续回复
- 你可以在一次回复中包含多个指令

**当前任务数据：**
{task_context}

**重要提醒：**
- 当用户要求创建任务时，请使用create_task指令而不是直接描述
- 当用户要求查找任务时，请使用search_tasks指令
- 所有操作都通过这些JSON指令完成，不要依赖系统预设的解析逻辑
- 请记住我们的对话历史，这样可以提供更好的连续性服务。"""
        
        # 构建消息，包含对话历史
        messages = [
            {
                "role": "system",
                "content": enhanced_system_prompt
            }
        ]
        
        # 添加对话历史（除了系统消息）
        conversation_context = get_conversation_context()
        messages.extend(conversation_context)
        
        # 调用OpenAI兼容API
        response = call_openai_api(messages, config)
        
        if response:
            # 解析AI回复中的操作指令
            ai_actions = parse_ai_actions(response)
            action_results = []
            
            # 执行AI指令
            for action in ai_actions:
                result = execute_ai_action(action)
                action_results.append(result)
            
            # 如果有操作结果，构建包含结果的回复
            if action_results:
                # 生成包含操作结果的回复
                enhanced_response = generate_action_response(response, action_results)
                add_to_conversation_history("assistant", enhanced_response)
                return jsonify({
                    'response': enhanced_response,
                    'source': 'ai_with_actions',
                    'actions': action_results
                })
            else:
                # 没有操作指令，正常回复
                add_to_conversation_history("assistant", response)
                return jsonify({
                    'response': response,
                    'source': 'ai'
                })
        else:
            # API调用失败，降级到本地回复
            response = generate_local_response(user_message)
            add_to_conversation_history("assistant", response)
            return jsonify({
                'response': response,
                'source': 'local_fallback'
            })
            
    except Exception as e:
        print(f"AI聊天错误: {e}")
        error_response = '抱歉，我遇到了一些问题。请稍后再试。'
        add_to_conversation_history("assistant", error_response)
        return jsonify({
            'response': error_response,
            'source': 'error'
        }), 500

def parse_ai_actions(response):
    """解析AI回复中的操作指令"""
    import re
    import json
    
    actions = []
    
    # 改进的JSON解析模式，支持嵌套结构
    # 使用更精确的正则表达式来匹配完整的JSON对象
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*"action"[^{}]*\}'
    
    # 首先尝试匹配包含action的JSON
    matches = re.findall(json_pattern, response, re.DOTALL)
    
    # 如果没有找到，尝试更宽松的匹配
    if not matches:
        # 查找所有可能的JSON对象
        json_pattern = r'\{(?:[^{}]|(?R))*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
    
    for match in matches:
        try:
            # 清理可能的空白字符
            clean_match = match.strip()
            action_data = json.loads(clean_match)
            if 'action' in action_data and 'data' in action_data:
                actions.append(action_data)
                print(f"成功解析AI指令: {action_data}")  # 调试日志
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}, 内容: {match}")  # 调试日志
            continue
    
    print(f"总共解析到 {len(actions)} 个AI指令")  # 调试日志
    return actions

def execute_ai_action(action):
    """执行AI操作指令"""
    try:
        action_type = action.get('action')
        data = action.get('data', {})
        
        if action_type == 'create_task':
            return execute_create_task(data)
        elif action_type == 'create_list':
            return execute_create_list(data)
        elif action_type == 'update_task':
            return execute_update_task(data)
        elif action_type == 'delete_task':
            return execute_delete_task(data)
        elif action_type == 'search_tasks':
            return execute_search_tasks(data)
        else:
            return {
                'success': False,
                'error': f'不支持的操作类型: {action_type}',
                'action': action_type
            }
            
    except Exception as e:
        print(f"执行AI操作失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'action': action.get('action', 'unknown')
        }

def execute_create_task(data):
    """执行创建任务操作"""
    try:
        # 获取当前用户ID
        if current_user.is_authenticated:
            user_id = int(current_user.id)
        else:
            return {
                'success': False,
                'error': '用户未登录',
                'action': 'create_task'
            }
        
        title = data.get('title', '').strip()
        if not title:
            return {
                'success': False,
                'error': '任务标题不能为空',
                'action': 'create_task'
            }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 如果指定了列表名称，查找或创建列表
        list_id = None
        list_name = data.get('list_name')
        if list_name:
            cursor.execute('SELECT id FROM task_lists WHERE name = ? AND user_id = ?', (list_name, user_id))
            result = cursor.fetchone()
            if result:
                list_id = result['id']
            else:
                # 创建新列表
                cursor.execute('''
                    INSERT INTO task_lists (name, icon, color, sort_order, user_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    list_name,
                    data.get('icon', '📋'),
                    data.get('color', '#0078d4'),
                    999,
                    user_id
                ))
                list_id = cursor.lastrowid
        
        # 如果没有指定列表，使用用户的默认列表
        if not list_id:
            cursor.execute('SELECT id FROM task_lists WHERE user_id = ? ORDER BY sort_order LIMIT 1', (user_id,))
            result = cursor.fetchone()
            list_id = result['id'] if result else None
        
        # 如果仍然没有列表，创建一个默认列表
        if not list_id:
            cursor.execute('''
                INSERT INTO task_lists (name, icon, color, sort_order, user_id)
                VALUES (?, ?, ?, ?, ?)
            ''', ('默认列表', '📋', '#0078d4', 0, user_id))
            list_id = cursor.lastrowid
        
        # 创建任务
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, due_date, start_time, end_time, list_id, is_important, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title,
            data.get('description', ''),
            data.get('priority', 'medium'),
            data.get('due_date'),
            data.get('start_time'),
            data.get('end_time'),
            list_id,
            data.get('is_important', False),
            user_id
        ))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'action': 'create_task',
            'task_id': task_id,
            'list_id': list_id,
            'title': title,
            'message': f'任务"{title}"创建成功'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'create_task'
        }

def execute_create_list(data):
    """执行创建列表操作"""
    try:
        # 获取当前用户ID
        if current_user.is_authenticated:
            user_id = int(current_user.id)
        else:
            return {
                'success': False,
                'error': '用户未登录',
                'action': 'create_list'
            }
        
        name = data.get('name', '').strip()
        if not name:
            return {
                'success': False,
                'error': '列表名称不能为空',
                'action': 'create_list'
            }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取用户最大的排序顺序
        cursor.execute('SELECT MAX(sort_order) as max_order FROM task_lists WHERE user_id = ?', (user_id,))
        max_order = cursor.fetchone()['max_order'] or 0
        
        cursor.execute('''
            INSERT INTO task_lists (name, icon, color, sort_order, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            name,
            data.get('icon', '📋'),
            data.get('color', '#0078d4'),
            max_order + 1,
            user_id
        ))
        
        list_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'action': 'create_list',
            'list_id': list_id,
            'name': name,
            'message': f'列表"{name}"创建成功'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'create_list'
        }

def execute_update_task(data):
    """执行更新任务操作"""
    try:
        # 获取当前用户ID
        if current_user.is_authenticated:
            user_id = int(current_user.id)
        else:
            return {
                'success': False,
                'error': '用户未登录',
                'action': 'update_task'
            }
        
        task_id = data.get('task_id')
        if not task_id:
            return {
                'success': False,
                'error': '任务ID不能为空',
                'action': 'update_task'
            }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 构建更新语句
        update_fields = []
        update_values = []
        
        for field in ['title', 'description', 'priority', 'due_date', 'start_time', 'end_time', 'list_id', 'is_important']:
            if field in data:
                update_fields.append(f"{field} = ?")
                update_values.append(data[field])
        
        if 'completed' in data:
            update_fields.append("completed = ?")
            update_values.append(data['completed'])
            if data['completed']:
                update_fields.append("completed_at = ?")
                update_values.append(datetime.now().isoformat())
            else:
                update_fields.append("completed_at = ?")
                update_values.append(None)
        
        if not update_fields:
            return {
                'success': False,
                'error': '没有要更新的字段',
                'action': 'update_task'
            }
        
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())
        update_values.append(task_id)
        update_values.append(user_id)
        
        cursor.execute(f'''
            UPDATE tasks 
            SET {', '.join(update_fields)}
            WHERE id = ? AND user_id = ?
        ''', update_values)
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'action': 'update_task',
            'task_id': task_id,
            'message': f'任务{task_id}更新成功'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'update_task'
        }

def execute_delete_task(data):
    """执行删除任务操作"""
    try:
        # 获取当前用户ID
        if current_user.is_authenticated:
            user_id = int(current_user.id)
        else:
            return {
                'success': False,
                'error': '用户未登录',
                'action': 'delete_task'
            }
        
        task_id = data.get('task_id')
        if not task_id:
            return {
                'success': False,
                'error': '任务ID不能为空',
                'action': 'delete_task'
            }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'action': 'delete_task',
            'task_id': task_id,
            'message': f'任务{task_id}删除成功'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'delete_task'
        }

def execute_search_tasks(data):
    """执行搜索任务操作"""
    try:
        # 获取当前用户ID
        if current_user.is_authenticated:
            user_id = int(current_user.id)
        else:
            return {
                'success': False,
                'error': '用户未登录',
                'action': 'search_tasks'
            }
        
        query = data.get('query', '').strip()
        if not query:
            return {
                'success': False,
                'error': '搜索关键词不能为空',
                'action': 'search_tasks'
            }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.id, t.title, t.description, t.completed, t.priority, 
                   t.due_date, t.list_id, tl.name as list_name, tl.icon as list_icon
            FROM tasks t
            LEFT JOIN task_lists tl ON t.list_id = tl.id
            WHERE t.user_id = ? AND (t.title LIKE ? OR t.description LIKE ?)
            ORDER BY t.is_important DESC, t.due_date ASC
        ''', (user_id, f'%{query}%', f'%{query}%'))
        
        results = cursor.fetchall()
        conn.close()
        
        tasks = []
        for result in results:
            tasks.append({
                'id': result['id'],
                'title': result['title'],
                'description': result['description'],
                'completed': bool(result['completed']),
                'priority': result['priority'],
                'due_date': result['due_date'],
                'list_id': result['list_id'],
                'list_name': result['list_name'],
                'list_icon': result['list_icon']
            })
        
        return {
            'success': True,
            'action': 'search_tasks',
            'query': query,
            'results': tasks,
            'count': len(tasks),
            'message': f'找到{len(tasks)}个相关任务'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'search_tasks'
        }

def generate_action_response(original_response, action_results):
    """生成包含操作结果的回复"""
    if not action_results:
        return original_response
    
    # 统计成功和失败的操作
    successful_actions = [r for r in action_results if r['success']]
    failed_actions = [r for r in action_results if not r['success']]
    
    response_parts = []
    
    # 添加成功操作的结果
    if successful_actions:
        for result in successful_actions:
            if result['action'] == 'create_task':
                response_parts.append(f'✅ {result["message"]}')
            elif result['action'] == 'create_list':
                response_parts.append(f'✅ {result["message"]}')
            elif result['action'] == 'update_task':
                response_parts.append(f'✅ {result["message"]}')
            elif result['action'] == 'delete_task':
                response_parts.append(f'✅ {result["message"]}')
            elif result['action'] == 'search_tasks':
                response_parts.append(f'🔍 {result["message"]}')
    
    # 添加失败操作的结果
    if failed_actions:
        for result in failed_actions:
            response_parts.append(f'❌ 操作失败: {result["error"]}')
    
    # 组合回复
    if response_parts:
        action_summary = '\n'.join(response_parts)
        # 移除原始回复中的JSON指令
        clean_response = re.sub(r'\{[^{}]*"action"[^{}]*\}', '', original_response, flags=re.DOTALL)
        clean_response = clean_response.strip()
        
        if clean_response:
            return f'{clean_response}\n\n{action_summary}'
        else:
            return action_summary
    else:
        return original_response

def call_openai_api(messages, config):
    """调用OpenAI兼容API"""
    try:
        headers = {
            'Authorization': f'Bearer {config["assistant"]["api_key"]}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': config['assistant']['model'],
            'messages': messages,
            'max_tokens': config['assistant']['max_tokens'],
            'temperature': config['assistant']['temperature']
        }
        
        response = requests.post(
            f"{config['assistant']['api_base']}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            print(f"API调用失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"API调用异常: {e}")
        return None

def get_task_context():
    """获取当前任务数据作为AI上下文"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取基本统计
        cursor.execute('SELECT COUNT(*) as total FROM tasks')
        total_tasks = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as completed FROM tasks WHERE completed = 1')
        completed_tasks = cursor.fetchone()['completed']
        
        cursor.execute('SELECT COUNT(*) as important FROM tasks WHERE is_important = 1 AND completed = 0')
        important_tasks = cursor.fetchone()['important']
        
        # 获取最近的任务
        cursor.execute('''
            SELECT title, completed, priority, due_date 
            FROM tasks 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_tasks = cursor.fetchall()
        
        conn.close()
        
        context = f"总任务数: {total_tasks}, 已完成: {completed_tasks}, 重要待办: {important_tasks}\n"
        context += "最近任务:\n"
        for task in recent_tasks:
            status = "✓" if task['completed'] else "○"
            priority = task['priority'] or 'medium'
            due_date = f" (截止: {task['due_date']})" if task['due_date'] else ""
            context += f"{status} {task['title']} [{priority}]{due_date}\n"
        
        return context
        
    except Exception as e:
        print(f"获取任务上下文失败: {e}")
        return "无法获取任务数据"

def parse_task_creation_request(user_message):
    """解析用户的任务创建请求"""
    import re
    
    # 初始化任务数据
    task_data = {
        'title': '',
        'description': '',
        'priority': 'medium',
        'due_date': None,
        'start_time': None,
        'end_time': None,
        'is_important': False,
        'list_name': None
    }
    
    message = user_message.strip()
    
    # 提取任务标题（主要内容）
    # 常见的任务创建模式
    patterns = [
        r'创建[一个]?任务[：:]\s*(.+)',
        r'新建[一个]?任务[：:]\s*(.+)',
        r'添加[一个]?任务[：:]\s*(.+)',
        r'任务[：:]\s*(.+)',
        r'提醒我?(.+)',
        r'我需要?(.+)',
        r'帮我?(.+)',
        r'(.+)任务',
    ]
    
    title = None
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            break
    
    # 如果没有匹配到模式，尝试提取整个消息作为标题
    if not title:
        # 过滤掉常见的对话词汇
        filtered_message = re.sub(r'^(你好|请问|帮我|可以|能否|我想|我要|需要)', '', message).strip()
        if filtered_message:
            title = filtered_message
    
    if not title:
        return None
    
    task_data['title'] = title
    
    # 提取优先级
    priority_keywords = {
        '高': ['高', '重要', '紧急', '优先', '马上', '立即', 'urgent', 'important', 'high'],
        '低': ['低', '不急', '稍后', '有空', 'low', 'later']
    }
    
    for priority, keywords in priority_keywords.items():
        if any(keyword in message for keyword in keywords):
            task_data['priority'] = priority
            break
    
    # 提取重要性
    important_keywords = ['重要', '关键', '核心', '必须', '一定', 'star', 'important']
    if any(keyword in message for keyword in important_keywords):
        task_data['is_important'] = True
    
    # 提取时间信息
    from datetime import datetime, date, timedelta
    
    # 今天
    if '今天' in message:
        task_data['due_date'] = date.today().isoformat()
    # 明天
    elif '明天' in message:
        task_data['due_date'] = (date.today() + timedelta(days=1)).isoformat()
    # 后天
    elif '后天' in message:
        task_data['due_date'] = (date.today() + timedelta(days=2)).isoformat()
    # 本周
    elif '本周' in message or '这周' in message:
        # 找到本周日
        days_ahead = 6 - date.today().weekday()
        if days_ahead >= 0:
            task_data['due_date'] = (date.today() + timedelta(days=days_ahead)).isoformat()
    # 下周
    elif '下周' in message:
        task_data['due_date'] = (date.today() + timedelta(days=7)).isoformat()
    
    # 提取具体时间
    time_patterns = [
        r'(\d{1,2})[点时](\d{0,2})',
        r'(\d{1,2}):(\d{2})',
        r'上午(\d{1,2})[点时](\d{0,2})',
        r'下午(\d{1,2})[点时](\d{0,2})',
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, message)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            
            # 处理上午/下午
            if '下午' in message and hour < 12:
                hour += 12
            elif '上午' in message and hour == 12:
                hour = 0
            
            task_data['start_time'] = f"{hour:02d}:{minute:02d}"
            # 默认持续1小时
            end_hour = hour + 1
            task_data['end_time'] = f"{end_hour:02d}:{minute:02d}"
            break
    
    # 提取列表名称
    list_patterns = [
        r'在["""]?(.+?)["""]?列表',
        r'添加到["""]?(.+?)["""]?',
        r'放到["""]?(.+?)["""]?',
    ]
    
    for pattern in list_patterns:
        match = re.search(pattern, message)
        if match:
            task_data['list_name'] = match.group(1).strip()
            break
    
    return task_data

def create_task_from_parsed_data(task_data):
    """根据解析的数据创建任务"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 如果指定了列表名称，查找或创建列表
        list_id = None
        if task_data.get('list_name'):
            cursor.execute('SELECT id FROM task_lists WHERE name = ?', (task_data['list_name'],))
            result = cursor.fetchone()
            if result:
                list_id = result['id']
            else:
                # 创建新列表
                cursor.execute('''
                    INSERT INTO task_lists (name, icon, color, sort_order)
                    VALUES (?, ?, ?, ?)
                ''', (
                    task_data['list_name'],
                    '📋',
                    '#0078d4',
                    999  # 放在最后
                ))
                list_id = cursor.lastrowid
        
        # 如果没有指定列表，使用默认列表
        if not list_id:
            cursor.execute('SELECT id FROM task_lists ORDER BY sort_order LIMIT 1')
            result = cursor.fetchone()
            list_id = result['id'] if result else 1
        
        # 创建任务
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, due_date, start_time, end_time, list_id, is_important)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_data['title'],
            task_data['description'],
            task_data['priority'],
            task_data['due_date'],
            task_data['start_time'],
            task_data['end_time'],
            list_id,
            task_data['is_important']
        ))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'task_id': task_id,
            'list_id': list_id,
            'task_data': task_data
        }
        
    except Exception as e:
        print(f"创建任务失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def generate_local_response(user_message):
    """生成本地回复（当AI不可用时）"""
    lower_message = user_message.lower()
    
    # 尝试解析任务创建请求
    task_data = parse_task_creation_request(user_message)
    if task_data:
        # 创建任务
        result = create_task_from_parsed_data(task_data)
        if result['success']:
            response = f'✅ 任务已创建："{task_data["title"]}"'
            
            # 添加详细信息
            if task_data.get('due_date'):
                response += f'\n📅 截止日期：{task_data["due_date"]}'
            if task_data.get('start_time'):
                response += f'\n⏰ 时间：{task_data["start_time"]}'
            if task_data.get('priority') != 'medium':
                priority_text = {'high': '高', 'low': '低'}
                response += f'\n🔴 优先级：{priority_text.get(task_data["priority"], "中")}'
            if task_data.get('is_important'):
                response += f'\n⭐ 已标记为重要'
            
            response += '\n\n还有什么需要帮助的吗？'
            return response
        else:
            return f'❌ 创建任务失败：{result.get("error", "未知错误")}'
    
    # 创建任务相关
    if any(keyword in lower_message for keyword in ['创建', '新建', '添加', '任务']):
        return '好的！我来帮你创建任务。请告诉我任务的详细信息，比如：\n\n• "创建任务：完成项目报告"\n• "明天下午3点开会"\n• "添加重要任务：准备演示文稿"\n\n我可以理解自然语言并自动设置时间和优先级！📝'
    
    # 查找任务相关
    if any(keyword in lower_message for keyword in ['查找', '搜索', '找']):
        return '我可以帮你查找任务！请使用顶部的搜索框，输入关键词来查找你需要的任务。你可以搜索任务标题或描述内容。🔍'
    
    # 总结相关
    if any(keyword in lower_message for keyword in ['总结', '统计', '报告']):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as total FROM tasks')
            total_tasks = cursor.fetchone()['total']
            
            cursor.execute('SELECT COUNT(*) as completed FROM tasks WHERE completed = 1')
            completed_tasks = cursor.fetchone()['completed']
            
            conn.close()
            
            completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
            
            return f'📊 **任务总结报告**\n\n• 总任务数: {total_tasks}\n• 已完成: {completed_tasks}\n• 待完成: {total_tasks - completed_tasks}\n• 完成率: {completion_rate}%\n\n继续加油！💪'
        except:
            return '抱歉，无法获取任务统计数据。'
    
    # 问候相关
    if any(keyword in lower_message for keyword in ['你好', '嗨', '早上好', '下午好', '晚上好']):
        hour = datetime.now().hour
        if hour < 12:
            return '早上好！今天有什么任务计划吗？🌟 我可以帮你创建和管理今天的任务。'
        elif hour < 18:
            return '下午好！需要我帮你整理任务或制定计划吗？'
        else:
            return '晚上好！今天完成任务了吗？我可以帮你明天的计划。'
    
    # 帮助相关
    if any(keyword in lower_message for keyword in ['帮助', '怎么用', '功能']):
        return '''我可以帮助你：
📋 创建、编辑和管理任务
🔍 查找和搜索任务
📊 提供任务统计和总结
⭐ 设置任务优先级
📅 管理截止日期
💡 提供时间管理建议

有什么具体需要帮助的吗？'''
    
    # 默认回复
    return '我理解你的需求。虽然我目前使用的是基础回复模式，但我可以帮你管理任务。你可以尝试问我关于创建任务、查找任务或获取任务总结的问题。🤝'

@app.route('/api/ai/history', methods=['GET', 'DELETE'])
def handle_conversation_history():
    """处理对话历史"""
    if request.method == 'GET':
        # 获取对话历史
        return jsonify({
            'history': conversation_history,
            'count': len(conversation_history)
        })
    
    elif request.method == 'DELETE':
        # 清空对话历史
        clear_conversation_history()
        return jsonify({
            'success': True,
            'message': '对话历史已清空'
        })

@app.route('/api/ai/test', methods=['POST'])
def test_ai_connection():
    """测试AI连接"""
    try:
        data = request.get_json()
        config = load_ai_config()
        api_key = config['assistant'].get('api_key', '')
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': '未配置API密钥'
            })
        
        # 发送测试消息
        test_message = "你好，这是一个连接测试。"
        messages = [
            {
                "role": "system",
                "content": "你是一个AI助手。"
            },
            {
                "role": "user",
                "content": test_message
            }
        ]
        
        response = call_openai_api(messages, config)
        
        if response:
            return jsonify({
                'success': True,
                'response': response,
                'source': 'ai'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'API调用失败'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 用户认证相关API
@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        
        # 验证输入
        if not username or not email or not password:
            return jsonify({
                'success': False,
                'error': '用户名、邮箱和密码不能为空'
            }), 400
        
        if len(username) < 3:
            return jsonify({
                'success': False,
                'error': '用户名至少需要3个字符'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': '密码至少需要6个字符'
            }), 400
        
        # 验证邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'success': False,
                'error': '邮箱格式不正确'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查用户名和邮箱是否已存在
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'error': '用户名或邮箱已存在'
            }), 400
        
        # 哈希密码
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # 创建用户
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, full_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # 创建用户默认偏好设置
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_preferences (user_id, theme, language, accent_color)
            VALUES (?, 'light', 'zh-CN', '#0078d4')
        ''', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '注册成功',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'注册失败: {str(e)}'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username_or_email = data.get('username', '').strip()  # 改为接收username参数
        password = data.get('password', '')
        remember_me = data.get('remember', False)  # 改为接收remember参数
        
        if not username_or_email or not password:
            return jsonify({
                'success': False,
                'error': '用户名/邮箱和密码不能为空'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查找用户（支持用户名或邮箱登录）
        cursor.execute('''
            SELECT * FROM users 
            WHERE (username = ? OR email = ?) AND is_active = 1
        ''', (username_or_email, username_or_email))
        
        user_data = cursor.fetchone()
        conn.close()
        
        if not user_data:
            return jsonify({
                'success': False,
                'error': '用户名/邮箱或密码错误'
            }), 401
        
        # 验证密码
        if not bcrypt.checkpw(password.encode('utf-8'), user_data['password_hash'].encode('utf-8')):
            return jsonify({
                'success': False,
                'error': '用户名/邮箱或密码错误'
            }), 401
        
        # 创建用户对象并登录
        user = User(user_data)
        login_user(user, remember=remember_me)
        
        # 更新最后登录时间
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET last_login = ? WHERE id = ?
        ''', (datetime.now().isoformat(), user.id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'avatar_url': user.avatar_url
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'登录失败: {str(e)}'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """用户登出"""
    try:
        logout_user()
        return jsonify({
            'success': True,
            'message': '已成功登出'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'登出失败: {str(e)}'
        }), 500

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """获取当前用户信息"""
    return jsonify({
        'success': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'full_name': current_user.full_name,
            'avatar_url': current_user.avatar_url,
            'email_verified': current_user.email_verified,
            'created_at': current_user.created_at,
            'last_login': current_user.last_login
        }
    })

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """检查认证状态"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'full_name': current_user.full_name,
                'avatar_url': current_user.avatar_url
            }
        })
    else:
        return jsonify({
            'authenticated': False
        })

# 登录和注册页面
@app.route('/login')
def login_page():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    """注册页面"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout_page():
    """登出页面"""
    logout_user()
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
