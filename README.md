# 🤖 Smart Recruiter AI — Intelligent Recruitment System

An AI-powered recruitment platform built with **Flask**, **spaCy NLP**, and **MySQL** that automates resume screening, candidate ranking, skill analysis, and interview question generation — all in one system.

---

## 🌟 Features

### 🧠 AI & NLP Core
- **Resume Parsing** — Extracts candidate name, email, experience, and skills from uploaded PDF resumes
- **Job-Resume Matching** — Uses spaCy `en_core_web_md` NLP model to calculate similarity score between job description and each resume
- **Dynamic Skill Extraction** — Automatically detects 30+ tech skills from resume text
- **Experience Calculator** — Parses date ranges from resumes to compute total work experience
- **AI Interview Questions** — Generates customized interview questions using **Groq LLM API** (Llama 3.3 70B)

### 👤 HR User
- Upload multiple resumes at once for batch analysis
- View AI match scores for all candidates
- Filter and search applicants by name, position, or skill
- View detailed match score breakdown per candidate
- View skill heatmap comparing candidate pool vs job requirements
- Generate a **Selection Dossier PDF** — a ranked, merged resume bundle
- Export all candidates to **CSV**
- Send bulk emails to selected candidates
- Manage profile, theme, and notification preferences

### 👨‍💼 Admin
- Admin Control Center with live analytics dashboard
- View all registered users with their roles and profiles
- Add, update, and delete users
- View system logs (candidate processing + user registration activity)
- Monitor daily resume upload stats via Chart.js graph

### 🔐 Authentication
- Role-based login — **Admin** and **HR User**
- Register new users with role selection
- Secure session management via Flask-Login
- Password change with current password verification
- Profile photo upload

---

## 🛠️ Tech Stack

| Layer           | Technology                                      |
|-----------------|-------------------------------------------------|
| Backend         | Python, Flask, Flask-Login, Flask-SQLAlchemy    |
| AI / NLP        | spaCy (`en_core_web_md`), Groq API (Llama 3.3) |
| Database        | MySQL (via PyMySQL + SQLAlchemy ORM)            |
| Frontend        | HTML, CSS, Bootstrap 5, JavaScript, Chart.js    |
| PDF Processing  | PyPDF2, pypdf, ReportLab                        |
| Email           | Flask-Mail (Gmail SMTP)                         |
| Forms & Security| Werkzeug Security, secure_filename              |
| Other           | python-dateutil, csv, json                      |

---

## 📁 Project Structure

```
smart-recruitement-system/
│
├── app.py                    # Main Flask app — all routes & business logic
├── config.py                 # DB, mail, and secret key configuration
├── requirements.txt          # Python dependencies
│
├── modules/
│   ├── analysis.py           # Resume analysis logic
│   ├── ranking.py            # Candidate ranking logic
│   └── generator.py          # Question generation logic
│
├── static/
│   ├── css/
│   │   └── style.css         # Custom styles
│   ├── js/                   # Frontend JS
│   ├── images/
│   │   └── hero-bg.jpg       # Landing page background
│   └── uploads/              # Uploaded resumes & profile photos
│
└── templates/
    ├── index.html            # Landing / Home page
    ├── login.html            # Login page
    ├── register.html         # Registration page
    ├── navbar.html           # Shared navigation bar
    ├── dashboard.html        # HR user dashboard
    ├── upload.html           # Resume upload & JD input
    ├── applicants.html       # Applicants list with search & pagination
    ├── results.html          # AI analysis results
    ├── match_score.html      # Detailed candidate match breakdown
    ├── skill_heatmap.html    # Skill gap visualization (Chart.js)
    ├── settings.html         # User settings & profile management
    ├── admin.html            # Admin panel
    └── admin_dashboard.html  # Admin control center
```

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.8+
- MySQL Server
- pip

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/smart-recruitement-system.git
cd smart-recruitement-system
```

### 2. Create & Activate Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the spaCy NLP Model

```bash
python -m spacy download en_core_web_md
```

> The app will also attempt to auto-download this model on first run if not found.

### 5. Set Up the Database

Open MySQL and create the database:

```sql
CREATE DATABASE smart_recruiter_db;
```

Then let Flask auto-create tables on first run (handled by `db.create_all()` in `app.py`).

### 6. Configure the App

Edit `config.py` with your own credentials:

```python
class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:YOUR_PASSWORD@localhost/smart_recruiter_db'
    SECRET_KEY = 'your-secret-key'

    MAIL_USERNAME = 'your-email@gmail.com'
    MAIL_PASSWORD = 'your-gmail-app-password'
    MAIL_DEFAULT_SENDER = ('Your Company Name', 'your-email@gmail.com')
