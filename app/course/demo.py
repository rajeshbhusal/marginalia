"""A hand-written demo course, so the reader can be tried without an API key.

Sections 1 to 4 are written; 5 and 6 are left for the configured model to write just in time.
"""

import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from app.course.blocks import new_block_id
from app.course.models import Course, Section
from app.course.schemas import CourseStatus, SectionStatus
from app.db.base_model import get_utc_now
from app.tutor.models import Thread, ThreadMessage
from app.util import short_id

DEMO_MODEL = "demo (hand-written)"

GOAL = "understand Bayes' theorem and how to update beliefs with evidence"

DIAGNOSTICS = [
    {
        "question": "How familiar are you with probability?",
        "options": [
            "Not at all",
            "I know the basics, like coin flips and dice",
            "I've used probability in my studies or work",
            "I'm comfortable with conditional probability",
        ],
        "correct_option": None,
        "concept": "Self-assessed experience",
        "answer": 1,
    },
    {
        "question": "A fair die is rolled. What is the probability of rolling an even number?",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_option": 2,
        "concept": "Basic probability",
        "answer": 2,
    },
    {
        "question": "What does P(A | B) mean?",
        "options": [
            "The probability that A and B both happen",
            "The probability of A, given that B has happened",
            "The probability of B, given that A has happened",
            "The probability that A or B happens",
        ],
        "correct_option": 1,
        "concept": "Conditional probability notation",
        "answer": 1,
    },
    {
        "question": "A disease affects 1 in 1,000 people. A test for it is 99% accurate. "
        "You test positive. Roughly how likely is it that you have the disease?",
        "options": ["About 99%", "About 50%", "About 9%", "Less than 1%"],
        "correct_option": 2,
        "concept": "Base rates",
        "answer": 0,
    },
]

PROFILE = {
    "level": "intermediate",
    "summary": "Comfortable with basic probability and conditional notation, but not yet with "
    "how evidence should update a belief: the base-rate question tripped them up.",
    "strengths": ["Basic probability", "Conditional probability notation"],
    "gaps": ["Base rates", "Updating beliefs with evidence"],
}

OUTLINE = [
    {
        "title": "Probability as a degree of belief",
        "summary": "Treat probabilities as measured confidence, and condition on what you know.",
        "sections": [
            (
                "beliefs",
                "Probabilities as degrees of belief",
                "Why a probability can describe how confident you are, not just how often "
                "something happens.",
            ),
            (
                "conditional",
                "Conditional probability, visually",
                "How knowing one thing changes the probability of another, shown with counts "
                "and trees.",
            ),
        ],
    },
    {
        "title": "Bayes' theorem",
        "summary": "Derive the rule for updating beliefs and see why base rates matter.",
        "sections": [
            (
                "derivation",
                "Deriving Bayes' theorem",
                "A two-line derivation, and what the prior, likelihood and posterior each mean.",
            ),
            (
                "base-rates",
                "The base-rate trap",
                "Why a positive result from a 99% accurate test can still mean you're "
                "probably fine.",
            ),
        ],
    },
    {
        "title": "Bayesian updating in practice",
        "summary": "Use Bayes repeatedly, and check your intuition with code.",
        "sections": [
            (
                "updating",
                "Updating step by step",
                "Today's posterior is tomorrow's prior: chaining several pieces of evidence.",
            ),
            (
                "simulation",
                "Simulating Bayes in Python",
                "Verify the maths by simulating a population and counting.",
            ),
        ],
    },
]

