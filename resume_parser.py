import pdfplumber

SKILL_BANK = [
    "Python",
    "Java",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "HTML",
    "CSS",
    "JavaScript",
    "React",
    "Flask",
    "Django",
    "Git",
    "GitHub",
    "Excel",
    "Power BI",
    "Data Analysis",
    "Web Scraping",
    "BeautifulSoup",
    "API",
    "SEO",
    "Digital Marketing",
    "Content Writing",
    "Communication",
    "Leadership",
    "Teamwork",
    "Problem Solving"
]


def extract_text_from_pdf(pdf_path):
    text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

    except Exception:
        raise ValueError(
            "Could not read PDF. Please upload a valid text-based PDF resume."
        )

    if not text.strip():
        raise ValueError(
            "No readable text found. Please upload a text-based PDF, not a scanned image."
        )

    return text


def extract_skills(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    text_lower = text.lower()

    found_skills = []

    for skill in SKILL_BANK:
        if skill.lower() in text_lower:
            found_skills.append(skill)

    return found_skills