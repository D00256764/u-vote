"""
Voting Service - Handles secure vote casting
"""
from flask import Flask, request, jsonify
import sys
import os
from datetime import datetime

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

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'voting'}), 200

@app.route('/elections/<int:election_id>/ballot', methods=['GET'])
def get_ballot(election_id):
    """Get election ballot (options) - requires valid token"""
    try:
        token = request.headers.get('X-Voting-Token')
        
        if not token:
            return jsonify({'error': 'Voting token required'}), 401
        
        with db_pool.get_cursor(commit=False) as cursor:
            # Validate token
            cursor.execute(
                """
                SELECT vt.id, vt.is_used, vt.expires_at, e.status
                FROM voting_tokens vt
                JOIN elections e ON e.id = vt.election_id
                WHERE vt.token = %s AND vt.election_id = %s
                """,
                (token, election_id)
            )
            token_result = cursor.fetchone()
            
            if not token_result:
                return jsonify({'error': 'Invalid token'}), 401
            
            token_id, is_used, expires_at, election_status = token_result
            
            if is_used:
                return jsonify({'error': 'Token already used'}), 400
            
            if datetime.now() > expires_at:
                return jsonify({'error': 'Token expired'}), 400
            
            if election_status != 'open':
                return jsonify({'error': 'Election is not open'}), 400
            
            # Get election details and options
            cursor.execute(
                """
                SELECT e.id, e.title, e.description
                FROM elections e
                WHERE e.id = %s
                """,
                (election_id,)
            )
            election = cursor.fetchone()
            
            cursor.execute(
                """
                SELECT id, option_text, display_order
                FROM election_options
                WHERE election_id = %s
                ORDER BY display_order, id
                """,
                (election_id,)
            )
            options = cursor.fetchall()
        
        return jsonify({
            'election': {
                'id': election[0],
                'title': election[1],
                'description': election[2]
            },
            'options': [
                {
                    'id': opt[0],
                    'text': opt[1],
                    'order': opt[2]
                }
                for opt in options
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/vote', methods=['POST'])
def cast_vote(election_id):
    """Cast a vote - single use, immutable"""
    try:
        token = request.headers.get('X-Voting-Token')
        data = request.get_json()
        option_id = data.get('option_id')
        
        if not token:
            return jsonify({'error': 'Voting token required'}), 401
        
        if not option_id:
            return jsonify({'error': 'Option ID required'}), 400
        
        with db_pool.get_cursor() as cursor:
            # Validate token and get details
            cursor.execute(
                """
                SELECT vt.id, vt.voter_id, vt.is_used, vt.expires_at, e.status
                FROM voting_tokens vt
                JOIN elections e ON e.id = vt.election_id
                WHERE vt.token = %s AND vt.election_id = %s
                FOR UPDATE
                """,
                (token, election_id)
            )
            token_result = cursor.fetchone()
            
            if not token_result:
                return jsonify({'error': 'Invalid token'}), 401
            
            token_id, voter_id, is_used, expires_at, election_status = token_result
            
            # Validation checks
            if is_used:
                return jsonify({'error': 'Vote already cast with this token'}), 400
            
            if datetime.now() > expires_at:
                return jsonify({'error': 'Token expired'}), 400
            
            if election_status != 'open':
                return jsonify({'error': 'Election is not open'}), 400
            
            # Validate option belongs to this election
            cursor.execute(
                "SELECT id FROM election_options WHERE id = %s AND election_id = %s",
                (option_id, election_id)
            )
            if not cursor.fetchone():
                return jsonify({'error': 'Invalid option for this election'}), 400
            
            # Get previous vote hash for chain (optional)
            cursor.execute(
                """
                SELECT vote_hash FROM votes 
                WHERE election_id = %s 
                ORDER BY id DESC LIMIT 1
                """,
                (election_id,)
            )
            previous_result = cursor.fetchone()
            previous_hash = previous_result[0] if previous_result else None
            
            # Insert vote (hash is auto-generated by trigger)
            cursor.execute(
                """
                INSERT INTO votes (election_id, option_id, previous_hash)
                VALUES (%s, %s, %s)
                RETURNING id, vote_hash
                """,
                (election_id, option_id, previous_hash)
            )
            vote_id, vote_hash = cursor.fetchone()
            
            # Mark token as used
            cursor.execute(
                """
                UPDATE voting_tokens 
                SET is_used = TRUE, used_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (token_id,)
            )
        
        return jsonify({
            'message': 'Vote cast successfully',
            'vote_id': vote_id,
            'vote_hash': vote_hash
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/votes/<int:vote_id>/verify', methods=['GET'])
def verify_vote(vote_id):
    """Verify a vote exists (public verification)"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT id, election_id, vote_hash, cast_at
                FROM votes
                WHERE id = %s
                """,
                (vote_id,)
            )
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'exists': False}), 404
        
        return jsonify({
            'exists': True,
            'vote_id': result[0],
            'election_id': result[1],
            'vote_hash': result[2],
            'cast_at': result[3].isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