SECTIONS = {
    "beliefs": {
        "recap": "Probabilities can be read as degrees of belief that depend on your "
        "information. They follow the same rules as frequencies, and good beliefs are calibrated.",
        "research": {
            "notes": "- Two main interpretations: frequency (long-run proportion) and Bayesian "
            "(degree of belief given information).\n- Both satisfy Kolmogorov's axioms "
            "(1933).\n- Calibration: forecasts of p% should come true about p% of the time.",
            "sources": [
                {
                    "title": "Bayesian probability",
                    "url": "https://en.wikipedia.org/wiki/Bayesian_probability",
                },
                {
                    "title": "Probability axioms",
                    "url": "https://en.wikipedia.org/wiki/Probability_axioms",
                },
            ],
        },
        "blocks": [
            {
                "type": "text",
                "markdown": "When a forecaster says there's a **70% chance of rain tomorrow**, "
                "tomorrow will only happen once. You can't run it a hundred times and count the "
                "wet ones. The 70% is a statement about *confidence*: given the pressure charts, "
                "the satellite images and decades of similar days, rain is fairly likely.\n\n"
                "That's the **Bayesian** reading of probability: a number between 0 and 1 that "
                "measures how strongly the available information supports a claim. The other "
                "common reading, the **frequency** interpretation, defines probability as the "
                "long-run proportion of times something happens in repeated trials, like the "
                "share of heads in thousands of coin flips. For dice and coins the two agree. "
                "For one-off events (an election, a diagnosis, whether a bridge design is "
                "safe) only the belief reading makes sense.",
            },
            {
                "type": "callout",
                "variant": "key_idea",
                "title": "Key idea",
                "markdown": "A probability measures how confident you should be **given what "
                "you know**. Two people with different information can rationally assign "
                "different probabilities to the same event, and both can be right.",
            },
            {
                "type": "diagram",
                "mermaid": 'flowchart LR\n  I["What you know"] --> B["Belief: P(rain) = 0.7"]\n'
                '  E["New evidence: dark clouds"] --> U["Updated belief: P(rain) = 0.9"]\n'
                "  B --> U",
                "caption": "A probability is a snapshot of belief. New evidence moves it, which "
                "is exactly what Bayes' theorem will make precise.",
            },
            {
                "type": "text",
                "markdown": "Whichever reading you use, probabilities obey the same three rules, "
                "set out by Andrey Kolmogorov in 1933:\n\n"
                "1. Every probability is between 0 and 1: $0 \\le P(A) \\le 1$.\n"
                "2. Something certain has probability 1.\n"
                "3. If $A$ and $B$ can't both happen, $P(A \\text{ or } B) = P(A) + P(B)$.\n\n"
                "A handy consequence is the **complement rule**:\n\n"
                "$$P(\\text{not } A) = 1 - P(A)$$\n\n"
                "Beliefs can also be checked against reality. A forecaster is **well "
                "calibrated** if, on the days they say 70%, it rains on about 70% of them. "
                "Calibration is how a degree of belief earns its number.",
            },
            {
                "type": "example",
                "title": "Two people, one coin",
                "markdown": "Your friend flips a coin and covers it with their hand, then "
                "sneaks a look.\n\n"
                "1. Before anyone looks, you both assign $P(\\text{heads}) = 0.5$.\n"
                "2. Your friend sees heads. For them, $P(\\text{heads}) = 1$. For you, still "
                "$0.5$. Neither of you is wrong: you hold different information.\n"
                '3. Your friend says "it isn\'t tails". Now you know what they know, and your '
                "probability jumps to 1.\n\n"
                "The coin never changed. Your *information* did, so your probability did too.",
            },
            {
                "type": "exercise",
                "prompt": 'A forecaster said **"30% chance of rain"** on 200 days.\n\n'
                "1. If they are well calibrated, on roughly how many of those days should it "
                "have rained?\n2. It actually rained on 110 of them. What do you conclude?",
                "hints": [
                    "Calibration means stated probabilities match observed frequencies.",
                    "Compare 30% of 200 with the 110 days it actually rained.",
                ],
                "solution": "1. About $0.3 \\times 200 = 60$ days.\n"
                "2. Rain fell on $110 / 200 = 55\\%$ of those days, far more than 30%. The "
                "forecaster is badly overconfident that it will stay dry: when they say 30%, "
                "it's closer to a coin flip, so you'd mentally adjust their 30% forecasts "
                "upwards.",
            },
        ],
    },
    "conditional": {
        "recap": "P(A | B) is the probability of A within the world where B happened: "
        "P(A and B) / P(B). It differs from P(B | A), and the multiplication rule links them.",
        "research": {
            "notes": "- P(A | B) = P(A and B) / P(B), defined when P(B) > 0.\n- Confusing "
            "P(A | B) with P(B | A) is called the confusion of the inverse.\n- Counting "
            "natural frequencies makes conditional probabilities easier to reason about.",
            "sources": [
                {
                    "title": "Conditional probability",
                    "url": "https://en.wikipedia.org/wiki/Conditional_probability",
                },
                {
                    "title": "Confusion of the inverse",
                    "url": "https://en.wikipedia.org/wiki/Confusion_of_the_inverse",
                },
            ],
        },
        "blocks": [
            {
                "type": "text",
                "markdown": "Conditional probability answers one question: **if I know $B$ "
                "happened, how likely is $A$?** Knowing $B$ shrinks the world you're "
                "considering to just the outcomes where $B$ is true. Within that smaller world, "
                "you ask what share also has $A$:\n\n"
                "$$P(A \\mid B) = \\frac{P(A \\text{ and } B)}{P(B)}$$\n\n"
                "(defined whenever $P(B) > 0$). The easiest way to see it is to count people "
                "instead of juggling percentages.",
            },
            {
                "type": "diagram",
                "mermaid": "flowchart TD\n"
                '  All["100 people"] --> Dog["40 own a dog"]\n'
                '  All --> NoDog["60 don\'t own a dog"]\n'
                '  Dog --> DW["30 walk daily"]\n'
                '  Dog --> DN["10 don\'t walk daily"]\n'
                '  NoDog --> NW["12 walk daily"]\n'
                '  NoDog --> NN["48 don\'t walk daily"]',
                "caption": "A frequency tree: each branch splits a group into the people who "
                "do and don't have the next property.",
            },
            {
                "type": "text",
                "markdown": "Read the answers straight off the tree:\n\n"
                "| Question | Count | Probability |\n|---|---|---|\n"
                "| $P(\\text{walks} \\mid \\text{dog})$ | 30 of 40 dog owners | $0.75$ |\n"
                "| $P(\\text{walks})$ | 42 of 100 people | $0.42$ |\n"
                "| $P(\\text{dog} \\mid \\text{walks})$ | 30 of 42 walkers | $\\approx 0.71$ |\n\n"
                "Notice that $P(\\text{walks} \\mid \\text{dog}) = 0.75$ but "
                "$P(\\text{dog} \\mid \\text{walks}) \\approx 0.71$. They're different questions "
                "about different groups, so they have different answers.",
            },
            {
                "type": "callout",
                "variant": "warning",
                "title": "P(A | B) is not P(B | A)",
                "markdown": "Swapping the two, sometimes called the **confusion of the "
                'inverse**, is the most common mistake in reasoning about evidence. "Most '
                'people with the disease test positive" says nothing on its own about whether '
                "most people who test positive have the disease. Bayes' theorem is the tool "
                "that converts one into the other.",
            },
            {
                "type": "text",
                "markdown": "Rearranging the definition gives the **multiplication rule**, which "
                "you'll use constantly:\n\n"
                "$$P(A \\text{ and } B) = P(A \\mid B)\\,P(B) = P(B \\mid A)\\,P(A)$$\n\n"
                "In the tree: $P(\\text{dog and walks}) = 0.75 \\times 0.40 = 0.30$, the 30 "
                "people on the far-left branch.",
            },
            {
                "type": "example",
                "title": "Two dice, both directions",
                "markdown": "Roll two fair dice.\n\n"
                "- $P(\\text{sum is } 8 \\mid \\text{first die is } 3)$: you need a 5 on the "
                "second die, so it's $1/6$.\n"
                "- $P(\\text{first die is } 3 \\mid \\text{sum is } 8)$: the rolls summing to 8 "
                "are (2,6), (3,5), (4,4), (5,3) and (6,2). One of the five starts with 3, so "
                "it's $1/5$.\n\nSame two events, opposite conditioning, different answers.",
            },
            {
                "type": "exercise",
                "prompt": "Using the tree above, what is "
                "$P(\\text{dog} \\mid \\text{doesn't walk daily})$?",
                "hints": [
                    "First count everyone who doesn't walk daily.",
                    "That's 10 dog owners plus 48 non-owners.",
                ],
                "solution": "$58$ people don't walk daily, and $10$ of them own a dog, so "
                "$P(\\text{dog} \\mid \\text{doesn't walk}) = 10/58 \\approx 0.17$.",
            },
        ],
    },
    "derivation": {
        "recap": "Bayes' theorem follows from writing P(A and B) both ways. Posterior = "
        "likelihood x prior / evidence; in odds form, posterior odds = prior odds x likelihood "
        "ratio.",
        "research": {
            "notes": "- Bayes' theorem: P(H | E) = P(E | H) P(H) / P(E).\n- Named after "
            "Thomas Bayes; his essay was published posthumously in 1763.\n- Law of total "
            "probability: P(E) = P(E | H) P(H) + P(E | not H) P(not H).",
            "sources": [
                {
                    "title": "Bayes' theorem",
                    "url": "https://en.wikipedia.org/wiki/Bayes%27_theorem",
                },
                {
                    "title": "Law of total probability",
                    "url": "https://en.wikipedia.org/wiki/Law_of_total_probability",
                },
            ],
        },
        "blocks": [
            {
                "type": "text",
                "markdown": "Bayes' theorem falls out of the multiplication rule in two lines. "
                "Write $P(A \\text{ and } B)$ both ways:\n\n"
                "$$P(A \\mid B)\\,P(B) = P(B \\mid A)\\,P(A)$$\n\n"
                "and divide by $P(B)$:\n\n"
                "$$P(A \\mid B) = \\frac{P(B \\mid A)\\,P(A)}{P(B)}$$\n\n"
                "That's the whole theorem, named after Thomas Bayes, whose essay on it was "
                "published in 1763, two years after his death. Its power comes from what the "
                "letters stand for when $A$ is a **hypothesis** $H$ and $B$ is some "
                "**evidence** $E$.",
            },
            {
                "type": "callout",
                "variant": "definition",
                "title": "The four parts",
                "markdown": "- **Prior** $P(H)$: how plausible the hypothesis was before the "
                "evidence.\n"
                "- **Likelihood** $P(E \\mid H)$: how expected the evidence is if the "
                "hypothesis is true.\n"
                "- **Evidence** $P(E)$: how expected the evidence is overall.\n"
                "- **Posterior** $P(H \\mid E)$: how plausible the hypothesis is after the "
                "evidence.",
            },
            {
                "type": "diagram",
                "mermaid": "flowchart LR\n"
                '  P["Prior: P(H)"] --> M["Multiply by the likelihood P(E given H)"]\n'
                '  M --> D["Divide by P(E), the total chance of the evidence"]\n'
                '  D --> Q["Posterior: P(H given E)"]',
                "caption": "Bayes' theorem as a pipeline: weight the prior by how well the "
                "hypothesis predicted the evidence, then rescale.",
            },
            {
                "type": "text",
                "markdown": "You rarely know $P(E)$ directly, but you can build it from the "
                "two ways the evidence can arise (the **law of total probability**):\n\n"
                "$$P(E) = P(E \\mid H)\\,P(H) + P(E \\mid \\neg H)\\,P(\\neg H)$$\n\n"
                "Dividing the theorem for $H$ by the theorem for $\\neg H$ cancels $P(E)$ and "
                "gives the **odds form**, often the quickest way to calculate:\n\n"
                "$$\\underbrace{\\frac{P(H \\mid E)}{P(\\neg H \\mid E)}}_{\\text{posterior odds}}"
                " = \\underbrace{\\frac{P(H)}{P(\\neg H)}}_{\\text{prior odds}} \\times "
                "\\underbrace{\\frac{P(E \\mid H)}{P(E \\mid \\neg H)}}_{\\text{likelihood "
                "ratio}}$$",
            },
            {
                "type": "code",
                "language": "python",
                "code": "def posterior(prior, p_evidence_if_true, p_evidence_if_false):\n"
                '    """P(hypothesis | evidence), by Bayes\' theorem."""\n'
                "    p_evidence = p_evidence_if_true * prior + p_evidence_if_false * (1 - prior)\n"
                "    return p_evidence_if_true * prior / p_evidence\n\n\n"
                '# 20% of email is spam. "Free money" appears in 40% of spam\n'
                "# and in 1% of other mail.\n"
                "print(round(posterior(0.20, 0.40, 0.01), 3))  # 0.909",
                "caption": "The theorem in four lines of Python, applied to a spam filter.",
            },
            {
                "type": "example",
                "title": "The spam filter, with odds",
                "markdown": "1. Prior odds of spam: $0.2 : 0.8 = 1 : 4$.\n"
                '2. Likelihood ratio of seeing "free money": $0.40 / 0.01 = 40$.\n'
                "3. Posterior odds: $1 : 4 \\times 40 = 40 : 4 = 10 : 1$.\n"
                "4. Convert back: $P(\\text{spam} \\mid \\text{free money}) = 10 / 11 \\approx "
                "0.909$, matching the code.",
            },
            {
                "type": "exercise",
                "prompt": "Machine A makes 60% of a factory's widgets and 2% of them are "
                "faulty. Machine B makes the other 40%, and 5% of those are faulty. You pick a "
                "faulty widget. What's the probability it came from machine B?",
                "hints": [
                    'The hypothesis is "made by B"; the evidence is "faulty".',
                    "Use the law of total probability for P(faulty).",
                ],
                "solution": "$P(\\text{faulty}) = 0.6 \\times 0.02 + 0.4 \\times 0.05 = 0.012 + "
                "0.020 = 0.032$, so\n\n"
                "$$P(B \\mid \\text{faulty}) = \\frac{0.05 \\times 0.4}{0.032} = "
                "\\frac{0.020}{0.032} = 0.625$$\n\n"
                "Machine B makes fewer widgets but most of the faulty ones.",
            },
        ],
    },
    "base-rates": {
        "recap": "With a rare condition, false positives from the large healthy group swamp "
        "the true positives: a 99% accurate test for a 1-in-1,000 disease gives about a 9% "
        "chance of illness after one positive result, and about 91% after two.",
        "research": {
            "notes": "- Base-rate neglect: ignoring prior probabilities when judging evidence "
            "(studied by Kahneman and Tversky in the 1970s).\n- Casscells et al. (1978) asked "
            "Harvard Medical School staff and students a version of this question; the most "
            "common answer was 95% when the correct answer was about 2%.\n- Sensitivity = "
            "P(positive | ill); specificity = P(negative | healthy).",
            "sources": [
                {
                    "title": "Base rate fallacy",
                    "url": "https://en.wikipedia.org/wiki/Base_rate_fallacy",
                },
                {
                    "title": "Sensitivity and specificity",
                    "url": "https://en.wikipedia.org/wiki/Sensitivity_and_specificity",
                },
            ],
        },
        "blocks": [
            {
                "type": "text",
                "markdown": "Back to the question from your diagnostic: a disease affects "
                "**1 in 1,000** people, and a test catches 99% of cases (its **sensitivity**) "
                "while correctly clearing 99% of healthy people (its **specificity**). You "
                'test positive. Most people answer "99%". The right answer is about **9%**.\n\n'
                "Ignoring how rare the condition is, the **base rate**, is called base-rate "
                "neglect, and experts fall for it too. When a version of this question was put "
                "to staff and students at Harvard Medical School in 1978, the most common "
                "answer was 95%; the correct answer was about 2%.",
            },
            {
                "type": "diagram",
                "mermaid": "flowchart TD\n"
                '  A["100,000 people"] --> S["100 have the disease"]\n'
                '  A --> H["99,900 are healthy"]\n'
                '  S --> SP["99 test positive"]\n'
                '  S --> SN["1 tests negative"]\n'
                '  H --> HP["999 test positive"]\n'
                '  H --> HN["98,901 test negative"]',
                "caption": "Of the 1,098 positive results, only 99 come from people who are ill.",
            },
            {
                "type": "text",
                "markdown": "The tree shows why. The test is wrong for only 1% of healthy "
                "people, but there are so many healthy people that their 999 false positives "
                "outnumber the 99 true ones ten to one. Bayes' theorem gives the same answer "
                "without the counting:\n\n"
                "$$P(\\text{ill} \\mid +) = \\frac{0.99 \\times 0.001}{0.99 \\times 0.001 + "
                "0.01 \\times 0.999} = \\frac{0.00099}{0.01098} \\approx 0.09$$",
            },
            {
                "type": "callout",
                "variant": "key_idea",
                "title": "Key idea",
                "markdown": "When a condition is rare, false positives from the large healthy "
                "group can swamp the true positives from the small ill group. Always ask: of "
                "everyone who tests positive, how many actually have it?",
            },
            {
                "type": "code",
                "language": "python",
                "code": "import random\n\nrandom.seed(1)\nill_and_positive = positive = 0\n"
                "for _ in range(1_000_000):\n"
                "    ill = random.random() < 0.001\n"
                "    if random.random() < (0.99 if ill else 0.01):\n"
                "        positive += 1\n"
                "        ill_and_positive += ill\n\n"
                'print(f"P(ill | positive) = {ill_and_positive / positive:.3f}")  # about 0.09',
                "caption": "Simulate a million people and count: the share of positives who "
                "are ill comes out close to 0.09.",
            },
            {
                "type": "example",
                "title": "A second positive test",
                "markdown": "Suppose a second, independent test also comes back positive. "
                "Yesterday's posterior becomes today's prior:\n\n"
                "1. Prior odds after the first test: $99 : 999$ (about 1 to 10).\n"
                "2. Likelihood ratio of a positive result: $0.99 / 0.01 = 99$.\n"
                "3. New odds: $99 \\times 99 : 999 = 9801 : 999$, about 9.8 to 1.\n"
                "4. So $P(\\text{ill} \\mid ++) = 9801 / 10800 \\approx 0.91$.\n\n"
                "One positive result is weak evidence for a rare disease; two make it likely.",
            },
            {
                "type": "exercise",
                "prompt": "A condition affects **2%** of people. A test has 90% sensitivity "
                "and 95% specificity. What is the probability that someone who tests positive "
                "has the condition?",
                "hints": [
                    "Specificity of 95% means 5% of healthy people test positive.",
                    "Work out P(positive) first, from both groups.",
                ],
                "solution": "$P(+) = 0.90 \\times 0.02 + 0.05 \\times 0.98 = 0.018 + 0.049 = "
                "0.067$, so\n\n"
                "$$P(\\text{condition} \\mid +) = \\frac{0.018}{0.067} \\approx 0.27$$\n\n"
                "About 27%: better than the 9% above because the condition is twenty times more "
                "common, but still far from 90%.",
            },
        ],
    },
}

