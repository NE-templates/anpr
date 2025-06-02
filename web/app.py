from flask import Flask, render_template, jsonify, request
from datetime import datetime
from db import *

app = Flask(__name__)

# Route for the main dashboard
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# API Routes
@app.route('/api/revenue')
def api_revenue():
    try:
        total_revenue = get_total_revenue()
        return jsonify({'total_revenue': total_revenue})
    except Exception as e:
        print(f"[API ERROR] Revenue: {e}")
        return jsonify({'total_revenue': 0}), 500

@app.route('/api/daily-stats')
def api_daily_stats():
    try:
        period = request.args.get('period', '7d')
        stats = get_daily_stats()
        
        # Filter based on period
        if period == '30d':
            # Get last 30 days of stats
            stats = stats[:30] if len(stats) > 30 else stats
        else:  # Default to 7d
            stats = stats[:7] if len(stats) > 7 else stats
            
        return jsonify(stats)
    except Exception as e:
        print(f"[API ERROR] Daily stats: {e}")
        return jsonify([]), 500

@app.route('/api/recent-activity')
def api_recent_activity():
    try:
        limit = int(request.args.get('limit', 10))
        conn = connect_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT plate_number, payment_status, amount, timestamp, gate
                FROM parking_sessions
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (limit,))
            sessions = cursor.fetchall()
            
            activities = []
            for session in sessions:
                if session['payment_status'] == 1:
                    activities.append({
                        'type': 'payment',
                        'title': f"Payment received from {session['plate_number']} - RWF {session['amount']:,.0f}",
                        'time': format_time_ago(session['timestamp']),
                        'icon': 'fa-credit-card'
                    })
                elif session['gate'] == 'unauthorized':
                    activities.append({
                        'type': 'alert',
                        'title': f"Unauthorized exit attempt: {session['plate_number']}",
                        'time': format_time_ago(session['timestamp']),
                        'icon': 'fa-exclamation-triangle'
                    })
                elif session['payment_status'] == 2:
                    activities.append({
                        'type': 'exit',
                        'title': f"Vehicle {session['plate_number']} exited",
                        'time': format_time_ago(session['timestamp']),
                        'icon': 'fa-sign-out-alt'
                    })
                else:
                    activities.append({
                        'type': 'entry',
                        'title': f"Vehicle {session['plate_number']} entered at {session['gate']}",
                        'time': format_time_ago(session['timestamp']),
                        'icon': 'fa-car'
                    })
            
            cursor.close()
            conn.close()
            return jsonify(activities)
        return jsonify([]), 500
    except Exception as e:
        print(f"[API ERROR] Recent activity: {e}")
        return jsonify([]), 500

@app.route('/api/recent-sessions')
def api_recent_sessions():
    try:
        limit = int(request.args.get('limit', 20))
        conn = connect_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT plate_number, payment_status, amount, timestamp, gate
                FROM parking_sessions
                ORDER BY timestamp DESC
                LIMIT %s
            ''', (limit,))
            sessions = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify(sessions)
        return jsonify([]), 500
    except Exception as e:
        print(f"[API ERROR] Recent sessions: {e}")
        return jsonify([]), 500

@app.route('/api/active-vehicles')
def api_active_vehicles():
    try:
        conn = connect_db()
        if conn:
            cursor = conn.cursor()
            # Count vehicles that entered but haven't paid or exited
            cursor.execute('''
                SELECT COUNT(DISTINCT plate_number) as count
                FROM parking_sessions ps1
                WHERE payment_status = 0
                AND NOT EXISTS (
                    SELECT 1 FROM parking_sessions ps2
                    WHERE ps2.plate_number = ps1.plate_number
                    AND ps2.timestamp > ps1.timestamp
                    AND ps2.payment_status IN (1, 2)
                )
            ''')
            result = cursor.fetchone()
            count = result[0] if result else 0
            cursor.close()
            conn.close()
            return jsonify({'count': count})
        return jsonify({'count': 0}), 500
    except Exception as e:
        print(f"[API ERROR] Active vehicles: {e}")
        return jsonify({'count': 0}), 500

@app.route('/api/occupancy-rate')
def api_occupancy_rate():
    try:
        # This is a simplified calculation - you may want to adjust based on your parking lot capacity
        TOTAL_CAPACITY = 100  # Adjust this to your actual parking capacity
        
        conn = connect_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(DISTINCT plate_number) as occupied
                FROM parking_sessions ps1
                WHERE payment_status = 0
                AND NOT EXISTS (
                    SELECT 1 FROM parking_sessions ps2
                    WHERE ps2.plate_number = ps1.plate_number
                    AND ps2.timestamp > ps1.timestamp
                    AND ps2.payment_status IN (1, 2)
                )
            ''')
            result = cursor.fetchone()
            occupied = result[0] if result else 0
            rate = round((occupied / TOTAL_CAPACITY) * 100, 1) if TOTAL_CAPACITY > 0 else 0
            cursor.close()
            conn.close()
            return jsonify({'rate': rate, 'occupied': occupied, 'capacity': TOTAL_CAPACITY})
        return jsonify({'rate': 0}), 500
    except Exception as e:
        print(f"[API ERROR] Occupancy rate: {e}")
        return jsonify({'rate': 0}), 500

