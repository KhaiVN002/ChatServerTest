"""Publish/query the LANL demo graph using an existing Neo4j database."""

import os

from neo4j import GraphDatabase


DEMO_ID = "metroasist:lanl:baseline:v1"
LABELS = ("MetroDemo", "MetroCase", "MetroWindow", "MetroEvent", "MetroHost", "MetroAccount", "MetroProcess")


def open_driver():
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        connection_timeout=5,
        max_transaction_retry_time=3,
        telemetry_disabled=True,
    )


def database():
    return os.getenv("NEO4J_DATABASE", "neo4j")


def publish(driver, data):
    cases, windows, events = [], [], []
    for case in data["cases"].values():
        cases.append({key: value for key, value in case.items() if key != "windows"})
        for window in case["windows"]:
            windows.append({key: value for key, value in window.items() if key != "events"} | {"case": case["id"]})
            events.extend({"window": window["id"], "event": event} for event in window["events"])

    def upsert(tx):
        tx.run("""
            MERGE (d:MetroDemo {id: $demo})
            SET d.stage = $stage
            WITH d
            UNWIND $rows AS row
            MERGE (c:MetroCase {id: row.id})
            SET c += row
            MERGE (d)-[:HAS_CASE]->(c)
            MERGE (h:MetroHost {id: 'lanl:host:' + row.host})
            SET h.name = row.host
            MERGE (c)-[:TRACKS]->(h)
            """, demo=DEMO_ID, stage=data["stage"], rows=cases).consume()
        tx.run("""
            UNWIND $rows AS row
            MATCH (c:MetroCase {id: row.case})
            MERGE (w:MetroWindow {id: row.id})
            SET w += row
            MERGE (c)-[:HAS_WINDOW]->(w)
            """, rows=windows).consume()
        for start in range(0, len(events), 1_000):
            tx.run("""
                UNWIND $rows AS row
                MATCH (w:MetroWindow {id: row.window})
                MERGE (e:MetroEvent {id: row.event.id})
                SET e += row.event
                MERGE (w)-[:HAS_EVENT]->(e)
                FOREACH (name IN CASE WHEN row.event.src IS NULL OR row.event.src IN ['?', ''] THEN [] ELSE [row.event.src] END |
                    MERGE (h:MetroHost {id: 'lanl:host:' + name}) SET h.name = name
                    MERGE (e)-[:FROM_HOST]->(h))
                FOREACH (name IN CASE WHEN row.event.dst IS NULL OR row.event.dst IN ['?', ''] THEN [] ELSE [row.event.dst] END |
                    MERGE (h:MetroHost {id: 'lanl:host:' + name}) SET h.name = name
                    MERGE (e)-[:TO_HOST]->(h))
                FOREACH (name IN CASE WHEN row.event.account IS NULL OR row.event.account IN ['?', ''] THEN [] ELSE [row.event.account] END |
                    MERGE (a:MetroAccount {id: 'lanl:account:' + name}) SET a.name = name
                    MERGE (a)-[:ACTED_IN]->(e))
                FOREACH (name IN CASE WHEN row.event.target_account IS NULL OR row.event.target_account IN ['?', ''] THEN [] ELSE [row.event.target_account] END |
                    MERGE (a:MetroAccount {id: 'lanl:account:' + name}) SET a.name = name
                    MERGE (e)-[:TARGET_ACCOUNT]->(a))
                FOREACH (name IN CASE WHEN row.event.process IS NULL OR row.event.process IN ['?', ''] THEN [] ELSE [row.event.process] END |
                    MERGE (p:MetroProcess {id: 'lanl:process:' + name}) SET p.name = name
                    MERGE (e)-[:OBSERVED_PROCESS]->(p))
                """, rows=events[start:start + 1_000]).consume()

    with driver.session(database=database()) as session:
        for label in LABELS:
            session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE").consume()
        session.execute_write(upsert)


def read_case(driver, metric):
    def fetch(tx):
        return list(tx.run("""
            MATCH (d:MetroDemo {id: $demo})-[:HAS_CASE]->(c:MetroCase {metric: $metric})
                  -[:HAS_WINDOW]->(w:MetroWindow)
            WHERE w.reference OR d.stage = 'replay'
            OPTIONAL MATCH (w)-[:HAS_EVENT]->(e:MetroEvent)
            WHERE NOT w.reference AND e.id IN w.examples
            RETURN properties(c) AS case_data, properties(w) AS window_data,
                   w.center AS center, collect(properties(e)) AS events
            ORDER BY center
            """, demo=DEMO_ID, metric=metric))

    with driver.session(database=database()) as session:
        rows = session.execute_read(fetch)
    if not rows:
        raise FileNotFoundError("Chưa có dữ liệu demo trong Neo4j.")
    return rows[0]["case_data"] | {
        "windows": [row["window_data"] | {"events": row["events"]} for row in rows]
    }
