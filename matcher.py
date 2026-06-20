from database import get_all_jobs


def normalize(skill):
    return skill.strip().lower()


def match_jobs(user_skills):
    """
    Compares resume skills with job skills.
    Gives more realistic match percentages.
    """

    jobs = get_all_jobs()

    user_skill_set = set()

    for skill in user_skills:
        if skill:
            user_skill_set.add(normalize(skill))

    results = []

    for job in jobs:

        job_skills_raw = job["skills"] or ""

        job_skills = [
            normalize(skill)
            for skill in job_skills_raw.split(",")
            if skill.strip()
        ]

        matched_skills = []

        for skill in job_skills:
            if skill in user_skill_set:
                matched_skills.append(skill.title())

        matched_count = len(matched_skills)

        # This prevents jobs with only 1 or 2 skills from becoming 100%
        minimum_skill_count = 5

        denominator = max(
            len(job_skills),
            minimum_skill_count
        )

        score = round(
            (matched_count / denominator) * 100
        )

        results.append({
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "skills": job["skills"],
            "matched_skills": matched_skills,
            "score": score,
            "link": job["link"],
            "source": job["source"]
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    positive_results = [
        job for job in results
        if job["score"] > 0
    ]

    if positive_results:
        return positive_results[:5]

    return results[:5]