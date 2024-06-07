from flask import Flask, render_template, request, redirect, session, url_for
import pyrebase
from firebase_config import firebaseConfig
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import os
from werkzeug.utils import secure_filename
import glob
from flask import jsonify
import whisper
from pytube import YouTube
from pypdf import PdfReader
import google.generativeai as genai


# Initialize Flask app
app = Flask(__name__)
app.secret_key = "Afdgdfgdg1f5G3H4dft4sdrH"
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Configure Firebase
cred = credentials.Certificate('[path to your creditials of firebase]')
firebase_admin.initialize_app(cred, {
    'databaseURL': '[link of databaseURL provided by firebase]',
    'storageBucket': '[link of storageBucket provided by firebase]'
})
# gemini-api-key
genai.configure(api_key= "[api key by gemini-api]")

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
token = ""
video_link = ""
filename = ""


# Create a reference to the database
ref = db.reference('/')

# Question Generator
def generate_questions(text_output):
    try:
        model = genai.GenerativeModel('gemini-pro')
        data = []
        data.append(text_output)
        data.append("Generate 10 descriptive type questions from given content in the python dictionary format(question as key and answer as value in string).")
        messages = [{'role':'user','parts': data}]
        response = model.generate_content(messages)
        question_data = response.text.strip("```").split("=")[1].strip().strip("{").strip("}").strip()
        result = question_card(question_data)
        return result
    except Exception as e:
        print("The error is: ",e)
        return generate_questions(text_output)

def question_card(data):
    question = data.split("\"")
    question = [item.strip(',\n  : ') for item in question if item.strip()]
    question = [item for item in question if (item!='' and item!=':')]
    question_array = []
    for i in range(0,len(question),2):
        pair = []
        pair.append(question[i])
        pair.append(question[i+1])
        question_array.append(pair)
    return question_array


# Routes
@app.route('/')
def home():
    if 'user' in session:
        return render_template('home.html',user=session['user'])
    else:
        return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    global token
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = user['email']
            result = firebase.auth().sign_in_with_email_and_password(email,password)
            token = result.get('localId')
            return redirect('/')
        except Exception as e:
            error_message = "Invalid email or password. Please try again."
            return render_template('login.html', error=error_message)
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    global token
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        sex = request.form['sex']
        age = request.form['age']
        try:
            user = auth.create_user_with_email_and_password(email, password)
            user_data = {"name": name, "sex": sex, "age": age, "email": email}
            result = firebase.auth().sign_in_with_email_and_password(email,password)
            token = result.get('localId')
            ref.child("users").child(token).push(user_data)
            session['user'] = email
            return redirect('/')
        except Exception as e:
            error_message = "Failed to create account. Please try again. Note: Please enter password atleast of 6 character."
            return render_template('signup.html', error=error_message)

    return render_template('signup.html')

@app.route('/process_video', methods=['POST'])
def process_video():
    global token
    link = request.form['youtube_link']
    ref.child("users").child(token).child('link').push(link)
    return redirect(url_for('video'))

@app.route('/video')
def video():
    global token
    global video_link
    links = ref.child("users").child(token).child('link').get()
    for key, value in links.items():
        pass
    video_link = value
    if "watch" in video_link:
        video_link = "embed/".join(video_link.split("watch?v="))
    elif "u.b" in video_link:
        video_link = "https://www.youtube.com/embed/" + video_link.split("be/")[1].split("?")[0]
    return render_template('video.html', link=video_link)

def video_questions2():
    try: 
        global video_link
        yt = YouTube(video_link) 
        video = yt.streams.filter(only_audio=True).first()
        destination = './static/youtube_videos'
        out_file = video.download(output_path=destination) 
        os.rename(out_file, "static/youtube_videos/audio.mp3") 
        model = whisper.load_model("base")
        result = model.transcribe("static/youtube_videos/audio.mp3")
        return generate_questions(result["text"])
    except Exception as e:
        print("The error is: ",e)
        video_questions2()

@app.route('/video_questions')
def video_questions():
    text = video_questions2()
    return jsonify({'questions': text}) 


@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    global filename
    file = request.files['pdf_file']
    filename = file.filename
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return redirect(url_for('pdf', filename=filename))

@app.route('/pdf/<filename>')
def pdf(filename):
    return render_template('pdf.html', filename=filename)

@app.route('/pdf_questions')
def pdf_questions():
    global filename
    filepath = "static/uploads/" + filename
    print(filepath)
    reader = PdfReader(filepath)
    temp = ""
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        temp += page.extract_text()
    text = generate_questions(temp)
    return jsonify({'questions': text})

@app.route('/logout')
def logout():
    for file in glob.glob('static/uploads/*'):
        os.remove(file)
    for file in glob.glob('static/youtube_videos/*'):
        os.remove(file)
    session.pop('user', None)
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True, port=8001)
