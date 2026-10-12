from collections import Counter

from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'apexserve_secret_key_change_in_production'

# Demo-only credentials; use a persistent user store and hashed passwords in production.
DEMO_ACCOUNTS = {
    'employee': {'password': 'employee123', 'role': 'user', 'display_name': 'Employee'},
    'agent': {'password': 'admin123', 'role': 'admin', 'display_name': 'IT Agent'},
}

# In-memory database storing tickets with initial sample comments
tickets_db = [
    {
        'id': 12,
        'title': 'dsdsd',
        'description': 'sdsdsdsd...',
        'category': 'Software',
        'priority': 'Critical',
        'status': 'Open',
        'feedback': [],
        'comments': [
            {'author': 'System', 'role': 'system', 'text': 'Ticket created and queued for agent review.'},
            {'author': 'User', 'role': 'user', 'text': 'Any update on this issue?'}
        ]
    }
]

next_ticket_id = 13

@app.route('/', methods=['GET', 'POST'])
def index():
    global next_ticket_id

    # Handle ticket creation
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        priority = request.form.get('priority')
        description = request.form.get('description')

        if title and description:
            new_ticket = {
                'id': next_ticket_id,
                'title': title,
                'description': description,
                'category': category,
                'priority': priority,
                'status': 'Open',
                'feedback': [],
                'comments': [
                    {'author': 'System', 'role': 'system', 'text': 'Ticket submitted successfully.'}
                ]
            }
            tickets_db.append(new_ticket)
            next_ticket_id += 1
            return redirect(url_for('index'))

    role = session.get('role', 'guest')
    error = session.pop('error', None)
    view = request.args.get('view', 'overview')
    if view not in {'overview', 'queue', 'analytics'}:
        view = 'overview'

    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    filtered_tickets = tickets_db
    if status_filter.casefold() != 'all':
        filtered_tickets = [
            ticket for ticket in filtered_tickets
            if ticket.get('status', '').casefold() == status_filter.casefold()
        ]
    if priority_filter.casefold() != 'all':
        filtered_tickets = [
            ticket for ticket in filtered_tickets
            if ticket.get('priority', '').casefold() == priority_filter.casefold()
        ]
    if search_query:
        query = search_query.casefold()
        filtered_tickets = [
            ticket for ticket in filtered_tickets
            if query in ' '.join(str(ticket.get(field, '')) for field in (
                'id', 'title', 'description', 'category', 'priority', 'status'
            )).casefold()
        ]

    total_tickets = len(tickets_db)
    resolved_count = sum(
        ticket.get('status', '').casefold() == 'resolved'
        for ticket in tickets_db
    )
    open_count = sum(
        ticket.get('status', '').casefold() == 'open'
        for ticket in tickets_db
    )
    in_progress_count = sum(
        ticket.get('status', '').casefold() == 'in progress'
        for ticket in tickets_db
    )
    ratings = [
        feedback['rating']
        for ticket in tickets_db
        for feedback in ticket.get('feedback', [])
        if isinstance(feedback.get('rating'), int)
    ]
    category_breakdown = [
        {'label': label, 'count': count}
        for label, count in sorted(Counter(
            ticket.get('category', 'Uncategorized') for ticket in tickets_db
        ).items())
    ]
    priority_breakdown = [
        {'label': label, 'count': count}
        for label, count in sorted(Counter(
            ticket.get('priority', 'Unspecified') for ticket in tickets_db
        ).items())
    ]
    status_breakdown = [
        {'label': label, 'count': count}
        for label, count in sorted(Counter(
            ticket.get('status', 'Unknown') for ticket in tickets_db
        ).items())
    ]

    return render_template(
        'index.html',
        role=role,
        username=session.get('username'),
        tickets=filtered_tickets if view == 'queue' else tickets_db,
        view=view,
        search_query=search_query,
        status_filter=status_filter,
        priority_filter=priority_filter,
        total_tickets=total_tickets,
        open_count=open_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        resolution_rate=round(resolved_count / total_tickets * 100) if total_tickets else 0,
        average_rating=round(sum(ratings) / len(ratings), 1) if ratings else None,
        feedback_count=len(ratings),
        category_breakdown=category_breakdown,
        priority_breakdown=priority_breakdown,
        status_breakdown=status_breakdown,
        error=error,
    )


@app.route('/add_comment/<int:ticket_id>', methods=['POST'])
def add_comment(ticket_id):
    comment_text = request.form.get('comment', '').strip()
    anonymous = request.form.get('anonymous') == 'on'
    role = session.get('role', 'guest')

    if comment_text:
        for ticket in tickets_db:
            if ticket['id'] == ticket_id:
                if anonymous or role == 'guest':
                    author_name = 'Anonymous'
                    comment_role = 'anonymous'
                else:
                    author_name = session['username']
                    comment_role = role
                ticket['comments'].append({
                    'author': author_name,
                    'role': comment_role,
                    'text': comment_text
                })
                break
    return redirect(url_for('index', _anchor=f'thread-{ticket_id}'))


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    account = DEMO_ACCOUNTS.get(username)

    if account and password == account['password']:
        session.clear()
        session['username'] = account['display_name']
        session['role'] = account['role']
    else:
        session['error'] = 'Invalid username or password.'
    return redirect(url_for('index'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/feedback/<int:ticket_id>', methods=['POST'])
def submit_feedback(ticket_id):
    ticket = next((item for item in tickets_db if item['id'] == ticket_id), None)
    rating = request.form.get('rating', '')
    feedback_text = request.form.get('feedback', '').strip()

    if ticket is not None and ticket['status'] == 'Resolved' and rating in {'1', '2', '3', '4', '5'}:
        ticket.setdefault('feedback', []).append({
            'rating': int(rating),
            'author': session.get('username', 'Anonymous'),
            'text': feedback_text,
        })
    else:
        session['error'] = 'Feedback is available for resolved tickets. Please choose a rating from 1 to 5.'
    return redirect(url_for('index', _anchor=f'thread-{ticket_id}'))


@app.route('/resolve_ticket/<int:ticket_id>')
def resolve_ticket(ticket_id):
    if session.get('role') == 'admin':
        for ticket in tickets_db:
            if ticket['id'] == ticket_id:
                ticket['status'] = 'Resolved'
                ticket['comments'].append({
                    'author': 'IT Agent',
                    'role': 'admin',
                    'text': 'Ticket marked as RESOLVED.'
                })
                break
    return redirect(url_for('index'))


@app.route('/delete_ticket/<int:ticket_id>')
def delete_ticket(ticket_id):
    if session.get('role') == 'admin':
        global tickets_db
        tickets_db = [t for t in tickets_db if t['id'] != ticket_id]
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)