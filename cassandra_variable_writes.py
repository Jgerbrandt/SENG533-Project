import os
import uuid
import time
import random
import string
from cassandra.cluster import Cluster
from prometheus_client import start_http_server, Summary, Counter


os.environ["CASSANDRA_DRIVER_EVENT_LOOP"] = "asyncio"

cluster = Cluster(['localhost'])
session = cluster.connect()


session.execute("""
    CREATE KEYSPACE IF NOT EXISTS test
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
""")
session.set_keyspace('test')

for i in range(1, 11):
    session.execute(f"""
        CREATE TABLE IF NOT EXISTS write{i} (
            id UUID PRIMARY KEY,
            name text,
            age int,
            is_active boolean,
            tags list<text>,
            metadata map<text, text>
        )
    """)
    session.execute(f"""
        CREATE INDEX IF NOT EXISTS ON write{i} (is_active)
    """)
    session.execute(f"""
        CREATE INDEX IF NOT EXISTS ON write{i} (age)
    """)


def define_metrics(prefix):
    return {
        "time": Summary(f'cassandra_{prefix}_duration_seconds', f'Time spent on Cassandra {prefix} write operations'),
        "counter": Counter(f'cassandra_{prefix}_throughput_total', f'Total number of Cassandra {prefix} write operations')
    }

metric_sets = {
    "one_kb_60_false": define_metrics("one_kb_60_false"),
    "ten_kb_60_false": define_metrics("ten_kb_60_false"),
    "twenty_kb_60_false": define_metrics("twenty_kb_60_false"),
    "fifty_kb_60_false": define_metrics("fifty_kb_60_false"),
    "one_hundred_kb_60_false": define_metrics("one_hundred_kb_60_false"),
    "one_kb_60_true": define_metrics("one_kb_60_true"),
    "ten_kb_60_true": define_metrics("ten_kb_60_true"),
    "twenty_kb_60_true": define_metrics("twenty_kb_60_true"),
    "fifty_kb_60_true": define_metrics("fifty_kb_60_true"),
    "one_hundred_kb_60_true": define_metrics("one_hundred_kb_60_true"),
}


def generate_random_string(size):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size))

def test_query_performance_cassandra(timer, table_name, duration_seconds, complex_query=False):
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            if complex_query:
                # complex query with indexed fields
                query = f"""
                    SELECT name, age, tags FROM {table_name}
                    WHERE is_active = True AND age >= 30
                    LIMIT 10
                """
                with timer.time():
                    rows = session.execute(query)
                    results = list(rows)
            else:
                # simple query using indexed field
                query = f"""
                    SELECT * FROM {table_name}
                    WHERE is_active = True
                    LIMIT 1
                """
                with timer.time():
                    result = session.execute(query).one()
    except Exception as e:
        print(f"Failed to execute query: {e}")

def populate_table_with_data(table_name, num_records=1000):
    for _ in range(num_records):
        id = uuid.uuid4()
        name = generate_random_string(random.randint(5, 50))
        age = random.randint(18, 80)
        is_active = random.choice([True, False])
        tags = [generate_random_string(10) for _ in range(random.randint(1, 10))]
        metadata = {"key": generate_random_string(20), "value": generate_random_string(20)}
        created_at = time.time() - random.randint(0, 31536000)
        data = generate_random_string(random.randint(100, 1024))

        query = f"""
            INSERT INTO {table_name} (id, name, age, is_active, tags, metadata, created_at, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (id, name, age, is_active, tags, metadata, created_at, data)
        session.execute(query, values)





def test_variable_data_size_cassandra(timer, counter, table_name, size_kb, duration_seconds, multiple_types=False):
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            data_size = size_kb * 1024
            id = uuid.uuid4()

            if multiple_types:
                other_fields_size = (
                    4 +  # age
                    1 +  # is_active
                    5 * 10 +  # tags
                    40  # metadata
                )
                name_size = max(0, data_size - other_fields_size)
                name = generate_random_string(name_size)
                tags = [generate_random_string(10) for _ in range(5)]
                metadata = {
                    "key": generate_random_string(20),
                    "value": generate_random_string(20)
                }
                query = f"""
                    INSERT INTO {table_name} (id, name, age, is_active, tags, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                values = (id, name, random.randint(18, 80), random.choice([True, False]), tags, metadata)
            else:
                name = generate_random_string(data_size)
                query = f"""
                    INSERT INTO {table_name} (id, name)
                    VALUES (%s, %s)
                """
                values = (id, name)

            with timer.time():
                session.execute(query, values)
                counter.inc()
    except Exception as e:
        print(f"Failed to insert into {table_name}: {e}")


def main():
    start_http_server(8000)
    print("Prometheus metrics available at http://localhost:8000/metrics")

    #populate_table_with_data("write6", num_records=1000)
    #query_metric = Summary('cassandra_query_duration_seconds', 'Time spent on Cassandra query operations')
    #test_query_performance_cassandra(query_metric, "write6", 60, complex_query=True)

    # Execute all test cases
    test_variable_data_size_cassandra(metric_sets["one_kb_60_false"]["time"], metric_sets["one_kb_60_false"]["counter"], "write1", 1, 60, multiple_types=False)
    test_variable_data_size_cassandra(metric_sets["ten_kb_60_false"]["time"], metric_sets["ten_kb_60_false"]["counter"], "write2", 10, 60, multiple_types=False)
    test_variable_data_size_cassandra(metric_sets["twenty_kb_60_false"]["time"], metric_sets["twenty_kb_60_false"]["counter"], "write3", 20, 60, multiple_types=False)
    test_variable_data_size_cassandra(metric_sets["fifty_kb_60_false"]["time"], metric_sets["fifty_kb_60_false"]["counter"], "write4", 50, 60, multiple_types=False)
    test_variable_data_size_cassandra(metric_sets["one_hundred_kb_60_false"]["time"], metric_sets["one_hundred_kb_60_false"]["counter"], "write5", 100, 60, multiple_types=False)

    test_variable_data_size_cassandra(metric_sets["one_kb_60_true"]["time"], metric_sets["one_kb_60_true"]["counter"], "write6", 1, 60, multiple_types=True)
    test_variable_data_size_cassandra(metric_sets["ten_kb_60_true"]["time"], metric_sets["ten_kb_60_true"]["counter"], "write7", 10, 60, multiple_types=True)
    test_variable_data_size_cassandra(metric_sets["twenty_kb_60_true"]["time"], metric_sets["twenty_kb_60_true"]["counter"], "write8", 20, 60, multiple_types=True)
    test_variable_data_size_cassandra(metric_sets["fifty_kb_60_true"]["time"], metric_sets["fifty_kb_60_true"]["counter"], "write9", 50, 60, multiple_types=True)
    test_variable_data_size_cassandra(metric_sets["one_hundred_kb_60_true"]["time"], metric_sets["one_hundred_kb_60_true"]["counter"], "write10", 100, 60, multiple_types=True)

    print("TEST COMPLETED")

if __name__ == "__main__":
    main()
    while True:
        time.sleep(10)