THREADS = [
    {
        "section": "base-rates",
        "block": 3,  # The key-idea callout
        "quote": "false positives from the large healthy group can swamp the true positives",
        "prefix": "When a condition is rare, ",
        "suffix": " from the small ill group.",
        "messages": [
            ("learner", "Why doesn't the 99% accuracy matter more here?"),
            (
                "tutor",
                'It does matter, it just isn\'t the only number in play. "99% accurate" '
                "describes the test **for one person**: 99 in 100 ill people test positive, "
                "and 1 in 100 healthy people does. But a positive result comes from the whole "
                "population, where healthy people outnumber ill ones 999 to 1.\n\n"
                "So the two error rates get multiplied by very different group sizes:\n\n"
                "| Group | People per 100,000 | Positive results |\n|---|---|---|\n"
                "| Ill | 100 | 99 |\n| Healthy | 99,900 | 999 |\n\n"
                "A 1% false-positive rate applied to 99,900 people makes ten times more "
                "positives than a 99% hit rate applied to 100. Make the test 99.9% specific "
                "and the answer jumps to about 50%; make the disease more common and it climbs "
                "too. Accuracy and base rate both matter. The trap is ignoring the second.",
            ),
        ],
    }
]


async def load_demo_course(db: AsyncSession) -> Course:
    """Add a fresh copy of the demo course (new ids each time) and return it."""
    now = get_utc_now()
    diagnostics, answers = [], []
    for item in DIAGNOSTICS:
        question_id = short_id("q")
        diagnostics.append({k: v for k, v in item.items() if k != "answer"} | {"id": question_id})
        answers.append({"question_id": question_id, "option": item["answer"]})

    outline, section_ids = [], {}
    for module in OUTLINE:
        sections = []
        for key, title, summary in module["sections"]:
            section_ids[key] = uuid.uuid4()
            sections.append({"id": str(section_ids[key]), "title": title, "summary": summary})
        outline.append(
            {
                "id": short_id("m"),
                "title": module["title"],
                "summary": module["summary"],
                "sections": sections,
            }
        )

    course = Course(
        title="Bayesian Thinking: Updating Beliefs with Evidence",
        description="A visual, practical introduction to reasoning with Bayes' theorem: why "
        "evidence should shift your beliefs by just the right amount, practised on medical "
        "tests, spam filters and everyday judgements.",
        goal=GOAL,
        depth="practitioner",
        learning_style="visual",
        status=CourseStatus.in_progress,
        diagnostics=diagnostics,
        answers=answers,
        profile=PROFILE,
        outline=outline,
        model=DEMO_MODEL,
        current_section_id=section_ids["beliefs"],
    )
    db.add(course)

    block_ids: dict[str, list[str]] = {}
    position = 0
    for module_index, module in enumerate(OUTLINE):
        for key, title, summary in module["sections"]:
            content = SECTIONS.get(key)
            section = Section(
                id=section_ids[key],
                course_id=course.id,
                position=position,
                module_index=module_index,
                module_title=module["title"],
                title=title,
                summary=summary,
            )
            if content:
                block_ids[key] = [new_block_id() for _ in content["blocks"]]
                section.status = SectionStatus.ready
                section.blocks = [
                    block | {"id": block_id}
                    for block, block_id in zip(content["blocks"], block_ids[key], strict=True)
                ]
                section.recap = content["recap"]
                section.research = content["research"]
                section.model = DEMO_MODEL
                section.generated_at = now
            db.add(section)
            position += 1

    for item in THREADS:
        thread = Thread(
            course_id=course.id,
            section_id=section_ids[item["section"]],
            block_id=block_ids[item["section"]][item["block"]],
            quote=item["quote"],
            prefix=item["prefix"],
            suffix=item["suffix"],
        )
        db.add(thread)
        for role, content in item["messages"]:
            db.add(ThreadMessage(thread_id=thread.id, role=role, content=content))

    await db.commit()
    return course
