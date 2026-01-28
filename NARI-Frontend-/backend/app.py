"""
NARI Backend - Flask API Server (Integrated with Nova LLM)
Provides REST API for chat with NARI's full LLM client, memory, and tools.
"""

import sys
import os
import asyncio

# Add Nova project to path for imports
NOVA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Nova-Long-Horizon-Agentic-Ai'))
sys.path.insert(0, NOVA_PATH)

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from models import db, Chat, Message, UploadedFile

# Import Nova LLM components
from config import Config, get_config, reload_config
from llm_client import get_client, Message as LLMMessage, LLMResponse
from mem_0 import get_memory_service, MemoryType
from tools import registry, execute_tool_call

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nari.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database
db.init_app(app)

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Nova components
config = None
llm_client = None
memory_service = None

def init_nova():
    """Initialize Nova LLM components."""
    global config, llm_client, memory_service
    
    # Load config from Nova's .env
    os.chdir(NOVA_PATH)
    config = reload_config()
    os.chdir(os.path.dirname(__file__))
    
    llm_client = get_client(config=config)
    memory_service = get_memory_service(config=config)
    
    print(f"Nova initialized: Provider={config.default_provider.value}, Model={config.current_model}")
    print(f"Memory enabled: {memory_service.is_enabled}")


# =============================================================================
# Chat History Endpoints
# =============================================================================

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get all chat history."""
    chats = Chat.query.order_by(Chat.updated_at.desc()).all()
    return jsonify([chat.to_dict() for chat in chats])


@app.route('/api/history', methods=['POST'])
def save_history():
    """Save or sync chat history."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    chats_data = data if isinstance(data, list) else [data]
    
    saved_chats = []
    for chat_data in chats_data:
        chat_id = chat_data.get('id')
        
        if chat_id:
            chat = Chat.query.get(chat_id)
            if not chat:
                chat = Chat(id=chat_id, title=chat_data.get('title', 'New Chat'))
                db.session.add(chat)
        else:
            chat = Chat(title=chat_data.get('title', 'New Chat'))
            db.session.add(chat)
        
        chat.title = chat_data.get('title', chat.title)
        
        # Handle messages
        messages_data = chat_data.get('messages', [])
        Message.query.filter_by(chat_id=chat.id).delete()
        
        for msg_data in messages_data:
            msg = Message(
                chat_id=chat.id,
                role=msg_data.get('role', 'user'),
                content=msg_data.get('content', '')
            )
            db.session.add(msg)
        
        saved_chats.append(chat)
    
    db.session.commit()
    return jsonify([chat.to_dict() for chat in saved_chats])


