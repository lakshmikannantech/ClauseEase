import re
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
from docx import Document
import fitz  # PyMuPDF
import io
import textstat

# -----------------------
# Simplification dictionary
# -----------------------
simplification_dict = {
    "party": "party",
    "law": "law",
    "contract": "agreement",
    "notice": "notice",
    "rights": "rights",
    "services": "services",
    "payment": "payment",
    "liable": "responsible",
    "warranty": "guarantee",
    "agreement": "deal",
    "compensation": "payment",
    "scope of services": "services included",
    "representation": "statement",
    "dispute": "disagreement",
    "confidentiality": "privately",
    "confidential": "private",
    "governing law": "applicable law",
    "termination clause": "end agreement clause",
    "arbitration": "dispute resolution",
    "indemnify": "protect against loss",
    "jurisdiction": "legal area",
    "force majeure": "unforeseen event",
    "intellectual property": "ownership rights",
    "limitation of liability": "limit responsibility",
    "non-disclosure": "keep secret",
    "severability": "separate parts",
    "breach of contract": "breaking agreement",
    "termination for convenience": "end for any reason"
}

# -----------------------
# Global legal terms lists
# -----------------------
simple_terms = [
    "party", "law", "contract", "notice", "rights", "services", "payment", 
    "termination", "date", "amount", "obligation", "agreement", "scope",
    "delivery", "signature", "document", "record", "responsibility",
    "liability", "warranty", "confidentiality", "access", "approval",
    "period", "duration", "location", "work", "result", "service provider"
]

medium_terms = [
    "liable", "warranty", "agreement", "compensation", "scope of services",
    "representation", "dispute", "delivery", "performance", "confidential",
    "governing law", "payment terms", "termination clause", "indemnification",
    "assignment", "intellectual property rights", "notification", "breach notice",
    "remedies", "hold harmless", "non-compete", "compliance", "data protection",
    "force majeure", "conflict of interest", "arbitration clause", "penalty",
    "subcontract", "acceptance", "limitations", "independent contractor",
    "notice period", "terms and conditions"
]

complex_terms = [
    "arbitration", "indemnify", "jurisdiction", "force majeure", 
    "intellectual property", "limitation of liability", "non-disclosure",
    "severability", "breach of contract", "termination for convenience",
    "dispute resolution", "assignment and delegation", "governing jurisdiction",
    "covenant not to compete", "waiver of rights", "confidential information",
    "successors and assigns", "liquidated damages", "entire agreement",
    "binding effect", "infringement", "patent rights", "trademark rights",
    "copyrights", "third party rights", "subrogation", "termination upon notice",
    "independent contractor status", "representations and warranties"
]

legal_patterns = [
    "shall", "hereby", "party of the first part", "notwithstanding",
    "in witness whereof", "subject to", "as agreed herein", "pursuant to",
    "for the avoidance of doubt", "without limitation", "unless otherwise agreed",
    "in accordance with", "to the extent permitted", "as set forth herein",
    "notwithstanding anything to the contrary", "including but not limited to",
    "in connection with", "as applicable", "effective date", "from time to time",
    "for the purposes of", "hereinabove", "hereinafter", "mutatis mutandis",
    "in the event that", "save as otherwise provided", "as the case may be"
]

# -----------------------
# Function to simplify text
# -----------------------
def simplify_legal_text(text, simplification_dict):
    terms_sorted = sorted(simplification_dict.keys(), key=lambda x: -len(x))
    simplified_text = text
    for term in terms_sorted:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        replacement = f'<span class="simplified-word">{simplification_dict[term]}</span>'
        simplified_text = pattern.sub(replacement, simplified_text)
    return simplified_text

# -----------------------
# Flask App Setup
# -----------------------
app = Flask(__name__)
app.secret_key = 'clauseease_secret_key'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, "files", "users.txt")
UPLOAD_DIR = os.path.join(BASE_DIR, "files", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "files"), exist_ok=True)

# -----------------------
# User Functions
# -----------------------
def load_users():
    users = {}
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                username, password = line.strip().split(',')
                users[username] = password
    return users

