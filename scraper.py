import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from database import insert_job, delete_all_jobs, init_db
from utils.retry import get_with_retry


BASE_URL = "https://merojob.com"
URL = "https://merojob.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_text(text):
    """
    Removes extra spaces, new lines, and bullet symbols.
    """
    if not text:
        return ""

    text = text.replace("•", " ")
    text = text.replace("\xa0", " ")
    text = text.replace("|", " | ")
    return " ".join(text.split())


def make_full_link(href):
    """
    Converts relative Merojob links into full links.
    """
    return urljoin(BASE_URL, href)


def get_text_lines(soup):
    """
    Converts page text into clean non-empty lines.
    Useful for reading sections like Skills Required.
    """
    raw_text = soup.get_text("\n", strip=True)

    lines = []
    for line in raw_text.splitlines():
        line = clean_text(line)
        if line:
            lines.append(line)

    return lines


def is_navigation_or_category(text):
    """
    Removes menu words, filter words, and category words.
    These are not real job titles or company names.
    """
    text_lower = clean_text(text).lower().strip()

    bad_words = [
        "search",
        "search jobs",
        "browse jobs",
        "blog",
        "blogs",
        "training",
        "trainings",
        "events",
        "login",
        "register",
        "for employers",
        "all jobs",
        "jobs by function",
        "jobs by title",
        "jobs by industry",
        "jobs by location",
        "jobs by organization",
        "top employers",
        "top jobs",
        "company",
        "individual jobs",
        "view all",
        "read more",
        "read more...",
        "faq",
        "payment",
        "recruitment services",
        "terms",
        "privacy",
        "contact us",
        "about us",
        "filter",
        "clear all",
        "apply filters",
        "posted today",
        "posted this week",
        "posted this month",
        "full time",
        "part time",
        "contract",
        "internship",
        "traineeship",
        "volunteer",
        "save job",
        "apply now",
        "login to apply",
        "similar jobs powered by merojob ai",
        "more jobs by this organization",
        "more jobs from this organization",
    ]

    if text_lower in bad_words:
        return True

    if len(text_lower) < 3:
        return True

    return False


def looks_like_company_name(text):
    """
    Checks if text can be treated as a company name.
    """
    text = clean_text(text)

    if not text:
        return False

    if is_navigation_or_category(text):
        return False

    if len(text) > 100:
        return False

    bad_company_words = [
        "search",
        "filter",
        "posted",
        "expired",
        "apply",
        "job",
        "jobs",
        "vacancy",
        "vacancies",
        "deadline",
        "salary",
        "experience",
        "required",
    ]

    text_lower = text.lower()

    for word in bad_company_words:
        if word in text_lower:
            return False

    return True


def is_probable_job_link(href):
    """
    Merojob job detail links usually look like:
    /frontend-developer-193

    This avoids scraping menu links, company links, blog links, etc.
    """
    if not href:
        return False

    full_link = make_full_link(href)
    parsed = urlparse(full_link)

    if "merojob.com" not in parsed.netloc:
        return False

    path = parsed.path.strip("/").lower()

    if not path:
        return False

    blocked_prefixes = [
        "search",
        "jobs",
        "job",
        "employer",
        "company",
        "blog",
        "training",
        "events",
        "login",
        "register",
        "account",
        "about",
        "contact",
        "faq",
        "terms",
        "privacy",
    ]

    for prefix in blocked_prefixes:
        if path == prefix or path.startswith(prefix + "/"):
            return False

    # Most Merojob job URLs end with a numeric id.
    return bool(re.search(r"-\d+/?$", path))


def normalize_skill(skill):
    """
    Normalizes skill names.
    """
    skill = clean_text(skill)

    skill = skill.strip(":-|,.;")
    skill_lower = skill.lower()

    mappings = {
        "css": "CSS",
        "html": "HTML",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "reactjs": "React",
        "react.js": "React",
        "ui/ux": "UI/UX",
        "ui ux": "UI/UX",
        "sql": "SQL",
        "mysql": "MySQL",
        "postgresql": "PostgreSQL",
        "git": "Git",
        "github": "GitHub",
        "seo": "SEO",
        "ms excel": "Excel",
        "microsoft excel": "Excel",
        "power bi": "Power BI",
    }

    if skill_lower in mappings:
        return mappings[skill_lower]

    # Keep common uppercase style for short technical words.
    if skill_lower in ["php", "aws", "api", "qa"]:
        return skill.upper()

    return skill.title()


