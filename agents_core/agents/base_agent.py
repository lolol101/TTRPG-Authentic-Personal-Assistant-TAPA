import os
import sys

from langchain_core.runnables import Runnable

sys.path.append(os.path.abspath(".."))
from agents_core.state import State


class BaseAgent:
    def __init__(self, llm_chain: Runnable):
        self.llm_chain = llm_chain
        
    def __call__(self, state: State):
        response = self.llm_chain.invoke(state)
        return {"messages": response}  
        