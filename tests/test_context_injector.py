import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory.context_injector import build_memory_context

context = build_memory_context()
if context:
    print(context)
else:
    print("No memory context available.")