from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime, timedelta
from telegram.helpers import escape_markdown
# from telethon.sync import TelegramClient
# from telethon.tl.functions.contacts import ImportContactsRequest
# from telethon.tl.types import InputPhoneContact

import os
import asyncio
import config

bot = None
bot_app = None
bot_loop = None 

# ===== Database Config =====
DB_USER = "u198317474_staffHours"
DB_PASS = "BB0124147678bb"
DB_HOST = "auth-db1712.hstgr.io"
DB_NAME = "u198317474_telegramappbot"
DB_PORT = 3306

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ===== SQLAlchemy Engine with Connection Pool =====
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,  # <— keeps dead connections from being reused
    pool_recycle=18000   # <— refreshes connection before MySQL timeout
)
db_session = scoped_session(sessionmaker(bind=engine))

# ===== Query Execution =====
# def execute_query(query, params=None, fetch=True):
#     with engine.connect() as connection:
#         result = connection.execute(text(query), params or {})
#         if fetch:
#             return result.fetchall()
#         else:
#             connection.commit()

def execute_query(query, params=None, fetch=True):
    session = db_session()
    try:
        result = session.execute(text(query), params or {})
        if fetch:
            return result.fetchall()
        else:
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close() 
# ===== Table Creation =====
def create_employee_info_table():
    execute_query('''
        CREATE TABLE IF NOT EXISTS employee_info (
            employee_id VARCHAR(255) NOT NULL PRIMARY KEY,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            username VARCHAR(255),
            full_name VARCHAR(255) NOT NULL,
            city VARCHAR(255) NOT NULL,
            status INT(1) NOT NULL DEFAULT 0,
            hours_per_month DECIMAL(10,2) NOT NULL DEFAULT 0
        );
    ''', fetch=False)

def create_request_table():
    execute_query('''
        CREATE TABLE IF NOT EXISTS request (
            request_id INT AUTO_INCREMENT PRIMARY KEY, 
            hours DECIMAL(2,1) NOT NULL DEFAULT 0, 
            age_group VARCHAR(10),
            branch VARCHAR(255) NOT NULL,
            employee_id VARCHAR(255), 
            timing DATETIME DEFAULT UTC_TIMESTAMP,
            status INT(1) NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employee_info(employee_id) ON DELETE CASCADE
        );
    ''', fetch=False)

def create_branches_table():
    execute_query('''
        CREATE TABLE IF NOT EXISTS branches (
            branch_id INT(225) AUTO_INCREMENT PRIMARY KEY, 
            city VARCHAR(255), 
            branch VARCHAR(255) 
        );
    ''', fetch=False)

def create_month_table():
    execute_query('''
        CREATE TABLE IF NOT EXISTS month (
            id INT PRIMARY KEY AUTO_INCREMENT,
            start INT NOT NULL DEFAULT 26,
            end INT NOT NULL DEFAULT 25
        );
    ''', fetch=False)

def create_instructor_branches():
    execute_query('''
        CREATE TABLE IF NOT EXISTS instructor_branches (
            id INT AUTO_INCREMENT PRIMARY KEY,  
            status INT(1) NOT NULL DEFAULT 0,
            employee_id VARCHAR(255),
            branch_id INT(255),
            FOREIGN KEY (employee_id) REFERENCES employee_info(employee_id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE CASCADE,
            UNIQUE (employee_id, branch_id)
        );
    ''', fetch=False)

