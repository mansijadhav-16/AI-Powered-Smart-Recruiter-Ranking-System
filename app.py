import os
import subprocess
import sys
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import spacy
import json
import random
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy 
from config import Config
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from datetime import datetime, timezone
from flask import send_from_directory
import re
from dateutil import parser
from flask_mail import Mail, Message
from io import BytesIO
from flask import send_file
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import csv
from io import StringIO
from config import GROQ_API_KEY
from flask import make_response
from sqlalchemy import desc
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text 
from sqlalchemy import func
from datetime import datetime, timedelta
from flask import flash, redirect, url_for, render_template

def load_nlp_model():
    model_name = "en_core_web_md" 
    try:
        temp_nlp = spacy.load(model_name)
        print(f"✅ NLP Model '{model_name}' loaded successfully!")
        return temp_nlp
    except OSError:
        print(f"⚠️ Model '{model_name}' not found. Downloading now...")
        try:
            subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
            return spacy.load(model_name)
        except Exception as e:
            print(f"❌ Failed to download model: {e}")
            return None

nlp = load_nlp_model()

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)

mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page' # Error image_142f44 fix

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 1. Configuration Setup
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

PHOTO_UPLOAD_FOLDER = 'static/profile_pics'
app.config['PHOTO_UPLOAD_FOLDER'] = PHOTO_UPLOAD_FOLDER
ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# SQLAlchemy Setup
db = SQLAlchemy(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    role = db.Column(db.String(100))
    score = db.Column(db.Integer)
    status = db.Column(db.String(50))
    date = db.Column(db.String(50))

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True, default='default.png')
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    job_title = db.Column(db.String(100))
    bio = db.Column(db.Text)
    email_match = db.Column(db.Boolean, default=True)
    email_alerts = db.Column(db.Boolean, default=True)
    push_browser = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(50), default='Light Mode')
    language = db.Column(db.String(50), default='English (US)')
    timezone = db.Column(db.String(50), default='Eastern Time (ET)')
    analytics_tracking = db.Column(db.Boolean, default=True)
    data_retention = db.Column(db.String(50), default='2 years')
    two_factor_enabled = db.Column(db.Boolean, default=False)
    account_type = db.Column(db.String(100), default='Professional Plan')
    member_since = db.Column(db.String(100), default=datetime.now().strftime('%B %d, %Y'))
    account_id_custom = db.Column(db.String(100), default='usr_7f8a9b2c3d4e5f6g')

class CandidateResult(db.Model):
    __tablename__ = 'candidate_results'
    id = db.Column(db.Integer, primary_key=True)
    candidate_name = db.Column(db.String(255))
    filename = db.Column(db.String(255))
    email = db.Column(db.String(100), nullable=True)
    position = db.Column(db.String(255))
    experience = db.Column(db.String(100))
    skills = db.Column(db.Text) 
    score = db.Column(db.String(10))
    status = db.Column(db.String(50))
    upload_date = db.Column(db.String(20))

class JobRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(100), unique=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(20), default='info') # info, success, warning
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_photo(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS

def extract_email(text):
    if not text:
        return "N/A"
    # Ye pattern zyada types ke emails capture karta hai
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    return emails[0] if emails else "N/A"

def calculate_total_experience(text):
    text_lower = text.lower()
    
    # --- 1. Direct Pattern Check (e.g., "3 years 2 months") ---
    direct_match = re.search(r'(\d+)\s*(?:year|yr)s?[\s,]*(\d+)\s*(?:month|mon)s?', text_lower)
    if direct_match:
        return f"{direct_match.group(1)}y {direct_match.group(2)}m"
    
    # --- 2. Date Range Calculation (The AI Part) ---
    # Regex to find date ranges like "Jan 2020 - Mar 2023" or "2018 to Present"
    date_range_pattern = r'([A-Za-z]+\s+\d{4}|\d{2}/\d{4}|\d{4})\s*(?:-|to|until)\s*([A-Za-z]+\s+\d{4}|\d{2}/\d{4}|\d{4}|present|current|now)'
    ranges = re.findall(date_range_pattern, text_lower)
    
    total_months = 0
    if ranges:
        for start_str, end_str in ranges:
            try:
                # Start date parse karein
                start_date = parser.parse(start_str, fuzzy=True)
                
                # End date parse karein (Present = Aaj ki date)
                if any(x in end_str for x in ['present', 'current', 'now']):
                    end_date = datetime.now()
                else:
                    end_date = parser.parse(end_str, fuzzy=True)
                
                # Difference nikalna mahino mein
                diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                if diff > 0:
                    total_months += diff
            except:
                continue

    # --- 3. Result Formatting ---
    if total_months > 0:
        years = total_months // 12
        months = total_months % 12
        
        result = ""
        if years > 0: result += f"{years} Years "
        if months > 0: result += f"{months} Months"
        return result.strip()

    # --- 4. Fallback: Agar dates nahi mili toh simple "years" search ---
    simple_match = re.search(r'(\d+(?:\.\d+)?)\+?\s*(?:year|yr)s?', text_lower)
    if simple_match:
        return f"{simple_match.group(1)} Years"

    # --- 5. Final Fallback: Fresher ---
    return "Fresher"

def extract_dynamic_info(text):
    import re
    text_lower = text.lower()
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    tech_keywords = [
        'python', 'java', 'javascript', 'html', 'css', 'react', 'node', 'mongodb', 'sql', 'mysql', 
        'aws', 'docker', 'git', 'github', 'rest api', 'flask', 'django', 'express', 'spring', 
        'angular', 'vue', 'machine learning', 'data science', 'devops', 'firebase', 'postman', 
        'typescript', 'c++', 'c#', 'php', 'laravel', 'swift', 'flutter', 'tableau', 'power bi',
        'excel', 'word', 'azure', 'kubernetes', 'jenkins', 'linux', 'manual testing', 'automation'
    ]

    # 2. Skill-Heavy Sections Identification
    skills_keywords = ['skills', 'expertise', 'technologies', 'tools', 'competencies']
    stop_keywords = ['education', 'experience', 'projects', 'declaration', 'hobbies', 'personal', 'summary']
    
    found_skills = []

    for tech in tech_keywords:
        if re.search(r'\b' + re.escape(tech) + r'\b', text_lower):
            found_skills.append(tech.title() if len(tech) > 3 else tech.upper())

    start_capture = False
    for line in lines:
        l_lower = line.lower()
        if any(key in l_lower for key in skills_keywords) and len(l_lower) < 30:
            start_capture = True
            continue
        if start_capture:
            if any(stop in l_lower for stop in stop_keywords) and len(l_lower) < 25:
                start_capture = False
                break
            
            # Line ko split karke non-technical skills (Management, Leadership etc.) uthayein
            parts = re.split(r'[,|•●▪○*·\t]', line)
            for part in parts:
                clean = part.strip()
                # Filtering: Bahut badi line na ho aur garbage words na hon
                if 3 < len(clean) < 30 and not any(g in clean.lower() for g in ['mumbai', 'india', 'name', 'phone']):
                    found_skills.append(clean)

    # 3. Position Logic (Cleanest)
    actual_pos = "Candidate"
    job_titles = ['developer', 'engineer', 'manager', 'analyst', 'accountant', 'designer', 'fresher', 'intern']
    for line in lines[:8]:
        if any(jt in line.lower() for jt in job_titles):
            actual_pos = line
            break

    # Duplicates hatayein aur Cleaning karein
    final_list = []
    for s in found_skills:
        # Symbols hatayein (brackets etc.)
        s_clean = re.sub(r'[^\w\s.#+]', '', s).strip()
        if s_clean and s_clean.lower() not in [f.lower() for f in final_list]:
            # Sirf 1-3 words ki skills lein (varna puri sentence aa jati hai)
            if len(s_clean.split()) <= 3:
                final_list.append(s_clean)

    return actual_pos, final_list[:12]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/register_user', methods=['POST'])
def register_user():
    new_user = User(
        username=request.form.get('username'),
        email=request.form.get('email'),
        password=request.form.get('password'),
        role=request.form.get('role')
    )
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/login_submit', methods=['POST'])
def login_submit():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email, password=password).first()
    
    if user:
        login_user(user) # login fix
        session['username'] = user.username 
        session['user_id'] = user.id
        session['role'] = user.role.lower()
        
        if user.role.lower() == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    else:
        flash("Invalid Credentials! Please try again.", "danger")
        return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    name = session.get('username', 'User')
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
  
    total_resumes = CandidateResult.query.count()
    analyzed_today = CandidateResult.query.count() 
    high_matches = CandidateResult.query.filter(CandidateResult.score >= 80).count()
    pending_review = CandidateResult.query.filter(CandidateResult.status == 'Pending').count()

    applicants = CandidateResult.query.order_by(CandidateResult.id.desc()).limit(5).all()
    return render_template('dashboard.html', 
                           name=name, 
                           profile=profile, 
                           total_resumes=total_resumes,
                           analyzed_today=analyzed_today,
                           high_matches=high_matches,
                           pending_review=pending_review,
                           applicants=applicants)

