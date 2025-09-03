import os
import random
import json
import sqlite3
import click # Import click for CLI commands
from flask import Flask, render_template, request, jsonify, send_from_directory, g, session

# Initialize Flask app
app = Flask(__name__)

# Configure a secret key for session management
# IMPORTANT: Replace with a real secret key in production!
# When deploying to Render and setting SECRET_KEY as an environment variable,
# Flask automatically reads it from the environment.
# Remove or comment out this line when setting SECRET_KEY via environment variables.
app.config['SECRET_KEY'] = 'your_very_secret_key_here'


# Configure the folder where images are stored
# Make sure this path is correct for your local environment
IMAGE_FOLDER = './extracted_images/Images'
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER

# --- Database Setup ---
DATABASE = 'ranking.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return db

@app.teardown_appcontext
def close_db(error):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    try:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        print('Initialized the database.')
    except FileNotFoundError:
        print("schema.sql not found. Database not initialized.")
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        db.rollback()


# Add a CLI command to initialize the database
@app.cli.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

# --- End Database Setup ---

# Removed presented_images set as ranking is now persistent in DB
# Re-initialize a set to keep track of presented images for the current session
# This state will now be stored in Flask's session object


@app.route('/')
def index():
    # Initialize presented_images in session if it doesn't exist
    if 'presented_images' not in session:
        session['presented_images'] = []
    return render_template('index.html')

@app.route('/image/<filename>')
def serve_image(filename):
    try:
        return send_from_directory(app.config['IMAGE_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({"error": "Image not found"}), 404

@app.route('/next_batch')
def next_batch():
    # Get presented images from session
    presented_images = set(session.get('presented_images', []))

    # Get all available image files
    all_images = os.listdir(app.config['IMAGE_FOLDER'])
    # Filter out macOS-specific files
    image_files = [f for f in all_images
                   if not f.startswith('._')
                   and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

    # Find images that have NOT been presented in the current session
    available_images = [f for f in image_files if f not in presented_images]

    if len(available_images) >= 5:
        batch_images = random.sample(available_images, 5)
    else:
        batch_images = available_images  # Return all remaining images if less than 5

    # Add the selected images to the set of presented images for the current session
    presented_images.update(batch_images)
    session['presented_images'] = list(presented_images) # Store updated set back in session

    return jsonify({"images": batch_images})

@app.route('/rank', methods=['POST'])
def rank_images():
    data = request.get_json()
    ranked_images = data.get('rankedImages', [])

    db = get_db()

    points = 5
    for image in ranked_images:
        # Insert or update points in the database
        # If image exists, update points; otherwise, insert with new points
        db.execute('INSERT OR IGNORE INTO rankings (image_filename, points) VALUES (?, 0)', (image,))
        db.execute('UPDATE rankings SET points = points + ? WHERE image_filename = ?', (points, image))
        points -= 1

    db.commit()

    # Fetch updated leaderboard data from the database
    cursor = db.execute('SELECT image_filename, points FROM rankings ORDER BY points DESC')
    leaderboard_data = [{"filename": row['image_filename'], "points": row['points']} for row in cursor.fetchall()]

    return jsonify({"status": "success", "leaderboard": leaderboard_data})

@app.route('/leaderboard')
def get_leaderboard():
    """Flask route to return the current leaderboard data from the database."""
    db = get_db()
    try:
        cursor = db.execute('SELECT image_filename, points FROM rankings ORDER BY points DESC')
        leaderboard_data = [{"filename": row['image_filename'], "points": row['points']} for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        # If rankings table doesn't exist yet, return an empty leaderboard
        leaderboard_data = []
    return jsonify({"leaderboard": leaderboard_data})


# Removed save/load progress routes and logic


if __name__ == '__main__':
    # When running directly (e.g., python app.py), initialize the db
    with app.app_context():
         init_db()

    # Run the Flask application
    # For local development, you can run it directly using 'python app.py'
    # or use 'flask --app app.py run' after initializing the db with 'flask --app app.py init-db'
    app.run(debug=True) # Set debug=False for production