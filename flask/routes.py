from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from telegram import Bot
from telegram.helpers import escape_markdown
from sqlalchemy.exc import OperationalError

from db import execute_query, get_custom_date_range, safe_md

import asyncio
import traceback

main = Blueprint('main', __name__)

TOKEN_INSTRUCTOR = "7599846821:AAHzq6O49ozV2MhXhDc-xDes1o2K_hzmIPw"
TOKEN_MANAGER = "8209629905:AAEdvxOKjoii9BIo3Z6w6N1ZtqeaNO3GJQk"
TOKEN_TOP_MANAGER = "7731581469:AAFHs5aHAeKXseZvC7az2ONxT3LnJZ8AS4s"

@main.route('/')
def index():
    return 'Welcome to the Flask App!'

# ----------------------------- start.html ---------------------------------------------------- #
@main.route('/get_status_and_type/<employee_id>', methods=['GET'])
def get_employee_status(employee_id):
    try:
        query = """
            SELECT status, hours_per_month
            FROM employee_info
            WHERE employee_id = :employee_id
        """
        result = execute_query(query, {'employee_id': employee_id})

        if result and len(result) > 0:
            row = result[0]

            if hasattr(row, "_mapping"):  
                row = dict(row._mapping)

            return jsonify({
                "status": "success",
                "data": row
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Employee not found"
            }), 404

    except OperationalError as e:
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500
# ----------------------------- start.html ---------------------------------------------------- #

# ----------------------------- course.html/add_course.html ----------------------------------- #
# ----------------------------- archive_courses.html/history.html ----------------------------- #
@main.route('/get_employee_status/<employee_id>', methods=['GET'])
def employee_status_route(employee_id):
    try:
        employee_info = get_employee_status(employee_id)
        if employee_info:
            return jsonify({'status': 'success', 'data': employee_info})
        else:
            return jsonify({'status': 'error', 'message': 'employee not found'}), 404
    except OperationalError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def get_employee_status(employee_id):
    # Check in employee_info
    employee_query = """
        SELECT full_name, hours_per_month, status 
        FROM employee_info 
        WHERE employee_id = :employee_id
    """
    employee_result = execute_query(employee_query, {'employee_id': employee_id})
    print("employee_info result:", employee_result)

    if employee_result:
        full_name, hours_per_month, status = employee_result[0]
        if status == 1:
            return {
                "full_name": full_name,
                "hours_per_month": float(hours_per_month),
                "status": 1
            }

    # If not found or status != 1 in employee_info, check instructor_branches
    instructor_query = """
        SELECT e.full_name, 0.00 AS hours_per_month, ib.status 
        FROM instructor_branches ib
        JOIN employee_info e ON ib.employee_id = e.employee_id
        WHERE ib.employee_id = :employee_id
    """
    instructor_result = execute_query(instructor_query, {'employee_id': employee_id})
    print("instructor_branches result:", instructor_result)

    if instructor_result:
        full_name, hours_per_month, status = instructor_result[0]
        if status == 1:
            return {
                "full_name": full_name,
                "hours_per_month": 0.00,
                "status": 1
            }

    print("No matching employee found.")
    return None
# ----------------------------- start.html/course.html/add_course.html ------------------------ #
# ----------------------------- archive_courses.html/history.html ----------------------------- #

