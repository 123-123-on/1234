import sqlite3
import json
from datetime import datetime, date

def migrate_database():
    """迁移数据库，添加用户系统支持"""
    conn = sqlite3.connect('settings.db')
    cursor = conn.cursor()
    
    try:
        # 检查是否需要创建用户表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            # 创建用户表
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    avatar_url TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    email_verified BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            print("创建用户表")
        
        # 检查tasks表是否有user_id字段
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_id' not in columns:
            # 添加user_id字段
            cursor.execute('ALTER TABLE tasks ADD COLUMN user_id INTEGER')
            print("添加tasks.user_id字段")
        
        # 检查task_lists表是否有user_id字段
        cursor.execute("PRAGMA table_info(task_lists)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_id' not in columns:
            # 添加user_id字段
            cursor.execute('ALTER TABLE task_lists ADD COLUMN user_id INTEGER')
            print("添加task_lists.user_id字段")
        
        # 检查是否有start_time和end_time字段
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = [column[1] for column in cursor.fetchall()]
        
        if 'start_time' not in task_columns:
            cursor.execute('ALTER TABLE tasks ADD COLUMN start_time TIME')
            cursor.execute('ALTER TABLE tasks ADD COLUMN end_time TIME')
            print("添加start_time和end_time字段")
        
        # 检查user_preferences表是否有user_id字段
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(user_preferences)")
            pref_columns = [column[1] for column in cursor.fetchall()]
            
            if 'user_id' not in pref_columns:
                # 如果表存在但没有user_id字段，需要重建表
                cursor.execute('ALTER TABLE user_preferences RENAME TO user_preferences_old')
                print("重命名旧的user_preferences表")
                
                # 创建新的user_preferences表
                cursor.execute('''
                    CREATE TABLE user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE NOT NULL,
                        theme TEXT DEFAULT 'light',
                        language TEXT DEFAULT 'zh-CN',
                        accent_color TEXT DEFAULT '#0078d4',
                        font_size TEXT DEFAULT 'medium',
                        animations_enabled BOOLEAN DEFAULT 1,
                        transparency_enabled BOOLEAN DEFAULT 1,
                        view_mode TEXT DEFAULT 'list',
                        show_completed BOOLEAN DEFAULT 1,
                        default_list_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')
                print("创建新的user_preferences表")
                
                # 如果旧表有数据，尝试迁移（这里简单处理，使用默认用户ID）
                cursor.execute('SELECT COUNT(*) FROM user_preferences_old')
                if cursor.fetchone()[0] > 0:
                    cursor.execute('''
                        INSERT INTO user_preferences (user_id, theme, language, accent_color, show_completed)
                        SELECT 1, theme, language, accent_color, show_completed FROM user_preferences_old LIMIT 1
                    ''')
                    print("迁移user_preferences数据")
                
                # 删除旧表
                cursor.execute('DROP TABLE user_preferences_old')
                print("删除旧的user_preferences表")
        
        # 创建默认用户（如果不存在）
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            import bcrypt
            default_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name)
                VALUES (?, ?, ?, ?)
            ''', ('admin', 'admin@example.com', default_password, '系统管理员'))
            print("创建默认管理员用户")
        
        # 获取默认用户ID
        cursor.execute('SELECT id FROM users WHERE username = "admin"')
        default_user = cursor.fetchone()
        if default_user:
            user_id = default_user[0]
            
            # 更新现有任务数据，关联到默认用户
            cursor.execute('UPDATE tasks SET user_id = ? WHERE user_id IS NULL', (user_id,))
            cursor.execute('UPDATE task_lists SET user_id = ? WHERE user_id IS NULL', (user_id,))
            print(f"将现有数据关联到默认用户 (ID: {user_id})")
        
        # 创建会话表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            print("创建用户会话表")
        
        conn.commit()
        print("数据库迁移完成：添加了用户系统支持")
            
    except sqlite3.OperationalError as e:
        print(f"数据库迁移失败: {e}")
        conn.rollback()
    finally:
        conn.close()

def init_database():
    """初始化SQLite数据库"""
    conn = sqlite3.connect('settings.db')
    cursor = conn.cursor()
    
    # 删除旧表（如果存在）
    cursor.execute('DROP TABLE IF EXISTS settings')
    cursor.execute('DROP TABLE IF EXISTS system_info')
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            avatar_url TEXT,
            is_active BOOLEAN DEFAULT 1,
            email_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # 创建任务表（添加user_id字段）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            due_date DATE,
            start_time TIME,
            end_time TIME,
            list_id INTEGER,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            is_important BOOLEAN DEFAULT 0,
            FOREIGN KEY (list_id) REFERENCES task_lists (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 创建任务列表表（添加user_id字段）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📋',
            color TEXT DEFAULT '#0078d4',
            sort_order INTEGER DEFAULT 0,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 创建用户偏好表（修改为基于user_id）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'zh-CN',
            accent_color TEXT DEFAULT '#0078d4',
            font_size TEXT DEFAULT 'medium',
            animations_enabled BOOLEAN DEFAULT 1,
            transparency_enabled BOOLEAN DEFAULT 1,
            view_mode TEXT DEFAULT 'list',
            show_completed BOOLEAN DEFAULT 1,
            default_list_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 创建用户会话表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_default_task_lists():
    """获取默认任务列表数据"""
    return [
        ('我的一天', '☀️', '#0078d4', 0),
        ('重要', '⭐', '#ff6b35', 1),
        ('已计划', '📅', '#107c10', 2),
        ('任务', '📋', '#5c2d91', 3),
        ('购物', '🛒', '#ff8c00', 4),
        ('工作', '💼', '#0078d4', 5),
        ('个人', '👤', '#107c10', 6)
    ]

def get_default_tasks():
    """获取默认任务数据"""
    today = date.today().isoformat()
    tomorrow = date.fromordinal(date.today().toordinal() + 1).isoformat()
    next_week = date.fromordinal(date.today().toordinal() + 7).isoformat()
    
    return [
        # 我的一天 (list_id=1)
        ('完成项目报告', '整理本周工作进展并提交报告', 0, 'high', today, 1, 1),
        ('团队会议', '下午3点的产品讨论会议', 0, 'medium', today, 1, 0),
        ('回复邮件', '处理客户咨询邮件', 0, 'medium', today, 1, 0),
        
        # 重要 (list_id=2)
        ('项目截止日期', '完成最终版本的项目交付', 0, 'high', next_week, 2, 1),
        ('客户演示', '准备下周一的产品演示', 0, 'high', next_week, 2, 1),
        
        # 已计划 (list_id=3)
        ('生日聚会', '朋友的生日庆祝活动', 0, 'low', next_week, 3, 0),
        ('体检预约', '年度健康检查', 0, 'medium', next_week, 3, 0),
        
        # 任务 (list_id=4) - 添加一些通用任务
        ('学习新技术', '学习Python和Web开发', 0, 'medium', tomorrow, 4, 0),
        ('整理房间', '周末大扫除', 0, 'low', tomorrow, 4, 0),
        
        # 购物 (list_id=5)
        ('牛奶和面包', '日常食品采购', 0, 'medium', today, 5, 0),
        ('办公文具', '购买笔记本和笔', 0, 'low', tomorrow, 5, 0),
        
        # 工作 (list_id=6)
        ('代码审查', '审查团队成员的代码提交', 0, 'medium', today, 6, 0),
        ('更新文档', '更新API接口文档', 0, 'low', tomorrow, 6, 0),
        
        # 个人 (list_id=7)
        ('健身计划', '晚上7点健身房锻炼', 0, 'medium', today, 7, 0),
        ('阅读新书', '完成第三章的阅读', 0, 'low', tomorrow, 7, 0)
    ]

def insert_default_data():
    """插入默认数据"""
    conn = sqlite3.connect('settings.db')
    cursor = conn.cursor()
    
    # 检查是否已经有用户数据
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        print("没有用户数据，跳过默认数据初始化")
        conn.close()
        return
    
    # 获取第一个用户ID
    cursor.execute('SELECT id FROM users ORDER BY id LIMIT 1')
    user_result = cursor.fetchone()
    if not user_result:
        print("没有找到用户，跳过默认数据初始化")
        conn.close()
        return
    
    user_id = user_result[0]
    
    # 检查该用户是否已有任务列表
    cursor.execute('SELECT COUNT(*) FROM task_lists WHERE user_id = ?', (user_id,))
    if cursor.fetchone()[0] > 0:
        print(f"用户 {user_id} 已有数据，跳过初始化")
        conn.close()
        return
    
    # 插入用户偏好
    cursor.execute('''
        INSERT OR IGNORE INTO user_preferences (user_id, theme, language, accent_color, default_list_id)
        VALUES (?, 'light', 'zh-CN', '#0078d4', 4)
    ''', (user_id,))
    
    # 插入默认任务列表
    default_lists = get_default_task_lists()
    for task_list in default_lists:
        cursor.execute('''
            INSERT INTO task_lists (name, icon, color, sort_order, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', task_list + (user_id,))
    
    # 获取插入的任务列表ID映射
    cursor.execute('SELECT id, name FROM task_lists WHERE user_id = ? ORDER BY sort_order', (user_id,))
    list_mapping = {row[1]: row[0] for row in cursor.fetchall()}
    
    # 插入默认任务
    default_tasks = get_default_tasks()
    for task in default_tasks:
        # 映射list_id到实际的ID
        list_name_to_id = {
            1: '我的一天',
            2: '重要', 
            3: '已计划',
            4: '任务',
            5: '购物',
            6: '工作',
            7: '个人'
        }
        list_name = list_name_to_id.get(task[5], '任务')
        actual_list_id = list_mapping.get(list_name, list_mapping.get('任务', 1))
        
        cursor.execute('''
            INSERT INTO tasks (title, description, completed, priority, due_date, list_id, is_important, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', task[:6] + (task[6], user_id))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_database()
    insert_default_data()
    print("任务清单数据库初始化完成！")
