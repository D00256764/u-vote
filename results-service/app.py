"""
Results Service - Handles result tallying and display after election closes
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

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'results'}), 200

@app.route('/elections/<int:election_id>/results', methods=['GET'])
def get_results(election_id):
    """Get election results (read-only, only after election closes)"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            # Check election status
            cursor.execute(
                "SELECT id, title, status, closed_at FROM elections WHERE id = %s",
                (election_id,)
            )
            election = cursor.fetchone()
            
            if not election:
                return jsonify({'error': 'Election not found'}), 404
            
            election_id, title, status, closed_at = election
            
            if status != 'closed':
                return jsonify({
                    'error': 'Results not available',
                    'message': 'Election must be closed to view results'
                }), 403
            
            # Get vote counts by option
            cursor.execute(
                """
                SELECT 
                    eo.id,
                    eo.option_text,
                    eo.display_order,
                    COUNT(v.id) as vote_count
                FROM election_options eo
                LEFT JOIN votes v ON v.option_id = eo.id
                WHERE eo.election_id = %s
                GROUP BY eo.id, eo.option_text, eo.display_order
                ORDER BY vote_count DESC, eo.display_order
                """,
                (election_id,)
            )
            results = cursor.fetchall()
            
            # Get total votes
            cursor.execute(
                "SELECT COUNT(*) FROM votes WHERE election_id = %s",
                (election_id,)
            )
            total_votes = cursor.fetchone()[0]
            
            # Get total eligible voters
            cursor.execute(
                "SELECT COUNT(*) FROM voters WHERE election_id = %s",
                (election_id,)
            )
            total_voters = cursor.fetchone()[0]
        
        # Calculate percentages
        results_data = []
        for result in results:
            option_id, option_text, display_order, vote_count = result
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            
            results_data.append({
                'option_id': option_id,
                'option_text': option_text,
                'vote_count': vote_count,
                'percentage': round(percentage, 2)
            })
        
        return jsonify({
            'election': {
                'id': election_id,
                'title': title,
                'status': status,
                'closed_at': closed_at.isoformat() if closed_at else None
            },
            'summary': {
                'total_votes': total_votes,
                'total_voters': total_voters,
                'turnout_percentage': round(total_votes / total_voters * 100, 2) if total_voters > 0 else 0
            },
            'results': results_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/audit', methods=['GET'])
def get_audit_trail(election_id):
    """Get audit information (vote hashes, hash chain verification)"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            # Check election exists and is closed
            cursor.execute(
                "SELECT status FROM elections WHERE id = %s",
                (election_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'error': 'Election not found'}), 404
            
            if result[0] != 'closed':
                return jsonify({'error': 'Audit trail only available for closed elections'}), 403
            
            # Get all votes with hashes
            cursor.execute(
                """
                SELECT id, vote_hash, previous_hash, cast_at
                FROM votes
                WHERE election_id = %s
                ORDER BY id ASC
                """,
                (election_id,)
            )
            votes = cursor.fetchall()
        
        audit_data = []
        hash_chain_valid = True
        
        for i, vote in enumerate(votes):
            vote_id, vote_hash, previous_hash, cast_at = vote
            
            # Verify hash chain
            if i > 0:
                expected_previous_hash = votes[i-1][1]  # Previous vote's hash
                if previous_hash != expected_previous_hash:
                    hash_chain_valid = False
            
            audit_data.append({
                'vote_id': vote_id,
                'vote_hash': vote_hash,
                'previous_hash': previous_hash,
                'cast_at': cast_at.isoformat(),
                'sequence': i + 1
            })
        
        return jsonify({
            'election_id': election_id,
            'total_votes': len(votes),
            'hash_chain_valid': hash_chain_valid,
            'audit_trail': audit_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/elections/<int:election_id>/statistics', methods=['GET'])
def get_statistics(election_id):
    """Get detailed statistics about the election"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            # Basic election info
            cursor.execute(
                """
                SELECT title, status, created_at, opened_at, closed_at
                FROM elections WHERE id = %s
                """,
                (election_id,)
            )
            election = cursor.fetchone()
            
            if not election:
                return jsonify({'error': 'Election not found'}), 404
            
            title, status, created_at, opened_at, closed_at = election
            
            # Vote statistics
            cursor.execute(
                "SELECT COUNT(*) FROM votes WHERE election_id = %s",
                (election_id,)
            )
            total_votes = cursor.fetchone()[0]
            
            # Voter statistics
            cursor.execute(
                "SELECT COUNT(*) FROM voters WHERE election_id = %s",
                (election_id,)
            )
            total_voters = cursor.fetchone()[0]
            
            # Token statistics
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_tokens,
                    SUM(CASE WHEN is_used THEN 1 ELSE 0 END) as used_tokens
                FROM voting_tokens
                WHERE election_id = %s
                """,
                (election_id,)
            )
            token_stats = cursor.fetchone()
            total_tokens, used_tokens = token_stats
            
            # Time-based vote distribution (if closed)
            vote_timeline = []
            if status == 'closed':
                cursor.execute(
                    """
                    SELECT 
                        DATE_TRUNC('hour', cast_at) as hour,
                        COUNT(*) as vote_count
                    FROM votes
                    WHERE election_id = %s
                    GROUP BY hour
                    ORDER BY hour
                    """,
                    (election_id,)
                )
                timeline_data = cursor.fetchall()
                vote_timeline = [
                    {'hour': row[0].isoformat(), 'count': row[1]}
                    for row in timeline_data
                ]
        
        return jsonify({
            'election': {
                'title': title,
                'status': status,
                'created_at': created_at.isoformat(),
                'opened_at': opened_at.isoformat() if opened_at else None,
                'closed_at': closed_at.isoformat() if closed_at else None
            },
            'statistics': {
                'total_voters': total_voters,
                'total_tokens': total_tokens or 0,
                'used_tokens': used_tokens or 0,
                'total_votes': total_votes,
                'turnout_rate': round(total_votes / total_voters * 100, 2) if total_voters > 0 else 0
            },
            'vote_timeline': vote_timeline
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)