```

> ⚠️ **Never commit real credentials to GitHub!** Use environment variables or add `config.py` to `.gitignore`.

### 7. Run the Application

```bash
python app.py
```

Visit `http://127.0.0.1:8000` in your browser.

---

## 🗄️ Database Models

| Model             | Description                                            |
|-------------------|--------------------------------------------------------|
| `User`            | Login accounts with role (admin / user)                |
| `UserProfile`     | Extended profile info, preferences, and profile photo  |
| `CandidateResult` | Analyzed resume data — skills, score, status, etc.     |
| `Candidate`       | Basic candidate record (name, email, role, score)      |
| `JobRole`         | Available job roles for dropdown selection             |
| `Notification`    | Per-user in-app notifications                          |

---

## 🔑 User Roles

| Role  | Access                                                   |
|-------|----------------------------------------------------------|
| Admin | Full access — user management, analytics, system logs   |
| User  | HR features — resume upload, analysis, applicant views  |

**To create an Admin:** Register normally, then update `role = 'admin'` in the `user` table directly in MySQL.

---

## 🤖 AI Features In Detail

### Resume Matching (spaCy NLP)
- Job description is converted to a spaCy `Doc` object
- Each uploaded resume is parsed and also converted to a `Doc`
- Cosine similarity is computed → converted to a match percentage
- Candidates are labeled: **Excellent Match** (≥80%), **Good Match** (≥60%), **Potential Match** (<60%)

### Interview Question Generation (Groq API)
- Uses **Llama 3.3 70B** model via Groq API
- HR selects: job role, question type (Technical/Behavioral/etc.), difficulty, and count
- Returns structured JSON questions rendered in the UI

### Skill Heatmap
- Aggregates skills across all candidates in the database
- Compares against the job description skills
- Visualizes demand vs. availability gap using Chart.js

### Smart Selection Dossier (PDF Export)
- Ranks selected candidates by match score
- Creates a formatted summary page with medal-style rank indicators
- Merges individual resumes into a single downloadable PDF

---

## 📧 Gmail Setup for Bulk Email

1. Enable **2-Step Verification** on your Gmail account
2. Go to **Google Account → Security → App Passwords**
3. Generate an App Password
4. Paste it as `MAIL_PASSWORD` in `config.py`

---

## 📌 Key API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page |
| `/login` | GET/POST | Login |
| `/register` | GET/POST | Registration |
| `/dashboard` | GET | HR dashboard |
| `/analyze_candidates` | POST | Upload & analyze resumes |
| `/applicants` | GET | Paginated applicant list |
| `/match_score/<id>` | GET | Detailed match breakdown |
| `/skill_heatmap` | GET | Skill gap chart |
| `/generate_questions` | POST | AI interview questions |
| `/generate_dossier` | POST | Export ranked PDF |
| `/export_all_candidates` | GET | Download CSV |
| `/send_bulk_emails` | POST | Email selected candidates |
| `/admin_dashboard` | GET | Admin control center |
| `/admin/users` | GET | List all users (JSON) |
| `/admin/add_user` | POST | Add new user |
| `/admin/delete_user/<id>` | POST | Delete user |
| `/api/admin/stats` | GET | Admin stats (JSON) |

---

## 🚀 Future Improvements

- [ ] ATS-style resume scoring with weighted criteria
- [ ] Calendar integration for scheduling interviews
- [ ] LinkedIn profile import for candidates
- [ ] Role-based job posting management
- [ ] Multi-language resume support
- [ ] Feedback loop to improve AI matching over time

## 👨‍💻 Author
Mansi Jadhav 
GitHub: (https://github.com/mansijadhav-16)
