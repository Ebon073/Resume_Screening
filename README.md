# Resume Screening Helper using ATS System

## Overview
This project is an AI-powered Resume Screening System built using Streamlit.  
It helps HR teams automatically screen, rank, and shortlist candidates based on skills and experience.



## Features
- Upload resumes (PDF/DOCX)
- Extracts name, email, phone, experience
- AI-based skill matching using NLP (spaCy)
- ATS scoring system (skills + experience + keywords)
- Candidate ranking system
- Separate view for qualified and junior candidates
- Download shortlisted results as CSV



##  Tech Stack
- Python
- Streamlit
- spaCy
- pandas
- pdfplumber
- python-docx



##  How to Run

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py