def create_course():
    execute_query('''
        CREATE TABLE IF NOT EXISTS course (
            course_id INT(225) AUTO_INCREMENT PRIMARY KEY,  
            branch_id INT(255),
            level INT(2),
            mode VARCHAR(7),
            day VARCHAR(10),
            time VARCHAR(225),
            age INT(2),
            employee_id VARCHAR(255),
            hour_per_lecture INT(2),
            timing DATETIME DEFAULT UTC_TIMESTAMP,
            course_name VARCHAR(225),
            archived INT(1) DEFAULT 0,
            system INT(1) DEFAULT 0,
            done INT(1) DEFAULT 0,
            sent INT(1) DEFAULT 0,
            room INT(10),
            number_of_students INT(2),
            type INT(1) DEFAULT 0,
            classroom_link VARCHAR(2048),
            daftara_course_link VARCHAR(2048),
            state INT(1),
            FOREIGN KEY (employee_id) REFERENCES employee_info(employee_id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id) REFERENCES branches(branch_id) ON DELETE CASCADE
        );
    ''', fetch=False)

def create_request_course():
    execute_query('''
        CREATE TABLE IF NOT EXISTS request_course (
            id INT(255) AUTO_INCREMENT PRIMARY KEY,  
            course_id INT(255),
            employee_id VARCHAR(255),
            lecture INT(2),
            hours_per_lecture DECIMAL(2,1),
            status INT(1) DEFAULT 0,
            compensation INT(1) DEFAULT 0,
            timing DATETIME DEFAULT UTC_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employee_info(employee_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE CASCADE
        );
    ''', fetch=False)

def create_instructor_courses():
    execute_query('''
        CREATE TABLE IF NOT EXISTS instructor_courses (
            id INT(255) AUTO_INCREMENT PRIMARY KEY,  
            course_id INT(255),
            employee_id VARCHAR(255),
            FOREIGN KEY (employee_id) REFERENCES employee_info(employee_id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE CASCADE,
            UNIQUE (course_id, employee_id)
        );
    ''', fetch=False)

# ===== Test Connection =====
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection (via SQLAlchemy + PyMySQL) is successful!")
except Exception as err:
    print(f"Error connecting to DB: {err}")

# ===== Reset Hours on 25th =====
def reset_hours_if_25th():
    # today = datetime.now()
    # if today.day == 25 and today.hour == 20 and today.minute >= 20:
    try:
        execute_query(
            "UPDATE employee_info SET hours_per_month = 0 WHERE hours_per_month >= 0",
            fetch=False
        )
        print("Employee hours reset successfully.")
    except Exception as e:
        print("Error resetting hours:", e)

# ===== Custom Date Range =====
def get_custom_date_range():
    result = execute_query("SELECT start, end FROM month ORDER BY id DESC LIMIT 1")
    start_day, end_day = result[0]

    today = datetime.now()
    if today.day >= start_day:
        start_date = today.replace(day=start_day)
        end_date = (today + timedelta(days=32)).replace(day=end_day)
    else:
        start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=start_day)
        end_date = today.replace(day=end_day)

    start_str = start_date.strftime('%Y-%m-%d 00:00:00')
    end_str = end_date.strftime('%Y-%m-%d 23:59:59')

    return start_str, end_str

# ===== escape_markdown =====
def safe_md(value):
    if value is None:
        return ""
    return escape_markdown(str(value), version=2)

