import os
from flask import Flask, jsonify, render_template_string, request, abort
from flask_cors import CORS
from dotenv import load_dotenv
from database import Database
from aws_monitor import AWSMonitor
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)
db = Database()

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DASHBOARD_SECRET = os.getenv('DASHBOARD_SECRET', 'change_this_secret')


# ─────────────────────────────────────────
# HTML TEMPLATES
# ─────────────────────────────────────────

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Monitor Bot - Admin Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0f0f1a; color: #ffffff; font-family: 'Segoe UI', sans-serif; }
        .header { background: #1a1a2e; padding: 20px 30px; border-bottom: 1px solid #333; }
        .header h1 { color: #00d4ff; font-size: 22px; }
        .header p { color: #888; font-size: 13px; margin-top: 4px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }
        .stat-card .label { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card .value { color: #00d4ff; font-size: 32px; font-weight: bold; margin-top: 8px; }
        .stat-card .sub { color: #666; font-size: 12px; margin-top: 4px; }
        .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }
        .chart-card h3 { color: #ffffff; font-size: 14px; margin-bottom: 15px; }
        .users-table { background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }
        .users-table h3 { color: #ffffff; font-size: 14px; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th { color: #888; font-size: 11px; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
        td { padding: 10px 12px; border-bottom: 1px solid #222; font-size: 13px; }
        .badge { padding: 3px 8px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-premium { background: #ffd700; color: #000; }
        .badge-free { background: #333; color: #888; }
        @media (max-width: 768px) { .charts-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>AWS Monitor Bot — Admin Dashboard</h1>
        <p>Last updated: <span id="lastUpdated"></span></p>
    </div>
    <div class="container">
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card"><div class="label">Total Users</div><div class="value" id="totalUsers">-</div></div>
            <div class="stat-card"><div class="label">Premium Users</div><div class="value" id="premiumUsers">-</div></div>
            <div class="stat-card"><div class="label">Revenue This Month</div><div class="value" id="revenue">-</div></div>
            <div class="stat-card"><div class="label">Total Revenue</div><div class="value" id="totalRevenue">-</div></div>
            <div class="stat-card"><div class="label">AWS Accounts</div><div class="value" id="accounts">-</div></div>
            <div class="stat-card"><div class="label">Active Alerts</div><div class="value" id="alerts">-</div></div>
            <div class="stat-card"><div class="label">New Users Today</div><div class="value" id="newToday">-</div></div>
            <div class="stat-card"><div class="label">New This Week</div><div class="value" id="newWeek">-</div></div>
        </div>
        <div class="charts-grid">
            <div class="chart-card">
                <h3>User Growth (Last 30 Days)</h3>
                <canvas id="userChart" height="200"></canvas>
            </div>
            <div class="chart-card">
                <h3>Free vs Premium</h3>
                <canvas id="planChart" height="200"></canvas>
            </div>
        </div>
        <div class="users-table">
            <h3>Recent Users</h3>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Username</th>
                        <th>Plan</th>
                        <th>Joined</th>
                    </tr>
                </thead>
                <tbody id="usersTableBody"></tbody>
            </table>
        </div>
    </div>
    <script>
        const SECRET = '{{ secret }}';

        async function loadStats() {
            const res = await fetch(`/api/admin/stats?secret=${SECRET}`);
            const data = await res.json();

            document.getElementById('totalUsers').textContent = data.total_users;
            document.getElementById('premiumUsers').textContent = data.premium_users;
            document.getElementById('revenue').textContent = `Rs.${data.revenue_this_month}`;
            document.getElementById('totalRevenue').textContent = `Rs.${data.total_revenue || 0}`;
            document.getElementById('accounts').textContent = data.total_accounts;
            document.getElementById('alerts').textContent = data.active_alerts;
            document.getElementById('newToday').textContent = data.new_today;
            document.getElementById('newWeek').textContent = data.new_this_week;
            document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();

            // Plan pie chart
            new Chart(document.getElementById('planChart'), {
                type: 'doughnut',
                data: {
                    labels: ['Free', 'Premium'],
                    datasets: [{
                        data: [data.free_users, data.premium_users],
                        backgroundColor: ['#333', '#ffd700'],
                        borderWidth: 0
                    }]
                },
                options: {
                    plugins: { legend: { labels: { color: '#fff' } } }
                }
            });
        }

        async function loadUserGrowth() {
            const res = await fetch(`/api/admin/user-growth?secret=${SECRET}`);
            const data = await res.json();

            new Chart(document.getElementById('userChart'), {
                type: 'bar',
                data: {
                    labels: data.map(d => d.date),
                    datasets: [{
                        label: 'New Users',
                        data: data.map(d => d.count),
                        backgroundColor: '#00d4ff',
                        borderRadius: 4
                    }]
                },
                options: {
                    plugins: { legend: { labels: { color: '#fff' } } },
                    scales: {
                        x: { ticks: { color: '#888' }, grid: { color: '#222' } },
                        y: { ticks: { color: '#888', stepSize: 1 }, grid: { color: '#222' } }
                    }
                }
            });
        }

        async function loadUsers() {
            const res = await fetch(`/api/admin/users?secret=${SECRET}`);
            const users = await res.json();
            const tbody = document.getElementById('usersTableBody');
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td>${u.first_name}</td>
                    <td>${u.username ? '@' + u.username : '-'}</td>
                    <td><span class="badge badge-${u.plan}">${u.plan.toUpperCase()}</span></td>
                    <td>${u.created_at}</td>
                </tr>
            `).join('');
        }

        loadStats();
        loadUserGrowth();
        loadUsers();
        setInterval(loadStats, 30000); // 30 sec mein refresh
    </script>
</body>
</html>
"""

USER_CHART_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Cost Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0f0f1a; color: #fff; font-family: 'Segoe UI', sans-serif; padding: 20px; }
        h2 { color: #00d4ff; margin-bottom: 5px; }
        p { color: #888; font-size: 13px; margin-bottom: 20px; }
        .chart-container { background: #1a1a2e; border-radius: 12px; padding: 20px; }
        .controls { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        button { background: #2a2a4a; color: #fff; border: 1px solid #444; padding: 8px 16px;
                 border-radius: 8px; cursor: pointer; font-size: 13px; }
        button:hover { background: #00d4ff; color: #000; }
        button.active { background: #00d4ff; color: #000; }
        .tip { color: #666; font-size: 11px; margin-top: 10px; }
    </style>
</head>
<body>
    <h2>AWS Cost Trend</h2>
    <p>Account: {{ account_name }} | Region: {{ region }}</p>
    <div class="chart-container">
        <div class="controls">
            <button onclick="loadChart(7)" id="btn7">7 Days</button>
            <button onclick="loadChart(30)" id="btn30" class="active">30 Days</button>
            <button onclick="loadChart(90)" id="btn90">90 Days</button>
            <button onclick="loadChart(180)" id="btn180">6 Months</button>
            <button onclick="resetZoom()">Reset Zoom</button>
        </div>
        <canvas id="costChart" height="300"></canvas>
        <p class="tip">Pinch to zoom • Drag to pan • Double-tap to reset</p>
    </div>
    <script>
        let chart = null;
        const userId = '{{ user_id }}';
        const secret = '{{ secret }}';

        async function loadChart(days) {
            document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
            document.getElementById('btn' + days).classList.add('active');

            const res = await fetch(`/api/user/chart-data?user_id=${userId}&days=${days}&secret=${secret}`);
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            const labels = data.map(d => d.date);
            const costs = data.map(d => d.cost);

            if (chart) chart.destroy();

            chart = new Chart(document.getElementById('costChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Daily Cost ($)',
                        data: costs,
                        borderColor: '#00d4ff',
                        backgroundColor: 'rgba(0, 212, 255, 0.1)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    interaction: { intersect: false, mode: 'index' },
                    plugins: {
                        legend: { labels: { color: '#fff' } },
                        tooltip: {
                            callbacks: {
                                label: ctx => `Cost: $${ctx.parsed.y.toFixed(4)}`
                            }
                        },
                        zoom: {
                            zoom: {
                                wheel: { enabled: true },
                                pinch: { enabled: true },
                                mode: 'x'
                            },
                            pan: {
                                enabled: true,
                                mode: 'x'
                            }
                        }
                    },
                    scales: {
                        x: { ticks: { color: '#888' }, grid: { color: '#222' } },
                        y: {
                            ticks: {
                                color: '#888',
                                callback: val => '$' + val.toFixed(2)
                            },
                            grid: { color: '#222' }
                        }
                    }
                }
            });
        }

        function resetZoom() {
            if (chart) chart.resetZoom();
        }

        loadChart(30);
    </script>
</body>
</html>
"""


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    return "AWS Monitor Bot Dashboard - Running"

@app.route('/admin')
def admin_dashboard():
    secret = request.args.get('secret', '')
    if secret != DASHBOARD_SECRET:
        abort(403)
    return render_template_string(ADMIN_HTML, secret=DASHBOARD_SECRET)

@app.route('/chart/<int:user_id>')
def user_chart(user_id):
    secret = request.args.get('secret', '')
    if secret != DASHBOARD_SECRET:
        # Public access allowed for user's own chart
        pass

    accounts = db.get_aws_accounts(user_id)
    if not accounts:
        return "No AWS account connected", 404

    account = accounts[0]
    creds = db.get_aws_credentials(account['account_id'])

    return render_template_string(
        USER_CHART_HTML,
        user_id=user_id,
        account_name=account['account_name'],
        region=creds['region'],
        secret=DASHBOARD_SECRET
    )

@app.route('/api/admin/stats')
def api_admin_stats():
    secret = request.args.get('secret', '')
    if secret != DASHBOARD_SECRET:
        abort(403)
    stats = db.get_admin_stats()
    return jsonify(stats)

@app.route('/api/admin/users')
def api_admin_users():
    secret = request.args.get('secret', '')
    if secret != DASHBOARD_SECRET:
        abort(403)
    users = db.get_all_users()
    result = []
    for u in users:
        result.append({
            'first_name': u['first_name'],
            'username': u['username'],
            'plan': u['plan'],
            'created_at': u['created_at'].strftime('%d-%m-%Y') if u['created_at'] else '-'
        })
    return jsonify(result)

@app.route('/api/admin/user-growth')
def api_user_growth():
    secret = request.args.get('secret', '')
    if secret != DASHBOARD_SECRET:
        abort(403)

    conn = db._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        rows = cursor.fetchall()
        data = [{'date': str(row[0]), 'count': row[1]} for row in rows]
        return jsonify(data)
    except Exception as e:
        return jsonify([])
    finally:
        cursor.close()
        db._put_conn(conn)


@app.route('/api/user/chart-data')
def api_user_chart_data():
    user_id = request.args.get('user_id', type=int)
    days = request.args.get('days', 30, type=int)

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    accounts = db.get_aws_accounts(user_id)
    if not accounts:
        return jsonify({'error': 'No AWS account connected'}), 404

    creds = db.get_aws_credentials(accounts[0]['account_id'])
    if not creds:
        return jsonify({'error': 'Credentials error'}), 500

    try:
        monitor = AWSMonitor(creds['access_key'], creds['secret_key'], creds['region'])

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        response = monitor.cost_explorer.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )

        data = []
        for day in response['ResultsByTime']:
            data.append({
                'date': day['TimePeriod']['Start'],
                'cost': round(float(day['Total']['UnblendedCost']['Amount']), 4)
            })

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Dashboard starting on http://0.0.0.0:5000")
    print(f"Admin URL: http://your-ec2-ip:5000/admin?secret={DASHBOARD_SECRET}")
    app.run(host='0.0.0.0', port=5000, debug=False)