def save_user(username, password):
    with open(USER_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{username},{password}\n")

# -----------------------
# Routes
# -----------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        if username in users:
            flash('Username already exists.')
            return redirect(url_for('register'))
        save_user(username, password)
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    from flask import get_flashed_messages
    get_flashed_messages()  # clear previous messages

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        if username in users and users[username] == password:
            session['username'] = username
            flash(f'Welcome, {username}!', 'success')
            return redirect(url_for('document_ingestion'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # clear everything
    flash('Logged out successfully.')
    return redirect(url_for('login'))

# -----------------------
# Document Ingestion
# -----------------------
@app.route('/document_ingestion', methods=['GET'])
def document_ingestion():
    if 'username' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    return render_template('document_ingestion.html')

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'username' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('document_ingestion'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected for upload.', 'error')
        return redirect(url_for('document_ingestion'))

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(file_path)
    session['uploaded_file'] = file_path

    flash(f'File "{file.filename}" uploaded successfully!', 'success')
    return redirect(url_for('text_processing'))

# -----------------------
# Text Processing
# -----------------------
@app.route('/text_processing', methods=['GET', 'POST'])
def text_processing():
    if 'username' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    input_text = ""
    highlighted_text = ""

    if 'uploaded_file' in session:
        file_path = session['uploaded_file']  # keep in session
        ext = file_path.lower().split('.')[-1]
        try:
            if ext == 'txt':
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    input_text = f.read()
            elif ext == 'docx':
                doc = Document(file_path)
                input_text = '\n'.join([p.text for p in doc.paragraphs])
            elif ext == 'pdf':
                doc = fitz.open(file_path)
                input_text = '\n'.join([page.get_text() for page in doc])
        except Exception as e:
            flash(f"Error reading file: {e}", 'error')

    # Highlight legal terms
    words = re.findall(r'\w+|\s+|[^\s\w]+', input_text)
    highlighted_words = []
    for word in words:
        lw = word.lower()
        if lw in complex_terms:
            highlighted_words.append(f'<span style="background-color:red;color:white;">{word}</span>')
        elif lw in medium_terms:
            highlighted_words.append(f'<span style="background-color:orange;color:white;">{word}</span>')
        elif lw in simple_terms:
            highlighted_words.append(f'<span style="background-color:green;color:white;">{word}</span>')
        elif lw in legal_patterns:
            highlighted_words.append(f'<span style="background-color:blue;color:white;">{word}</span>')
        else:
            highlighted_words.append(word)

    highlighted_text = ''.join(highlighted_words)

    # Store in session for back-navigation
    session['original_text'] = input_text
    session['highlighted_text'] = highlighted_text

    return render_template('text_processing.html',
                           input_text=input_text,
                           highlighted_text=highlighted_text)

# -----------------------
# Text Simplification
# -----------------------
@app.route('/text_simplification', methods=['GET', 'POST'])
def text_simplification():
    if 'username' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    original_text = session.get('original_text', '')
    simplified_text = ''
    summary = ''

    if original_text:
        simplified_text = simplify_legal_text(original_text, simplification_dict)
        sentences = original_text.split('.')[:2]
        summary = '.'.join(sentences).strip() + '.'

    # Save simplified text in session
    session['simplified_text'] = simplified_text

    return render_template('text_simplification.html',
                           original_text=original_text,
                           simplified_text=simplified_text,
                           summary=summary)

# -----------------------
# Preview Page
# -----------------------
@app.route('/preview', methods=['GET'])
def preview():
    if 'username' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    original_text = session.get('original_text', '')
    simplified_text = session.get('simplified_text', '')

    if not original_text:
        flash('No text available for preview.')
        return redirect(url_for('text_processing'))

    # Detect legal terms dynamically
    legal_terms_combined = set()
    for term_list in [simple_terms, medium_terms, complex_terms]:
        for term in term_list:
            if re.search(r'\b' + re.escape(term) + r'\b', original_text, re.IGNORECASE):
                legal_terms_combined.add(term)
    legal_terms_list = sorted(list(legal_terms_combined))
    terms_count = len(legal_terms_list)

    # Readability score
    readability_score = textstat.flesch_kincaid_grade(original_text)

    return render_template('preview.html',
                           original_text=original_text,
                           simplified_text=simplified_text,
                           legal_terms=legal_terms_list,
                           terms_count=terms_count,
                           readability_score=readability_score)

# -----------------------
# Download Report
# -----------------------
@app.route('/download_report', methods=['POST'])
def download_report():
    original_text = request.form.get('original_text', '')
    simplified_text = request.form.get('simplified_text', '')
    legal_terms = request.form.getlist('legal_terms[]')
    readability_score = request.form.get('readability_score', '')

    simplified_text_plain = re.sub(r'<[^>]+>', '', simplified_text)

    terms_count = len(legal_terms)
    report_content = f"=== Simplified Contract Report ===\n\n"
    report_content += f"Legal Terms Detected: {terms_count}\n"
    report_content += f"Detected Terms: {', '.join(legal_terms)}\n\n"
    report_content += f"Flesch-Kincaid Readability Score: {readability_score}\n\n"
    report_content += "Simplified Text:\n"
    report_content += simplified_text_plain

    return send_file(
        io.BytesIO(report_content.encode()),
        mimetype='text/plain',
        as_attachment=True,
        download_name='simplified_report.txt'
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