# ===== Instructor Courses Table Cleaning =====
async def send_report_managers_async(bot_app):
    # Get all courses that are archived but not marked done
    query = '''
        SELECT c.course_name, c.course_id, c.employee_id, ei.full_name, c.branch_id, b.branch
        FROM course c
        JOIN employee_info ei ON c.employee_id = ei.employee_id
        JOIN branches b ON c.branch_id = b.branch_id
        WHERE c.archived = 1 AND c.done = 0 AND c.system = 1 AND c.sent = 0
    '''
    results = execute_query(query)
    results = [dict(row._mapping) for row in results]

    # Get top managers (hours_per_month == -2)
    top_managers = execute_query('''
        SELECT employee_id 
        FROM employee_info 
        WHERE hours_per_month = -2
    ''')
    top_managers = [dict(row._mapping) for row in top_managers]

    # Get branch managers (hours_per_month == -1)
    branch_managers = execute_query('''
        SELECT employee_id, full_name 
        FROM employee_info 
        WHERE hours_per_month = -1
    ''')
    branch_managers = [dict(row._mapping) for row in branch_managers]

    for row in results:
        course_id = row["course_id"]
        course_name = escape_markdown(row["course_name"], version=2)
        course_branch = row["branch"]

        # Find all distinct instructors who taught this course
        instructors = execute_query('''
            SELECT DISTINCT rc.employee_id, ei.full_name, ei.username
            FROM request_course rc
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            WHERE rc.course_id = :course_id
        ''', {"course_id": course_id})
        instructors = [dict(inst._mapping) for inst in instructors]

        instructor_count = len(instructors)

        # Start building report message
        message = (
            f"📨 Group \n*{course_name}*\n completed ✅👍 "
            f"by *{escape_markdown(str(instructor_count), version=2)}* instructor\\(s\\)\n\n"
            f"Details:\n\n"
        )

        # Instructor details
        for inst in instructors:
            inst_id = inst["employee_id"]
            inst_name = escape_markdown(inst["full_name"], version=2)

            stats = execute_query('''
                SELECT COUNT(course_id) AS lecture_count, 
                       SUM(hour_per_lecture) AS total_hours
                FROM request_course
                WHERE employee_id = :employee_id AND course_id = :course_id
            ''', {"employee_id": inst_id, "course_id": course_id})
            stats = [dict(s._mapping) for s in stats]

            lecture_count = escape_markdown(str(stats[0]["lecture_count"] or 0), version=2)
            total_hours = escape_markdown(str(stats[0]["total_hours"] or 0), version=2)

            message += (
                f"*ENG/* {inst_name}\n\n"
                f"*number of lectures:* {lecture_count}\n"
                f"*total hours:* {total_hours}\n\n"
            )

        sent_success = False    

        # --- Send to top managers ---
        for manager in top_managers:
            manager_id = manager["employee_id"]
            try:
                await bot_app.bot.send_message(
                    chat_id=manager_id,
                    text=message,
                    parse_mode="MarkdownV2"
                )
                sent_success = True
                print(f"Sent report to top manager {manager_id}")
            except Exception as e:
                print(f"Failed to send to {manager_id}: {e}")

        # --- Send to branch managers (only same branch) ---
        for manager in branch_managers:
            manager_id = manager["employee_id"]
            manager_branch = manager["full_name"]  # branch stored in full_name

            if str(manager_branch) == str(course_branch):  # match by branch
                try:
                    await bot_app.bot.send_message(
                        chat_id=manager_id,
                        text=message,
                        parse_mode="MarkdownV2"
                    )
                    sent_success = True
                    print(f"Sent report to branch manager {manager_id} (branch {manager_branch})")
                except Exception as e:
                    print(f"Failed to send to {manager_id}: {e}")

        # --- Update 'sent' flag in the course table if at least one message sent successfully ---
        if sent_success:
            execute_query(
                'UPDATE course SET sent = 1 WHERE course_id = :course_id',
                {'course_id': course_id},
                fetch=False
            )
            print(f"[INFO] Updated 'sent' flag for course_id={course_id}")

        # After reporting, delete from instructor_courses
        execute_query(
            'DELETE FROM instructor_courses WHERE course_id = :course_id',
            {'course_id': course_id},
            fetch=False
        )

def send_report_managers(bot_app):
    try:
        asyncio.run(mismatch_hours_async(bot_app))
        print("[DEBUG] Report sent successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] send_report_managers failed: {e}")