@app.route('/api/history/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Delete a specific chat."""
    chat = Chat.query.get(chat_id)
    
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    db.session.delete(chat)
    db.session.commit()
    
    return jsonify({'success': True, 'deleted_id': chat_id})


# =============================================================================
# Chat/AI Endpoint using Nova LLM Client
# =============================================================================

@app.route('/api/chat', methods=['POST'])
def chat():
    """Send message and get AI response using Nova LLM client."""
    data = request.get_json()
    
    if not data or 'text' not in data:
        return jsonify({'error': 'No message text provided'}), 400
    
    user_text = data.get('text', '')
    model_type = data.get('model', 'Fast')  # 'Fast' or 'Thinking'
    chat_id = data.get('chat_id')
    
    try:
        # Build messages for LLM
        messages = []
        
        # Get memory context
        memory_context = ""
        if memory_service and memory_service.is_enabled:
            memory_context = memory_service.get_memory_context(
                query=user_text,
                user_id=config.memory_user_id,
                max_memories=5,
            )
        
        # System message with memory
        system_content = llm_client.system_instruction
        if memory_context:
            system_content += f"\n\n## Your Memories About This User:\n{memory_context}"
        
        messages.append(LLMMessage(role="system", content=system_content))
        
        # Load chat history if chat_id provided
        if chat_id:
            db_chat = Chat.query.get(chat_id)
            if db_chat:
                for msg in db_chat.messages:
                    messages.append(LLMMessage(
                        role=msg.role if msg.role != 'ai' else 'assistant',
                        content=msg.content
                    ))
        
        # Add current user message
        messages.append(LLMMessage(role="user", content=user_text))
        
        # Get tools
        tools = registry.get_tools_for_llm()
        
        # Call LLM asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        response: LLMResponse = loop.run_until_complete(
            llm_client.chat(messages, tools=tools, stream=False)
        )
        
        ai_content = response.content
        
        # Handle tool calls if any
        if response.tool_calls:
            tool_results = []
            for tc in response.tool_calls:
                result = execute_tool_call(tc)
                tool_results.append({
                    'tool': tc.get('name', ''),
                    'result': result[:500] if len(result) > 500 else result
                })
                
                # Add tool response to messages
                messages.append(LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls
                ))
                messages.append(LLMMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tc.get('id', ''),
                    name=tc.get('name', '')
                ))
            
            # Get follow-up response
            follow_up: LLMResponse = loop.run_until_complete(
                llm_client.chat(messages, tools=tools, stream=False)
            )
            ai_content = follow_up.content
        
        loop.close()
        
        # Extract and store memories
        if memory_service and memory_service.is_enabled and config.memory_auto_extract:
            memory_service.extract_and_store(
                user_input=user_text,
                assistant_response=ai_content,
                user_id=config.memory_user_id,
            )
        
        return jsonify({
            'content': ai_content,
            'model': config.current_model,
            'provider': config.default_provider.value,
            'processSteps': model_type == 'Thinking'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'content': f'Sorry, an error occurred: {str(e)}'
        }), 500


# =============================================================================
# Memory Endpoints
# =============================================================================

@app.route('/api/memories', methods=['GET'])
def get_memories():
    """Get user memories."""
    if not memory_service or not memory_service.is_enabled:
        return jsonify({'error': 'Memory service not enabled'}), 503
    
    query = request.args.get('query', '')
    
    if query:
        memories = memory_service.search(
            query=query,
            user_id=config.memory_user_id,
            limit=10
        )
    else:
        memories = memory_service.get_all(
            user_id=config.memory_user_id,
            limit=20
        )
    
    return jsonify([{
        'id': m.id,
        'content': m.content,
        'type': m.memory_type.value,
        'created_at': m.created_at.isoformat() if m.created_at else None
    } for m in memories])


# =============================================================================
# File Upload Endpoint
# =============================================================================

ALLOWED_EXTENSIONS = {
    'document': {'pdf', 'doc', 'docx', 'txt', 'md'},
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'},
    'code': {'js', 'py', 'java', 'cpp', 'c', 'html', 'css', 'json', 'xml', 'ts', 'tsx'}
}


def allowed_file(filename, file_type):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS.get(file_type, set())


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_type = request.form.get('type', 'document')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename, file_type):
        return jsonify({'error': f'File type not allowed for {file_type}'}), 400
    
    filename = secure_filename(file.filename)
    
    import time
    unique_filename = f"{int(time.time())}_{filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    file.save(file_path)
    file_size = os.path.getsize(file_path)
    
    uploaded_file = UploadedFile(
        filename=filename,
        file_type=file_type,
        file_path=file_path,
        file_size=file_size
    )
    db.session.add(uploaded_file)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'fileId': uploaded_file.id,
        'filename': filename,
        'file_type': file_type,
        'file_size': file_size
    })


# =============================================================================
# Health Check
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'provider': config.default_provider.value if config else 'unknown',
        'model': config.current_model if config else 'unknown',
        'memory_enabled': memory_service.is_enabled if memory_service else False
    })


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database initialized!")
    
    init_nova()
    
    print(f"Starting NARI Backend on http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
