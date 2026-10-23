from app import jobs


async def create_course(client, **overrides) -> dict:
    payload = {
        "goal": "learn Bayesian statistics",
        "depth": "practitioner",
        "learning_style": "visual",
    } | overrides
    response = await client.post("/api/courses", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def plan_course(client, **overrides) -> dict:
    """Create a course, answer the diagnostic and wait for the outline."""
    course = await create_course(client, **overrides)
    answers = [{"question_id": q["id"], "option": 0} for q in course["diagnostics"]]
    response = await client.post(f"/api/courses/{course['id']}/answers", json={"answers": answers})
    assert response.status_code == 202, response.text
    await jobs.drain()
    course = (await client.get(f"/api/courses/{course['id']}")).json()
    assert course["status"] == "outline_ready", course
    return course


async def start_course(client, **overrides) -> dict:
    """Plan and start a course, and wait until its first section is written."""
    course = await plan_course(client, **overrides)
    response = await client.post(f"/api/courses/{course['id']}/start")
    assert response.status_code == 200, response.text
    await jobs.drain()
    return (await client.get(f"/api/courses/{course['id']}")).json()
