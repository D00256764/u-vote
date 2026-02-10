"""
Voter Service - Handles voter list uploads and token generation
"""
from flask import Flask, request, jsonify
import sys
import os
import csv
from io import StringIO

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
from security import generate_voting_token, generate_token_expiry

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'voter'}), 200

@app.route('/elections/<int:election_id>/voters/upload', methods=['POST'])
def upload_voters(election_id):
    """Upload voter list from CSV"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Read CSV
        csv_data = file.read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_data))
        
        # Validate CSV has email column
        if 'email' not in csv_reader.fieldnames:
            return jsonify({'error': 'CSV must have "email" column'}), 400
        
        voters_added = 0
        voters_skipped = 0
        
        with db_pool.get_cursor() as cursor:
            for row in csv_reader:
                email = row.get('email', '').strip()
                if not email:
                    continue
                
                try:
                    cursor.execute(
                        "INSERT INTO voters (election_id, email) VALUES (%s, %s)",
                        (election_id, email)
                    )
                    voters_added += 1
                except Exception:
                    # Skip duplicates
                    voters_skipped += 1
                    continue
        
        return jsonify({
            'message': 'Voters uploaded successfully',
            'voters_added': voters_added,
            'voters_skipped': voters_skipped
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/voters', methods=['POST'])
def add_voter(election_id):
    """Add a single voter"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        with db_pool.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO voters (election_id, email) VALUES (%s, %s) RETURNING id",
                (election_id, email)
            )
            voter_id = cursor.fetchone()[0]
        
        return jsonify({
            'message': 'Voter added successfully',
            'voter_id': voter_id
        }), 201
        
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            return jsonify({'error': 'Voter already exists for this election'}), 409
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/voters', methods=['GET'])
def get_voters(election_id):
    """Get all voters for an election"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT v.id, v.email, v.created_at,
                       EXISTS(SELECT 1 FROM voting_tokens WHERE voter_id = v.id) as has_token
                FROM voters v
                WHERE v.election_id = %s
                ORDER BY v.created_at DESC
                """,
                (election_id,)
            )
            voters = cursor.fetchall()
        
        return jsonify({
            'voters': [
                {
                    'id': v[0],
                    'email': v[1],
                    'created_at': v[2].isoformat(),
                    'has_token': v[3]
                }
                for v in voters
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/tokens/generate', methods=['POST'])
def generate_tokens(election_id):
    """Generate voting tokens for all voters in an election"""
    try:
        data = request.get_json() or {}
        expiry_hours = data.get('expiry_hours', 168)  # Default 7 days
        
        with db_pool.get_cursor() as cursor:
            # Get all voters without tokens
            cursor.execute(
                """
                SELECT v.id FROM voters v
                WHERE v.election_id = %s
                AND NOT EXISTS (
                    SELECT 1 FROM voting_tokens vt 
                    WHERE vt.voter_id = v.id 
                    AND vt.is_used = FALSE
                )
                """,
                (election_id,)
            )
            voters = cursor.fetchall()
            
            tokens_generated = 0
            generated_tokens = []
            
            for voter in voters:
                voter_id = voter[0]
                token = generate_voting_token()
                expires_at = generate_token_expiry(expiry_hours)
                
                cursor.execute(
                    """
                    INSERT INTO voting_tokens (token, voter_id, election_id, expires_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (token, voter_id, election_id, expires_at)
                )
                
                # Get voter email
                cursor.execute("SELECT email FROM voters WHERE id = %s", (voter_id,))
                email = cursor.fetchone()[0]
                
                generated_tokens.append({
                    'email': email,
                    'token': token,
                    'expires_at': expires_at.isoformat()
                })
                tokens_generated += 1
        
        return jsonify({
            'message': 'Tokens generated successfully',
            'tokens_generated': tokens_generated,
            'tokens': generated_tokens
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tokens/<token>/validate', methods=['GET'])
def validate_token(token):
    """Validate a voting token"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT vt.id, vt.voter_id, vt.election_id, vt.is_used, 
                       vt.expires_at, e.status
                FROM voting_tokens vt
                JOIN elections e ON e.id = vt.election_id
                WHERE vt.token = %s
                """,
                (token,)
            )
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'valid': False, 'error': 'Invalid token'}), 404
        
        token_id, voter_id, election_id, is_used, expires_at, election_status = result
        
        # Check if token is used
        if is_used:
            return jsonify({'valid': False, 'error': 'Token already used'}), 400
        
        # Check if token is expired
        from datetime import datetime
        if datetime.now() > expires_at:
            return jsonify({'valid': False, 'error': 'Token expired'}), 400
        
        # Check if election is open
        if election_status != 'open':
            return jsonify({'valid': False, 'error': 'Election is not open'}), 400
        
        return jsonify({
            'valid': True,
            'election_id': election_id,
            'voter_id': voter_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