def extract_skills_from_skill_section(lines):
    """
    Extracts actual skills from the 'Skills Required' section of a job detail page.

    Example section from Merojob:
    Skills Required
    Required skills for this job
    Communication
    Problem Solving
    Css
    Javascript
    HTML
    Salary
    """
    skills = []
    inside_skills = False

    stop_headings = {
        "salary",
        "applying procedure",
        "job description",
        "job specification",
        "about the organization",
        "more jobs by this organization",
        "more jobs from this organization",
        "similar jobs powered by merojob ai",
        "apply before",
        "offered salary",
    }

    skip_lines = {
        "skills required",
        "required skills for this job",
        "required skill for this job",
        "skill required",
        "skills",
    }

    for line in lines:
        line_clean = clean_text(line)
        line_lower = line_clean.lower()

        if line_lower == "skills required":
            inside_skills = True
            continue

        if inside_skills and line_lower in stop_headings:
            break

        if not inside_skills:
            continue

        if line_lower in skip_lines:
            continue

        if is_navigation_or_category(line_clean):
            continue

        # Avoid long description sentences being stored as skills.
        if len(line_clean) > 45:
            continue

        # Avoid metadata lines.
        if ":" in line_clean:
            continue

        skill = normalize_skill(line_clean)

        if skill and skill not in skills:
            skills.append(skill)

    return skills


def extract_explicit_skills_from_text(text):
    """
    Fallback only.

    This scans actual job detail text for explicit skill names.
    It does NOT assume Python from generic words like developer/software/IT.
    """
    text_lower = text.lower()

    skill_patterns = {
        "Python": r"\bpython\b",
        "Django": r"\bdjango\b",
        "Flask": r"\bflask\b",
        "FastAPI": r"\bfastapi\b",
        "JavaScript": r"\bjavascript\b|\bjs\b",
        "TypeScript": r"\btypescript\b",
        "React": r"\breact(?:\.js|js)?\b",
        "Next.js": r"\bnext(?:\.js|js)?\b",
        "Vue.js": r"\bvue(?:\.js|js)?\b",
        "Angular": r"\bangular\b",
        "Node.js": r"\bnode(?:\.js|js)?\b",
        "Express.js": r"\bexpress(?:\.js|js)?\b",
        "HTML": r"\bhtml\b",
        "CSS": r"\bcss\b",
        "Tailwind CSS": r"\btailwind\b|\btailwind css\b",
        "Bootstrap": r"\bbootstrap\b",
        "PHP": r"\bphp\b",
        "Laravel": r"\blaravel\b",
        "Java": r"\bjava\b",
        "Spring Boot": r"\bspring boot\b",
        "C#": r"\bc#\b",
        ".NET": r"\b\.net\b|\bdotnet\b",
        "C++": r"\bc\+\+\b",
        "SQL": r"\bsql\b",
        "MySQL": r"\bmysql\b",
        "PostgreSQL": r"\bpostgresql\b|\bpostgres\b",
        "MongoDB": r"\bmongodb\b|\bmongo db\b",
        "Git": r"\bgit\b",
        "GitHub": r"\bgithub\b",
        "Docker": r"\bdocker\b",
        "Kubernetes": r"\bkubernetes\b|\bk8s\b",
        "AWS": r"\baws\b",
        "Azure": r"\bazure\b",
        "Google Cloud": r"\bgoogle cloud\b|\bgcp\b",
        "Figma": r"\bfigma\b",
        "UI/UX": r"\bui\s*/\s*ux\b|\bui ux\b",
        "SEO": r"\bseo\b",
        "Digital Marketing": r"\bdigital marketing\b",
        "Content Writing": r"\bcontent writing\b",
        "Communication": r"\bcommunication\b",
        "Problem Solving": r"\bproblem solving\b",
        "Troubleshooting": r"\btroubleshooting\b",
        "Coordination": r"\bcoordination\b",
        "Leadership": r"\bleadership\b",
        "Excel": r"\bexcel\b|\bms excel\b|\bmicrosoft excel\b",
        "Power BI": r"\bpower bi\b",
        "Data Analysis": r"\bdata analysis\b",
        "Accounting": r"\baccounting\b",
        "Finance": r"\bfinance\b",
    }

    detected_skills = []

    for skill, pattern in skill_patterns.items():
        if re.search(pattern, text_lower):
            detected_skills.append(skill)

    return detected_skills


def extract_location_from_text(text):
    """
    Finds location from job detail text.
    """
    locations = [
        "Kathmandu",
        "Lalitpur",
        "Bhaktapur",
        "Pokhara",
        "Biratnagar",
        "Butwal",
        "Chitwan",
        "Dharan",
        "Janakpur",
        "Birgunj",
        "Hetauda",
        "Nepalgunj",
        "Itahari",
        "Bharatpur",
        "Nepal",
    ]

    text_lower = text.lower()

    for location in locations:
        if location.lower() in text_lower:
            return location

    return "Nepal"


