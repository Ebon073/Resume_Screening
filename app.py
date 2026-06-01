import streamlit as st
import pandas as pd
import pdfplumber
import docx
import re
import os
import smtplib
from email.mime.text import MIMEText
import spacy
import time
import tempfile
import random
import json
from string import Template

with open("skill.json", "r") as f:
    skill_aliases = json.load(f)


@st.cache_resource
def load_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


nlp = load_nlp()

WEIGHTS = {"skills": 0.7, "experience": 0.2, "keyword_bonus": 0.1}

STRONG_KEYWORDS = [
    "project",
    "developed",
    "engineer",
    "machine learning",
    "api",
    "system",
    "architecture",
    "design",
    "deployment",
    "optimization",
]


def _normalize_alias(alias):
    return re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip()


def _build_skill_alias_tokens(aliases):
    return [
        tuple(_normalize_alias(alias).split()) for alias in aliases if alias.strip()
    ]


def extract_name(txt):
    
    if nlp is None:
        return "Candidate"

    doc = nlp(txt)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text

    return "Candidate"


def _build_skill_token_map():
    token_map = {}
    for skill, aliases in skill_aliases.items():
        token_map[skill] = _build_skill_alias_tokens(aliases)
    return token_map


@st.cache_data
def get_skill_tokens():
    return _build_skill_token_map()


SKILL_ALIAS_TOKENS = get_skill_tokens()

# MAX_ALIAS_WORDS = max(
#   (len(tokens) for aliases in SKILL_ALIAS_TOKENS.values() for tokens in aliases),
#   default=1, )


def _normalize_text(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def pdf_txt(file):
    try:
        with pdfplumber.open(file) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def docx_txt(file):
    try:
        doc = docx.Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def save_uploaded_file(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        return tmp.name


def ats_score(txt, doc, req_skills, cand_exp, req_exp):
    txt_norm = _normalize_text(txt)

    tokens_set = set(t.lemma_.lower() for t in doc if t.is_alpha)

    matched_skills = []

    skill_score = 0

    # txt_lower = txt.lower()

    for sk in req_skills:
        found = False

        for alias_tokens in SKILL_ALIAS_TOKENS.get(sk, []):
            phrase = " ".join(alias_tokens)
            if phrase in txt_norm:
                found = True
                break
        if found:
            skill_score += 1
            matched_skills.append(sk)

    skill_score = (skill_score / len(req_skills)) * 100 if req_skills else 0

    exp_score = 100 if req_exp == 0 else min((cand_exp / req_exp) * 100, 100)

    keyword_hits = 0

    for keyword in STRONG_KEYWORDS:
        keyword_tokens = keyword.lower().split()

        # multi-word keyword support (e.g., "machine learning")
        if all(tok in tokens_set for tok in keyword_tokens):
            keyword_hits += 1

    keyword_score = min(keyword_hits * 10, 100)

    final_score = (
        WEIGHTS["skills"] * skill_score
        + WEIGHTS["experience"] * exp_score
        + WEIGHTS["keyword_bonus"] * keyword_score
    )

    return round(final_score, 2), matched_skills


def is_valid_email(email):
    return (
        re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-.]+)?$", email)
        is not None
    )


st.set_page_config(page_title="Resume Screening Helper", layout="wide")


def send_email(sender, password, receiver, subject, body):

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)

        server.ehlo()
        server.starttls()
        server.ehlo()

        server.login(sender, password)

        server.send_message(msg)

        server.quit()

        return True

    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False


st.title("Resume Screening Helper")

st.sidebar.header("Job Requirements")

sk_in = st.sidebar.text_area("Required Skills (comma separated)", " ")

req_sk = [sk.strip() for sk in sk_in.split(",") if sk.strip()]

req_exp = st.sidebar.number_input("Required Experience (Years)", min_value=0)

min_score = st.sidebar.slider("Minimum Compatibility (%)", 0, 100, 75)

max_candidates = st.sidebar.number_input(
    "Maximum Candidates To Invite", min_value=1, value=100
)

#company_email = os.getenv("COMPANY_EMAIL", st.sidebar.text_input("Company Email"))

company_email = st.sidebar.text_input(
    "Company Email",
    key="company_email"
)

company_password = st.sidebar.text_input(
    "Company Email Password",
    type="password",
    key="company_password"
)

email_subject = st.sidebar.text_input("Email Subject", value="Interview Invitation")