@app.route('/get_candidates')
def get_candidates():
    candidates = CandidateResult.query.order_by(CandidateResult.score.desc()).limit(5).all()
    
    candidate_list = []
    for c in candidates:
        candidate_list.append({
            "id": c.id,
            "name": c.candidate_name, # Apne model ke column name ke hisaab se check karna
            "email": c.email,
            "score": c.score,
            "skills": c.skills
        })
    return jsonify(candidate_list)

@app.route('/get_saved_candidates', methods=['GET'])
@login_required
def get_saved_candidates():
    try:
        candidates = CandidateResult.query.order_by(CandidateResult.id.desc()).all()
        results = []
        for c in candidates:
            # Safer way: Agar email column nahi hai toh error nahi aayega
            email_val = getattr(c, 'email', 'N/A') 
            
            results.append({
                "candidate": c.candidate_name,
                "email": email_val,
                "filename": c.filename,
                "position": c.position,
                "experience": c.experience,
                "skills": json.loads(c.skills) if c.skills else [],
                "score": c.score,
                "status": c.status,
                "upload_date": c.upload_date
            })
        return jsonify(results)
    except Exception as e:
        print(f"DEBUG ERROR: {e}") # Terminal mein error dekhein
        return jsonify([]) # Khali list bhejien taaki table crash na ho

@app.route('/logout')
def logout():
    logout_user() # AttributeError image_14aea7 fix
    session.clear()
    return redirect(url_for('home')) # BuildError image_142b61 fix