# ----------------------------- home.html ----------------------------------------------------- #
@main.route('/update_hour_employee', methods=['POST'])
def update_hour_employee():
    try:
        data = request.json
        employee_id = data.get('employee_id')

        if not employee_id:
            return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

        # Get full range tuple
        start_str, end_str = get_custom_date_range()
        today = datetime.now()
        print(today.day)
        print(f"Used range: {start_str} -> {end_str}")

        # Sum approved hours within selected range
        result = execute_query(
            """
            SELECT SUM(rc.hour_per_lecture), c.system
            FROM request_course rc
            JOIN course c ON rc.course_id = c.course_id
            WHERE rc.employee_id = :employee_id
              AND rc.status = 1
              AND c.system = 0
              AND rc.timing BETWEEN :start AND :end
            """,
            {
                "employee_id": employee_id,
                "start": start_str,
                "end": end_str
            }
        )

        total_approved_hours = result[0][0] if result and result[0][0] is not None else 0
        print(total_approved_hours)

        # Update employee_info
        execute_query(
            """
                UPDATE employee_info
                SET hours_per_month = :total_hours
                WHERE employee_id = :employee_id
            """,
            {
                "total_hours": total_approved_hours,
                "employee_id": employee_id
            },
            fetch=False
        )

        return jsonify({
            'status': 'success',
            'message': f'Total approved hours updated: {total_approved_hours}',
            'total_hours': total_approved_hours
        })

    except Exception as e:
        traceback.print_exc()
        print(e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- home.html ----------------------------------------------------- #

# ----------------------------- response.html ------------------------------------------------- #
@main.route('/get_all_waiting_requests/<employee_id>', methods=['GET'])
def get_all_waiting_requests_route(employee_id):
    try:
        request_info = get_all_waiting_requests(employee_id)
        if request_info:
            return jsonify({'status': 'success', 'data': request_info})
        else:
            return jsonify({'status': 'error', 'message': 'ID not found'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def get_all_waiting_requests(employee_id):
    query = """
        SELECT c.course_id, c.course_name, rc.id, rc.hour_per_lecture, rc.timing, rc.status
        FROM request_course rc
        JOIN course c ON rc.course_id = c.course_id
        JOIN employee_info ei ON rc.employee_id = ei.employee_id
        WHERE rc.employee_id = :employee_id AND rc.status = 0
    """
    results = execute_query(query, {"employee_id": employee_id})
    return [{
        "course_id": row[0],
        "course_name": row[1],
        "id": row[2],
        "hours_per_lecture": row[3],
        "timing": row[4].strftime("%d - %m - %Y") + "&emsp;" + row[4].strftime("%I:%M:%S %p"),
        "status": row[5]
    } for row in results] if results else []

@main.route('/delete_request', methods=['POST'])
def delete_request():
    try:
        data = request.get_json()
        request_id = data.get('request_id')

        if not request_id:
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        query = "DELETE FROM request_course Where id = :request_id"
        params = {"request_id": request_id}
        execute_query(query, params=params, fetch=False)

        return jsonify({'status': 'success', 'message': 'Request deleted successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- response.html ------------------------------------------------- #

# ----------------------------- old_histoy.html / complete_history.html ----------------------- #
@main.route('/get_all_request_info/<employee_id>', methods=['GET'])
def request_all_info_route(employee_id):
    try:
        request_info = get_all_request_info(employee_id)
        if isinstance(request_info, dict) and 'error' in request_info:
            return jsonify({'status': 'error', 'message': request_info['error']}), 400
        elif request_info:
            return jsonify({'status': 'success', 'data': request_info})
        else:
            return jsonify({'status': 'error', 'message': 'ID not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def get_all_request_info(employee_id):
    try:
        target_id = request.args.get('target_id')  # Person whose requests to retrieve
        city = request.args.get('city')

        if not target_id:
            return {'error': 'Missing target_id'}

        # Get manager info
        emp_result = execute_query(
            "SELECT hours_per_month, city, full_name FROM employee_info WHERE employee_id = :employee_id",
            {"employee_id": employee_id}
        )

        if not emp_result:
            return {'error': 'Employee not found'}

        hours_per_month, _, manager_branch = emp_result[0]

        # Define query and parameters based on role
        if hours_per_month == -1:
            print(">>>>>>>>>>>>>>    Manager")
            # Manager: See requests from employees in same branch
            query = """
                SELECT rc.course_id, c.course_name, rc.id, rc.hour_per_lecture, rc.timing, rc.status 
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE rc.employee_id = :employee_id AND b.branch = :branch
            """
            params = {"branch": manager_branch, "employee_id": target_id}

        elif hours_per_month == -2:
            print(">>>>>>>>>>>>>>   Top Manager")
            # Top Manager: See requests from employees in same city
            query = """
                SELECT rc.course_id, c.course_name, rc.id, rc.hour_per_lecture, rc.timing, rc.status
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE ei.city = :city AND rc.employee_id = :employee_id
            """
            params = {"city": city, "employee_id": target_id}

        else:
            print(">>>>>>>>>>>>>>    Instructor")
            # Normal employee: Only see their own requests
            query = """
                SELECT c.course_id, c.course_name, rc.id, rc.hour_per_lecture, rc.timing, rc.status
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE rc.employee_id = :employee_id
            """
            params = {"employee_id": employee_id}

        results = execute_query(query, params)
        print(results)
        formatted = [{
            "course_id": row[0],
            "course_name": row[1],
            "id": row[2],
            "hours_per_lecture": row[3],
            "timing": row[4].strftime("%d - %m - %Y") + "&emsp;" + row[4].strftime("%I:%M:%S %p"),
            "status": row[5]
        } for row in results] if results else []

        return formatted

    except Exception as e:
        print(e)
        return {'error': str(e)}

@main.route('/get_month', methods=['GET'])
def get_month():
    try:
        result = execute_query("SELECT start, end FROM month ORDER BY id DESC LIMIT 1")
        if not result:
            return jsonify({'status': 'error', 'message': 'Month config not found'}), 404
        
        start_day, end_day = result[0]
        return jsonify({'status': 'success', 'start': start_day, 'end': end_day})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- old_histoy.html / complete_history.html  ----------------------- #

# ----------------------------- request.html --------------------------------------------------- #
@main.route('/get_branches_for_employee/<employee_id>', methods=['GET'])
def get_branches_for_employee(employee_id):
    try:
        # Join instructor_branches and branches to get branch names for given employee_id
        query = '''
            SELECT b.branch 
            FROM instructor_branches ib
            JOIN branches b ON ib.branch_id = b.branch_id
            WHERE ib.employee_id = :employee_id
        '''
        result = execute_query(query, {"employee_id": employee_id})
        branch_list = [row[0] for row in result]

        return jsonify({'status': 'success', 'branches': branch_list})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/request_hours', methods=['POST'])
def request_hours():
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        hours = data.get('hours')
        age = data.get('age_group')
        branch = data.get('branch')
        timing = data.get('timing') or datetime.now().strftime('%d-%m-%y %I:%M:%S %p')

        # Validate required fields
        if not employee_id or not hours or not branch or not age:
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        # Use named parameters for SQLAlchemy-style execution
        query = """
            INSERT INTO request (hours, age_group, branch, employee_id, timing)
            VALUES (:hours, :age_group, :branch, :employee_id, :timing)
        """
        params = {
            "hours": hours,
            "age_group": age,
            "branch": branch,
            "employee_id": employee_id,
            "timing": timing
        }

        execute_query(query, params=params, fetch=False)

        return jsonify({'status': 'success', 'message': 'Request recorded successfully'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_instructor_courses/<employee_id>', methods=['GET'])
def get_instructor_courses(employee_id):
    try:
        query = """
            SELECT course.course_id, course.course_name, course.hour_per_lecture
            FROM course
            INNER JOIN instructor_courses ON course.course_id = instructor_courses.course_id
            WHERE instructor_courses.employee_id = :employee_id
        """
        result = execute_query(query, params= {"employee_id": employee_id}, fetch=True)
        print(result)
        if not result:
            return jsonify({'status': 'success', 'data': [], 'message': 'No courses found for instructor'}), 200

        course_list = [{'id': row[0], 'name': row[1], "max_hours": row[2]} for row in result]
        return jsonify({'status': 'success', 'data': course_list}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@main.route('/request_course_lecture', methods=['POST'])
def request_course_lecture():
    data = request.get_json()
    course_id = data.get('course_id')
    employee_id = data.get('employee_id')
    lecture = data.get('lecture')
    hour_per_lecture = data.get('hour_per_lecture')
    compensation = data.get('compensation')
    timing_str = data.get('timing')

    try:
        try:
            # 24-hour format (e.g., "2025-10-03 14:30:00")
            timing = datetime.strptime(timing_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            timing = datetime.now()

    except Exception:
        timing = datetime.now()

    if not all([course_id, employee_id, hour_per_lecture]):
        return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

    try:
        insert_query = '''
            INSERT INTO request_course (course_id, employee_id, lecture, hour_per_lecture, compensation, timing)
            VALUES (:course_id, :employee_id, :lecture, :hour_per_lecture, :compensation, :timing);
        '''
        execute_query(insert_query, 
                      {"course_id": course_id, "employee_id": employee_id, 
                       "lecture": lecture, "hour_per_lecture": hour_per_lecture, 
                       "compensation": compensation, "timing": timing}, fetch=False)
        
        print("Inserted:", course_id, employee_id, lecture, hour_per_lecture, compensation, timing)
        return jsonify({'status': 'success', 'message': 'Request submitted successfully'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- request.html --------------------------------------------------- #

# ----------------------------- history.html --------------------------------------------------- #
@main.route('/get_request_info/<employee_id>', methods=['GET'])
def request_info_route(employee_id):
    try:
        target_id = request.args.get('target_id')  # Person whose data is queried
        city = request.args.get('city')

        if not target_id:
            return jsonify({'status': 'error', 'message': 'Missing employee_id or target_id'}), 400

        start_str, end_str = get_custom_date_range()
        today = datetime.now()
        print(today.day)
        print(f"Used range: {start_str} -> {end_str}")

        # Get employee info
        emp_result = execute_query(
            "SELECT hours_per_month, city, full_name FROM employee_info WHERE employee_id = :employee_id",
            {"employee_id": employee_id}
        )

        if not emp_result:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        hours_per_month, _, full_name = emp_result[0]

        # Set query and parameters
        if hours_per_month == -1:
            print(">>>>>>>>>>> Manager")

            query = """
                SELECT rc.id, c.course_name, rc.hour_per_lecture, rc.timing, rc.status 
                FROM course c
                JOIN request_course rc ON c.course_id = rc.course_id
                JOIN branches b ON c.branch_id = b.branch_id

                WHERE b.branch = :branch AND rc.status != 0 
                      AND rc.employee_id = :employee_id 
                      AND rc.timing BETWEEN :start AND :end
                      AND c.system = 0
            """
            params = {"branch": full_name, "employee_id": target_id, "start": start_str, "end": end_str}

        elif hours_per_month == -2:
            print(">>>>>>>>>>> Top Manager")

            if not city:
                return jsonify({'status': 'error', 'message': 'Missing city parameter'}), 400
    
            query = """
                SELECT rc.id, c.course_name, rc.hour_per_lecture, rc.timing, rc.status 
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN employee_info e ON rc.employee_id = e.employee_id
                WHERE e.city = :city 
                      AND rc.status != 0 
                      AND rc.employee_id = :employee_id 
                      AND rc.timing BETWEEN :start AND :end
                      AND c.system = 0
            """
            params = {"city": city, "employee_id": target_id, "start": start_str, "end": end_str}

        else:
            print(">>>>>>>>>>> Normal Employee")
            query = """
                SELECT rc.id, c.course_name, rc.hour_per_lecture, rc.timing, rc.status 
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                
                WHERE rc.employee_id = :employee_id 
                      AND rc.status != 0 
                      AND rc.timing BETWEEN :start AND :end
                      AND c.system = 0
            """
            params = {"employee_id": employee_id, "start": start_str, "end": end_str}

        # Execute and format result
        results = execute_query(query, params)

        filtered = [{
            "id": row[0],
            "course_name": row[1],
            "hour_per_lecture": row[2],
            "timing": row[3].strftime("%Y-%m-%d %H:%M:%S"),
            "status": row[4]
        } for row in results]

        return jsonify({'status': 'success', 'data': filtered})

    except Exception as e:
        print(e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_total_hours', methods=['GET'])
def get_total_hours_route():
    try:
        employee_id = request.args.get('employee_id')  # The requester
        target_id = request.args.get('target_id')      # The person whose hours are being queried
        city = request.args.get('city')

        if not employee_id or not target_id:
            return jsonify({'status': 'error', 'message': 'Missing employee_id or target_id'}), 400

        # Get current month date range
        start_str_current, end_str_current = get_custom_date_range()

        # Compute previous month by shifting the current start date back one month
        start_dt_current = datetime.strptime(start_str_current, "%Y-%m-%d %H:%M:%S")
        start_dt_previous = start_dt_current - relativedelta(months=1)
        end_dt_previous = start_dt_current - timedelta(seconds=1)

        start_str_previous = start_dt_previous.strftime("%Y-%m-%d %H:%M:%S")
        end_str_previous = end_dt_previous.strftime("%Y-%m-%d %H:%M:%S")

        # Get info about requesting employee
        emp_result = execute_query(
            "SELECT city, hours_per_month, full_name FROM employee_info WHERE employee_id = :employee_id",
            {"employee_id": employee_id}
        )
        if not emp_result:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        _, hours_per_month, full_name = emp_result[0]

        # Helper function for generating the right query
        def get_hours_query(start, end):
            if hours_per_month == -1:
                # Manager
                query = """
                    SELECT SUM(rc.hour_per_lecture)
                    FROM request_course rc
                    JOIN course c ON rc.course_id = c.course_id
                    JOIN branches b ON c.branch_id = b.branch_id
                    WHERE rc.status = 1
                    AND rc.timing BETWEEN :start AND :end
                    AND b.branch = :branch
                    AND rc.employee_id = :employee_id
                    AND c.system = 0
                """
                return execute_query(query, {"start": start, "end": end, "branch": full_name, "employee_id": target_id})

            elif hours_per_month == -2:
                # Top Manager
                query = """
                    SELECT SUM(rc.hour_per_lecture)
                    FROM request_course rc
                    JOIN employee_info ei ON rc.employee_id = ei.employee_id
                    JOIN course c ON rc.course_id = c.course_id
                    WHERE rc.status = 1
                      AND rc.timing BETWEEN :start AND :end
                      AND ei.city = :city
                      AND rc.employee_id = :employee_id
                      AND c.system = 0
                """
                return execute_query(query, {"start": start, "end": end, "city": city, "employee_id": target_id})

            else:
                # Normal employee: only access own data
                if employee_id != target_id:
                    return jsonify({'status': 'error', 'message': 'Unauthorized access to target employee data'}), 403

                query = """
                    SELECT SUM(rc.hour_per_lecture)
                    FROM request_course rc
                    JOIN course c ON rc.course_id = c.course_id
                    WHERE rc.employee_id = :employee_id
                      AND rc.status = 1
                      AND rc.timing BETWEEN :start AND :end
                      AND c.system = 0
                """
                return execute_query(query, {"employee_id": employee_id, "start": start, "end": end})

        # Get hours for both months
        result_current = get_hours_query(start_str_current, end_str_current)
        result_previous = get_hours_query(start_str_previous, end_str_previous)

        # Extract totals
        total_current = float(result_current[0][0]) if result_current and result_current[0][0] is not None else 0.0
        total_previous = float(result_previous[0][0]) if result_previous and result_previous[0][0] is not None else 0.0

        return jsonify({
            'status': 'success',
            'data': {
                'employee_id': target_id,
                'current_month': {
                    'total_hours': total_current,
                    'range': {'start': start_str_current, 'end': end_str_current}
                },
                'previous_month': {
                    'total_hours': total_previous,
                    'range': {'start': start_str_previous, 'end': end_str_previous}
                }
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- history.html --------------------------------------------------- #

# ----------------------------- employee.html/control_request.html/complete_history.html ------- #
# ----------------------------- home.html/instructors.html ------------------------------------- #
@main.route('/get_employee_info/<employee_id>', methods=['GET'])
def employee_info_route(employee_id):
    employee_info = get_employee_info(employee_id)
    if employee_info:
        return jsonify({'status': 'success', 'data': employee_info})
    else:
        return jsonify({'status': 'error', 'message': 'Employee not found'}), 404
    
def get_employee_info(employee_id):
    try:
        result = execute_query(
            "SELECT full_name, hours_per_month FROM employee_info WHERE employee_id = :employee_id",
            {"employee_id": employee_id}
        )
        if result:
            return {
                "full_name": result[0][0],
                "hours_per_month": result[0][1],
            }
        return None
    except Exception as e:
        print("Error in get_employee_info:", e)
        return None
# ----------------------------- employee.html/control_request.html/complete_history.html ------- #
# ----------------------------- home.html/instructors.html ------------------------------------- #

# ----------------------------- all.html/course.html/employee.html ----------------------------- #
# ----------------------------- history.html/instructors.html/employee.html -------------------- #
@main.route('/update_status', methods=['POST'])
def update_status():
    try:
        data = request.json
        request_id = data.get('request_id')
        status = data.get('status')

        if request_id is None or status is None:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        result = execute_query("SELECT employee_id FROM request_course WHERE id = :request_id", {"request_id": request_id})
        if not result:
            return jsonify({'status': 'error', 'message': 'Request not found'}), 404

        employee_id = result[0][0]

        execute_query("UPDATE request_course SET status = :status WHERE id = :request_id", {"status": status, "request_id": request_id}, fetch=False)

        result = execute_query(
            "SELECT SUM(hour_per_lecture) FROM request_course WHERE employee_id = :employee_id AND status = 1",
            {"employee_id": employee_id}
        )
        total_hours = result[0][0] if result and result[0][0] is not None else 0

        # execute_query(
        #     "UPDATE employee_info SET hours_per_month = :hours_per_month WHERE employee_id = :employee_id",
        #     {"hours_per_month": total_hours, "employee_id": employee_id},
        #     fetch=False
        # )

        return jsonify({
            'status': 'success',
            'message': 'Request status updated and hours calculated',
            'employee_id': employee_id,
            'hours_per_month': total_hours
        })

    except Exception as e:
        print("Error in /update_status:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- all.html/course.html/employee.html ----------------------------- #
# ----------------------------- history.html/instructors.html/employee.html -------------------- #

# @main.route('/debug_all_employees', methods=['GET'])
# def debug_all_employees():
#     try:
#         result = execute_query("SELECT employee_id, full_name FROM employee_info")
#         return jsonify(result)
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': str(e)}), 500

# ----------------------------- instructors.html ----------------------------------------------- #
@main.route('/delete_employee', methods=['POST'])
def delete_employee():
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')

        if not employee_id:
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        query = "DELETE FROM employee_info Where employee_id = :employee_id"
        params = {"employee_id": employee_id}
        execute_query(query, params=params, fetch=False)

        return jsonify({'status': 'success', 'message': 'Request deleted successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_employee_request', methods=['GET']) 
def get_employee_request():
    manager_employee_id = request.args.get('employee_id')
    override_city = request.args.get('city')  # Only required for top managers

    if not manager_employee_id:
        return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

    try:
        # Get manager role info and city
        result = execute_query("""
            SELECT full_name, hours_per_month, city FROM employee_info
            WHERE employee_id = :employee_id
        """, {"employee_id": manager_employee_id})
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404
        
        full_name, hours_per_month, manager_city = result[0]

        # Manager (hours_per_month == -1)
        if hours_per_month == -1:
            print(">>>>>>>>>>>>>>> Manager")

            branch_result = execute_query("""
                SELECT branch_id FROM branches WHERE branch = :full_name
            """, {"full_name": full_name})
            
            if not branch_result:
                return jsonify({'status': 'error', 'message': 'Branch not found for manager'}), 404

            branch_id = branch_result[0][0]

            # Get employees assigned to that branch from instructor_branches
            employees = execute_query("""
                SELECT ei.employee_id, ei.full_name, ei.city, ib.status, ib.branch_id, b.branch
                FROM employee_info ei
                JOIN instructor_branches ib ON ei.employee_id = ib.employee_id
                JOIN branches b ON ib.branch_id = b.branch_id
                WHERE ib.branch_id = :branch_id
            """, {"branch_id": branch_id})

            employee_list = [
                {
                    'employee_id': emp[0],
                    'full_name': emp[1],
                    'city': emp[2],
                    'status': emp[3],
                    'branch_id': emp[4],
                    'branch': emp[5],
                    'role': 'manager'
                } for emp in employees
            ]

        # Top Manager (hours_per_month == -2)
        elif hours_per_month == -2:
            print(">>>>>>>>>>>>>>> Top Manager")

            if not override_city:
                return jsonify({'status': 'error', 'message': 'Missing city parameter for top manager'}), 400

            if override_city.lower() == "online":
                employees = execute_query("""
                    SELECT ei.employee_id, ei.full_name, ei.city, ei.status AS ei_status, ib.status AS ib_status, ib.branch_id, b.branch
                    FROM employee_info ei
                    JOIN instructor_branches ib ON ei.employee_id = ib.employee_id
                    JOIN branches b ON ib.branch_id = b.branch_id
                    WHERE ib.branch_id = 8 AND ei.hours_per_month >= 0
                """)
            else: 
                employees = execute_query("""
                    SELECT ei.employee_id, ei.full_name, ei.city, ei.status AS ei_status, ib.status AS ib_status, ib.branch_id, b.branch
                    FROM employee_info ei
                    JOIN instructor_branches ib ON ei.employee_id = ib.employee_id
                    JOIN branches b ON ib.branch_id = b.branch_id
                    WHERE ei.city = :city AND ei.hours_per_month >= 0
                """, {"city": override_city})

            employee_list = [
                {
                    'employee_id': emp[0],
                    'full_name': emp[1],
                    'city': emp[2],
                    'status': emp[3],         # keep employee_info.status
                    'ib_status': emp[4],      # add instructor_branches.status
                    'branch_id': emp[5],
                    "branch": emp[6],
                    'role': 'top_manager'
                } for emp in employees
            ]

        else:
            return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

        return jsonify({'status': 'success', 'employees': employee_list})

    except Exception as e:
        print("Error fetching employee requests:", e)
        return jsonify({'status': 'error', 'message': 'Failed to fetch employee requests'}), 500
    
@main.route('/update_status_employee', methods=['POST'])
def update_status_employee():
    try:
        data = request.json
        employee_id = data.get('employee_id')
        branch_id = data.get('branch_id')  # Added this
        status = data.get('status')

        # Validate inputs
        if not employee_id or not branch_id or status not in [1, 2]:
            return jsonify({'status': 'error', 'message': 'Invalid input'}), 400

        # Update only the specific employee + branch row
        query = "UPDATE instructor_branches SET status = :status WHERE employee_id = :employee_id AND branch_id = :branch_id"
        params = {"status": status, "employee_id": employee_id, "branch_id": branch_id}
        execute_query(query, params=params, fetch=False)

        return jsonify({'status': 'success', 'message': 'Status updated'})

    except Exception as e:
        print("Error updating status:", e)
        return jsonify({'status': 'error', 'message': 'Database update failed'}), 500


@main.route('/update_status_employee_info', methods=['POST'])
def update_status_employee_info():
    data = request.get_json()
    employee_id = data.get('employee_id')
    status = data.get('status')

    if not employee_id or status is None:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        execute_query("""
            UPDATE employee_info SET status = :status WHERE employee_id = :employee_id
        """, {"status": status, "employee_id": employee_id}, fetch=False)

        return jsonify({'status': 'success', 'message': 'Status updated'})
    except Exception as e:
        print("Error updating status in employee_info:", e)
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'Failed to update status'}), 500
# ----------------------------- instructors.html ----------------------------------------------- #

# ----------------------------- control_request.html/add_course.html/course.html --------------- #
@main.route('/get_employee_names', methods=['GET'])
def get_employee_names():
    manager_employee_id = request.args.get('employee_id')
    url_city = request.args.get('city')  # For top manager case

    if not manager_employee_id:
        return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

    try:
        # Get manager role and city
        result = execute_query("""
            SELECT hours_per_month, city, full_name FROM employee_info
            WHERE employee_id = :employee_id
        """, {"employee_id": manager_employee_id})
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Manager not found'}), 404

        hours_per_month, manager_city, manager_full_name = result[0]

        if hours_per_month == -2:  # Top Manager
            if not url_city:
                return jsonify({'status': 'error', 'message': 'City parameter required for top managers'}), 400

            city_to_use = url_city

            # Top manager: Fetch instructors whose branch city matches selected city
            employees = execute_query("""
                SELECT DISTINCT e.employee_id, e.full_name, b.city
                FROM employee_info e
                JOIN instructor_branches ib 
                    ON e.employee_id = ib.employee_id
                JOIN branches b 
                    ON ib.branch_id = b.branch_id
                WHERE b.city = :city
                AND e.hours_per_month >= 0
                AND e.status = 1
                AND ib.status = 1
            """, {"city": city_to_use})

        elif hours_per_month == -1:  # Manager

            # Get manager's branch_id by matching full_name to branch name
            branch_result = execute_query("""
                SELECT branch_id FROM branches
                WHERE branch = :branch AND city = :city
            """, {"branch": manager_full_name, "city": manager_city})

            if not branch_result:
                return jsonify({'status': 'error', 'message': 'Manager branch not found'}), 404

            manager_branch_id = branch_result[0][0]

            # Fetch employees whose instructor_branches.branch_id matches manager_branch_id
            employees = execute_query("""
                SELECT DISTINCT e.employee_id, e.full_name, e.city
                FROM employee_info e
                JOIN instructor_branches ib ON e.employee_id = ib.employee_id
                WHERE ib.branch_id = :branch_id
                  AND e.hours_per_month >= 0
                  AND e.status = 1 AND ib.status = 1
            """, {"branch_id": manager_branch_id})

        else:
            return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

        response = [{'id': row[0], 'name': row[1], 'city': row[2]} for row in employees]
        return jsonify({'status': 'success', 'employees': response})

    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': 'Server error'}), 500
# ----------------------------- control_request.html/add_course.html/course.html --------------- #

# ----------------------------- add_course.html/request.html ----------------------------------- #
@main.route('/request_course', methods=['POST'])
def request_course():
    try:
        # === Step 0: Get manager ID from query string ===
        manager_id = request.args.get('employee')
        if not manager_id:
            return jsonify({'status': 'error', 'message': 'Missing manager ID in query parameters'}), 400

        # === Step 1: Get JSON payload ===
        data = request.get_json()
        instructor_id = data.get('employee_id')  # Instructor ID
        system = data.get('system')
        type = data.get('type')
        level = data.get('level')
        mode = 'offline'
        day = data.get('day')
        time = data.get('time')
        room = data.get('room')
        age = data.get('age')
        state = data.get('state')
        code = data.get('code')
        hour = data.get('hour_per_lecture')
        timing_str = data.get('timing')
        print(type)
        try:
            try:
                # 24-hour format (e.g., "2025-10-03 14:30:00")
                timing = datetime.strptime(timing_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                timing = datetime.now()

        except Exception:
            timing = datetime.now()

        # Validate required fields
        required_fields = [level, mode, day, age, system, type, state]
        if not all(required_fields):
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400
        
        if not instructor_id:
            instructor_id = None
        
        if not hour:
            hour = 2

        # === Step 2: Get manager role and branch info ===
        role_result = execute_query(
            "SELECT hours_per_month, city, full_name FROM employee_info WHERE employee_id = :employee_id",
            params={"employee_id": manager_id}, fetch=True
        )

        if not role_result:
            return jsonify({'status': 'error', 'message': 'Manager not found'}), 404

        hours_per_month, manager_city, manager_branch = role_result[0]

        # === Step 3: Decide city, branch, and branch_id based on role ===
        if hours_per_month == -1:  # Manager
            course_city = manager_city
            course_branch = manager_branch

            branch_result = execute_query("""
                SELECT branch_id FROM branches WHERE city = :city AND branch = :branch
            """, params={"city": course_city, "branch": course_branch}, fetch=True)

        elif hours_per_month == -2:  # Top Manager
            requested_city = request.args.get('city')
            requested_branch = request.args.get('branch')

            if not requested_city or not requested_branch:
                return jsonify({'status': 'error', 'message': 'City and Branch required for top manager'}), 400

            course_city = requested_city
            course_branch = requested_branch

            branch_result = execute_query("""
                SELECT branch_id FROM branches WHERE city = :city AND branch = :branch
            """, params={"city": course_city, "branch": course_branch}, fetch=True)
        else:
            return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

        if not branch_result:
            return jsonify({'status': 'error', 'message': 'Branch not found'}), 404

        branch_id = branch_result[0][0]

        # === Step 4: Build course_name ===
        if course_city.lower().startswith('alexandria'):
            city_prefix = course_city[:4].upper()
        elif course_city.lower().startswith('online'):
            mode = 'online'
            city_prefix = course_city.upper()
        elif course_city.lower().startswith('Dakahlia'):
            city_prefix = course_branch[:3].upper()
        else:
            city_prefix = course_city[:3].upper()

        if course_branch.lower().startswith('damanhour'):
            branch_prefix = f'{course_branch[0].upper()}1'
        elif course_branch.lower().startswith("el-khalifa"):
            branch_prefix = "K"
        elif course_branch.lower().startswith("al-zahraa"):
            branch_prefix = "Z"
        else:
            branch_prefix = course_branch[0].upper()

        # if code:
        #     if course_branch.lower().startswith('mansoura'): 
        #         course_name = f"{course_branch[:3].upper()}/RC{level}/{day}/{time}/{room.upper()}/{age} {code}"
        #     elif course_branch.lower().startswith('online'):
        #         course_name = f"{course_branch.upper()}/RC{level}/{day}/{time}/{room.upper()}/{age} {code}"
        #     else:
        #         course_name = f"{city_prefix}-{branch_prefix}/RC{level}/{day}/{time}/{room.upper()}/{age} {code}"

        # else:
        #     if course_branch.lower().startswith('mansoura'): 
        #         course_name = f"{course_branch[:3].upper()}/RC{level}/{day}/{time}/{room.upper()}/{age}"
        #     elif course_branch.lower().startswith('online'):
        #         course_name = f"{course_branch.upper()}/RC{level}/{day}/{time}/{room.upper()}/{age}"
        #     else: 
        #         course_name = f"{city_prefix}-{branch_prefix}/RC{level}/{day}/{time}/{room.upper()}/{age}"

        branch = course_branch.lower()

        # Determine the prefix depending on branch
        if branch.startswith('mansoura'):
            prefix = course_branch[:3].upper()
        elif branch.startswith('online'):
            prefix = course_branch.upper()
        else:
            prefix = f"{city_prefix}-{branch_prefix}"

        # Build the base path
        if mode == 'online':
            if type == "1":
                course_name = f"{prefix}/RC{level}/{day}/{time}(Private)/{age}"
            else:
                course_name = f"{prefix}/RC{level}/{day}/{time}/{age}"
        else:
            course_name = f"{prefix}/RC{level}/{day}/{time}/{room.upper()}/{age}"

        # Add code if exists
        if code:
            course_name += f" {code}"

        # === Step 5: Insert into course table ===
        insert_query = """
            INSERT INTO course (branch_id, system, level, mode, day, time, age, employee_id, hour_per_lecture, timing, course_name, room, type, state)
            VALUES (:branch_id, :system, :level, :mode, :day, :time, :age, :employee_id, :hour_per_lecture, :timing, :course_name, :room, :type, :state)
        """
        insert_params = {
            "branch_id": branch_id,
            "system": system,
            "level": level,
            "mode": mode,
            "day": day,
            "time": time,
            "age": age,
            "employee_id": instructor_id,
            "hour_per_lecture": hour,
            "timing": timing,
            "course_name": course_name,
            "room": room,
            "type": type,
            "state": state
        }
        execute_query(insert_query, params=insert_params, fetch=False)

        # === Step 6: Get latest course_id ===
        course_id = execute_query(
            "SELECT course_id FROM course ORDER BY course_id DESC LIMIT 1", fetch=True
        )[0][0]

        return jsonify({
            'status': 'success',
            'message': 'Course request recorded successfully',
            "course_id": course_id
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- add_course.html/request.html ----------------------------------- #

# ----------------------------- add_course.html/course.html ------------------------------------ #
@main.route('/add_instructor', methods=['POST'])
def add_instructor():
    try:
        data = request.get_json()
        course_id = data.get('course_id')
        employee_id = data.get('employee_id')
        print("Received data for /add_instructor:", data)

        # Validation
        if not course_id:
            return jsonify({'status': 'error', 'message': 'Missing course_id'}), 400
        elif not employee_id:
            return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

        # Insert into instructor_courses
        insert_query = '''
            INSERT INTO instructor_courses (course_id, employee_id)
            VALUES (:course_id, :employee_id)
        '''
        execute_query(insert_query, params={"course_id": course_id, "employee_id": employee_id}, fetch=False)

        return jsonify({
            'status': 'success',
            'message': 'Course request recorded successfully',
            'course_id': course_id
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- add_course.html/course.html ------------------------------------ #

# ----------------------------- home_top_manager.html/home_manager.html ------------------------ #
@main.route('/get_manager_info/<employee_id>', methods=['GET'])
def get_manager_info_route(employee_id):
    employee_info = get_manager_info(employee_id)
    if employee_info:
        return jsonify({'status': 'success', 'data': employee_info})
    else:
        return jsonify({'status': 'error', 'message': 'employee not found'}), 404

def get_manager_info(employee_id):
    query = "SELECT city, full_name FROM employee_info WHERE employee_id = :employee_id"
    result = execute_query(query, {"employee_id": employee_id})
    if result:
        return {
            "city": result[0][0],
            "full_name": result[0][1]
        }
    return None
# ----------------------------- home_top_manager.html/home_manager.html ------------------------ #

# ----------------------------- branch.html ---------------------------------------------------- #
@main.route('/get_cities', methods=['GET'])
def get_cities():
    try:
        query = "SELECT DISTINCT city FROM branches"
        result = execute_query(query)
        cities = [{'name': row[0]} for row in result]
        return jsonify({'status': 'success', 'cities': cities})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_branches_by_city', methods=['GET'])
def get_branches_by_city():
    city = request.args.get('city')
    if not city:
        return jsonify({'status': 'error', 'message': 'City not provided'}), 400

    try:
        query = "SELECT DISTINCT branch FROM branches WHERE city = :city"
        result = execute_query(query, {"city": city})
        branches = [{'name': row[0]} for row in result]
        return jsonify({'status': 'success', 'branches': branches})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- branch.html ---------------------------------------------------- #

# ----------------------------- employee.html -------------------------------------------------- #
@main.route('/get_all_requests_by_city', methods=['GET'])
def get_all_requests_by_city():
    manager_employee_id = request.args.get('employee_id')
    url_city = request.args.get('city')  # Required only for top managers

    if not manager_employee_id:
        return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

    try:
        # Step 1: Get manager details
        result = execute_query("""
            SELECT hours_per_month, city, full_name FROM employee_info
            WHERE employee_id = :employee_id
        """, {'employee_id': manager_employee_id})
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Manager not found'}), 404

        hours_per_month, manager_city, manager_full_name = result[0]

        if hours_per_month == -2:
            # Top Manager
            if not url_city:
                return jsonify({'status': 'error', 'message': 'City parameter required for top managers'}), 400

            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.lecture
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE b.city = :city AND rc.status = 0
            """, {'city': url_city})

        elif hours_per_month == -1:
            # Manager
            branch_result = execute_query("""
                SELECT branch_id FROM branches
                WHERE branch = :branch AND city = :city
            """, {'branch': manager_full_name, 'city': manager_city})

            if not branch_result:
                return jsonify({'status': 'error', 'message': 'Manager branch not found'}), 404

            manager_branch_id = branch_result[0][0]

            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.lecture
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE b.branch_id = :branch_id AND rc.status = 0
            """, {'branch_id': manager_branch_id})

        else:
            print(">>>>>>>>>>>>>>>>> Instructor")
            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.employee_id, rc.lecture
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE rc.employee_id = :employee_id AND rc.status = 0
            """, {'employee_id': manager_employee_id})

            if not manager_employee_id:
                return jsonify({'status': 'error', 'message': 'Instructor not found'}), 400

        response = []
        for row in requests:
            row_data = {
                'id': row[0], 
                'hour_per_lecture': row[1],
                'status': row[2],
                'course_name': row[3],
                'employee_name': row[4],
                "timing": row[5].strftime("%d - %m - %Y") + "&emsp;" + row[5].strftime("%I:%M:%S %p"),
                'course_id': row[6],
                'lecture': row[7]
            }
            response.append(row_data)

        return jsonify({'status': 'success', 'data': response})

    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': 'Server error'}), 500
# ----------------------------- employee.html -------------------------------------------------- #

# ----------------------------- all.html ------------------------------------------------------- #
@main.route('/get_all_requests_to_manager', methods=['GET'])
def get_all_requests_to_manager():
    try:

        results = execute_query("""
            SELECT rc.id, rc.hour_per_lecture, rc.timing, rc.status, ei.full_name, c.course_name
            FROM request_course rc
            JOIN course c ON rc.course_id = c.course_id
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            WHERE rc.status = 0
            ORDER BY rc.timing DESC
        """)

        data = [{
            "id": row[0],
            "hour_per_lecture": row[1],
            "timing": row[2].strftime("%d - %m - %Y") + "&emsp;" + row[2].strftime("%I:%M:%S %p"),
            "status": row[3],
            "full_name": row[4],
            "course_name": row[5]
        } for row in results]

        return jsonify({'status': 'success', 'data': data})

    except Exception as e:
        print(e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- all.html ------------------------------------------------------- #

# ----------------------------- home_top_manager.html/home_manager.html/home.html -------------- #
@main.route('/send_feedback', methods=['POST'])
def handle_feedback():
    data = request.get_json()
    employee_id = data.get("employee_id")
    message = data.get("message")

    if not employee_id or not message:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        # Get employee info
        result = execute_query(
            "SELECT full_name, city, username, hours_per_month FROM employee_info WHERE employee_id = :employee_id",
            {"employee_id": employee_id}
        )

        if not result:
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        full_name, city, username, hours_per_month = result[0]
        username_display = f"@{username}" if username else "___"

        # Escape user data
        full_name_esc = escape_markdown(full_name, version=2)
        city_esc = escape_markdown(city, version=2)
        username_display_esc = escape_markdown(username_display, version=2)
        message_esc = escape_markdown(message, version=2)

        # Format feedback message
        text = (
            f"*New Feedback Received*\n\n"
            f"*Name🧍‍♂️:* {full_name_esc}\n"
            f"*City🏙️:* {city_esc}\n"
            f"*Username👷‍♂️:* {username_display_esc}\n"
            f"*Message📩:* {message_esc}"
        )

        # Choose bot token based on hours_per_month
        ADMIN_ID = 1189998133  # Change if needed

        if hours_per_month == -1:
            token = TOKEN_MANAGER
            bot_name = "Manager Bot"
        elif hours_per_month == -2:
            token = TOKEN_TOP_MANAGER
            bot_name = "Top Manager Bot"
        else:
            token = TOKEN_INSTRUCTOR
            bot_name = "Instructor Bot"

        # Send feedback message using the correct bot
        async def send_feedback_async():
            bot = Bot(token=token)
            await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="MarkdownV2")

        asyncio.run(send_feedback_async())

        return jsonify({'status': 'success', 'message': f'Feedback sent via {bot_name}'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500
# ----------------------------- home_top_manager.html/home_manager.html/home.html -------------- #

# ----------------------------- add_branch.html ------------------------------------------------ #
@main.route('/get_all_cities_branches', methods=['GET'])
def get_all_cities_branches():
    try:
        query = "SELECT branch_id, city, branch FROM branches"
        results = execute_query(query)

        data = [{'branch_id': row[0], 'city': row[1], 'branch': row[2]} for row in results]
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        print("Error fetching branches:", e)
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

@main.route('/add_branch', methods=['POST'])
def add_branch():
    data = request.get_json()
    city = data.get('city')
    branch = data.get('branch')

    if not city or not branch:
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        query = "INSERT INTO branches (city, branch) VALUES (:city, :branch)"
        execute_query(query, {"city": city, "branch": branch}, fetch=False)
        return jsonify({'status': 'success'})
    except Exception as e:
        print("Error inserting branch:", e)
        return jsonify({'status': 'error', 'message': 'Insert failed'}), 500

@main.route('/edit_branch', methods=['POST'])
def edit_branch():
    data = request.get_json()
    print("Received JSON:", data)

    id = data.get('branch_id')
    city = data.get('city')
    branch = data.get('branch')

    if not city or not branch or not id:
        print("Missing one of the fields:", city, branch, id)
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        query = "UPDATE branches SET branch = :branch, city = :city WHERE branch_id = :branch_id"
        execute_query(query, {"city": city, "branch": branch, "branch_id": id}, fetch=False)
        return jsonify({'status': 'success'})
    except Exception as e:
        print("Error updating branch:", e)
        return jsonify({'status': 'error', 'message': 'Update failed'}), 500
# ----------------------------- add_branch.html ------------------------------------------------ #

# ----------------------------- total.html ----------------------------------------------------- #
@main.route('/report', methods=['GET'])
def report():
    branch = request.args.get('branch')

    if not branch:
        return jsonify({'status': 'error', 'message': 'Missing branch name'}), 400

    try:
        start_str, end_str = get_custom_date_range()
        today = datetime.now()
        print(today.day)
        print(f"Used range: {start_str} -> {end_str}")

        # Total hours + number of employees
        summary_query = """
            SELECT 
                SUM(rc.hour_per_lecture) AS total_hours,
                COUNT(DISTINCT rc.employee_id) AS total_employees
            FROM request_course rc
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            JOIN course c ON rc.course_id = c.course_id
            JOIN branches b ON c.branch_id = b.branch_id
            WHERE rc.status = 1
              AND b.branch = :branch
              AND ei.hours_per_month >= 0
              AND rc.timing BETWEEN :start AND :end
        """
        summary_result = execute_query(summary_query, {"branch": branch, "start": start_str, "end": end_str})
        total_hours = float(summary_result[0][0]) if summary_result and summary_result[0][0] is not None else 0.0
        total_employees = int(summary_result[0][1]) if summary_result and summary_result[0][1] is not None else 0

        # Get the maximum total hours
        max_hours_query = """
            SELECT MAX(total) FROM (
                SELECT SUM(rc.hour_per_lecture) AS total
                FROM request_course rc
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                WHERE rc.status = 1
                  AND b.branch = :branch
                  AND ei.hours_per_month >= 0
                  AND rc.timing BETWEEN :start AND :end
                GROUP BY rc.employee_id
            ) AS sub
        """
        max_hours_result = execute_query(max_hours_query, {"branch": branch, "start": start_str, "end": end_str})
        max_hours = float(max_hours_result[0][0]) if max_hours_result and max_hours_result[0][0] is not None else 0.0

        # Get all employees who have that max total
        top_employees_query = """
            SELECT ei.full_name, SUM(rc.hour_per_lecture) AS total
            FROM request_course rc
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            JOIN course c ON rc.course_id = c.course_id
            JOIN branches b ON c.branch_id = b.branch_id
            WHERE rc.status = 1
              AND b.branch = :branch
              AND ei.hours_per_month >= 0
              AND rc.timing BETWEEN :start AND :end
            GROUP BY ei.employee_id
            HAVING total = :total
        """
        top_employees = execute_query(top_employees_query, {"branch": branch, "start": start_str, "end": end_str, "total": max_hours})
        top_employee_list = [{'name': name, 'hours': float(hours)} for name, hours in top_employees]

        return jsonify({
            'status': 'success',
            'branch': branch,
            'total_hours': total_hours,
            'total_employees': total_employees,
            'top_employees': top_employee_list
        })

    except Exception as e:
        print(e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@main.route('/get_branches_for_city', methods=['GET'])
def get_branches_for_city():
    city = request.args.get('city')
    if not city:
        return jsonify({'status': 'error', 'message': 'Missing city'}), 400

    try:
        branches = execute_query("SELECT branch FROM branches WHERE city = :city", {"city": city})
        branch_names = [b[0] for b in branches]
        return jsonify({'status': 'success', 'branches': branch_names})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- total.html ----------------------------------------------------- #

# ----------------------------- archive_courses_instructor.html/course.html/archive_courses ---- #
# ----------------------------- response_course.html ------------------------------------------- #
@main.route('/get_course_name', methods=['GET'])
def get_course_name():
    manager_employee_id = request.args.get('employee_id')
    url_city = request.args.get('city') 

    print(url_city)
    if not manager_employee_id:
        return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

    try:
        result = execute_query("""
            SELECT hours_per_month, city, full_name FROM employee_info
            WHERE employee_id = :employee_id
        """, {'employee_id': manager_employee_id})
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Manager not found'}), 404

        hours_per_month, manager_city, manager_full_name = result[0]

        if hours_per_month == -2:
            print(">>>>>>>>>>>>>>> Top Manager")
            if not url_city:
                return jsonify({'status': 'error', 'message': 'City parameter required for top managers'}), 400

            courses = execute_query("""
                SELECT DISTINCT c.course_id, c.course_name, c.archived, c.system, c.done
                FROM course c
                JOIN branches b ON c.branch_id = b.branch_id
                WHERE b.city = :city
            """, {'city': url_city})

        elif hours_per_month == -1:
            print(">>>>>>>>>>>>>>> Manager")
            branch_result = execute_query("""
                SELECT branch_id FROM branches
                WHERE branch = :branch AND city = :city
            """, {'branch': manager_full_name, 'city': manager_city})

            if not branch_result:
                return jsonify({'status': 'error', 'message': 'Manager branch not found'}), 404

            manager_branch_id = branch_result[0][0]

            courses = execute_query("""
                SELECT DISTINCT course_id, course_name, archived, system, done
                FROM course
                WHERE branch_id = :branch_id
            """, {'branch_id': manager_branch_id})

        else:
            print(">>>>>>>>>>>>>>>>> Instructor")
            courses = execute_query("""
                SELECT DISTINCT c.course_id, c.course_name, c.archived, c.system, c.done
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                WHERE rc.employee_id = :employee_id
            """, {'employee_id': manager_employee_id})

            if not manager_employee_id:
                return jsonify({'status': 'error', 'message': 'Instructor not found'}), 400

        response = [{'course_id': row[0], 'course_name': row[1], 'archived': row[2], 'system': row[3], 'done': row[4]} for row in courses]
        return jsonify({'status': 'success', 'courses': response})

    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- archive_courses_instructor.html/course.html/archive_courses ---- #
# ----------------------------- response_course.html ------------------------------------------- #

# ----------------------------- course.html ---------------------------------------------------- #
@main.route('/update_status_course', methods=['POST'])
def update_status_course():
    try:
        data = request.json
        request_course_id = data.get('id')
        status = data.get('status')

        if request_course_id is None:
            return jsonify({'status': 'error', 'message': 'Missing parameters id'}), 400
        elif status is None:
            return jsonify({'status': 'error', 'message': 'Missing parameters status'}), 400
        
        result = execute_query("SELECT employee_id FROM request_course WHERE id = :id", {"id": request_course_id})
        if not result:
            print(request_course_id)
            print(status)
            return jsonify({'status': 'error', 'message': 'Request not found'}), 404

        employee_id = result[0][0]
        # lecture_number = result[0][1]

        execute_query("UPDATE request_course SET status = :status WHERE id = :id", {"status": status, "id": request_course_id}, fetch=False)

        return jsonify({
            'status': 'success',
            'message': 'Request status updated and hours calculated',
            'employee_id': employee_id,
            # 'lecture_number': lecture_number
        })

    except Exception as e:
        print("Error in /update_status_course:", e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/edit_course/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    data = request.get_json()
    print("Received JSON:", data)

    day = data.get('day')
    time = data.get('time')
    room = data.get('room')
    hours = data.get('hours')  

    try:
        if not hours:
            hours = 2

        old_course = execute_query(
            "SELECT course_name FROM course WHERE course_id = :course_id",
            {"course_id": course_id},
            fetch=True
        )

        if not old_course:
            return jsonify({'status': 'error', 'message': 'Course not found'}), 404

        old_course_name = old_course[0][0]  

        parts = old_course_name.split('/')

        if len(parts) >= 5:
            parts[2] = day or parts[2]       
            parts[3] = time or parts[3]     
            parts[4] = room.upper() or parts[4] 
        else:
            print("Unexpected course_name format:", old_course_name)

        new_course_name = '/'.join(parts)

        update_query = '''
            UPDATE course 
            SET day = :day, time = :time, hour_per_lecture = :hour_per_lecture, course_name = :course_name
            WHERE course_id = :course_id
        '''
        execute_query(update_query, {"day": day, "time": time, "hour_per_lecture": hours, "course_name": new_course_name, "course_id": course_id}, fetch=False)


        return jsonify({'status': 'success'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# @main.route('/archive_course', methods=['POST'])
# def archive_course():
#     data = request.get_json()
#     course_id = data.get('course_id')
#     print(course_id)
#     if not course_id:
#         return jsonify({"status": "error", "message": "Missing course_id"}), 400
    
#     try:
#         execute_query("UPDATE course SET archived = 1 WHERE course_id = :course_id", 
#                       {"course_id": course_id},
#                       fetch=False)
#         return jsonify({"status": "success"})
#     except Exception as e:
#         traceback.print_exc()
#         return jsonify({"status": "error", "message": str(e)}), 500

@main.route('/archive_course', methods=['POST'])
def archive_course():
    data = request.get_json()
    course_id = data.get('course_id')
    print(course_id)

    if not course_id:
        return jsonify({"status": "error", "message": "Missing course_id"}), 400

    try:
        # Archive the course
        execute_query(
            "UPDATE course SET archived = 1 WHERE course_id = :course_id",
            {"course_id": course_id},
            fetch=False
        )

        # Delete related instructor-course relationship(s)
        execute_query(
            "DELETE FROM instructor_courses WHERE course_id = :course_id",
            {"course_id": course_id},
            fetch=False
        )

        return jsonify({"status": "success"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@main.route('/get_course_info', methods=['GET'])
def get_course_info():
    manager_employee_id = request.args.get('employee_id')
    url_city = request.args.get('city')  # Required only for top managers

    if not manager_employee_id:
        return jsonify({'status': 'error', 'message': 'Missing employee_id'}), 400

    try:
        # Step 1: Get manager details
        result = execute_query("""
            SELECT hours_per_month, city, full_name FROM employee_info
            WHERE employee_id = :employee_id
        """, {'employee_id': manager_employee_id})
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Manager not found'}), 404

        hours_per_month, manager_city, manager_full_name = result[0]

        if hours_per_month == -2:
            # Top Manager
            if not url_city:
                return jsonify({'status': 'error', 'message': 'City parameter required for top managers'}), 400

            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.lecture, rc.compensation, rc.employee_id
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE b.city = :city
                ORDER BY rc.timing DESC
            """, {'city': url_city})

        elif hours_per_month == -1:
            # Manager
            branch_result = execute_query("""
                SELECT branch_id FROM branches
                WHERE branch = :branch AND city = :city
            """, {'branch': manager_full_name, 'city': manager_city})

            if not branch_result:
                return jsonify({'status': 'error', 'message': 'Manager branch not found'}), 404

            manager_branch_id = branch_result[0][0]

            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.lecture, rc.compensation, rc.employee_id
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN branches b ON c.branch_id = b.branch_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE b.branch_id = :branch_id
                ORDER BY rc.timing DESC
            """, {'branch_id': manager_branch_id})

        else:
            print(">>>>>>>>>>>>>>>>> Instructor")
            requests = execute_query("""
                SELECT rc.id, rc.hour_per_lecture, rc.status, c.course_name, ei.full_name, rc.timing, c.course_id, rc.lecture, rc.compensation, rc.employee_id
                FROM request_course rc
                JOIN course c ON rc.course_id = c.course_id
                JOIN employee_info ei ON rc.employee_id = ei.employee_id
                WHERE rc.employee_id = :employee_id
                ORDER BY rc.timing DESC
            """, {'employee_id': manager_employee_id})

            if not manager_employee_id:
                return jsonify({'status': 'error', 'message': 'Instructor not found'}), 400
            
            if not requests:
                return jsonify({'status': 'success', 'data': []})

        response = []
        for row in requests:
            response.append({
                'id': row[0],
                'hour_per_lecture': row[1],
                'status': row[2],
                'course_name': row[3],
                'employee_name': row[4],
                "timing": row[5].strftime("%d - %m - %Y") + "&emsp;" + row[5].strftime("%I:%M %p"),
                'course_id': row[6],
                'lecture': row[7],
                'compensation': row[8],
                'employee_id': row[9]
            })

        return jsonify({'status': 'success', 'data': response})

    except Exception as e:
        print("Error:", e)
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

# ----------------------------- course.html ---------------------------------------------------- #

# ----------------------------- request.html --------------------------------------------------- #
@main.route('/get_last_lecture/<int:course_id>', methods=['GET'])
def get_last_lecture(course_id):
    # Execute query to get the maximum lecture number for the course
    last_lecture_query = execute_query('''
        SELECT MAX(lecture) AS last_lecture
        FROM request_course
        WHERE course_id = :course_id
    ''', {"course_id": course_id})

    # Extract the last lecture value
    last_lecture = last_lecture_query[0]._mapping["last_lecture"] or 0

    # Return the result as JSON
    return jsonify({
        "status": "success",
        "last_lecture": last_lecture
    })

@main.route('/send_order_compensation/<int:course_id>', methods=['GET'])
def send_order_compensation(course_id):
    try:
        compensation = request.args.get('compensation', type=int, default=0)

        # === Get managers ===
        top_managers = execute_query('''
            SELECT employee_id 
            FROM employee_info 
            WHERE hours_per_month = -2
        ''')
        top_managers = [row[0] for row in top_managers]

        branch_managers = execute_query('''
            SELECT employee_id, full_name
            FROM employee_info 
            WHERE hours_per_month = -1
        ''')
        branch_managers = [dict(row._mapping) for row in branch_managers]

        # === Get course info ===
        course = execute_query('''
            SELECT c.course_id, c.course_name, c.hour_per_lecture, b.branch
            FROM course c
            JOIN branches b ON c.branch_id = b.branch_id
            WHERE c.course_id = :course_id
        ''', {"course_id": course_id})

        if not course:
            return jsonify({"status": "error", "message": "Course not found"}), 404

        course = dict(course[0]._mapping)
        course_name = escape_markdown(course["course_name"], version=2)
        course_branch = escape_markdown(course["branch"], version=2)

        # === Get today's requests for this course ===
        query = execute_query('''
            SELECT DISTINCT rc.employee_id, rc.lecture AS request_hours, 
                            ei.full_name AS instructor_name, rc.timing, rc.compensation
            FROM request_course rc
            JOIN employee_info ei ON rc.employee_id = ei.employee_id
            WHERE rc.course_id = :course_id
              AND DATE(rc.timing) = CURDATE()
            ORDER BY rc.timing ASC
        ''', {"course_id": course_id})

        instructors = [dict(row._mapping) for row in query]
        if not instructors:
            return jsonify({"status": "ok", "message": "No requests today"})

        latest_request = instructors[-1]
        requested_lecture = latest_request["request_hours"]

        if requested_lecture is None:
            return jsonify({"status": "ok", "message": "Requested lecture not provided"})

        # === Get last lecture before today ===
        last_lecture_query = execute_query('''
            SELECT MAX(rc.lecture) AS last_lecture
            FROM request_course rc
            WHERE rc.course_id = :course_id
              AND DATE(rc.timing) < CURDATE()
        ''', {"course_id": course_id})

        last_lecture = last_lecture_query[0]._mapping["last_lecture"] or 0

        # === Prepare async send ===
        async def send_alerts(messages):
            # Each bot uses its own token
            top_bot = Bot(token=TOKEN_TOP_MANAGER)
            manager_bot = Bot(token=TOKEN_MANAGER)

            for chat_id, msg, role in messages:
                bot = top_bot if role == "top" else manager_bot
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="MarkdownV2")

        messages_to_send = []

        # === Case 1: Compensatory Lecture ===
        if compensation == 1:
            inst_name = escape_markdown(latest_request["instructor_name"], version=2)
            timing = escape_markdown(latest_request["timing"].strftime("%d-%m-%Y %I:%M:%S %p"), version=2)
            requested_lecture_fmt = escape_markdown(str(requested_lecture), version=2)
            hour_per_lecture_fmt = escape_markdown(str(course["hour_per_lecture"]), version=2)

            message = (
                f"⚠️ *Compensatory Lecture* ⚠️\n\n"
                f"In Group *{course_name}*:\n\n"
                f"*ENG/* {inst_name}\n"
                f"*Time:* {timing}\n\n"
                f"Requested a compensatory lecture with *{hour_per_lecture_fmt} hours*\n"
                f"Lecture number *{requested_lecture_fmt}*"
            )

            for manager_id in top_managers:
                messages_to_send.append((manager_id, message, "top"))

        # === Case 2: Wrong Lecture Order ===
        wrong_order = False

        if requested_lecture > last_lecture + 1:
            wrong_order = True
            reason = f"skipped expected lecture (expected {last_lecture + 1}, got {requested_lecture})"
        elif requested_lecture <= last_lecture:
            wrong_order = True
            reason = f"repeated or previous lecture (last given {last_lecture}, got {requested_lecture})"

        if wrong_order:
            inst_name = escape_markdown(latest_request["instructor_name"], version=2)
            timing = escape_markdown(latest_request["timing"].strftime("%d-%m-%Y %I:%M:%S %p"), version=2)
            requested_lecture_fmt = escape_markdown(str(requested_lecture), version=2)
            expected_lecture_fmt = escape_markdown(str(last_lecture + 1), version=2)

            message = (
                f"⚠️ *Wrong Lecture Order Detected* ⚠️\n\n"
                f"In Group *{course_name}*:\n\n"
                f"*ENG/* {inst_name}\n"
                f"*Time:* {timing}\n\n"
                f"Requested lecture number *{requested_lecture_fmt}*, "
                f"but the expected next lecture should be *{expected_lecture_fmt}*\n"
                f"Reason: {escape_markdown(reason, version=2)}"
            )

            # Send to top managers
            for manager_id in top_managers:
                messages_to_send.append((manager_id, message, "top"))

            # Send to branch managers with the same branch
            for manager in branch_managers:
                if escape_markdown(manager["full_name"], version=2) == course_branch:
                    messages_to_send.append((manager["employee_id"], message, "manager"))

        # === Send All Messages ===
        if messages_to_send:
            asyncio.run(send_alerts(messages_to_send))

        # === Response ===
        if wrong_order:
            return jsonify({
                "status": "alert",
                "message": "Wrong lecture order detected and alerts sent",
                "requested": requested_lecture,
                "expected": last_lecture + 1
            })
        else:
            return jsonify({
                "status": "ok",
                "message": "Lecture order is correct",
                "requested": requested_lecture,
                "expected": last_lecture + 1
            })


    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
# ----------------------------- request.html --------------------------------------------------- #

# ----------------------------- response_course.html ------------------------------------------- #
@main.route('/total_hours_course_instructor', methods=['GET'])
def total_hours_course_instructor():
    employee_id = request.args.get('employee_id', type=int)
    course_id = request.args.get('course_id', type=int)

    try:
        query = '''
            SELECT SUM(hour_per_lecture) AS total_hours FROM request_course 
            WHERE employee_id = :employee_id AND course_id = :course_id AND status = 1
        '''
        total = execute_query(query, {'employee_id': employee_id, 'course_id': course_id})
        total_hours = total[0]._mapping["total_hours"] or 0

        return jsonify({'status': 'success', 'total': total_hours}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- response_course.html ------------------------------------------- #

# ----------------------------- archive_courses.html ------------------------------------------- #
@main.route('/update_done', methods=['POST'])
def update_done():
    data = request.get_json()
    course_id = data.get('course_id')
    done = data.get('done')

    try:
        query = '''
            UPDATE course SET done = :done WHERE course_id = :course_id
        '''
        execute_query(query, {'course_id': course_id, 'done': done}, fetch=False)

        return jsonify({'status': 'success'})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)})

@main.route('/unarchive_course', methods=['POST'])
def unarchive_course():
    data = request.get_json()
    course_id = data.get('course_id')

    if not course_id:
        return jsonify({"status": "error", "message": "Missing course_id"}), 400

    try:
        # Fetch all employee_ids from request_course for this course
        get_query = '''
            SELECT DISTINCT employee_id
            FROM request_course
            WHERE course_id = :course_id
        '''
        employees = execute_query(get_query, {"course_id": course_id}, fetch=True)

        if not employees:
            return jsonify({"status": "error", "message": "No employees found for this course"}), 404

        # Unarchive the course
        execute_query(
            "UPDATE course SET archived = 0 WHERE course_id = :course_id",
            {"course_id": course_id},
            fetch=False
        )

        # Insert all employees into instructor_courses (if not already present)
        for emp in employees:
            employee_id = emp[0]  # Each row is a tuple like ('E123',)
            insert_query = '''
                INSERT INTO instructor_courses (course_id, employee_id)
                SELECT :course_id, :employee_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM instructor_courses
                    WHERE course_id = :course_id AND employee_id = :employee_id
                )
            '''
            execute_query(insert_query, {"course_id": course_id, "employee_id": employee_id}, fetch=False)

        return jsonify({"status": "success"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@main.route('/total_hours_in_this_course/<int:course_id>', methods=['GET'])
def total_hours_in_this_course(course_id):
    try:
        result = execute_query(
            'SELECT SUM(hour_per_lecture) AS total_hours FROM request_course WHERE course_id = :course_id AND status = 1',
            {'course_id': course_id}
        )
        total_hours = result[0][0] if result and result[0][0] is not None else 0
        return jsonify({'status': 'success', 'total_hours': total_hours})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- archive_courses.html ------------------------------------------- #

# ----------------------------- change.html ---------------------------------------------------- #
@main.route('/get_all_employees_by_city', methods=['GET'])
def get_all_employees_by_city():
    try:
        query = '''
            SELECT employee_id, full_name, city, hours_per_month FROM employee_info 
        '''
        employees = execute_query(query, fetch=True)

        data = [{
            "employee_id": row[0],
            "full_name": row[1],
            "city": row[2],
            "hours_per_month": row[3]
        } for row in employees]

        return jsonify({'status': 'success', 'message': 'get all employees successfully', 'data': data}), 200
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@main.route('/update_employee', methods=['POST'])
def update_employee():
    try:
        data = request.get_json()
        employee_id = data.get("employee_id")
        full_name = data.get("full_name")
        city = data.get("city")
        hours_per_month = data.get("hours_per_month")
        
        query = '''
            UPDATE employee_info
            SET full_name = :full_name, city = :city, hours_per_month = :hours_per_month
            WHERE employee_id = :employee_id
        '''
        execute_query(query, {
            'full_name': full_name,
            'city': city,
            'hours_per_month': hours_per_month,
            'employee_id': employee_id
        }, fetch=False)

        return jsonify({'status': 'success', 'message': 'Employee updated successfully'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
# ----------------------------- change.html ---------------------------------------------------- #

# =============================================== update month feature ========================= #
@main.route('/update_month', methods=['POST'])
def update_month():
    try:
        data = request.get_json()
        start = data.get("start")
        end = data.get("end")

        if not isinstance(start, int) or not isinstance(end, int):
            return jsonify({'status': 'error', 'message': 'Invalid input'}), 400

        query = "UPDATE month SET start = :start, end = :end WHERE id = 1"
        execute_query(query, {"start": start, "end": end}, fetch=False)

        return jsonify({'status': 'success', 'message': 'Month updated successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
