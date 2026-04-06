class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:YOURSQLPASSWORD@localhost/smart_recruiter_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'super_secret_key'


    # Email Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'YOUR GMAILID@gmail.com'  # Your gmail address
    MAIL_PASSWORD = 'your APP PASSWORD'  # Your gmail app password (generate this from your Google Account settings)
    MAIL_DEFAULT_SENDER = ('TechNova Solutions Pvt. Ltd.', 'your-email@gmail.com') #Your company name and email
    
    GROQ_API_KEY = "ENTER YOUR GROG API KEY" #your grog api key