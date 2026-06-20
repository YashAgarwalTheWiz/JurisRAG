from pydantic import BaseModel
from typing import List
from config import GROQ_API_KEY
from langchain_groq import ChatGroq

class SectionMention(BaseModel):
    number:str
    act_name:str

class CaseExtraction(BaseModel):
    cited_cases:List[str]
    acts:List[str]
    sections:List[SectionMention]
    judges:List[str]

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
structured_llm = llm.with_structured_output(CaseExtraction)

def extract(text):
    
    prompt=f'''
    You are a legal information extraction system. Given the full text of an Indian Supreme Court judgment, extract the following:

    1. cited_cases: Case IDs of all cases explicitly cited. Format strictly as year_casenumber (e.g. 2019_890). Only include cases where both year and case number are clearly identifiable.

    2. acts: Full names of all Acts explicitly mentioned in the text (e.g. "Indian Penal Code", "Arbitration and Conciliation Act").

    3. sections: All sections explicitly mentioned. For each, extract:
    - number: the section number as a string (e.g. "302", "25A")
    - act_name: the Act that section belongs to

    4. judges: Full names of all judges who presided over this case.

    Extract only what is explicitly stated in the text. Do not infer, guess, or hallucinate values.

    Case text:
    {text}
    '''
    result = structured_llm.invoke(prompt)
    return result