default_message = """
Mr/Mrs Candidate,

Congratulations!

We are pleased to inform you that your resume has been shortlisted for the next stage of our company hiring process. 
We were impressed with your qualifications and experience, and we would like to invite you for next steps in our recruitment process. 
we will be in touch with you shortly to provide further details about the  next steps and shedule for it.

Regards,
HR Team
"""

email_body = st.sidebar.text_area(
    "Invitation Message", value=default_message, height=200
)

folder_path = st.text_input(" Enter resume folder path ")

up_files = st.file_uploader(
    "Upload Resume Files", type=["pdf", "docx"], accept_multiple_files=True
)


def extract_profile(txt):
    # email
    em_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-.]+)?", txt)
    email = em_match.group(0) if em_match else "Not Found"

    # phone (India format)
    ph_match = re.search(r"(\+91[\-\s]?)?[6-9]\d{9}", txt)
    phone = ph_match.group(0) if ph_match else "Not Found"

    # experience
    exp_match = re.search(r"(\d+)\+?\s*(years|year|yrs|yr)", txt.lower())
    experience = int(exp_match.group(1)) if exp_match else 0

    warning = ""

    if experience > 60:

        warning = "Experience value seems unusually high. Capping at 60 years to avoid outliers."
        experience = 60  # cap at 60 years to avoid outliers

    return email, phone, experience, warning


if st.button("Screen Applicants"):
    st.session_state.pop("qualified_df_full", None)
    st.session_state.pop("all_applicants", None)

    all_files = []

    if up_files:
        all_files.extend(up_files)

    if folder_path:
        if os.path.exists(folder_path):
            base = os.path.realpath(folder_path)

            for f in os.listdir(folder_path):
                if not (f.endswith(".pdf") or f.endswith(".docx")):
                    continue

                full_path = os.path.realpath(os.path.join(base, f))

                # prevent path traversal
                if not full_path.startswith(base + os.sep):
                    continue

                all_files.append(full_path)

        elif os.path.exists("./" + folder_path):
            base = os.path.realpath("./" + folder_path)

            for f in os.listdir("./" + folder_path):
                if not (f.endswith(".pdf") or f.endswith(".docx")):
                    continue

                full_path = os.path.realpath(os.path.join(base, f))

                if not full_path.startswith(base + os.sep):
                    continue

                all_files.append(full_path)

        else:
            st.error("Invalid folder path")
            st.stop()

    if not all_files:
        st.warning("Please upload resumes.")
    else:
        total_resumes = len(all_files)
        res = []
        with st.spinner("Analyzing resumes..."):
            resumes = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(all_files):
                progress = int(((i + 1) / len(all_files)) * 100)
                progress_bar.progress(progress)
                status_text.text(f"Processing resume {i + 1}/{len(all_files)}")

                if isinstance(file, str):
                    file_path = file
                    f_name = os.path.basename(file)

                else:
                    file_path = save_uploaded_file(file)
                    f_name = file.name

                if f_name.lower().endswith(".pdf"):
                    txt = pdf_txt(file_path)

                elif f_name.lower().endswith(".docx"):
                    txt = docx_txt(file_path)

                else:
                    continue

                if not txt.strip():
                    continue

                # file cleanup for uploaded files
                if not isinstance(file, str):
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except PermissionError:
                        print(
                            f"Permission error while deleting {file_path}. It may be in use."
                        )
                    except Exception as e:
                        print(f"Cleanup error for {file_path}: {e}")

                resumes.append({"name": f_name, "text": txt})

            if not resumes:
                st.warning("No readable resumes found.")
                st.stop()

            docs = list(
                nlp.pipe([r["text"] for r in resumes], batch_size=100, n_process=1)
            )

            res = []

            for resume, doc in zip(resumes, docs):
                txt = resume["text"]
                f_name = resume["name"]

                email, phone, candidate_exp, warning = extract_profile(txt)
                score, matched_skills = ats_score(
                    txt, doc, req_sk, candidate_exp, req_exp
                )

                res.append(
                    {
                        "Resume name": f_name,
                        "Resume Text": txt,
                        "Compatibility (%)": score,
                        "Email": email,
                        "Phone": phone,
                        "Experience": f"{candidate_exp} Years",
                        "Experience Warning": warning,
                        "Experience Value": candidate_exp,
                        "Matched Skills": ", ".join(matched_skills),
                        "Missing Skills": ", ".join(
                            [sk for sk in req_sk if sk not in matched_skills]
                        ),
                    }
                )

        if res:
            df = pd.DataFrame(res)

            # 1. FILTER FIRST
            df = df[df["Compatibility (%)"] >= min_score].reset_index(drop=True)

            # 2. SORT
            df = df.sort_values(
                by=["Compatibility (%)", "Experience Value"], ascending=[False, False]
            ).reset_index(drop=True)

            # 3. RANKING
            df["Rank"] = range(1, len(df) + 1)

            # 4. SAVE FULL DATA (IMPORTANT)
            full_df = df.copy()

            # 5. SPLIT GROUPS
            qualified_df = df[df["Experience Value"] >= req_exp].copy()
            junior_df = df[df["Experience Value"] < req_exp].copy()

            # 6. LIMIT FOR DISPLAY
            df = df.head(max_candidates)

            # 7. NOW CREATE DISPLAY TABLES
            display_df = df.drop(columns=["Resume Text", "Experience Value"], errors="ignore")

            qualified_display = qualified_df.drop(
                columns=["Resume Text", "Experience Value"], errors="ignore"
            )

            junior_display = junior_df.drop(columns=["Resume Text", "Experience Value"], errors="ignore")

            # 8. CHECK EMPTY
            if qualified_df.empty and junior_df.empty:
                st.warning("No applicants matched the selected criteria.")

            else:
                # df.insert(0, "Rank", range(1, len(df) + 1))

                df = df.drop(columns=["Experience Value"])

                # display_df = df.drop(columns=["Resume Text"], errors="ignore") #display (hidden)

                st.info(f"Total resumes processed: {total_resumes}")
                st.info(f"Candidates shortlisted: {len(df)}")

                st.subheader("Ranked Applicants")
                st.dataframe(display_df, use_container_width=True)

                # Display qualified candidates
                st.subheader("Qualified Candidates")
                st.info("Candidates who fully meet the criteria.")
                qualified_display = qualified_df.drop(
                    columns=["Resume Text", "Experience Value"], errors="ignore"
                )

                if qualified_display.empty:
                    st.info("No candidates fully met the criteria.")
                else:
                    st.dataframe(qualified_display, use_container_width=True)

                st.subheader("Junior Candidates")
                st.info("Candidates with less experience.")
                junior_display = junior_df.drop(
                    columns=["Resume Text", "Experience Value"], errors="ignore"
                )

                if junior_display.empty:
                    st.info("No junior candidates fully met the criteria.")
                else:
                    st.dataframe(junior_display, use_container_width=True)

                st.subheader("Detailed View")

                csv = display_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Results", csv, "shortlisted_candidates.csv", "text/csv"
                )

                st.session_state["all_applicants"] = (
                    full_df.copy()
                )  # full data for invites
                st.session_state["qualified_df_full"] = (
                    full_df.copy()
                )  # full data for invites with text
                st.session_state["qualified_df_display"] = (
                    display_df.copy()
                )  # for display and download

                st.success("Screening Completed")

        else:
            st.warning("No valid resumes found.")

