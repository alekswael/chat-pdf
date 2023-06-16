import numpy as np
from flask_cors import CORS
from flask import Flask, jsonify, request, Response, stream_with_context, session
from flask_session import Session
from .database import db
from .readpdf import read_from_encode
from .qa_tool import QaTool
import json

import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://hybridintelligence.eu"}})

# check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
# initialize the app with Flask-SQLAlchemy
db.init_app(app)
with app.app_context():
    db.create_all()

qa_tool = QaTool()

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "sqlalchemy"

Session(app)

@app.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:8080'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
    return response

@app.route('/api/load-pdf/', methods=['POST', 'OPTIONS'])
def load_pdf():
    author = request.form.get('author')
    file_id = request.form.get('documentId')
    namespace = request.form.get('namespace')
    title = request.form.get('name')
    file = request.files['file']
    if not (author and file_id and namespace and file):
        return "Missing file or fileInfo", 401

    if qa_tool.namespace is None:
        qa_tool.set_namespace(namespace)
        session['namespace'] = namespace
        print(session)
    try:
        df = read_from_encode(file, author, file_id, namespace, title)
    except Exception as e:
        raise e
        return "Bad request", 402

    qa_tool.loading_data_to_pinecone(df)
    return f"Successfully loaded {file_id} to pinecone", 200

@app.route('/api/ask-query/', methods=['POST'])
def ask_query():
    if qa_tool.namespace != session['namespace']:
        qa_tool.set_namespace(session['namespace'])
    data = request.get_json()
    print(data)
    top_closest = 5
    result = qa_tool(query=data['query'],top_closest=top_closest)
    print(result.keys())
    content = []
    for doc in result['source_documents']:
        content.append((doc.page_content, doc.metadata['title']))
    response = {"result": result['result'], "source_documents": content}
    return response, 200

    
@app.route('/api/erase-all/', methods=['GET'])
def erase_all():
    qa_tool.delete_all()
    qa_tool.namespace = None
    session['namespace'] = None
    print(session)
    return "Successfully deleted all data", 200

@app.route('/api/hello/', methods=['GET'])
def hello():
    return "Hello world", 200