@app.route('/get_notifications')
@login_required
def get_notifications():
    try:
        user_id = current_user.id
        # Sirf unread notifications nikalna (is_read=False)
        notifications = Notification.query.filter_by(user_id=user_id, is_read=False)\
                                         .order_by(Notification.created_at.desc()).all()
        
        notif_list = []
        for n in notifications:
            notif_list.append({
                "title": n.title,
                "message": n.message,
                "time": n.created_at.strftime("%I:%M %p"), # Example: 10:30 AM
                "type": n.type
            })
            
        return jsonify({
            "status": "success",
            "count": len(notif_list), 
            "notifications": notif_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                if profile:
                    profile.profile_pic = filename
                else:
                    profile = UserProfile(user_id=current_user.id, profile_pic=filename)
                    db.session.add(profile)
                db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('settings.html', profile=profile)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    try:
        data = request.json
        profile = UserProfile.query.filter_by(user_id=current_user.id).first()
        
        if not profile:
            profile = UserProfile(user_id=current_user.id)
            db.session.add(profile)
        
        # Frontend ki keys ke saath match kijiye
        if 'first_name' in data: profile.first_name = data.get('first_name')
        if 'last_name' in data: profile.last_name = data.get('last_name')
        if 'phone' in data: profile.phone = data.get('phone') # 'phone_number' se badal kar 'phone' kiya
        if 'job_title' in data: profile.job_title = data.get('job_title')
        if 'bio' in data: profile.bio = data.get('bio')
        if 'theme' in data: profile.theme = data.get('theme')
        if 'language' in data: profile.language = data.get('language')
        
        # Checkbox handling
        if 'email_match' in data: profile.email_match = bool(data.get('email_match', False))
        if 'email_alerts' in data: profile.email_alerts = bool(data.get('email_alerts', False))
        if 'push_browser' in data: profile.push_browser = bool(data.get('push_browser', False))
        if 'analytics_tracking' in data: profile.analytics_tracking = bool(data.get('analytics_tracking', False))
        if 'two_factor_enabled' in data: profile.two_factor_enabled = bool(data.get('two_factor_enabled', False))


        if 'new_password' in data and data.get('new_password'):
            current_user.password = generate_password_hash(data.get('new_password'), method='pbkdf2:sha256')
            
        db.session.commit()
        return jsonify({"status": "success", "message": "Settings Updated!"})
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}") # Debugging ke liye
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    data = request.json
    curr = data.get('current_password')
    nxt = data.get('new_password')
    
    if not check_password_hash(current_user.password, curr):
        return jsonify({"status": "error", "message": "Invalid Password!"})
    
    try:
        # app.py mein check karein
        current_user.password = generate_password_hash(nxt, method='pbkdf2:sha256')
        db.session.commit()
        return jsonify({"status": "success", "message": "Your password has been changed successfully.!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)})

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    try:
        if 'profile_photo' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
            
        file = request.files['profile_photo']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400

        filename = secure_filename(f"user_{current_user.id}_{file.filename}")
        file_path = os.path.join('static/uploads', filename)
        file.save(file_path)

        profile = UserProfile.query.filter_by(user_id=current_user.id).first()
        profile.profile_pic = filename
        db.session.commit()

        return jsonify({
            "status": "success", 
            "url": url_for('static', filename='uploads/' + filename)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/analyze_candidates', methods=['POST'])
@login_required
def analyze_candidates():
    try:
        job_description = request.form.get('job_description')
        files = request.files.getlist('resumes')
        
        if not job_description or not files:
            return jsonify({"error": "Inputs missing"}), 400

        jd_doc = nlp(job_description)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # PDF se text nikalna
                resume_text = ""
                reader = PdfReader(file_path)
                for page in reader.pages:
                    resume_text += page.extract_text() or ""
                
                # --- ASLI AI EXTRACTION CALL ---
                actual_email = extract_email(resume_text)
                actual_exp = calculate_total_experience(resume_text)
                actual_position, skills_list = extract_dynamic_info(resume_text)
                
                # AI Score
                resume_doc = nlp(resume_text)
                similarity = jd_doc.similarity(resume_doc)
                match_percentage = int(similarity * 100)

                # Save to DB
                new_result = CandidateResult(
                    candidate_name=filename.split('.')[0].replace('_', ' ').title(),
                    filename=filename,
                    email=actual_email,
                    position=actual_position[:50], 
                    experience=actual_exp,
                    skills=json.dumps(skills_list), # Ab ye dynamic skills hain
                    score=f"{match_percentage}%",
                    status="Excellent Match" if match_percentage >= 80 else "Good Match" if match_percentage >= 60 else "Potential Match",
                    upload_date=datetime.now().strftime("%Y-%m-%d")
                )
                db.session.add(new_result)
        
        db.session.commit()
        return jsonify({"message": "Analysis Complete"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/view_resume/<filename>')
@login_required
def view_resume(filename):
    # 'uploads' ki jagah apne folder ka naam likhein jo config mein hai
    directory = app.config['UPLOAD_FOLDER'] 
    return send_from_directory(directory, filename)
        
@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    try:
        data = request.json
        api_key = GROQ_API_KEY
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        # --- NEW: User ne jo checkbox select kiye hain unhe uthao ---
        # Agar user ne kuch select nahi kiya toh default 'Technical' rakho
        selected_types = data.get('question_types', ['Technical'])
        types_str = ", ".join(selected_types)

        prompt = (
            f"Generate {data.get('num_questions', 5)} interview questions for {data.get('job_role')}. "
            f"The questions MUST be of these types: {types_str}. " # Ab ye Behavioral generate karega
            f"Skills: {data.get('focus_skills')}. Difficulty: {data.get('difficulty')}. "
            "Return ONLY JSON: {\"questions\": [{\"id\": 1, \"type\": \"Category\", \"text\": \"question\"}]}"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a professional HR assistant that generates interview questions in strict JSON format."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        # Groq se text nikalna
        raw_text = res_json['choices'][0]['message']['content'].strip()
        
        # JSON Cleaning (taki extra text error na de)
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        return jsonify(json.loads(raw_text))

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"questions": [{"id": 1, "type": "Error", "text": f"Error: {str(e)}"}]})

@app.route('/match_score/<int:candidate_id>')
@login_required
def match_score(candidate_id):
    # 1. Database se candidate uthao (id column se)
    candidate = CandidateResult.query.get_or_404(candidate_id)
    all_candidates = CandidateResult.query.order_by(CandidateResult.id.desc()).all()
    
    # 2. JD session se uthao (Ya default rakho testing ke liye)
    jd_text = session.get('last_jd', "Python Flask SQL AWS").lower()
    
    # 3. Candidate ki 'skills' column se data uthao (Asli Skills)
    c_skills = candidate.skills.lower() if candidate.skills else ""
    
    # 4. Comparison (Actual Logic)
    res_list = [s.strip() for s in c_skills.split(',') if s.strip()]
    jd_list = [w.strip() for w in jd_text.replace(',', ' ').split() if len(w) > 2]
    
    matched = [s.title() for s in res_list if any(word in s for word in jd_list)]
    missing = [w.title() for w in jd_list if not any(w in s for s in res_list)]

    # 5. Data dictionary for HTML
    analysis_data = {
        "candidate_name": candidate.candidate_name, # Table ka asli column
        "overall_score": candidate.score or 70,     # Table ka asli column
        "top_skills": list(set(matched)),
        "missing_skills": list(set(missing))[:6],
        "skills_match": int((len(matched)/len(jd_list)*100)) if jd_list else 0,
        "experience_match": 85 if "year" in str(candidate.experience).lower() else 50,
        "education_match": 90
    }
    
    return render_template('match_score.html', 
                           data=analysis_data,
                           all_candidates=CandidateResult.query.all(),
                           current_id=candidate_id)
                        
@app.route('/skill_heatmap')
@login_required
def skill_heatmap():
    # 1. Sare Candidates uthao
    all_applicants = CandidateResult.query.all()
    total_applicants = len(all_applicants)

    # 2. JD Skills (Requirements) - Ye session se lo ya default rakho
    jd_text = session.get('last_jd', "Python, Flask, SQL, Docker, AWS, React").lower()
    jd_skills = [s.strip() for s in jd_text.replace(',', ' ').split() if len(s) > 2]
    jd_skills = list(set(jd_skills))[:7] # Top 7 skills for chart

    # 3. Aggregate Analysis (Sare candidates ka milake)
    heatmap_stats = []
    for skill in jd_skills:
        # Count karo kitne candidates ke paas ye skill hai
        count_with_skill = 0
        for app in all_applicants:
            if app.skills and skill.lower() in app.skills.lower():
                count_with_skill += 1
        
        # Calculations
        demand = 95 # Market requirement hamesha high
        availability = round((count_with_skill / total_applicants * 100), 1) if total_applicants > 0 else 0
        gap = demand - availability
        
        heatmap_stats.append({
            "skill": skill.title(),
            "demand": demand,
            "availability": availability,
            "gap": gap
        })

    return render_template('skill_heatmap.html', skills=heatmap_stats, total=total_applicants)

# --- ADMIN API ROUTES ---
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
    
    recent_users = db.session.query(User, UserProfile).outerjoin(
        UserProfile, User.id == UserProfile.user_id
    ).order_by(desc(User.id)).limit(5).all()
    
    name = session.get('username', 'Admin')
    return render_template('admin_dashboard.html', name=name, users=recent_users)

@app.route('/admin/users')
@login_required
def get_users():
    if session.get('role') != 'admin':
        return jsonify([]), 403

    users_with_profiles = db.session.query(User, UserProfile).outerjoin(
        UserProfile, User.id == UserProfile.user_id
    ).all()

    user_list = []
    for u, p in users_with_profiles:
        if p and (p.first_name or p.last_name):
            display_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
        else:
            display_name = u.username

        user_list.append({
            "id": u.id,
            "username": display_name, 
            "email": u.email,
            "role": u.role,
            "job_title": p.job_title if p else "N/A",
            "phone": p.phone if p else "N/A",
            "status": "Active"
        })

    return jsonify(user_list)

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    try:
        total_users = User.query.count()
        # CandidateResult table se total candidates ka count uthao
        total_candidates = CandidateResult.query.count() 
        
        # Formatting for 'k' (e.g., 1500 -> 1.5k)
        if total_candidates >= 1000:
            formatted_candidates = f"{round(total_candidates/1000, 1)}k"
        else:
            formatted_candidates = str(total_candidates)

        return jsonify({
            "total_users": total_users,
            "total_candidates": formatted_candidates, # Key name updated
            "api_calls": total_candidates * 5,
            "server_load": "14%"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/analytics_data')
@login_required
def get_global_analytics():
    if session.get('role').lower() != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # 1. Total Counts (Simple & Direct)
        total_users = User.query.count()
        total_candidates = CandidateResult.query.count() 

        # Formatting (1500 -> 1.5k)
        formatted_cands = f"{round(total_candidates/1000, 1)}k" if total_candidates >= 1000 else str(total_candidates)

        # 2. Graph Data (Using 'upload_date' column)
        labels = []
        candidate_stats = []
        for i in range(6, -1, -1):
            target_date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # %a matlab Mon, Tue, etc.
            labels.append((datetime.now() - timedelta(days=i)).strftime('%a'))
            
            # Aapki column 'upload_date' String hai, isliye hum like match karenge ya exact date
            # Agar format '2023-10-27' jaisa hai toh ye kaam karega:
            count = CandidateResult.query.filter(CandidateResult.upload_date.like(f"{target_date}%")).count()
            candidate_stats.append(count)

        return jsonify({
            "labels": labels,
            "resume_stats": candidate_stats,
            "total_candidates": formatted_cands,
            "total_users": total_users,
            "server_load": "14%"
        })
    except Exception as e:
        print(f"Analytics DB Error: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/admin/update_profile', methods=['POST'])
@login_required
def update_profile():
    data = request.json
    new_username = data.get('username')
    
    # 1. Session se user_id nikalo
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "Session expired"}), 401

    user = User.query.get(user_id) 
    if user:
        try:
            # 2. Database update karo
            user.username = new_username
            db.session.commit()
            
            # 3. Zaroori: Dono session keys update karo jo aap use kar rahe ho
            session['username'] = new_username  # Dashboard ke liye
            session['name'] = new_username      # General use ke liye
            
            return jsonify({"success": True, "message": "Profile updated!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    
    return jsonify({"success": False, "message": "User not found"}), 404

from sqlalchemy import func
from datetime import datetime, timedelta

@app.route('/admin/add_user', methods=['POST'])
@login_required
def admin_add_user():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.json
    email = data.get('email')
    
    # Email check karein
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already exists in database"}), 400

    try:
        new_user = User(
            username=data.get('username'),
            email=email,
            password=data.get('password'),
            role=data.get('role')
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User added successfully!"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database Error: " + str(e)}), 500

# User Delete karne ke liye
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('role').lower() != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        # Step 1: Pehle UserProfile se data delete karo (Constraint hatane ke liye)
        UserProfile.query.filter_by(user_id=user_id).delete()
        
        # Step 2: Ab main User account delete karo
        user_to_delete = User.query.get(user_id)
        if user_to_delete:
            db.session.delete(user_to_delete)
            db.session.commit() # Database update confirm karo
            return jsonify({"success": True, "message": "User and Profile deleted!"})
        
        return jsonify({"success": False, "message": "User not found"}), 404

    except Exception as e:
        db.session.rollback() # Agar error aaye toh change cancel karo
        print(f"Delete Error: {e}") # Terminal mein check karo error kya hai
        return jsonify({"success": False, "message": "Database error: Clear relationships first"}), 500

@app.route('/admin/update_user/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if session.get('role').lower() != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.json
    user = User.query.get(user_id)
    # Important: UserProfile ko sahi se fetch karein
    profile = UserProfile.query.filter_by(user_id=user_id).first()

    if user:
        try:
            # 1. User Table Update
            user.username = data.get('username', user.username)
            user.role = data.get('role', user.role)

            # 2. UserProfile Table Update (Taki UI mein naam badle)
            if profile:
                full_name = data.get('username', '').strip().split(' ', 1)
                profile.first_name = full_name[0]
                profile.last_name = full_name[1] if len(full_name) > 1 else ""
            
            db.session.commit()
            return jsonify({"success": True})
            
        except Exception as e:
            db.session.rollback()
            print(f"Update Error: {e}") # Terminal mein error dekhein
            return jsonify({"success": False, "message": str(e)}), 500
            
    return jsonify({"success": False, "message": "User not found"}), 404

@app.route('/admin/system_logs')
@login_required
def get_system_logs():
    if session.get('role').lower() != 'admin':
        return jsonify([]), 403
    
    try:
        logs = []
        
        # 1. Latest Candidates (CandidateResult Table)
        latest_cands = CandidateResult.query.order_by(CandidateResult.id.desc()).limit(10).all()
        for c in latest_cands:
            logs.append({
                "time": c.upload_date or "Recent",
                "source": "AI Engine",
                "msg": f"Processed resume for candidate: {c.candidate_name}",
                "status": "Success"
            })

        # 2. Latest Users (User Table)
        latest_users = User.query.order_by(User.id.desc()).limit(5).all()
        for u in latest_users:
            logs.append({
                "time": "Today",
                "source": "Auth System",
                "msg": f"New user '{u.username}' registered to the platform",
                "status": "Info"
            })

        # Logs ko latest first dikhane ke liye reverse sort (optional)
        return jsonify(logs)
    except Exception as e:
        print(f"Log Error: {e}")
        return jsonify([]), 500

@app.route('/applicants')
@login_required
def applicants_page():
    name = session.get('username', 'User')
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    
    # --- PAGINATION LOGIC START ---
    page = request.args.get('page', 1, type=int) # Current page number (default 1)
    per_page = 10 # Ek page pe kitne candidates dikhane hain (Aap 5 ya 10 kar sakte ho)
    # --- PAGINATION LOGIC END ---

    search_query = request.args.get('search', '').strip()
    
    # 1. Filters ke liye saare unique data fetch karein (bina pagination ke)
    all_candidates = CandidateResult.query.all()
    positions = sorted(list(set([c.position for c in all_candidates if c.position])))
    unique_skills = set()
    for c in all_candidates:
        if c.skills:
            s_list = c.skills.replace('[', '').replace(']', '').replace("'", "").replace('"', '').split(',')
            for s in s_list:
                if s.strip(): unique_skills.add(s.strip())
    
    # 2. Base Query banayein Search logic ke sath
    query = CandidateResult.query
    if search_query:
        query = query.filter(
            (CandidateResult.candidate_name.like(f'%{search_query}%')) | 
            (CandidateResult.position.like(f'%{search_query}%'))
        )
    
    # 3. .all() ki jagah .paginate() use karein
    pagination = query.order_by(CandidateResult.id.desc()).paginate(page=page, per_page=per_page)
    candidates = pagination.items  # Sirf current page ke 10 log
        
    return render_template('applicants.html', 
                           applicants=candidates, 
                           pagination=pagination, # Ye object buttons banane mein kaam aayega
                           name=name, 
                           profile=profile, 
                           search_query=search_query,
                           positions=positions,
                           skills=sorted(list(unique_skills)))

@app.route('/api/candidates', methods=['GET'])
@login_required
def get_all_candidates_api():
    try:
        # Database se saare candidates fetch karna
        all_candidates = Candidate.query.all()
        
        # Data ko JSON format mein convert karna
        output = []
        for c in all_candidates:
            output.append({
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "position": c.role,
                "score": c.score,
                "status": c.status,
                "date": c.date
            })
            
        return jsonify({"candidates": output}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/send_bulk_emails', methods=['POST'])
@login_required
def send_bulk_emails():
    data = request.get_json()
    emails = data.get('emails', [])
    subject = data.get('subject')
    body = data.get('body')

    if not emails:
        return jsonify({"error": "No recipients selected"}), 400

    try:
        with mail.connect() as conn:
            for email in emails:
                msg = Message(
                    subject=subject,
                    recipients=[email.strip()],
                    body=body
                )
                conn.send(msg)
        return jsonify({"message": f"Successfully sent to {len(emails)} candidates!"}), 200
    except Exception as e:
        print(f"❌ Mail Error: {e}")
        return jsonify({"error": "Failed to send emails. Check your Gmail App Password."}), 500

@app.route('/delete_candidates', methods=['POST'])
def delete_candidates():
    data = request.json
    candidate_ids = data.get('ids', [])
    
    try:
        # 1. Database se records filter karke delete karein
        # 'CandidateResult' aapki class ka naam hoga
        CandidateResult.query.filter(CandidateResult.id.in_(candidate_ids)).delete(synchronize_session=False)
        
        # 2. Changes ko SAVE (Commit) karein - Iske bina delete nahi hoga!
        db.session.commit()
        
        return jsonify({"message": "Successfully deleted"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/add_candidate_manual', methods=['POST'])
@login_required
def add_candidate_manual():
    try:
        # 1. Form Data Capture
        name = request.form.get('name')
        email_from_form = request.form.get('email')
        pos_from_form = request.form.get('position') # Job description ki tarah treat karenge similarity ke liye
        file = request.files.get('resume')

        if not file:
            return jsonify({"error": "No resume file uploaded"}), 400

        # 2. File Save
        filename = secure_filename(f"{name}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # 3. PDF se Text Extract karna
        resume_text = ""
        reader = PdfReader(file_path)
        for page in reader.pages:
            resume_text += page.extract_text() or ""

        # 4. --- ASLI AI BRAIN (Wahi functions jo analyze_candidates mein hain) ---
        
        # Dashboard wala similarity logic
        jd_doc = nlp(pos_from_form) # Jo position select ki hai usey hi JD maan lete hain
        resume_doc = nlp(resume_text)
        similarity = jd_doc.similarity(resume_doc)
        match_percentage = int(similarity * 100)

        # Aapke helper functions call karein
        actual_email = extract_email(resume_text) or email_from_form # Agar PDF mein mile toh wo, warna form wala
        actual_exp = calculate_total_experience(resume_text)
        actual_position, skills_list = extract_dynamic_info(resume_text)

        # 5. Database Entry (CandidateResult class use karke)
        new_result = CandidateResult(
            candidate_name=name,
            filename=filename,
            email=actual_email,
            position=pos_from_form[:50], # Aapne form mein jo select kiya wahi dikhana best hai
            experience=actual_exp,
            skills=json.dumps(skills_list), # Dashboard ki tarah JSON format mein
            score=f"{match_percentage}%",
            status="Excellent Match" if match_percentage >= 80 else "Good Match" if match_percentage >= 60 else "Potential Match",
            upload_date=datetime.now().strftime("%Y-%m-%d")
        )

        db.session.add(new_result)
        db.session.commit()

        return jsonify({"message": "AI Analysis Complete & Candidate Added!"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Manual Add Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate_dossier', methods=['POST'])
def generate_dossier():
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        # 1. Database se candidates uthao
        candidates = CandidateResult.query.filter(CandidateResult.id.in_(ids)).all()
        
        # 2. SMART RANKING: Score ke basis par sort karo (High to Low)
        # Hum score se '%' hata kar integer mein convert kar rahe hain sorting ke liye
        ranked = sorted(candidates, key=lambda x: int(str(x.score).replace('%', '') or 0), reverse=True)

        writer = PdfWriter()

        # --- 3. PROFESSIONAL SUMMARY PAGE (Page 1) ---
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        
        # Header
        can.setFont("Helvetica-Bold", 22)
        can.setFillColorRGB(0.02, 0.2, 0.22) # Dark theme color
        can.drawString(50, 750, "Selection Dossier: AI Smart Ranking")
        
        can.setStrokeColorRGB(0.8, 0.8, 0.8)
        can.line(50, 740, 550, 740)
        
        # Table Headers
        can.setFont("Helvetica-Bold", 12)
        can.setFillColorRGB(0, 0, 0)
        can.drawString(50, 710, "Rank")
        can.drawString(100, 710, "Candidate Name")
        can.drawString(300, 710, "Position")
        can.drawString(480, 710, "Match Score")
        can.line(50, 705, 550, 705)

        # 4. YAHAN HAI MAIN LOGIC - Ranked Candidates ka Loop
        y = 680
        for i, c in enumerate(ranked):
            can.setFont("Helvetica", 11)
            
            # Rank with Medal Style Text
            rank_text = f"#{i+1}"
            if i == 0: rank_text = "🥇 #1"
            elif i == 1: rank_text = "🥈 #2"
            elif i == 2: rank_text = "🥉 #3"
            
            can.drawString(50, y, rank_text)
            can.drawString(100, y, str(c.candidate_name))
            can.drawString(300, y, str(c.position))
            
            # Score Highlight
            score_val = str(c.score)
            can.setFont("Helvetica-Bold", 11)
            can.drawString(480, y, score_val)
            
            y -= 30 # Agli line ke liye niche jao
            
            # Agar candidates zyada hain toh line draw karo
            can.setStrokeColorRGB(0.9, 0.9, 0.9)
            can.line(50, y+10, 550, y+10)
            
            if y < 50: # Page bhar gaya toh break
                break

        can.save()
        packet.seek(0)
        writer.add_page(PdfReader(packet).pages[0])

        # --- 5. MERGE RESUMES (Page 2 onwards) ---
        for c in ranked:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], c.filename)
            if os.path.exists(file_path):
                try:
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        writer.add_page(page)
                except:
                    continue 

        # Final Response
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        return send_file(output, as_attachment=True, download_name="Smart_Selection_Dossier.pdf", mimetype='application/pdf')

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/export_all_candidates')
def export_all_candidates():
    # 1. Database se saara data fetch karo
    candidates = CandidateResult.query.all()
    
    # 2. CSV ki memory file taiyar karo
    si = StringIO()
    cw = csv.writer(si)
    
    # Header likho
    cw.writerow(['Name', 'Email', 'Position', 'Experience', 'Score', 'Status'])
    
    # Data likho
    for c in candidates:
        cw.writerow([
            c.candidate_name, 
            c.email, 
            c.position, 
            c.experience, 
            c.score, 
            c.status
        ])
    
    # 3. Response taiyar karo
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=All_Candidates_{datetime.now().strftime('%Y-%m-%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    try:
        user_id = current_user.id
        
        # 1. Pehle UserProfile udaao (Jo admin panel mein job_title/phone dikha raha hai)
        # Kyunki p.user_id = u.id hai
        UserProfile.query.filter_by(user_id=user_id).delete()
        
        # 2. Agar is user ne koi candidates scan kiye hain, unhe bhi hatao
        # (Nahi toh Integrity Error aayega)
        try:
            from app import CandidateResult # Agar model ka naam yahi hai
            CandidateResult.query.filter_by(user_id=user_id).delete()
        except:
            pass

        # 3. Ab Main User (Login Table) udaao
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
        
        # 4. Final Save (Iske bina delete nahi hoga)
        db.session.commit()
        
        # 5. Logout and Clear everything
        logout_user()
        session.clear()
        
        return jsonify({"status": "success", "message": "Permanently deleted from all tables"})

    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Delete failed due to: {str(e)}") # Apne terminal mein error dekho
        return jsonify({"status": "error", "message": str(e)}), 500



if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(debug=True, port=8000)