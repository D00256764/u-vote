"""
Auth Service - Handles organizer authentication
"""
from flask import Flask, request, jsonify
import sys
import os

# Add shared directory to path. Support both local dev layout (service dir) and container layout (/app/shared).
current_dir = os.path.dirname(__file__)
possible_shared_paths = [
    os.path.join(current_dir, '..', 'shared'),
    os.path.join(current_dir, 'shared'),
    '/app/shared'
]
for p in possible_shared_paths:
    p_abs = os.path.abspath(p)
    if os.path.isdir(p_abs):
        sys.path.insert(0, p_abs)
        break

from database import db_pool
from security import hash_password, verify_password
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'auth'}), 200

@app.route('/register', methods=['POST'])
def register():
    """Register a new organizer"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert into database
        with db_pool.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO organizers (email, password_hash) VALUES (%s, %s) RETURNING id",
                (email, password_hash)
            )
            organizer_id = cursor.fetchone()[0]
        
        return jsonify({
            'message': 'Organizer registered successfully',
            'organizer_id': organizer_id
        }), 201
        
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            return jsonify({'error': 'Email already registered'}), 409
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    """Authenticate organizer and return JWT token"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Fetch organizer
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT id, password_hash FROM organizers WHERE email = %s",
                (email,)
            )
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        organizer_id, password_hash = result
        
        # Verify password
        if not verify_password(password, password_hash):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'organizer_id': organizer_id,
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'organizer_id': organizer_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify_token():
    """Verify JWT token"""
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token required'}), 400
        
        # Decode and verify token
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        
        return jsonify({
            'valid': True,
            'organizer_id': payload['organizer_id'],
            'email': payload['email']
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired', 'valid': False}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token', 'valid': False}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