@app.route('/api/active-alerts')
def api_active_alerts():
    try:
        conn = connect_db()
        if conn:
            cursor = conn.cursor()
            # Count unauthorized exits in the last 24 hours
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM parking_sessions
                WHERE gate = 'unauthorized'
                AND timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ''')
            result = cursor.fetchone()
            count = result[0] if result else 0
            cursor.close()
            conn.close()
            return jsonify({'count': count})
        return jsonify({'count': 0}), 500
    except Exception as e:
        print(f"[API ERROR] Active alerts: {e}")
        return jsonify({'count': 0}), 500

@app.route('/api/system-alerts')
def api_system_alerts():
    try:
        alerts = []
        conn = connect_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Check for unauthorized exits in last 24 hours
            cursor.execute('''
                SELECT plate_number, timestamp
                FROM parking_sessions
                WHERE gate = 'unauthorized'
                AND timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY timestamp DESC
                LIMIT 5
            ''')
            unauthorized = cursor.fetchall()
            
            for record in unauthorized:
                alerts.append({
                    'type': 'error',
                    'title': f"Unauthorized exit: {record['plate_number']}",
                    'time': format_time_ago(record['timestamp']),
                    'severity': 'high'
                })
            
            # Check for vehicles parked too long (over 24 hours)
            cursor.execute('''
                SELECT plate_number, timestamp
                FROM parking_sessions ps1
                WHERE payment_status = 0
                AND timestamp <= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                AND NOT EXISTS (
                    SELECT 1 FROM parking_sessions ps2
                    WHERE ps2.plate_number = ps1.plate_number
                    AND ps2.timestamp > ps1.timestamp
                    AND ps2.payment_status IN (1, 2)
                )
                ORDER BY timestamp ASC
                LIMIT 3
            ''')
            long_parked = cursor.fetchall()
            
            for record in long_parked:
                alerts.append({
                    'type': 'warning',
                    'title': f"Vehicle {record['plate_number']} parked over 24 hours",
                    'time': format_time_ago(record['timestamp']),
                    'severity': 'medium'
                })
            
            cursor.close()
            conn.close()
            
        if not alerts:
            alerts.append({
                'type': 'info',
                'title': 'No active alerts',
                'time': '',
                'severity': 'low'
            })
            
        return jsonify(alerts)
    except Exception as e:
        print(f"[API ERROR] System alerts: {e}")
        return jsonify([{
            'type': 'info',
            'title': 'No active alerts',
            'time': '',
            'severity': 'low'
        }]), 500

@app.route('/api/revenue-breakdown')
def api_revenue_breakdown():
    try:
        conn = connect_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT 
                    DATE(timestamp) as date,
                    SUM(amount) as daily_revenue
                FROM parking_sessions
                WHERE payment_status = 1 OR payment_status = 2
                AND timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp) DESC
            ''')
            daily_breakdown = cursor.fetchall()
            
            breakdown = {}
            for record in daily_breakdown:
                date_str = record['date'].strftime('%m/%d')
                breakdown[date_str] = float(record['daily_revenue'])
            
            cursor.close()
            conn.close()
            
            if not breakdown:
                breakdown = {'Today': 0}
                
            return jsonify(breakdown)
        return jsonify({'Today': 0}), 500
    except Exception as e:
        print(f"[API ERROR] Revenue breakdown: {e}")
        return jsonify({'Today': 0}), 500

def format_time_ago(timestamp):
    """Format timestamp as time ago string"""
    if isinstance(timestamp, str):
        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    
    now = datetime.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

if __name__ == '__main__':
    # Ensure database table exists
    create_table_if_not_exists()
    app.run(debug=True, host='0.0.0.0', port=5000)