# ===== Mismatch Hours =====
async def mismatch_hours_async(bot_app):
    # Get top managers (all branches)
    top_managers = execute_query('''
        SELECT employee_id 
        FROM employee_info 
        WHERE hours_per_month = -2
    ''')
    top_managers = [dict(row._mapping) for row in top_managers]

    # Get branch managers
    branch_managers = execute_query('''
        SELECT employee_id, full_name 
        FROM employee_info 
        WHERE hours_per_month = -1
    ''')
    branch_managers = [dict(row._mapping) for row in branch_managers]

    # Loop over all courses (with branch info)
    courses = execute_query('''
        SELECT c.course_id, c.course_name, c.hour_per_lecture, b.branch
        FROM course c
        JOIN branches b ON c.branch_id = b.branch_id
    ''')
    courses = [dict(c._mapping) for c in courses]

    for course in courses:
        course_id = course["course_id"]
        course_name = escape_markdown(course["course_name"], version=2)
        course_hours = course["hour_per_lecture"]
        course_branch = course["branch"]

        # Get all instructor requests for this course that happened TODAY
        query = execute_query('''
            SELECT DISTINCT 
                rc.employee_id, rc.hour_per_lecture AS request_hours, 
                ei.full_name AS instructor_name, ei.username AS instructor_username,
                rc.timing, b.branch,
                (
                    SELECT username 
                    FROM employee_info bm 
                    WHERE bm.hours_per_month = -1 AND bm.full_name = b.branch
                    LIMIT 1
                ) AS branch_username
            FROM request_course rc
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            JOIN course c ON rc.course_id = c.course_id
            JOIN branches b ON c.branch_id = b.branch_id
            WHERE rc.course_id = :course_id
            AND DATE(rc.timing) = CURDATE()
            AND compensation = 0
        ''', {"course_id": course_id})
        
        instructors = [dict(row._mapping) for row in query]

        for inst in instructors:
            request_hours = inst["request_hours"]
            if request_hours is None:
                continue

            if request_hours != course_hours:
                inst_name = escape_markdown(inst["instructor_name"], version=2)
                inst_username = escape_markdown(inst["instructor_username"] or "---", version=2)
                branch_username = escape_markdown(inst["branch_username"] or "---", version=2)
                timing = escape_markdown(inst["timing"].strftime("%d-%m-%Y %I:%M:%S %p"), version=2)
                request_hours_fmt = escape_markdown(str(request_hours), version=2)
                course_hours_fmt = escape_markdown(str(course_hours), version=2)

                message = (
                    f"⚠️⚠️ In Group *{course_name}*:\n\n"
                    f"*ENG/* {inst_name}\n\n"
                    f"*Instructor username:* @{inst_username}\n"
                    f"*Branch Username:* @{branch_username}\n\n"
                    f"Added a request at *{timing}*\n\n"
                    f"Selected *{request_hours_fmt}* hour\\(s\\) per lecture, "
                    f"but this group should be *{course_hours_fmt}* per lecture"
                )

                # --- Send to top managers (always) ---
                for manager in top_managers:
                    try:
                        await bot_app.bot.send_message(
                            chat_id=manager["employee_id"],
                            text=message,
                            parse_mode="MarkdownV2"
                        )
                        print(f"[INFO] Mismatch sent to top manager {manager['employee_id']}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send to top manager {manager['employee_id']}: {e}")

                # # --- Send to branch managers (only course branch) ---
                # for manager in branch_managers:
                #     manager_id = manager["employee_id"]
                #     manager_branch = manager["full_name"]  # branch stored in full_name

                #     if str(manager_branch) == str(course_branch):  # match course branch
                #         try:
                #             await bot_app.bot.send_message(
                #                 chat_id=manager_id,
                #                 text=message,
                #                 parse_mode="MarkdownV2"
                #             )
                #             print(f"[INFO] Mismatch sent to branch manager {manager_id} (branch {manager_branch})")
                #         except Exception as e:
                #             print(f"[ERROR] Failed to send to branch manager {manager_id}: {e}")

def mismatch_hours(bot_app):
    try:
        asyncio.run(mismatch_hours_async(bot_app))
        print("[DEBUG] Mismatch hours report sent successfully")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] mismatch_hours failed: {e}")
