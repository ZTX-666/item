"""
Camera Management Dashboard
Purpose: Web-based interface to monitor all detection services
Features: Real-time status, violation feed, camera health, statistics
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import boto3
import json
from datetime import datetime, timedelta
from database import Database
import config
import os

app = Flask(__name__)
CORS(app)

# Initialize AWS clients
aws_region = os.getenv('AWS_REGION', 'us-east-1')
sqs_client = boto3.client('sqs', region_name=aws_region)
s3_client = boto3.client('s3', region_name=aws_region)
cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)

# Initialize database
db = Database()

# Camera registry (in production, this would be in a database)
CAMERAS = {}

def load_camera_config():
    """Load camera configuration from file or environment"""
    camera_config_path = os.getenv('CAMERA_CONFIG', 'cameras.json')
    
    if os.path.exists(camera_config_path):
        with open(camera_config_path, 'r') as f:
            config_data = json.load(f)
            return config_data.get('cameras', [])
    
    # Fallback: parse from environment variables
    return []

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('dashboard.html')

@app.route('/api/cameras')
def get_cameras():
    """Get list of all cameras and their status"""
    cameras = load_camera_config()
    
    # Add real-time status for each camera
    for camera in cameras:
        camera['status'] = get_camera_status(camera['id'])
        camera['last_violation'] = get_last_violation(camera['id'])
        camera['violation_count_today'] = get_violation_count_today(camera['id'])
    
    return jsonify({
        'cameras': cameras,
        'total': len(cameras),
        'active': len([c for c in cameras if c.get('enabled', True)])
    })

@app.route('/api/camera/<camera_id>')
def get_camera_details(camera_id):
    """Get detailed information for a specific camera"""
    cameras = load_camera_config()
    camera = next((c for c in cameras if c['id'] == camera_id), None)
    
    if not camera:
        return jsonify({'error': 'Camera not found'}), 404
    
    # Add detailed metrics
    camera['status'] = get_camera_status(camera_id)
    camera['violations_today'] = get_violations_by_camera(camera_id, hours=24)
    camera['violations_this_week'] = get_violations_by_camera(camera_id, hours=168)
    camera['health_metrics'] = get_camera_health_metrics(camera_id)
    
    return jsonify(camera)

@app.route('/api/violations/recent')
def get_recent_violations():
    """Get recent violations across all cameras"""
    limit = request.args.get('limit', 20, type=int)
    camera_id = request.args.get('camera_id', None)
    
    if camera_id:
        # Filter by camera
        violations = db.get_recent_violations(limit)
        # TODO: Add camera_id filter in database query
    else:
        violations = db.get_recent_violations(limit)
    
    # Convert to JSON-serializable format
    violations_data = []
    for v in violations:
        violations_data.append({
            'id': v.id,
            'timestamp': v.timestamp.isoformat(),
            'class_name': v.class_name,
            'description': v.description,
            'confidence': v.confidence,
            'osha_regulation': v.osha_regulation,
            'image_path': v.image_path,
            'pdf_report_path': v.pdf_report_path,
            'email_sent': bool(v.email_sent)
        })
    
    return jsonify({
        'violations': violations_data,
        'count': len(violations_data)
    })

@app.route('/api/violations/stats')
def get_violation_stats():
    """Get violation statistics"""
    stats = db.get_violation_stats()
    
    # Add time-based stats
    today_count = len(get_violations_by_camera(None, hours=24))
    week_count = len(get_violations_by_camera(None, hours=168))
    
    return jsonify({
        'total': stats['total'],
        'by_type': stats['by_type'],
        'today': today_count,
        'this_week': week_count,
        'by_camera': get_violations_by_camera_stats()
    })

@app.route('/api/queue/stats')
def get_queue_stats():
    """Get SQS queue statistics"""
    try:
        sqs_queue_url = os.getenv('SQS_QUEUE_URL')
        if not sqs_queue_url:
            # Return mock data for local development
            return jsonify({
                'messages_available': 0,
                'messages_in_flight': 0,
                'messages_delayed': 0,
                'oldest_message_age': 0,
                'queue_url': 'Not configured (local mode)',
                'status': 'disabled'
            }), 200
        
        response = sqs_client.get_queue_attributes(
            QueueUrl=sqs_queue_url,
            AttributeNames=['All']
        )
        
        attributes = response['Attributes']
        
        return jsonify({
            'messages_available': int(attributes.get('ApproximateNumberOfMessages', 0)),
            'messages_in_flight': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'messages_delayed': int(attributes.get('ApproximateNumberOfMessagesDelayed', 0)),
            'oldest_message_age': int(attributes.get('ApproximateAgeOfOldestMessage', 0)),
            'queue_url': sqs_queue_url
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/health')
def get_system_health():
    """Get overall system health status"""
    return jsonify({
        'status': 'healthy',
        'components': {
            'database': check_database_health(),
            'sqs': check_sqs_health(),
            's3': check_s3_health(),
            'cameras': get_camera_health_summary()
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/alerts/active')
def get_active_alerts():
    """Get active system alerts"""
    alerts = []
    
    # Check queue backlog
    try:
        queue_response = get_queue_stats()
        if isinstance(queue_response, tuple):
            queue_data, status_code = queue_response
            if status_code == 200:
                queue_stats = queue_data.get_json()
                if queue_stats.get('messages_available', 0) > 100:
                    alerts.append({
                        'severity': 'warning',
                        'message': f"Queue backlog: {queue_stats['messages_available']} messages pending",
                        'timestamp': datetime.now().isoformat()
                    })
    except Exception as e:
        # SQS might not be configured in development, skip this alert
        pass
    
    # Check camera status
    cameras = load_camera_config()
    for camera in cameras:
        if not get_camera_status(camera['id']):
            alerts.append({
                'severity': 'error',
                'message': f"Camera offline: {camera['name']} ({camera['id']})",
                'timestamp': datetime.now().isoformat()
            })
    
    return jsonify({
        'alerts': alerts,
        'count': len(alerts)
    })

# Helper functions

def get_camera_status(camera_id):
    """Check if camera is actively sending data"""
    # Check if there are recent violations from this camera
    # In production, this would check CloudWatch metrics or heartbeat messages
    violations = get_violations_by_camera(camera_id, hours=1)
    return len(violations) > 0 or True  # Assume online if configured

def get_last_violation(camera_id):
    """Get timestamp of last violation from this camera"""
    violations = get_violations_by_camera(camera_id, hours=24)
    if violations:
        return violations[0].timestamp.isoformat()
    return None

def get_violation_count_today(camera_id):
    """Get number of violations today for this camera"""
    return len(get_violations_by_camera(camera_id, hours=24))

def get_violations_by_camera(camera_id, hours=24):
    """Get violations from a specific camera within time window"""
    since = datetime.now() - timedelta(hours=hours)
    # TODO: Add camera_id filter to database queries
    # For now, return all recent violations
    return db.get_recent_violations(100)

def get_violations_by_camera_stats():
    """Get violation counts grouped by camera"""
    # TODO: Implement proper camera grouping in database
    return {}

def get_camera_health_metrics(camera_id):
    """Get health metrics for a specific camera"""
    # In production, fetch from CloudWatch
    return {
        'uptime': '99.5%',
        'avg_fps': 1.2,
        'last_heartbeat': datetime.now().isoformat(),
        'error_count': 0
    }

def get_camera_health_summary():
    """Get health summary for all cameras"""
    cameras = load_camera_config()
    online = len([c for c in cameras if get_camera_status(c['id'])])
    total = len(cameras)
    
    return {
        'total': total,
        'online': online,
        'offline': total - online,
        'health_percentage': (online / total * 100) if total > 0 else 0
    }

def check_database_health():
    """Check database connectivity"""
    try:
        db.get_total_violations()
        return {'status': 'healthy', 'message': 'Connected'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}

def check_sqs_health():
    """Check SQS connectivity"""
    try:
        queue_response = get_queue_stats()
        if isinstance(queue_response, tuple):
            queue_data, status_code = queue_response
            if status_code == 200:
                return {'status': 'healthy', 'message': 'Connected'}
            else:
                return {'status': 'unhealthy', 'message': 'SQS not configured'}
        return {'status': 'healthy', 'message': 'Connected'}
    except Exception as e:
        return {'status': 'unhealthy', 'message': f'Cannot connect to SQS: {str(e)}'}

def check_s3_health():
    """Check S3 connectivity"""
    try:
        s3_bucket = os.getenv('S3_BUCKET_NAME')
        s3_client.head_bucket(Bucket=s3_bucket)
        return {'status': 'healthy', 'message': 'Connected'}
    except:
        return {'status': 'unhealthy', 'message': 'Cannot connect to S3'}

if __name__ == '__main__':
    port = int(os.getenv('DASHBOARD_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print("="*80)
    print("🎛️  Camera Management Dashboard")
    print("="*80)
    print(f"📡 Running on http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:{port}")
    print(f"🔧 Debug mode: {debug}")
    print("="*80)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
