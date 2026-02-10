"""
Frontend Service - Web interface using Flask and Jinja templates
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import sys
import os

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', 'your-secret-key-change-in-production')

# Service URLs
AUTH_SERVICE = os.getenv('AUTH_SERVICE_URL', 'http://auth-service:5001')
VOTER_SERVICE = os.getenv('VOTER_SERVICE_URL', 'http://voter-service:5002')
VOTING_SERVICE = os.getenv('VOTING_SERVICE_URL', 'http://voting-service:5003')
RESULTS_SERVICE = os.getenv('RESULTS_SERVICE_URL', 'http://results-service:5004')

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

# Authentication decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'token' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Organizer registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        try:
            response = requests.post(f'{AUTH_SERVICE}/register', json={
                'email': email,
                'password': password
            })
            
            if response.status_code == 201:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash(response.json().get('error', 'Registration failed'), 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Organizer login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            response = requests.post(f'{AUTH_SERVICE}/login', json={
                'email': email,
                'password': password
            })
            
            if response.status_code == 200:
                data = response.json()
                session['token'] = data['token']
                session['organizer_id'] = data['organizer_id']
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash(response.json().get('error', 'Login failed'), 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Organizer dashboard"""
    try:
        organizer_id = session.get('organizer_id')
        
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                """
                SELECT id, title, status, created_at, opened_at, closed_at
                FROM elections
                WHERE organizer_id = %s
                ORDER BY created_at DESC
                """,
                (organizer_id,)
            )
            elections = cursor.fetchall()
        
        elections_data = [
            {
                'id': e[0],
                'title': e[1],
                'status': e[2],
                'created_at': e[3],
                'opened_at': e[4],
                'closed_at': e[5]
            }
            for e in elections
        ]
        
        return render_template('dashboard.html', elections=elections_data)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/elections/create', methods=['GET', 'POST'])
@login_required
def create_election():
    """Create a new election"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        options = request.form.getlist('options[]')
        
        try:
            organizer_id = session.get('organizer_id')
            
            with db_pool.get_cursor() as cursor:
                # Create election
                cursor.execute(
                    """
                    INSERT INTO elections (organizer_id, title, description, status)
                    VALUES (%s, %s, %s, 'draft')
                    RETURNING id
                    """,
                    (organizer_id, title, description)
                )
                election_id = cursor.fetchone()[0]
                
                # Add options
                for i, option_text in enumerate(options):
                    if option_text.strip():
                        cursor.execute(
                            """
                            INSERT INTO election_options (election_id, option_text, display_order)
                            VALUES (%s, %s, %s)
                            """,
                            (election_id, option_text.strip(), i)
                        )
            
            flash('Election created successfully!', 'success')
            return redirect(url_for('election_detail', election_id=election_id))
        except Exception as e:
            flash(f'Error creating election: {str(e)}', 'danger')
    
    return render_template('create_election.html')

@app.route('/elections/<int:election_id>')
@login_required
def election_detail(election_id):
    """Election details"""
    try:
        with db_pool.get_cursor(commit=False) as cursor:
            # Get election
            cursor.execute(
                """
                SELECT e.id, e.title, e.description, e.status, e.created_at, 
                       e.opened_at, e.closed_at, e.organizer_id
                FROM elections e
                WHERE e.id = %s
                """,
                (election_id,)
            )
            election = cursor.fetchone()
            
            if not election or election[7] != session.get('organizer_id'):
                flash('Election not found or access denied', 'danger')
                return redirect(url_for('dashboard'))
            
            # Get options
            cursor.execute(
                """
                SELECT id, option_text, display_order
                FROM election_options
                WHERE election_id = %s
                ORDER BY display_order
                """,
                (election_id,)
            )
            options = cursor.fetchall()
            
            # Get voter count
            cursor.execute(
                "SELECT COUNT(*) FROM voters WHERE election_id = %s",
                (election_id,)
            )
            voter_count = cursor.fetchone()[0]
            
            # Get vote count
            cursor.execute(
                "SELECT COUNT(*) FROM votes WHERE election_id = %s",
                (election_id,)
            )
            vote_count = cursor.fetchone()[0]
        
        election_data = {
            'id': election[0],
            'title': election[1],
            'description': election[2],
            'status': election[3],
            'created_at': election[4],
            'opened_at': election[5],
            'closed_at': election[6],
            'voter_count': voter_count,
            'vote_count': vote_count
        }
        
        options_data = [
            {'id': o[0], 'text': o[1], 'order': o[2]}
            for o in options
        ]
        
        return render_template('election_detail.html', 
                             election=election_data, 
                             options=options_data)
    except Exception as e:
        flash(f'Error loading election: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/elections/<int:election_id>/open', methods=['POST'])
@login_required
def open_election(election_id):
    """Open an election"""
    try:
        with db_pool.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE elections 
                SET status = 'open', opened_at = CURRENT_TIMESTAMP
                WHERE id = %s AND organizer_id = %s AND status = 'draft'
                """,
                (election_id, session.get('organizer_id'))
            )
        flash('Election opened successfully!', 'success')
    except Exception as e:
        flash(f'Error opening election: {str(e)}', 'danger')
    
    return redirect(url_for('election_detail', election_id=election_id))

