from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from forecaster.db import Article, Question
from forecaster.timeutil import utcnow

# Entirely fictional: no real cities, companies or countries, so the repo
# contains no third-party content even in its demo fixtures.
_FICTIONAL_PLACES = [
    "Borealis City",
    "Kestrelia",
    "Vantrex Province",
    "New Sardoba",
    "Lake Averno",
    "Port Calyx",
    "Driftmark",
    "Umberfall",
    "Cindermoor",
    "Haleth Crossing",
]
_FICTIONAL_SUBJECTS = [
    "Vantrex Corp",
    "Haleth Rail Authority",
    "Cindermoor United",
    "Averno Energy",
    "the Driftmark Assembly",
    "Port Calyx Exchange",
    "Umberfall Technologies",
    "the Kestrelia Central Bank",
    "New Sardoba FC",
    "Borealis Spaceworks",
]
_EVENT_TEMPLATES = [
    "Will {subject} report a profit this quarter?",
    "Will {subject} announce a merger before {month} {year}?",
    "Will {place} experience a recorded heatwave above 40C in {year}?",
    "Will {subject} win its next match?",
    "Will {subject} launch its new product on schedule?",
    "Will {place}'s election result in a runoff?",
]


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def generate_demo_data(
    session_factory: sessionmaker[Session], n_questions: int, seed: int = 42
) -> None:
    rng = _rng(seed)
    now = utcnow()
    with session_factory() as session:
        for i in range(n_questions):
            place = rng.choice(_FICTIONAL_PLACES)
            subject = rng.choice(_FICTIONAL_SUBJECTS)
            template = rng.choice(_EVENT_TEMPLATES)
            title = template.format(subject=subject, place=place, month="March", year=now.year + 1)
            qid = f"demo:{i}"
            session.add(
                Question(
                    id=qid,
                    source="demo",
                    title=title,
                    url=f"https://example-demo.invalid/questions/{i}",
                    close_time=now + timedelta(days=rng.randint(7, 60)),
                    created_at=now,
                    market_prob=round(rng.uniform(0.1, 0.9), 2),
                    status="open",
                )
            )
            for j in range(rng.randint(0, 3)):
                session.add(
                    Article(
                        question_id=qid,
                        url=f"https://example-demo.invalid/news/{i}/{j}",
                        title=f"Fictional update {j} about {subject}",
                        domain="example-demo.invalid",
                        published_at=now - timedelta(days=rng.randint(1, 10)),
                        fetched_at=now,
                    )
                )
        session.commit()


def simulate_outcomes(session_factory: sessionmaker[Session], seed: int = 43) -> None:
    """The fake model has no skill, so outcomes are drawn independently of its
    forecasts — a fair 50/50 coin per question, exactly as the guide
    describes for the offline demo."""
    rng = _rng(seed)
    now = utcnow()
    with session_factory() as session:
        questions = session.query(Question).filter(Question.status == "open").all()
        for q in questions:
            q.status = "resolved"
            q.resolution = 1.0 if rng.random() < 0.5 else 0.0
            q.resolved_at = now
        session.commit()
