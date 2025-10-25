import sqlite3

def check_database():
    conn = sqlite3.connect('settings.db')
    cursor = conn.cursor()
    
    print("=== 任务列表和任务数量 ===")
    cursor.execute('''
        SELECT tl.id, tl.name, COUNT(t.id) as task_count
        FROM task_lists tl 
        LEFT JOIN tasks t ON tl.id = t.list_id 
        GROUP BY tl.id, tl.name 
        ORDER BY tl.sort_order
    ''')
    
    results = cursor.fetchall()
    for row in results:
        print(f"列表 {row[0]}: {row[1]} - {row[2]} 个任务")
    
    print("\n=== 详细任务信息 ===")
    cursor.execute('''
        SELECT t.id, t.title, t.list_id, tl.name as list_name
        FROM tasks t
        JOIN task_lists tl ON t.list_id = tl.id
        ORDER BY tl.sort_order, t.id
    ''')
    
    tasks = cursor.fetchall()
    for task in tasks:
        print(f"任务 {task[0]}: {task[1]} -> 列表 {task[2]} ({task[3]})")
    
    conn.close()

if __name__ == '__main__':
    check_database()
