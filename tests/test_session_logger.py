import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory.session_logger import create_session_logger

log_queue, worker = create_session_logger()
worker.start()

# Simulate a conversation
log_queue.put({"action": "turn", "speaker": "user", "text": "Hello Aegon."})
log_queue.put({"action": "turn", "speaker": "aegon", "text": "Good evening, Sir."})
log_queue.put({"action": "turn", "speaker": "user", "text": "I am feeling stressed about work."})
log_queue.put({"action": "turn", "speaker": "aegon", "text": "Understood, Sir. How can I help?"})
log_queue.put({"action": "task", "task_text": "Remind me to call mom tomorrow.", "groq_response": "Reminder set for tomorrow, Sir."})

# End session
log_queue.put(None)
log_queue.join()

print("Session logged. Check core/memory/sessions/ for the file.")