def extract_company_from_detail(lines, job_title, fallback_company):
    """
    Tries to find company name from detail page.

    On Merojob detail pages, company name often appears shortly before
    the job title.
    """
    if not job_title:
        return fallback_company or "Company not listed"

    job_title_lower = clean_text(job_title).lower()

    for index, line in enumerate(lines):
        if clean_text(line).lower() == job_title_lower:
            # Look above title for company name.
            for back_index in range(index - 1, max(index - 6, -1), -1):
                candidate = clean_text(lines[back_index])

                if looks_like_company_name(candidate):
                    return candidate

    if fallback_company and looks_like_company_name(fallback_company):
        return fallback_company

    return "Company not listed"


def scrape_job_detail(job_link, fallback_title, fallback_company, fallback_context):
    """
    Opens a job detail page and extracts:
    - actual skills from Skills Required
    - company
    - location

    If detail page fails, returns safe fallback data.
    """
    response = get_with_retry(
        job_link,
        headers=HEADERS,
        retries=3,
        timeout=10,
        use_proxy=True
    )

    if response is None:
        fallback_skills = extract_explicit_skills_from_text(
            fallback_title + " " + fallback_context
        )

        return {
            "title": fallback_title,
            "company": fallback_company or "Company not listed",
            "location": extract_location_from_text(fallback_context),
            "skills": ",".join(fallback_skills) if fallback_skills else "Not specified",
        }

    soup = BeautifulSoup(response.text, "html.parser")
    lines = get_text_lines(soup)
    detail_text = clean_text(soup.get_text(" ", strip=True))

    company = extract_company_from_detail(
        lines,
        fallback_title,
        fallback_company
    )

    location = extract_location_from_text(detail_text)

    skills = extract_skills_from_skill_section(lines)

    # Fallback: only explicit skills from real detail text.
    if not skills:
        skills = extract_explicit_skills_from_text(detail_text)

    skills_text = ",".join(skills) if skills else "Not specified"

    return {
        "title": fallback_title,
        "company": company,
        "location": location,
        "skills": skills_text,
    }


def scrape_jobs(limit=30, refresh=True):
    """
    Scrapes live jobs from Merojob homepage.
    Then opens each job detail page to collect real required skills.
    Saves jobs into SQLite database.
    """
    print("Scraping real jobs from Merojob...")

    response = get_with_retry(
        URL,
        headers=HEADERS,
        retries=3,
        timeout=10,
        use_proxy=True
    )

    if response is None:
        return {
            "success": False,
            "count": 0,
            "message": "Merojob could not be reached. Please try again."
        }

    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a")

    collected_jobs = []
    seen_links = set()
    seen_titles = set()

    last_company = "Company not listed"

    for link_tag in links:
        title = clean_text(link_tag.get_text(" ", strip=True))
        href = link_tag.get("href")

        if not title:
            continue

        # Track company names from homepage.
        if href and not is_probable_job_link(href) and looks_like_company_name(title):
            last_company = title
            continue

        if not href:
            continue

        if not is_probable_job_link(href):
            continue

        if is_navigation_or_category(title):
            continue

        job_link = make_full_link(href)

        if job_link in seen_links:
            continue

        title_key = title.lower()

        if title_key in seen_titles:
            continue

        seen_links.add(job_link)
        seen_titles.add(title_key)

        parent = link_tag.find_parent(["div", "li", "article", "section"])

        if parent:
            context_text = clean_text(parent.get_text(" ", strip=True))
        else:
            context_text = title

        detail_data = scrape_job_detail(
            job_link=job_link,
            fallback_title=title,
            fallback_company=last_company,
            fallback_context=context_text
        )

        collected_jobs.append({
            "title": detail_data["title"],
            "company": detail_data["company"],
            "location": detail_data["location"],
            "skills": detail_data["skills"],
            "link": job_link,
            "source": "Merojob"
        })

        print(
            f"Collected: {detail_data['title']} | "
            f"{detail_data['company']} | "
            f"{detail_data['skills']}"
        )

        if len(collected_jobs) >= limit:
            break

        # Small delay so we do not hit Merojob too aggressively.
        time.sleep(0.5)

    if collected_jobs and refresh:
        delete_all_jobs()

    for job in collected_jobs:
        insert_job(
            job["title"],
            job["company"],
            job["location"],
            job["skills"],
            job["link"],
            job["source"]
        )

    print(f"{len(collected_jobs)} jobs scraped and saved from Merojob.")

    return {
        "success": True,
        "count": len(collected_jobs),
        "message": f"{len(collected_jobs)} jobs scraped successfully from Merojob."
    }


if __name__ == "__main__":
    init_db()
    result = scrape_jobs(limit=30, refresh=True)
    print(result)