if st.button("Send Interview Invites"):
    if "qualified_df_full" not in st.session_state:
        st.warning("Please screen resumes first.")

    elif not company_email or not company_password:
        st.warning("Enter company email credentials.")

    else:
        success = 0

        df = st.session_state.get("qualified_df_full", None)

        if df is None or df.empty:
            st.warning("No qualified candidates to invite.")
            st.stop()

        MAX_PER_RUN = 10

        df = df.head(MAX_PER_RUN)

        for i, row in enumerate(df.itertuples(index=False)):
            success_flag = False

            email = getattr(row, "Email", None)
            email = "" if email is None else str(email).strip()

            if email and email != "Not Found" and is_valid_email(email):
                try:
                    # first attempt

                    body = Template(email_body).safe_substitute(
                        Rank=getattr(row, "Rank", "N/A"),
                        name=extract_name(getattr(row, "Resume Text", "")),
                    )

                    for attempt in range(2):  # to try twice
                        success_flag = send_email(
                            company_email, company_password, email, email_subject, body
                        )

                        if success_flag:
                            break

                        time.sleep(
                            (attempt + 1) * 10 + random.uniform(0, 10)
                        )  # wait before next attempt

                    if success_flag:
                        success += 1

                except Exception as e:
                    st.warning(f"Failed to send to {email}: {e}")

            if i > 0 and i % 5 == 0:
                time.sleep(30 + random.uniform(0, 30))

        st.success(f"{success} of {len(df)} invitation emails sent.")