@app.route('/elections/<int:election_id>/close', methods=['POST'])
@login_required
def close_election(election_id):
    """Close an election"""
    try:
        with db_pool.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE elections 
                SET status = 'closed', closed_at = CURRENT_TIMESTAMP
                WHERE id = %s AND organizer_id = %s AND status = 'open'
                """,
                (election_id, session.get('organizer_id'))
            )
        flash('Election closed successfully!', 'success')
    except Exception as e:
        flash(f'Error closing election: {str(e)}', 'danger')
    
    return redirect(url_for('election_detail', election_id=election_id))

@app.route('/elections/<int:election_id>/voters')
@login_required
def manage_voters(election_id):
    """Manage voters"""
    try:
        response = requests.get(f'{VOTER_SERVICE}/elections/{election_id}/voters')
        voters = response.json().get('voters', [])
        
        with db_pool.get_cursor(commit=False) as cursor:
            cursor.execute(
                "SELECT title, status FROM elections WHERE id = %s AND organizer_id = %s",
                (election_id, session.get('organizer_id'))
            )
            election = cursor.fetchone()
        
        if not election:
            flash('Election not found', 'danger')
            return redirect(url_for('dashboard'))
        
        return render_template('manage_voters.html', 
                             election_id=election_id,
                             election_title=election[0],
                             voters=voters)
    except Exception as e:
        flash(f'Error loading voters: {str(e)}', 'danger')
        return redirect(url_for('election_detail', election_id=election_id))

@app.route('/elections/<int:election_id>/voters/upload', methods=['POST'])
@login_required
def upload_voters(election_id):
    """Upload voters from CSV"""
    if 'file' not in request.files:
        flash('No file provided', 'danger')
        return redirect(url_for('manage_voters', election_id=election_id))
    
    file = request.files['file']
    
    try:
        response = requests.post(
            f'{VOTER_SERVICE}/elections/{election_id}/voters/upload',
            files={'file': (file.filename, file.stream, file.mimetype)}
        )
        
        if response.status_code == 201:
            data = response.json()
            flash(f"Uploaded {data['voters_added']} voters (skipped {data['voters_skipped']} duplicates)", 'success')
        else:
            flash(response.json().get('error', 'Upload failed'), 'danger')
    except Exception as e:
        flash(f'Error uploading voters: {str(e)}', 'danger')
    
    return redirect(url_for('manage_voters', election_id=election_id))

@app.route('/elections/<int:election_id>/tokens/generate', methods=['POST'])
@login_required
def generate_tokens(election_id):
    """Generate voting tokens"""
    try:
        response = requests.post(f'{VOTER_SERVICE}/elections/{election_id}/tokens/generate')
        
        if response.status_code == 201:
            data = response.json()
            flash(f"Generated {data['tokens_generated']} tokens", 'success')
        else:
            flash(response.json().get('error', 'Token generation failed'), 'danger')
    except Exception as e:
        flash(f'Error generating tokens: {str(e)}', 'danger')
    
    return redirect(url_for('manage_voters', election_id=election_id))

@app.route('/elections/<int:election_id>/results')
@login_required
def view_results(election_id):
    """View election results"""
    try:
        response = requests.get(f'{RESULTS_SERVICE}/elections/{election_id}/results')
        
        if response.status_code == 200:
            data = response.json()
            return render_template('results.html', data=data)
        else:
            flash(response.json().get('error', 'Could not load results'), 'warning')
            return redirect(url_for('election_detail', election_id=election_id))
    except Exception as e:
        flash(f'Error loading results: {str(e)}', 'danger')
        return redirect(url_for('election_detail', election_id=election_id))

@app.route('/vote/<token>')
def vote_page(token):
    """Voting page for voters"""
    try:
        # Validate token
        response = requests.get(f'{VOTER_SERVICE}/tokens/{token}/validate')
        
        if response.status_code != 200:
            error = response.json().get('error', 'Invalid token')
            return render_template('vote_error.html', error=error)
        
        token_data = response.json()
        election_id = token_data['election_id']
        
        # Get ballot
        ballot_response = requests.get(
            f'{VOTING_SERVICE}/elections/{election_id}/ballot',
            headers={'X-Voting-Token': token}
        )
        
        if ballot_response.status_code != 200:
            error = ballot_response.json().get('error', 'Could not load ballot')
            return render_template('vote_error.html', error=error)
        
        ballot_data = ballot_response.json()
        
        return render_template('vote.html', 
                             token=token,
                             election=ballot_data['election'],
                             options=ballot_data['options'])
    except Exception as e:
        return render_template('vote_error.html', error=str(e))

@app.route('/vote/submit', methods=['POST'])
def submit_vote():
    """Submit a vote"""
    token = request.form.get('token')
    option_id = request.form.get('option_id')
    
    try:
        # Get election ID first
        response = requests.get(f'{VOTER_SERVICE}/tokens/{token}/validate')
        if response.status_code != 200:
            flash('Invalid token', 'danger')
            return redirect(url_for('index'))
        
        election_id = response.json()['election_id']
        
        # Submit vote
        vote_response = requests.post(
            f'{VOTING_SERVICE}/elections/{election_id}/vote',
            headers={'X-Voting-Token': token},
            json={'option_id': int(option_id)}
        )
        
        if vote_response.status_code == 201:
            data = vote_response.json()
            return render_template('vote_success.html', 
                                 vote_hash=data['vote_hash'])
        else:
            error = vote_response.json().get('error', 'Vote submission failed')
            return render_template('vote_error.html', error=error)
    except Exception as e:
        return render_template('vote_error.html', error=str(e))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
